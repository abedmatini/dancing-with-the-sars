"""Turn a SiteData bundle into the small JSON the globe needs."""

from __future__ import annotations

from collections import OrderedDict
import gc
import threading

import numpy as np
import pandas as pd

from drought_monitor.assistant import build_context
from drought_monitor.data import (
    GROUP_GLOBAL,
    GROUP_LOCAL,
    SITE_CONFIGS,
    SiteData,
    format_coordinates,
    register_custom_site,
    sites_by_group,
)

RISK_RANGES = "Low 0–39.9 · Medium 40–64.9 · High 65–100"


def preset_catalog() -> dict:
    grouped = sites_by_group()
    groups = []
    for name in (GROUP_LOCAL, GROUP_GLOBAL):
        sites = []
        for site_id, label in grouped[name].items():
            config = SITE_CONFIGS[site_id]
            west, south, east, north = config["extent"]
            lat, lon = config["center"]
            sites.append(
                {
                    "id": site_id,
                    "name": label,
                    "lat": lat,
                    "lon": lon,
                    "coordinates": format_coordinates(lat, lon),
                    "west": west,
                    "south": south,
                    "east": east,
                    "north": north,
                    "terrain": config["terrain"],
                    "description": config["description"],
                }
            )
        groups.append({"name": name, "sites": sites})
    return {"groups": groups}


def risk_class_name(score: float) -> str:
    if score >= 65:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"


def _scene_index(site: SiteData, date: str | None) -> int:
    times = [pd.Timestamp(value) for value in site.soil_moisture.time.values]
    if not times:
        return 0
    if not date:
        return len(times) - 1
    target = pd.Timestamp(date)
    for index, stamp in enumerate(times):
        if stamp.normalize() == target.normalize():
            return index
    nearest = min(range(len(times)), key=lambda index: abs(times[index] - target))
    return nearest


def scene_payload(site: SiteData, source: str, date: str | None) -> dict:
    index = _scene_index(site, date)
    times = [pd.Timestamp(value) for value in site.soil_moisture.time.values]
    selected = times[index]
    soil = site.soil_moisture["soil_moisture"]
    soil_means = [float(soil.isel(time=step).mean()) for step in range(soil.sizes["time"])]
    units = soil.attrs.get("units", "m3 m-3")
    unit_label = "m³/m³" if units == "m3 m-3" else "wetness fraction"
    risk = site.runoff_risk["risk_index"].isel(time=index)
    score = float(risk.mean())
    risk_series = []
    for step, stamp in enumerate(times):
        step_score = float(site.runoff_risk["risk_index"].isel(time=step).mean())
        risk_series.append(
            {
                "date": stamp.strftime("%Y-%m-%d"),
                "score": round(step_score, 1),
                "class": risk_class_name(step_score),
            }
        )
    latest = site.rainfall.iloc[-1]
    west, south, east, north = [float(value) for value in site.boundary.total_bounds]
    using_mock = source == "mock" or bool(site.metadata.get("fallback"))
    climatology = (
        "POWER climatology" if source == "earthdata" and not using_mock else "1991–2020 climatology"
    )
    lat, lon = site.center
    return {
        "id": site.site_id,
        "name": site.name,
        "description": site.description,
        "lat": lat,
        "lon": lon,
        "coordinates": format_coordinates(lat, lon),
        "west": west,
        "south": south,
        "east": east,
        "north": north,
        "terrain": site.metadata.get("terrain", ""),
        "source": source,
        "using_mock": using_mock,
        "layers": site.metadata.get("layers", {}),
        "notice": site.metadata.get("notice", ""),
        "date": selected.strftime("%Y-%m-%d"),
        "dates": [stamp.strftime("%Y-%m-%d") for stamp in times],
        "rainfall": [
            {
                "time": row.time.strftime("%Y-%m-%d"),
                "observed_mm": float(row.observed_mm),
                "climatology_mm": float(row.climatology_mm),
                "anomaly_mm": float(row.anomaly_mm),
                "percent_normal": float(row.percent_normal),
            }
            for row in site.rainfall.itertuples(index=False)
        ],
        "rainfall_month": latest.time.strftime("%B %Y"),
        "percent_normal": float(latest.percent_normal),
        "anomaly_mm": float(latest.anomaly_mm),
        "climatology_name": climatology,
        "soil_moisture": [
            {"date": stamp.strftime("%Y-%m-%d"), "value": round(value, 4), "units": unit_label}
            for stamp, value in zip(times, soil_means, strict=True)
        ],
        "soil_value": soil_means[index],
        "soil_first": soil_means[0],
        "soil_unit": unit_label,
        "slope": {
            "mean": round(float(site.slope.mean()), 2),
            "min": round(float(site.slope.min()), 2),
            "max": round(float(site.slope.max()), 2),
            "units": "degrees",
        },
        "risk": {
            "score": round(score, 1),
            "class": risk_class_name(score),
            "ranges": RISK_RANGES,
        },
        "risk_series": risk_series,
        "burned_percent": round(float(site.burn_mask.mean()) * 100, 1),
    }


def context_for(payload: dict) -> dict:
    return build_context(
        site_name=payload["name"],
        coordinates=payload["coordinates"],
        slider_date=pd.Timestamp(payload["date"]).strftime("%d %B %Y"),
        rain_month=payload["rainfall_month"],
        percent_normal=payload["percent_normal"],
        anomaly_mm=payload["anomaly_mm"],
        climatology_name=payload["climatology_name"],
        soil_value=payload["soil_value"],
        soil_unit=payload["soil_unit"],
        soil_first=payload["soil_first"],
        risk_score=payload["risk"]["score"],
        risk_class=payload["risk"]["class"],
        burned_percent=payload["burned_percent"],
        mean_slope=payload["slope"]["mean"],
        source_mode=payload["source"],
        using_mock=payload["using_mock"],
        latitude=payload.get("lat"),
    )


def risk_grid(site: SiteData, date: str | None) -> dict:
    index = _scene_index(site, date)
    selected = pd.Timestamp(site.soil_moisture.time.values[index])
    values = np.nan_to_num(
        np.asarray(site.runoff_risk["risk_index"].isel(time=index).values, dtype="float64"),
        nan=0.0,
    )
    rows, cols = values.shape
    west, south, east, north = [float(value) for value in site.boundary.total_bounds]
    return {
        "date": selected.strftime("%Y-%m-%d"),
        "west": west,
        "south": south,
        "east": east,
        "north": north,
        "rows": int(rows),
        "cols": int(cols),
        "values": [[round(float(item), 1) for item in row] for row in values],
    }


def locate(lat: float, lon: float, source: str) -> SiteData:
    preset_id = _preset_at(lat, lon)
    site_id = preset_id or register_custom_site(lat, lon)
    return _cached_load(site_id, source if source in {"mock", "earthdata"} else "mock")


def _preset_at(lat: float, lon: float) -> str | None:
    """Use a preset when the click is on its pin, otherwise a 5 km custom box."""

    for site_id, config in SITE_CONFIGS.items():
        plat, plon = config["center"]
        if abs(plat - lat) <= 0.03 and abs(plon - lon) <= 0.03:
            return site_id
    return None


# The free Render instance has 512 MB. One loaded site is enough to answer
# the panel; keeping several Earthdata bundles, or building two at once,
# is what crosses that limit.
_CACHE: OrderedDict[tuple[str, str], SiteData] = OrderedDict()
_CACHE_LIMIT = 1
_LOAD_LOCK = threading.Lock()


def _cached_load(site_id: str, source: str) -> SiteData:
    from drought_monitor.data import load_site_data

    key = (site_id, source)
    with _LOAD_LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            _CACHE.move_to_end(key)
            return cached
        while len(_CACHE) >= _CACHE_LIMIT:
            _CACHE.popitem(last=False)
            gc.collect()
        site = load_site_data(site_id, source=source)  # type: ignore[arg-type]
        _CACHE[key] = site
        return site
