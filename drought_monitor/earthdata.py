"""Real NASA POWER, Copernicus DEM, and optional NISAR SME2 loaders.

Public searches and NASA POWER work without credentials. NISAR HDF5 granules
on ASF return HTTP 403 until ``EARTHDATA_TOKEN`` is present.
"""

from __future__ import annotations

from datetime import datetime
import calendar
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
import xarray as xr
from shapely.geometry import box

from drought_monitor.env import load_local_env
from drought_monitor.data import (
    GRID_SHAPE,
    resolve_site,
    seed_for,
    SiteData,
    _calculate_runoff_risk,
    _grid_coordinates,
    _mock_burn_mask,
    _mock_slope,
)

load_local_env()

CMR_GRANULES = "https://cmr.earthdata.nasa.gov/search/granules.json"
POWER_API = "https://power.larc.nasa.gov/api/temporal"
COPERNICUS_BUCKET = "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com"
NISAR_SHORT_NAME = "NISAR_L3_SME2_PROVISIONAL_V1"
PERIOD_START = "2026-06-01T00:00:00Z"
PERIOD_END = "2026-11-30T23:59:59Z"
FILL_VALUE = -900
USER_AGENT = "dancing-with-the-sars/1.0"
CACHE_DIR = Path.home() / ".cache" / "dancing-with-the-sars"


def earthdata_token() -> str | None:
    """Return a bearer token from the environment or Streamlit secrets."""

    token = os.environ.get("EARTHDATA_TOKEN")
    if token:
        return token.strip() or None
    try:
        import streamlit as st

        secret = st.secrets.get("EARTHDATA_TOKEN")
    except Exception:
        return None
    if secret:
        return str(secret).strip() or None
    return None


def load_earthdata_site(site_id: str) -> SiteData:
    """Build one site from public NASA data, with NISAR used when authorized."""

    config = resolve_site(site_id)
    extent = config["extent"]
    x, y, transform = _grid_coordinates(extent)
    token = earthdata_token()
    notices: list[str] = []
    layers: dict[str, str] = {}

    rainfall = _power_rainfall(config["center"])
    layers["rainfall"] = (
        "LIVE · NASA POWER PRECTOTCORR monthly total, versus POWER climatology"
    )

    try:
        nisar = search_nisar_granules(extent)
    except Exception as exc:
        nisar = []
        notices.append(f"The NISAR CMR search failed ({exc}).")
    soil, soil_layer, soil_notice = _soil_moisture(
        config, x, y, transform, token, nisar, select_granules(nisar)
    )
    layers["soil_moisture"] = soil_layer
    if soil_notice:
        notices.append(soil_notice)

    try:
        slope = _copernicus_slope(config["center"], extent, x, y, transform)
        layers["slope"] = "LIVE · Copernicus DEM GLO-30 public COG, slope in degrees"
    except Exception as exc:
        rng = np.random.default_rng(seed_for(site_id, config["center"]))
        slope = _mock_slope(config, x, y, transform, rng)
        layers["slope"] = "MOCK · seeded slope because the public DEM read failed"
        notices.append(f"Copernicus DEM could not be read ({exc}). Slope is synthetic.")

    rng = np.random.default_rng(seed_for(site_id, config["center"]) + 17)
    burn_mask = _mock_burn_mask(config, x, y, transform, rng)
    burn_mask.attrs["source"] = (
        "MOCK · seeded burn mask. MODIS MCD64A1 was not read."
    )
    layers["burn_mask"] = burn_mask.attrs["source"]
    notices.append(
        "The burn mask is still the seeded mock layer. A free MODIS burned-area "
        "download needs an Earthdata token and an approved LP DAAC application."
    )

    risk = _calculate_runoff_risk(soil, slope, burn_mask)
    risk.attrs["source"] = "Derived from the rainfall, soil, slope, and burn layers above"
    boundary = gpd.GeoDataFrame(
        {"site_id": [site_id], "name": [config["name"]]},
        geometry=[box(*extent)],
        crs="EPSG:4326",
    )
    return SiteData(
        site_id=site_id,
        name=config["name"],
        description=config["description"],
        center=config["center"],
        boundary=boundary,
        rainfall=rainfall,
        soil_moisture=soil,
        slope=slope,
        burn_mask=burn_mask,
        runoff_risk=risk,
        metadata={
            "source": "NASA Earthdata public products, with labeled mock layers",
            "fallback": False,
            "partial_mock": True,
            "notice": " ".join(notices),
            "layers": layers,
            "nisar_short_name": NISAR_SHORT_NAME,
            "nisar_granule_count": len(nisar),
            "token_present": bool(token),
            "orbit_repeat_days": 12,
            "crs": "EPSG:4326",
            "pumping_stress": config["pumping_stress"],
            "terrain": config.get("terrain", ""),
            "latitude": config["center"][0],
            "longitude": config["center"][1],
            "rainfall_product": layers["rainfall"],
            "soil_product": layers["soil_moisture"],
        },
    )


def search_nisar_granules(extent: tuple[float, float, float, float]) -> list[dict]:
    """Return NISAR SME2 granules whose CMR footprint meets the site box."""

    west, south, east, north = extent
    payload = _get_json(
        CMR_GRANULES,
        {
            "short_name": NISAR_SHORT_NAME,
            "bounding_box": f"{west},{south},{east},{north}",
            "temporal": f"{PERIOD_START},{PERIOD_END}",
            "page_size": 200,
        },
    )
    granules = []
    for entry in payload.get("feed", {}).get("entry", []):
        href = _hdf5_href(entry)
        if href is None or not entry.get("time_start"):
            continue
        granules.append(
            {
                "title": entry.get("title", ""),
                "time": pd.Timestamp(entry["time_start"]),
                "href": href,
            }
        )
    return granules


def select_granules(granules: list[dict], min_gap_days: int = 12, limit: int = 6) -> list[dict]:
    """Keep one granule about every 12 days, oldest first."""

    chosen: list[dict] = []
    last = None
    for granule in sorted(granules, key=lambda item: item["time"]):
        if last is None or (granule["time"] - last).days >= min_gap_days:
            chosen.append(granule)
            last = granule["time"]
        if len(chosen) >= limit:
            break
    return chosen


def _soil_moisture(config, x, y, transform, token, nisar, sampled):
    if token and sampled:
        try:
            dataset = _nisar_soil_dataset(sampled, config["extent"], x, y, transform, token)
            return (
                dataset,
                f"LIVE · {NISAR_SHORT_NAME} HDF5 via ASF, bearer token, up to 6 scenes",
                f"Read {dataset.sizes['time']} NISAR SME2 scenes with the Earthdata token.",
            )
        except Exception as exc:
            notice = (
                f"NISAR granules were found ({len(nisar)}), but reading them failed "
                f"({exc}). "
            )
    elif nisar:
        notice = (
            f"{len(nisar)} {NISAR_SHORT_NAME} granules intersect this site for "
            "June–November 2026, but ASF returns HTTP 403 without EARTHDATA_TOKEN. "
        )
    else:
        notice = (
            f"No {NISAR_SHORT_NAME} granules were found for this site in "
            "June–November 2026. "
        )
    dataset = _power_soil_dataset(config["center"], x, y, transform)
    return (
        dataset,
        "LIVE · NASA POWER MERRA-2 GWETTOP surface soil wetness, daily sample, site value repeated on the grid",
        notice
        + "Soil moisture is NASA POWER MERRA-2 surface wetness (dimensionless), "
        "not NISAR volumetric water content.",
    )


def _power_rainfall(center: tuple[float, float]) -> pd.DataFrame:
    lat, lon = center
    observed = _get_json(
        f"{POWER_API}/monthly/point",
        _power_params("PRECTOTCORR", lat, lon, start="2026", end="2026"),
    )
    climate = _get_json(
        f"{POWER_API}/climatology/point",
        _power_params("PRECTOTCORR", lat, lon),
    )
    monthly = observed["properties"]["parameter"]["PRECTOTCORR"]
    normals = climate["properties"]["parameter"]["PRECTOTCORR"]
    rows = []
    for key, value in monthly.items():
        if not key.isdigit() or float(value) <= FILL_VALUE:
            continue
        year, month = int(key[:4]), int(key[4:])
        days = calendar.monthrange(year, month)[1]
        month_name = datetime(year, month, 1).strftime("%b").upper()
        normal = float(normals[month_name])
        observed_mm = round(float(value) * days, 1)
        climatology_mm = round(normal * days, 1)
        rows.append(
            {
                "time": pd.Timestamp(year=year, month=month, day=1),
                "observed_mm": observed_mm,
                "climatology_mm": climatology_mm,
                "anomaly_mm": round(observed_mm - climatology_mm, 1),
                "percent_normal": round(100 * observed_mm / climatology_mm, 1),
            }
        )
    if not rows:
        raise RuntimeError("NASA POWER returned no valid precipitation months")
    return pd.DataFrame(rows)


def _power_soil_dataset(center, x, y, transform) -> xr.Dataset:
    lat, lon = center
    payload = _get_json(
        f"{POWER_API}/daily/point",
        _power_params("GWETTOP", lat, lon, start="20260601", end="20261114"),
    )
    series = payload["properties"]["parameter"]["GWETTOP"]
    valid = [
        (pd.Timestamp(key), float(value))
        for key, value in series.items()
        if key.isdigit() and float(value) > FILL_VALUE
    ]
    if len(valid) < 2:
        raise RuntimeError("NASA POWER returned no surface-wetness days")
    times = [item[0] for item in valid]
    values = np.array([item[1] for item in valid], dtype="float32")
    grid = np.broadcast_to(values[:, None, None], (len(times), *GRID_SHAPE)).copy()
    quality = np.zeros(grid.shape, dtype="uint8")
    return xr.Dataset(
        {
            "soil_moisture": (
                ("time", "y", "x"),
                grid,
                {
                    "long_name": "MERRA-2 surface soil wetness via NASA POWER",
                    "units": "1",
                    "valid_min": 0.0,
                    "valid_max": 1.0,
                    "_FillValue": -9999.0,
                },
            ),
            "quality_flag": (
                ("time", "y", "x"),
                quality,
                {"flag_values": [0, 1], "flag_meanings": "good dry_limit_warning"},
            ),
        },
        coords={
            "time": times,
            "y": ("y", y, {"standard_name": "latitude", "units": "degrees_north"}),
            "x": ("x", x, {"standard_name": "longitude", "units": "degrees_east"}),
        },
        attrs={
            "title": "NASA POWER MERRA-2 GWETTOP surface soil wetness",
            "source": "NASA POWER daily point, repeated across the site grid",
            "institution": "NASA Langley POWER / GMAO MERRA-2",
            "Conventions": "CF-1.8",
            "crs": "EPSG:4326",
            "transform": tuple(transform),
            "mock_data": "false",
            "stand_in_for": NISAR_SHORT_NAME,
        },
    )


def _nisar_soil_dataset(granules, extent, x, y, transform, token) -> xr.Dataset:
    frames = []
    times = []
    for granule in granules:
        path = _download(granule["href"], token)
        subset = _read_sme2_window(path, extent)
        frames.append(_resize(subset, GRID_SHAPE))
        times.append(granule["time"])
    stack = np.stack(frames).astype("float32")
    return xr.Dataset(
        {
            "soil_moisture": (
                ("time", "y", "x"),
                stack,
                {
                    "long_name": "NISAR L3 SME2 provisional surface soil moisture",
                    "units": "m3 m-3",
                    "valid_min": 0.0,
                    "valid_max": 0.6,
                    "_FillValue": -9999.0,
                },
            ),
            "quality_flag": (
                ("time", "y", "x"),
                np.zeros(stack.shape, dtype="uint8"),
                {"flag_values": [0, 1], "flag_meanings": "good dry_limit_warning"},
            ),
        },
        coords={
            "time": times,
            "y": ("y", y, {"standard_name": "latitude", "units": "degrees_north"}),
            "x": ("x", x, {"standard_name": "longitude", "units": "degrees_east"}),
        },
        attrs={
            "title": "NISAR L3 SME2 provisional soil moisture",
            "source": "ASF NISAR_L3_SME2_PROVISIONAL_V1",
            "crs": "EPSG:4326",
            "transform": tuple(transform),
            "mock_data": "false",
        },
    )


def _read_sme2_window(path: Path, extent) -> np.ndarray:
    import h5py

    west, south, east, north = extent
    with h5py.File(path, "r") as handle:
        candidates = []

        def visit(name, obj):
            if isinstance(obj, h5py.Dataset) and getattr(obj, "ndim", 0) == 2:
                lowered = name.lower()
                if "soil" in lowered and "moisture" in lowered:
                    candidates.append(name)

        handle.visititems(visit)
        if not candidates:
            raise ValueError(f"No soil-moisture dataset in {path.name}")
        latitudes, longitudes = _coordinate_vectors(handle, candidates[0])
        if latitudes is None or longitudes is None:
            raise ValueError("NISAR file has no recognizable latitude/longitude vectors")
        rows = np.where((latitudes >= south) & (latitudes <= north))[0]
        cols = np.where((longitudes >= west) & (longitudes <= east))[0]
        if rows.size == 0 or cols.size == 0:
            raise ValueError("NISAR grid does not overlap the site extent")
        # Read the site window only. The full granule is far larger than the
        # 512 MB on the free API instance.
        window = np.array(
            handle[candidates[0]][
                int(rows.min()) : int(rows.max()) + 1,
                int(cols.min()) : int(cols.max()) + 1,
            ],
            dtype="float32",
        )
    window = np.where(window < FILL_VALUE, np.nan, window)
    if not np.isfinite(window).any():
        raise ValueError("NISAR soil-moisture window is empty")
    fill = np.nanmedian(window)
    return np.where(np.isfinite(window), window, fill).astype("float32")


def _coordinate_vectors(handle, dataset_name: str):
    group_names = dataset_name.split("/")[:-1]
    groups = ["/".join(group_names[: index + 1]) for index in range(len(group_names))]
    latitudes = longitudes = None
    for group_name in reversed(groups):
        group = handle[group_name]
        for key, obj in group.items():
            if not isinstance(obj, h5py_dataset_type(handle)):
                continue
            lowered = key.lower()
            if obj.ndim == 1 and "lat" in lowered:
                latitudes = np.array(obj[()], dtype="float64")
            elif obj.ndim == 1 and ("lon" in lowered or lowered == "x"):
                longitudes = np.array(obj[()], dtype="float64")
        if latitudes is not None and longitudes is not None:
            return latitudes, longitudes
    return None, None


def h5py_dataset_type(handle):
    import h5py

    return h5py.Dataset


def _resize(values: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    if values.shape == shape:
        return values.astype("float32")
    src_y = np.linspace(0, 1, values.shape[0])
    src_x = np.linspace(0, 1, values.shape[1])
    dst_y = np.linspace(0, 1, shape[0])
    dst_x = np.linspace(0, 1, shape[1])
    interim = np.vstack([np.interp(dst_x, src_x, row) for row in values])
    return np.vstack([np.interp(dst_y, src_y, interim[:, col]) for col in range(shape[1])]).T.astype(
        "float32"
    )


def _copernicus_slope(center, extent, x, y, transform) -> xr.DataArray:
    lat, lon = center
    south_corner = int(np.floor(lat))
    west_corner = int(np.floor(lon))
    ns = "S" if south_corner < 0 else "N"
    ew = "W" if west_corner < 0 else "E"
    tile = (
        f"Copernicus_DSM_COG_10_{ns}{abs(south_corner):02d}_00_"
        f"{ew}{abs(west_corner):03d}_00_DEM"
    )
    url = f"/vsicurl/{COPERNICUS_BUCKET}/{tile}/{tile}.tif"
    west, south, east, north = extent
    with rasterio.open(url) as source:
        left = max(west, source.bounds.left)
        right = min(east, source.bounds.right)
        bottom = max(south, source.bounds.bottom)
        top = min(north, source.bounds.top)
        window = from_bounds(left, bottom, right, top, source.transform)
        elevation = source.read(1, window=window, out_shape=GRID_SHAPE, resampling=rasterio.enums.Resampling.average)
    elevation = elevation.astype("float64")
    latitude = float(np.mean(y))
    dx_m = abs(transform.a) * 111_320 * np.cos(np.deg2rad(latitude))
    dy_m = abs(transform.e) * 111_320
    gradient_y, gradient_x = np.gradient(elevation, dy_m, dx_m)
    degrees = np.degrees(np.arctan(np.hypot(gradient_x, gradient_y))).astype("float32")
    return xr.DataArray(
        degrees,
        dims=("y", "x"),
        coords={"y": y, "x": x},
        name="slope",
        attrs={
            "long_name": "terrain slope",
            "units": "degrees",
            "crs": "EPSG:4326",
            "transform": tuple(transform),
            "source": f"Copernicus DEM GLO-30 {tile}",
            "_FillValue": -9999.0,
        },
    )


def _power_params(parameter: str, lat: float, lon: float, **extra) -> dict[str, str]:
    params = {
        "parameters": parameter,
        "community": "AG",
        "longitude": f"{lon:.4f}",
        "latitude": f"{lat:.4f}",
        "format": "JSON",
    }
    params.update(extra)
    return params


_LAST_POWER_CALL = 0.0


def _pause_for_power(url: str) -> None:
    """Keep NASA POWER calls at least half a second apart."""

    global _LAST_POWER_CALL
    if "power.larc.nasa.gov" not in url:
        return
    gap = 0.5 - (time.monotonic() - _LAST_POWER_CALL)
    if gap > 0:
        time.sleep(gap)
    _LAST_POWER_CALL = time.monotonic()


def _get_json(url: str, params: dict | None = None) -> dict:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    _pause_for_power(url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from {url.split('?')[0]}") from exc


def _hdf5_href(entry: dict) -> str | None:
    for link in entry.get("links", []):
        href = link.get("href") or ""
        rel = link.get("rel") or ""
        if href.endswith(".h5") and "data#" in rel and "PRIVATE" not in href:
            return href
    return None


def _download(url: str, token: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    destination = CACHE_DIR / Path(urllib.parse.urlparse(url).path).name
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Authorization": f"Bearer {token}"},
    )
    partial = destination.with_suffix(destination.suffix + ".part")
    try:
        with urllib.request.urlopen(request, timeout=180) as response, partial.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
        partial.replace(destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return destination
