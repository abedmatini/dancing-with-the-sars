"""Preset registry and custom map locations."""

import numpy as np
import xarray as xr

from drought_monitor import earthdata
from drought_monitor.data import (
    CUSTOM_SITES,
    GROUP_GLOBAL,
    GROUP_LOCAL,
    SITE_CONFIGS,
    extent_size_km,
    load_site_data,
    register_custom_site,
    resolve_site,
    sites_by_group,
)


LOCAL_IDS = {
    "table_mountain",
    "cape_flats",
    "silvermine",
    "jonkershoek",
    "theewaterskloof",
    "atlantis",
    "hottentots_holland",
    "cederberg",
}
GLOBAL_IDS = {
    "palisades",
    "attica",
    "valparaiso",
    "blue_mountains",
    "central_valley",
}


def test_presets_are_grouped_and_a_few_kilometres_wide():
    grouped = sites_by_group()
    assert set(grouped[GROUP_LOCAL]) == LOCAL_IDS
    assert set(grouped[GROUP_GLOBAL]) == GLOBAL_IDS
    for site_id, config in SITE_CONFIGS.items():
        assert config["description"]
        assert config["terrain"]
        west, south, east, north = config["extent"]
        lat, lon = config["center"]
        assert south < lat < north
        assert west < lon < east
        width, height = extent_size_km(config["extent"])
        assert 4 <= width <= 15
        assert 4 <= height <= 15
        site = load_site_data(site_id)
        assert site.metadata["layers"]["burn_mask"].startswith("MOCK")
        assert site.name == config["name"]


def test_custom_site_is_deterministic_in_mock_mode():
    first_id = register_custom_site(-33.961, 18.411)
    second_id = register_custom_site(-33.964, 18.414)
    assert first_id == second_id
    assert first_id in CUSTOM_SITES
    config = resolve_site(first_id)
    assert config["center"] == (-33.96, 18.41)
    assert config["name"] == "Custom location"
    width, height = extent_size_km(config["extent"])
    assert width <= 5.05
    assert height <= 5.05
    first = load_site_data(first_id, source="mock")
    second = load_site_data(first_id, source="mock")
    np.testing.assert_array_equal(first.slope, second.slope)
    assert first.metadata["layers"]["burn_mask"].startswith("MOCK")
    assert "mock" in first.burn_mask.attrs["source"].lower()
    assert first.center == (-33.96, 18.41)


def test_custom_site_earthdata_labels_live_and_mock_layers(monkeypatch):
    monkeypatch.delenv("EARTHDATA_TOKEN", raising=False)
    monkeypatch.setattr(earthdata, "earthdata_token", lambda: None)
    monkeypatch.setattr(earthdata, "_get_json", lambda url, params=None: _power(url))
    monkeypatch.setattr(earthdata, "search_nisar_granules", lambda extent: [])

    def fake_slope(center, extent, x, y, transform):
        return xr.DataArray(
            np.full((len(y), len(x)), 5, dtype="float32"),
            dims=("y", "x"),
            coords={"y": y, "x": x},
            attrs={"units": "degrees", "crs": "EPSG:4326", "transform": tuple(transform)},
        )

    monkeypatch.setattr(earthdata, "_copernicus_slope", fake_slope)

    site_id = register_custom_site(34.048, -118.526)
    site = load_site_data(site_id, source="earthdata")

    assert site.name == "Custom location"
    assert site.center == (34.05, -118.53)
    assert site.metadata["fallback"] is False
    assert site.metadata["layers"]["rainfall"].startswith("LIVE")
    assert site.metadata["layers"]["soil_moisture"].startswith("LIVE")
    assert site.metadata["layers"]["slope"].startswith("LIVE")
    assert site.metadata["layers"]["burn_mask"].startswith("MOCK")
    assert "POWER" in site.metadata["layers"]["rainfall"]


def _power(url):
    if "climatology" in url:
        months = {name: 1.0 for name in (
            "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
            "JUL", "AUG", "SEP", "OCT", "NOV", "DEC", "ANN",
        )}
        return {"properties": {"parameter": {"PRECTOTCORR": months}}}
    if "daily" in url:
        return {"properties": {"parameter": {"GWETTOP": {"20260601": 0.4, "20260613": 0.5}}}}
    return {"properties": {"parameter": {"PRECTOTCORR": {"202606": 1.0}}}}
