import json
from pathlib import Path

from drought_monitor.data import GRID_SHAPE, list_sites


ROOT = Path(__file__).resolve().parents[1]


def test_static_dashboard_assets_cover_every_site_and_scene():
    summary = json.loads((ROOT / "web/data/summary.json").read_text())
    grids = json.loads((ROOT / "web/data/grids.json").read_text())

    assert set(summary["sites"]) == set(list_sites()) == set(grids["sites"])
    for site_id, site in grids["sites"].items():
        assert len(site["dates"]) == 16
        assert len(site["soil_moisture"]) == len(site["dates"])
        assert len(site["risk_index"]) == len(site["dates"])
        assert len(site["latitude"]) == GRID_SHAPE[0] // 2
        assert len(site["longitude"]) == GRID_SHAPE[1] // 2
        assert len(summary["sites"][site_id]["monthly_rainfall"]) == 11


def test_static_host_entrypoints_exist():
    assert "data/summary.json" in (ROOT / "web/app.js").read_text()
    assert (ROOT / "web/health.html").read_text().strip() == "ok"
    assert "scripts/start_static.sh" in (ROOT / "Procfile").read_text()
