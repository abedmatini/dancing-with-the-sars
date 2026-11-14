"""Saved study-site readings. The Database button reads this file and nothing else.

The rows are the prepared sites, written once from the seeded study copy.
A click that does not match a saved site returns nothing. This module does
not call NASA.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path

from drought_monitor.data import SITE_CONFIGS, load_site_data

from globe.api.serialize import risk_grid, scene_payload

STORED_NOTICE = (
    "Saved study-site copy. The Database button only reads these stored rows and does not call NASA."
)
_LOCK = threading.Lock()


def db_path() -> Path:
    override = os.environ.get("GLOBE_DB_PATH", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1] / "data" / "readings.sqlite"


def ensure_seed() -> None:
    path = db_path()
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS readings (
                    site_id TEXT PRIMARY KEY,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    scene_json TEXT NOT NULL,
                    grids_json TEXT NOT NULL
                )
                """
            )
            count = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
            if count:
                return
            for site_id in SITE_CONFIGS:
                site = load_site_data(site_id, source="mock")
                scene = scene_payload(site, "mock", None)
                scene["source"] = "database"
                scene["using_mock"] = True
                scene["notice"] = STORED_NOTICE
                scene["layers"] = {
                    name: value.replace("MOCK", "STORED", 1) if isinstance(value, str) else value
                    for name, value in scene["layers"].items()
                }
                grids = {day: risk_grid(site, day) for day in scene["dates"]}
                conn.execute(
                    "INSERT INTO readings (site_id, lat, lon, scene_json, grids_json) VALUES (?, ?, ?, ?, ?)",
                    (site_id, float(scene["lat"]), float(scene["lon"]), json.dumps(scene), json.dumps(grids)),
                )


def stored_scene(lat: float, lon: float, date: str | None) -> dict | None:
    row = _match(lat, lon)
    if row is None:
        return None
    scene = json.loads(row["scene_json"])
    return _at_date(scene, date)


def stored_grid(lat: float, lon: float, date: str | None) -> dict | None:
    row = _match(lat, lon)
    if row is None:
        return None
    grids = json.loads(row["grids_json"])
    if date and date in grids:
        return grids[date]
    if not grids:
        return None
    last = sorted(grids)[-1]
    return grids[last]


def _match(lat: float, lon: float) -> sqlite3.Row | None:
    ensure_seed()
    with sqlite3.connect(db_path()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT lat, lon, scene_json, grids_json FROM readings").fetchall()
    best: sqlite3.Row | None = None
    best_span = 0.06
    for row in rows:
        span = abs(float(row["lat"]) - lat) + abs(float(row["lon"]) - lon)
        if abs(float(row["lat"]) - lat) <= 0.03 and abs(float(row["lon"]) - lon) <= 0.03 and span < best_span:
            best = row
            best_span = span
    return best


def _at_date(scene: dict, date: str | None) -> dict:
    if not date or date not in scene.get("dates", []):
        return scene
    selected = dict(scene)
    selected["date"] = date
    risk = next(row for row in scene["risk_series"] if row["date"] == date)
    selected["risk"] = {**scene["risk"], "score": risk["score"], "class": risk["class"]}
    soil = next(row for row in scene["soil_moisture"] if row["date"] == date)
    selected["soil_value"] = soil["value"]
    return selected
