import json

import numpy as np
import rasterio
from rasterio.io import MemoryFile

from drought_monitor.data import (
    GRID_SHAPE,
    build_summary,
    list_sites,
    load_site_data,
    slope_geotiff_bytes,
    write_summary,
)


def test_all_sites_follow_the_data_contract():
    for site_id in list_sites():
        site = load_site_data(site_id)
        assert site.boundary.crs.to_string() == "EPSG:4326"
        assert list(site.rainfall.columns) == [
            "time",
            "observed_mm",
            "climatology_mm",
            "anomaly_mm",
            "percent_normal",
        ]
        assert site.soil_moisture["soil_moisture"].dims == ("time", "y", "x")
        assert site.soil_moisture["soil_moisture"].shape[1:] == GRID_SHAPE
        assert site.soil_moisture.attrs["crs"] == "EPSG:4326"
        assert site.soil_moisture["soil_moisture"].attrs["units"] == "m3 m-3"
        assert set(np.unique(site.runoff_risk["risk_class"])) <= {0, 1, 2}
        assert np.isfinite(site.runoff_risk["risk_index"]).all()


def test_mock_generation_is_deterministic():
    first = load_site_data("silvermine")
    second = load_site_data("silvermine")
    np.testing.assert_array_equal(
        first.soil_moisture["soil_moisture"], second.soil_moisture["soil_moisture"]
    )
    np.testing.assert_array_equal(first.slope, second.slope)


def test_slope_serializes_to_geotiff():
    site = load_site_data("table_mountain")
    payload = slope_geotiff_bytes(site)
    with MemoryFile(payload) as memfile, memfile.open() as dataset:
        assert dataset.driver == "GTiff"
        assert dataset.crs == rasterio.crs.CRS.from_epsg(4326)
        assert (dataset.height, dataset.width) == GRID_SHAPE
        assert dataset.tags()["units"] == "degrees"


def test_summary_counts_every_grid_cell_and_writes_json(tmp_path):
    summary = build_summary()
    expected_cells = GRID_SHAPE[0] * GRID_SHAPE[1]
    for values in summary["sites"].values():
        assert sum(values["risk_class_counts"].values()) == expected_cells
        assert len(values["soil_moisture_mean"]) == 16
        assert len(values["monthly_rainfall"]) == 11

    path = write_summary(tmp_path / "summary.json")
    assert json.loads(path.read_text()) == summary
