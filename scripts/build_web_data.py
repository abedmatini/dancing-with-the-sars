"""Build compact JSON assets for the dependency-free static dashboard."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from drought_monitor.data import list_sites, load_site_data, write_summary  # noqa: E402


WEB_DATA = ROOT / "web" / "data"


def rounded_grid(values: np.ndarray, digits: int) -> list[list[float]]:
    return np.round(values, digits).tolist()


def build() -> None:
    WEB_DATA.mkdir(parents=True, exist_ok=True)

    summary_path = write_summary(ROOT / "exports" / "summary.json")
    shutil.copyfile(summary_path, WEB_DATA / "summary.json")

    sites: dict[str, object] = {}
    for site_id in list_sites():
        site = load_site_data(site_id)
        # The full-resolution xarray objects remain the canonical mock data.
        # Downsampling by two keeps the browser asset small and responsive.
        soil = site.soil_moisture["soil_moisture"][:, ::2, ::2]
        risk = site.runoff_risk["risk_index"].transpose("time", "y", "x")[:, ::2, ::2]
        slope = site.slope[::2, ::2]
        sites[site_id] = {
            "name": site.name,
            "description": site.description,
            "center": list(site.center),
            "bounds": site.boundary.total_bounds.round(6).tolist(),
            "dates": [
                pd.Timestamp(value).strftime("%Y-%m-%d") for value in soil.time.values
            ],
            "longitude": np.round(soil.x.values, 6).tolist(),
            "latitude": np.round(soil.y.values, 6).tolist(),
            "soil_moisture": [
                rounded_grid(frame, 4) for frame in soil.values
            ],
            "risk_index": [rounded_grid(frame, 1) for frame in risk.values],
            "slope_degrees": rounded_grid(slope.values, 1),
            "burn_fraction": round(float(site.burn_mask.mean()), 4),
            "pumping_stress": bool(site.metadata["pumping_stress"]),
        }

    payload = {
        "metadata": {
            "title": "Dancing with the SARs — static mock grids",
            "source": "Deterministic synthetic NISAR-like data",
            "crs": "EPSG:4326",
            "grid_note": "Browser grids are 2x downsampled from canonical xarray data.",
        },
        "sites": sites,
    }
    (WEB_DATA / "grids.json").write_text(
        json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    build()
