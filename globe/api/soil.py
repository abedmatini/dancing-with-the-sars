"""Real soil readings for the 5 km study box.

The box shows a saved Open-Meteo series when the click is next to a gold pin,
a NISAR scene mean when Earthdata already supplied one, or a live NASA POWER
GWETTOP series. It never invents a seeded series.
"""

from __future__ import annotations

import json
from pathlib import Path

from drought_monitor.earthdata import gwetop_series

WEATHER_PATH = Path(__file__).resolve().parents[2] / "globe" / "web" / "public" / "showcase" / "weather.json"
# About 40 km. Farther clicks do not borrow a pin's weather file.
MAX_MATCH_DEG = 0.4

UNAVAILABLE = {
    "soil_available": False,
    "soil_note": "Data unavailable",
    "soil_moisture": [],
    "soil_value": 0.0,
    "soil_first": 0.0,
    "soil_unit": "",
}


def _saved_open_meteo(lat: float, lon: float) -> dict | None:
    if not WEATHER_PATH.is_file():
        return None
    document = json.loads(WEATHER_PATH.read_text())
    best: tuple[float, dict] | None = None
    for spot in document.get("spots", []):
        distance = (float(spot["lat"]) - lat) ** 2 + (float(spot["lon"]) - lon) ** 2
        if best is None or distance < best[0]:
            best = (distance, spot)
    if best is None or best[0] > MAX_MATCH_DEG**2:
        return None
    series = [
        {"date": day["date"], "value": float(day["soil_moisture"]), "units": "m³/m³"}
        for day in best[1].get("days", [])
        if day.get("soil_moisture") is not None
    ]
    if len(series) < 2:
        return None
    return _pack(series, "m³/m³", "Open-Meteo archive, saved for the nearest gold pin (0–7 cm)")


def _pack(series: list[dict], unit: str, note: str) -> dict:
    return {
        "soil_available": True,
        "soil_note": note,
        "soil_moisture": series,
        "soil_value": series[-1]["value"],
        "soil_first": series[0]["value"],
        "soil_unit": unit,
    }


def real_soil(lat: float, lon: float, current_layer: str, current_series: list[dict]) -> dict:
    """Choose the soil series the study box is allowed to show."""

    saved = _saved_open_meteo(lat, lon)
    if saved:
        return saved
    if current_layer.startswith("LIVE") and "NISAR" in current_layer and len(current_series) >= 2:
        return _pack(current_series, current_series[-1].get("units") or "m³/m³", current_layer)
    if current_layer.startswith("LIVE") and "POWER" in current_layer and len(current_series) >= 2:
        return _pack(current_series, current_series[-1].get("units") or "1", current_layer)
    try:
        series = [
            {"date": day, "value": round(value, 4), "units": "1"}
            for day, value in gwetop_series(lat, lon)
        ]
    except Exception:
        return dict(UNAVAILABLE)
    if len(series) < 2:
        return dict(UNAVAILABLE)
    return _pack(series, "1", "NASA POWER MERRA-2 GWETTOP, live")
