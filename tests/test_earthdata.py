import pandas as pd

from drought_monitor import earthdata
from drought_monitor.data import load_site_data


def _power_response(url, params=None):
    if "climatology" in url:
        months = {
            name: 3.0
            for name in (
                "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                "JUL", "AUG", "SEP", "OCT", "NOV", "DEC", "ANN",
            )
        }
        return {"properties": {"parameter": {"PRECTOTCORR": months}}}
    if "daily" in url:
        return {
            "properties": {
                "parameter": {
                    "GWETTOP": {"20260601": 0.80, "20260613": 0.70, "20260614": 0.60}
                }
            }
        }
    return {
        "properties": {
            "parameter": {"PRECTOTCORR": {"202606": 2.0, "202610": -999.0}}
        }
    }


def test_power_monthly_total_uses_days_in_month(monkeypatch):
    monkeypatch.setattr(earthdata, "_get_json", _power_response)
    frame = earthdata._power_rainfall((-33.9628, 18.4098))
    assert list(frame.columns) == [
        "time", "observed_mm", "climatology_mm", "anomaly_mm", "percent_normal",
    ]
    june = frame.iloc[0]
    assert june.observed_mm == 60.0
    assert june.climatology_mm == 90.0
    assert june.anomaly_mm == -30.0


def test_select_granules_keeps_about_twelve_days_apart():
    granules = [
        {"time": pd.Timestamp("2026-06-01"), "href": "a", "title": "a"},
        {"time": pd.Timestamp("2026-06-05"), "href": "b", "title": "b"},
        {"time": pd.Timestamp("2026-06-18"), "href": "c", "title": "c"},
    ]
    chosen = earthdata.select_granules(granules, min_gap_days=12, limit=6)
    assert [item["href"] for item in chosen] == ["a", "c"]


def test_earthdata_without_token_uses_power_and_explains_nisar(monkeypatch):
    monkeypatch.delenv("EARTHDATA_TOKEN", raising=False)
    monkeypatch.setattr(earthdata, "earthdata_token", lambda: None)
    monkeypatch.setattr(earthdata, "_get_json", _power_response)
    monkeypatch.setattr(
        earthdata,
        "search_nisar_granules",
        lambda extent: [
            {
                "time": pd.Timestamp("2026-06-18"),
                "href": "https://example.invalid/a.h5",
                "title": "g",
            }
        ],
    )
    slope = load_site_data("table_mountain").slope
    monkeypatch.setattr(earthdata, "_copernicus_slope", lambda *args, **kwargs: slope)

    site = load_site_data("table_mountain", source="earthdata")

    assert site.metadata["fallback"] is False
    assert site.metadata["token_present"] is False
    assert "EARTHDATA_TOKEN" in site.metadata["notice"]
    assert site.metadata["nisar_granule_count"] == 1
    assert site.soil_moisture["soil_moisture"].attrs["units"] == "1"
    assert "POWER" in site.metadata["layers"]["rainfall"]
    assert site.rainfall.iloc[0].observed_mm == 60.0
    assert site.soil_moisture.sizes["time"] == 3


def test_earthdata_failure_falls_back_to_labeled_mock(monkeypatch):
    def explode(site_id):
        raise RuntimeError("offline")

    monkeypatch.setattr(earthdata, "load_earthdata_site", explode)
    site = load_site_data("cape_flats", source="earthdata")

    assert site.metadata["fallback"] is True
    assert "mock" in site.metadata["notice"].lower()
    assert "offline" in site.metadata["notice"]
    assert site.soil_moisture["soil_moisture"].attrs["units"] == "m3 m-3"


def test_missing_token_is_reported_as_absent(monkeypatch):
    monkeypatch.delenv("EARTHDATA_TOKEN", raising=False)
    assert earthdata.earthdata_token() is None
