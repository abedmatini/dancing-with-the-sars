"""Downstream path parsing. No network."""

from globe.api.rivers import build_path


def _merit():
    return {
        "code": "success",
        "value": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"gnis_name": None, "nameid": "unknown"},
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [-118.55, 34.05],
                            [-118.54, 34.045],
                            [-118.53, 34.04],
                            [-118.52, 34.03],
                        ],
                    },
                }
            ],
        },
    }


def test_osm_name_lands_on_the_path_and_a_far_creek_is_ignored():
    osm = [
        {
            "type": "way",
            "tags": {"name": "Temescal Creek", "waterway": "stream"},
            "geometry": [
                {"lon": -118.541, "lat": 34.046},
                {"lon": -118.539, "lat": 34.044},
            ],
        },
        {
            "type": "way",
            "tags": {"name": "Far Creek", "waterway": "stream"},
            "geometry": [{"lon": -117.2, "lat": 33.2}],
        },
    ]
    path = build_path(_merit(), osm)
    assert path["coordinates"][0] == [-118.55, 34.05]
    assert path["coordinates"][-1] == [-118.52, 34.03]
    names = [river["name"] for river in path["rivers"]]
    assert names == ["Temescal Creek"]
    assert "Temescal Creek" in path["summary"]
    assert "OpenStreetMap" in path["credit"]


def test_merit_river_name_is_kept():
    merit = _merit()
    merit["value"]["features"][0]["properties"]["gnis_name"] = "Mississippi River"
    path = build_path(merit, [])
    assert path["rivers"][0]["name"] == "Mississippi River"
    assert path["credit"] == "MERIT-Basins"


def test_missing_path_is_a_quiet_empty_result():
    path = build_path({"value": {"features": []}}, [])
    assert path["coordinates"] == []
    assert "No downstream path" in path["summary"]
