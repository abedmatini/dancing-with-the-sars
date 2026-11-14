"""Data contract and loaders for the Cape Town drought monitor.

The dashboard only calls :func:`load_site_data`. Mock and future Earthdata
loaders must return the same ``SiteData`` object, keeping all source-specific
logic in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
import json
import math

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from affine import Affine
from rasterio.crs import CRS
from rasterio.io import MemoryFile
from shapely.geometry import box


@dataclass(frozen=True)
class SiteData:
    """Source-independent structures consumed by the Streamlit app."""

    site_id: str
    name: str
    description: str
    center: tuple[float, float]
    boundary: gpd.GeoDataFrame
    rainfall: pd.DataFrame
    soil_moisture: xr.Dataset
    slope: xr.DataArray
    burn_mask: xr.DataArray
    runoff_risk: xr.Dataset
    metadata: dict[str, Any]


GROUP_LOCAL = "Cape Town / Western Cape"
GROUP_GLOBAL = "Global"
CUSTOM_BOX_KM = 5.0

SITE_CONFIGS: dict[str, dict[str, Any]] = {
    "table_mountain": {
        "name": "Table Mountain / Cape Peninsula",
        "short_name": "Table Mountain",
        "group": GROUP_LOCAL,
        "terrain": "steep fynbos mountain",
        "center": (-33.9628, 18.4098),
        "description": "Fire-prone, steep fynbos slopes above the City Bowl.",
        "extent": (18.382, -33.989, 18.438, -33.937),
        "slope_range": (15.0, 46.0),
        "soil_base": 0.205,
        "rain_factor": 1.18,
        "burn_fraction": 0.24,
        "pumping_stress": False,
    },
    "cape_flats": {
        "name": "Cape Flats Aquifer",
        "short_name": "Cape Flats",
        "group": GROUP_LOCAL,
        "terrain": "low sandy aquifer",
        "center": (-34.0050, 18.5900),
        "description": "Low-gradient sandy aquifer with groundwater abstraction.",
        "extent": (18.548, -34.035, 18.632, -33.975),
        "slope_range": (0.5, 8.0),
        "soil_base": 0.155,
        "rain_factor": 0.82,
        "burn_fraction": 0.02,
        "pumping_stress": True,
    },
    "silvermine": {
        "name": "Silvermine Fynbos Catchment",
        "short_name": "Silvermine",
        "group": GROUP_LOCAL,
        "terrain": "steep fynbos headwaters",
        "center": (-34.0850, 18.4230),
        "description": "Steep fynbos headwaters draining toward False Bay.",
        "extent": (18.390, -34.115, 18.456, -34.055),
        "slope_range": (12.0, 42.0),
        "soil_base": 0.220,
        "rain_factor": 1.12,
        "burn_fraction": 0.34,
        "pumping_stress": False,
    },
    "jonkershoek": {
        "name": "Jonkershoek, Stellenbosch",
        "short_name": "Jonkershoek",
        "group": GROUP_LOCAL,
        "terrain": "steep fynbos mountain catchment",
        "center": (-33.9775, 18.9525),
        "description": "Steep sandstone fynbos catchment in the Jonkershoek valley east of Stellenbosch.",
        "extent": (18.920, -34.010, 18.985, -33.945),
        "slope_range": (12.0, 40.0),
        "soil_base": 0.210,
        "rain_factor": 1.22,
        "burn_fraction": 0.18,
        "pumping_stress": False,
    },
    "theewaterskloof": {
        "name": "Theewaterskloof Dam",
        "short_name": "Theewaterskloof",
        "group": GROUP_LOCAL,
        "terrain": "reservoir and mountain foothills",
        "center": (-34.0775, 19.2150),
        "description": "Open water and the slopes around a large storage reservoir. Terrain: reservoir and foothills.",
        "extent": (19.175, -34.105, 19.255, -34.050),
        "slope_range": (1.0, 22.0),
        "soil_base": 0.190,
        "rain_factor": 1.05,
        "burn_fraction": 0.10,
        "pumping_stress": False,
    },
    "atlantis": {
        "name": "Atlantis aquifer",
        "short_name": "Atlantis",
        "group": GROUP_LOCAL,
        "terrain": "low sandy coastal plain",
        "center": (-33.5700, 18.4850),
        "description": "Sandy coastal plain used for groundwater supply. Terrain: low coastal aquifer.",
        "extent": (18.440, -33.610, 18.530, -33.530),
        "slope_range": (0.2, 4.0),
        "soil_base": 0.140,
        "rain_factor": 0.70,
        "burn_fraction": 0.04,
        "pumping_stress": True,
    },
    "hottentots_holland": {
        "name": "Hottentots Holland / Grabouw",
        "short_name": "Grabouw",
        "group": GROUP_LOCAL,
        "terrain": "mountain fynbos and farmed foothills",
        "center": (-34.1400, 19.0250),
        "description": "Mountain slopes and farmed foothills between Grabouw and the Hottentots Holland ridge.",
        "extent": (18.980, -34.180, 19.070, -34.100),
        "slope_range": (8.0, 36.0),
        "soil_base": 0.200,
        "rain_factor": 1.15,
        "burn_fraction": 0.16,
        "pumping_stress": False,
    },
    "cederberg": {
        "name": "Cederberg",
        "short_name": "Cederberg",
        "group": GROUP_LOCAL,
        "terrain": "rocky sandstone mountains",
        "center": (-32.3650, 19.0650),
        "description": "Rocky sandstone mountains and dry-summer fynbos in the central Cederberg.",
        "extent": (19.020, -32.400, 19.110, -32.330),
        "slope_range": (10.0, 42.0),
        "soil_base": 0.160,
        "rain_factor": 0.62,
        "burn_fraction": 0.22,
        "pumping_stress": False,
    },
    "palisades": {
        "name": "Los Angeles / Palisades",
        "short_name": "Palisades",
        "group": GROUP_GLOBAL,
        "terrain": "steep coastal hills",
        "center": (34.0450, -118.5250),
        "description": "Fire and drought hotspot on steep coastal hills. Post-fire rain can move sediment.",
        "extent": (-118.560, 34.020, -118.490, 34.070),
        "slope_range": (8.0, 35.0),
        "soil_base": 0.120,
        "rain_factor": 0.55,
        "burn_fraction": 0.40,
        "pumping_stress": False,
    },
    "attica": {
        "name": "Attica, Greece",
        "short_name": "Attica",
        "group": GROUP_GLOBAL,
        "terrain": "dry Mediterranean hills",
        "center": (38.2220, 23.9200),
        "description": "Fire and drought hotspot on dry Mediterranean hills. Summer fire is followed by flash runoff.",
        "extent": (23.880, 38.190, 23.960, 38.255),
        "slope_range": (6.0, 28.0),
        "soil_base": 0.110,
        "rain_factor": 0.48,
        "burn_fraction": 0.30,
        "pumping_stress": False,
    },
    "valparaiso": {
        "name": "Valparaíso, Chile",
        "short_name": "Valparaíso",
        "group": GROUP_GLOBAL,
        "terrain": "steep coastal hills",
        "center": (-33.0500, -71.5800),
        "description": "Fire and drought hotspot on steep coastal hills above a port city.",
        "extent": (-71.620, -33.085, -71.540, -33.015),
        "slope_range": (10.0, 34.0),
        "soil_base": 0.130,
        "rain_factor": 0.58,
        "burn_fraction": 0.36,
        "pumping_stress": False,
    },
    "blue_mountains": {
        "name": "Blue Mountains, Australia",
        "short_name": "Blue Mountains",
        "group": GROUP_GLOBAL,
        "terrain": "sandstone escarpment and forest",
        "center": (-33.7200, 150.3100),
        "description": "Fire and drought hotspot on a forested sandstone escarpment.",
        "extent": (150.270, -33.750, 150.350, -33.690),
        "slope_range": (8.0, 38.0),
        "soil_base": 0.150,
        "rain_factor": 0.90,
        "burn_fraction": 0.28,
        "pumping_stress": False,
    },
    "central_valley": {
        "name": "Central Valley, California",
        "short_name": "Central Valley",
        "group": GROUP_GLOBAL,
        "terrain": "flat irrigated valley floor",
        "center": (36.6000, -120.2000),
        "description": "Groundwater hotspot on a flat irrigated valley floor. Pumping can lower the land surface.",
        "extent": (-120.245, 36.570, -120.155, 36.630),
        "slope_range": (0.1, 2.0),
        "soil_base": 0.170,
        "rain_factor": 0.28,
        "burn_fraction": 0.01,
        "pumping_stress": True,
    },
}

CUSTOM_SITES: dict[str, dict[str, Any]] = {}

SEEDS = {"table_mountain": 2601, "cape_flats": 2602, "silvermine": 2603}
RAINFALL_MONTHS = pd.date_range("2026-01-01", "2026-11-01", freq="MS")
CLIMATOLOGY_MM = np.array([15, 17, 22, 52, 108, 142, 126, 108, 62, 35, 24], dtype=float)
ACTUAL_RATIOS = np.array([0.78, 0.70, 0.64, 0.82, 0.91, 0.76, 0.68, 0.72, 0.58, 0.49, 0.43])
GRID_SHAPE = (36, 42)


def list_sites() -> dict[str, str]:
    """Return preset site IDs and display names."""

    return {site_id: config["name"] for site_id, config in SITE_CONFIGS.items()}


def sites_by_group() -> dict[str, dict[str, str]]:
    """Preset sites grouped for the region dropdown."""

    grouped = {GROUP_LOCAL: {}, GROUP_GLOBAL: {}}
    for site_id, config in SITE_CONFIGS.items():
        grouped[config["group"]][site_id] = config["name"]
    return grouped


def resolve_site(site_id: str) -> dict[str, Any]:
    """Return a preset or a registered custom site."""

    if site_id in SITE_CONFIGS:
        return SITE_CONFIGS[site_id]
    if site_id in CUSTOM_SITES:
        return CUSTOM_SITES[site_id]
    raise ValueError(f"Unknown site_id {site_id!r}. Choose from {list(SITE_CONFIGS)}")


def seed_for(site_id: str, center: tuple[float, float]) -> int:
    """Stable mock seed. Named presets keep their original seeds."""

    if site_id in SEEDS:
        return SEEDS[site_id]
    lat, lon = center
    mixed = int(round(lat * 100)) * 100_003 + int(round(lon * 100)) * 100_019
    return abs(mixed) % 2_000_000_000


def extent_size_km(extent: tuple[float, float, float, float]) -> tuple[float, float]:
    """Return width and height of a lon/lat box in kilometres."""

    west, south, east, north = extent
    mid_lat = (south + north) / 2
    height = (north - south) * 111.0
    width = (east - west) * 111.0 * math.cos(math.radians(mid_lat))
    return abs(width), abs(height)


def custom_extent(lat: float, lon: float, km: float = CUSTOM_BOX_KM) -> tuple[float, float, float, float]:
    """A box of about ``km`` on a side, never larger than that on the ground."""

    half = km / 2
    dlat = half / 111.0
    cosine = math.cos(math.radians(lat))
    if abs(cosine) < 0.2:
        dlon = half / (111.0 * 0.2)
    else:
        dlon = half / (111.0 * abs(cosine))
    # Cap the degree span so a polar click cannot request a huge longitude range.
    dlat = min(dlat, 2.5 / 111.0)
    dlon = min(dlon, 2.5 / (111.0 * 0.2))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def format_coordinates(lat: float, lon: float) -> str:
    north_south = "S" if lat < 0 else "N"
    east_west = "W" if lon < 0 else "E"
    return f"{abs(lat):.2f}°{north_south}, {abs(lon):.2f}°{east_west}"


def register_custom_site(lat: float, lon: float) -> str:
    """Create or reuse a 5 km site centred on rounded coordinates."""

    lat_r = round(float(lat), 2)
    lon_r = round(float(lon), 2)
    site_id = f"custom_{lat_r:+.2f}_{lon_r:+.2f}".replace("+", "p").replace("-", "m").replace(".", "d")
    if site_id not in CUSTOM_SITES:
        extent = custom_extent(lat_r, lon_r)
        CUSTOM_SITES[site_id] = {
            "name": "Custom location",
            "short_name": "Custom",
            "group": "Custom",
            "terrain": "map click",
            "center": (lat_r, lon_r),
            "description": (
                f"Custom location at {format_coordinates(lat_r, lon_r)}. "
                "The box is about 5 km on a side. "
                "The burn mask is a labeled mock layer."
            ),
            "extent": extent,
            "slope_range": (2.0, 25.0),
            "soil_base": 0.180,
            "rain_factor": 1.0,
            "burn_fraction": 0.08,
            "pumping_stress": False,
            "custom": True,
        }
    return site_id


def load_site_data(
    site_id: str, source: Literal["mock", "earthdata"] = "mock"
) -> SiteData:
    """Load one site's complete data bundle.

    This is the single integration boundary used by the UI. When real files
    arrive, implement ``_load_earthdata`` while preserving the returned shapes,
    variables, units, CRS metadata, and table columns.
    """

    resolve_site(site_id)
    if source == "mock":
        return _load_mock(site_id)
    if source == "earthdata":
        try:
            return _load_earthdata(site_id)
        except Exception as exc:
            site = _load_mock(site_id)
            site.metadata["source"] = "MOCK fallback after an Earthdata failure"
            site.metadata["fallback"] = True
            site.metadata["notice"] = (
                "NASA Earthdata could not be loaded "
                f"({type(exc).__name__}: {exc}). Showing the seeded mock dataset."
            )
            return site
    raise ValueError(f"Unsupported source: {source!r}")


def _load_mock(site_id: str) -> SiteData:
    config = resolve_site(site_id)
    rng = np.random.default_rng(seed_for(site_id, config["center"]))
    x, y, transform = _grid_coordinates(config["extent"])

    boundary = gpd.GeoDataFrame(
        {"site_id": [site_id], "name": [config["name"]]},
        geometry=[box(*config["extent"])],
        crs="EPSG:4326",
    )
    rainfall = _mock_rainfall(config, rng)
    slope = _mock_slope(config, x, y, transform, rng)
    burn_mask = _mock_burn_mask(config, x, y, transform, rng)
    soil_moisture = _mock_soil_moisture(config, rainfall, x, y, transform, rng)
    runoff_risk = _calculate_runoff_risk(soil_moisture, slope, burn_mask)

    return SiteData(
        site_id=site_id,
        name=config["name"],
        description=config["description"],
        center=config["center"],
        boundary=boundary,
        rainfall=rainfall,
        soil_moisture=soil_moisture,
        slope=slope,
        burn_mask=burn_mask,
        runoff_risk=runoff_risk,
        metadata={
            "source": "MOCK — synthetic Earthdata-like products",
            "orbit_repeat_days": 12,
            "rainfall_product": "CHIRPS-like monthly precipitation",
            "soil_product": "NISAR L3 SME2-like surface soil moisture",
            "crs": "EPSG:4326",
            "pumping_stress": config["pumping_stress"],
            "terrain": config.get("terrain", ""),
            "latitude": config["center"][0],
            "longitude": config["center"][1],
            "layers": {
                "rainfall": "MOCK · seeded monthly rainfall",
                "soil_moisture": "MOCK · seeded soil moisture",
                "slope": "MOCK · seeded slope",
                "burn_mask": "MOCK · seeded burn mask",
            },
        },
    )


def _grid_coordinates(
    extent: tuple[float, float, float, float],
) -> tuple[np.ndarray, np.ndarray, Affine]:
    west, south, east, north = extent
    height, width = GRID_SHAPE
    dx, dy = (east - west) / width, (north - south) / height
    x = west + dx * (np.arange(width) + 0.5)
    # North-to-south matches the row order of a north-up GeoTIFF.
    y = north - dy * (np.arange(height) + 0.5)
    transform = Affine(dx, 0.0, west, 0.0, -dy, north)
    return x, y, transform


def _mock_rainfall(config: dict[str, Any], rng: np.random.Generator) -> pd.DataFrame:
    climatology = CLIMATOLOGY_MM * config["rain_factor"]
    noise = rng.normal(0.0, 0.045, len(RAINFALL_MONTHS))
    observed = climatology * np.clip(ACTUAL_RATIOS + noise, 0.32, 1.05)
    anomaly = observed - climatology
    return pd.DataFrame(
        {
            "time": RAINFALL_MONTHS,
            "observed_mm": observed.round(1),
            "climatology_mm": climatology.round(1),
            "anomaly_mm": anomaly.round(1),
            "percent_normal": (100 * observed / climatology).round(1),
        }
    )


def _mock_slope(
    config: dict[str, Any],
    x: np.ndarray,
    y: np.ndarray,
    transform: Affine,
    rng: np.random.Generator,
) -> xr.DataArray:
    yy, xx = np.mgrid[-1:1:complex(len(y)), -1:1:complex(len(x))]
    terrain = (
        0.52
        + 0.25 * np.sin(2.4 * np.pi * xx)
        + 0.19 * np.cos(1.7 * np.pi * yy)
        + 0.12 * np.sin(2.2 * np.pi * (xx + yy))
        + rng.normal(0, 0.055, GRID_SHAPE)
    )
    terrain = (terrain - terrain.min()) / (terrain.max() - terrain.min())
    low, high = config["slope_range"]
    values = low + terrain * (high - low)
    return xr.DataArray(
        values.astype("float32"),
        dims=("y", "x"),
        coords={"y": y, "x": x},
        name="slope",
        attrs={
            "long_name": "terrain slope",
            "units": "degrees",
            "crs": "EPSG:4326",
            "transform": tuple(transform),
            "source": "MOCK Copernicus DEM-derived slope",
            "_FillValue": -9999.0,
        },
    )


def _mock_burn_mask(
    config: dict[str, Any],
    x: np.ndarray,
    y: np.ndarray,
    transform: Affine,
    rng: np.random.Generator,
) -> xr.DataArray:
    yy, xx = np.mgrid[-1:1:complex(len(y)), -1:1:complex(len(x))]
    patch = np.exp(-((xx - 0.22) ** 2 + (yy + 0.12) ** 2) / 0.22)
    patch += 0.55 * np.exp(-((xx + 0.48) ** 2 + (yy - 0.34) ** 2) / 0.12)
    threshold = np.quantile(patch + rng.normal(0, 0.08, GRID_SHAPE), 1 - config["burn_fraction"])
    values = (patch > threshold).astype("uint8")
    return xr.DataArray(
        values,
        dims=("y", "x"),
        coords={"y": y, "x": x},
        name="burn_flag",
        attrs={
            "long_name": "recent burn scar flag",
            "flag_values": [0, 1],
            "flag_meanings": "unburned burned",
            "crs": "EPSG:4326",
            "transform": tuple(transform),
            "source": "MOCK FIRMS/dNBR-like burn mask",
        },
    )


def _mock_soil_moisture(
    config: dict[str, Any],
    rainfall: pd.DataFrame,
    x: np.ndarray,
    y: np.ndarray,
    transform: Affine,
    rng: np.random.Generator,
) -> xr.Dataset:
    times = pd.date_range("2026-06-01", "2026-11-28", freq="12D")
    month_lookup = rainfall.set_index(rainfall["time"].dt.month)["percent_normal"]
    seasonal = np.array(
        [0.105 * np.exp(-((date.month - 7.0) / 2.15) ** 2) for date in times]
    )
    drought_effect = np.array([(month_lookup.loc[d.month] - 70.0) * 0.00055 for d in times])
    drying = np.linspace(0.015, -0.060, len(times))
    temporal = config["soil_base"] + seasonal + drought_effect + drying
    if config["pumping_stress"]:
        temporal -= np.linspace(0.005, 0.025, len(times))

    yy, xx = np.mgrid[-1:1:complex(len(y)), -1:1:complex(len(x))]
    spatial = 0.018 * np.sin(np.pi * xx) - 0.013 * yy + 0.008 * np.cos(2 * np.pi * yy)
    values = temporal[:, None, None] + spatial[None, :, :]
    values += rng.normal(0, 0.006, (len(times), *GRID_SHAPE))
    values = np.clip(values, 0.055, 0.43).astype("float32")
    quality = np.where(values < 0.07, 1, 0).astype("uint8")

    return xr.Dataset(
        {
            "soil_moisture": (
                ("time", "y", "x"),
                values,
                {
                    "long_name": "surface soil moisture",
                    "standard_name": "volume_fraction_of_water_in_soil",
                    "units": "m3 m-3",
                    "valid_min": 0.0,
                    "valid_max": 0.6,
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
            "title": "MOCK NISAR L3 SME2 Surface Soil Moisture",
            "source": "Synthetic NISAR-like 12-day repeat observations",
            "institution": "NASA Space Apps 2026 — Dancing with the SARs",
            "Conventions": "CF-1.8",
            "crs": "EPSG:4326",
            "transform": tuple(transform),
            "mock_data": "true",
        },
    )


def _calculate_runoff_risk(
    soil: xr.Dataset, slope: xr.DataArray, burn_mask: xr.DataArray
) -> xr.Dataset:
    slope_factor = np.clip(slope / 40.0, 0.0, 1.0)
    moisture = soil["soil_moisture"]
    # Volumetric water content uses the original 0.10–0.34 m3/m3 window.
    # A dimensionless wetness fraction, such as MERRA-2 GWETTOP, is already 0–1.
    if str(moisture.attrs.get("units", "m3 m-3")) == "1":
        wetness_factor = np.clip(moisture, 0.0, 1.0)
    else:
        wetness_factor = np.clip((moisture - 0.10) / 0.24, 0.0, 1.0)
    # Burned terrain has less interception and greater sediment mobility.
    index = 100 * (0.50 * slope_factor + 0.32 * wetness_factor + 0.18 * burn_mask)
    index = index.clip(0, 100).astype("float32").transpose("time", "y", "x")
    risk_class = xr.where(index >= 65, 2, xr.where(index >= 40, 1, 0)).astype("uint8")
    return xr.Dataset(
        {
            "risk_index": index.assign_attrs(
                long_name="runoff and erosion risk index",
                units="0-100",
                method="50% slope + 32% wetness + 18% burn scar",
            ),
            "risk_class": risk_class.assign_attrs(
                flag_values=[0, 1, 2], flag_meanings="low medium high"
            ),
        },
        attrs={
            "source": "MOCK derived product",
            "crs": soil.attrs["crs"],
            "classification": "low < 40; medium 40–64.9; high >= 65",
        },
    )


def slope_geotiff_bytes(site: SiteData) -> bytes:
    """Serialize the in-memory slope layer as a standards-based GeoTIFF."""

    transform = Affine(*site.slope.attrs["transform"][:6])
    with MemoryFile() as memfile:
        with memfile.open(
            driver="GTiff",
            height=site.slope.sizes["y"],
            width=site.slope.sizes["x"],
            count=1,
            dtype="float32",
            crs=CRS.from_string(site.slope.attrs["crs"]),
            transform=transform,
            nodata=-9999.0,
            compress="deflate",
        ) as dataset:
            dataset.write(site.slope.values, 1)
            dataset.update_tags(source=site.slope.attrs["source"], units="degrees")
        return memfile.read()


def _load_earthdata(site_id: str) -> SiteData:
    """Load real NASA and Copernicus layers into the ``SiteData`` contract.

    NISAR L3 SME2 HDF5 files are read with ``h5py`` when ``EARTHDATA_TOKEN`` is
    set. Without that token, soil moisture falls back to NASA POWER's MERRA-2
    surface wetness. Rainfall is NASA POWER. Slope is Copernicus GLO-30.
    The burn mask stays synthetic and is labeled as mock.
    """

    from drought_monitor.earthdata import load_earthdata_site

    return load_earthdata_site(site_id)


def build_summary() -> dict[str, Any]:
    """Build a compact, JSON-serializable summary for every mock site."""

    result: dict[str, Any] = {
        "metadata": {
            "title": "Dancing with the SARs — mock monitoring summary",
            "generated_from": "deterministic synthetic data",
            "period": "2026-01 to 2026-11",
            "risk_counts_represent": "latest 12-day observation",
        },
        "sites": {},
    }
    labels = {0: "low", 1: "medium", 2: "high"}
    for site_id in SITE_CONFIGS:
        site = load_site_data(site_id)
        soil_mean = site.soil_moisture["soil_moisture"].mean(("y", "x"))
        latest_classes = site.runoff_risk["risk_class"].isel(time=-1).values
        result["sites"][site_id] = {
            "name": site.name,
            "monthly_rainfall": [
                {
                    "month": row.time.strftime("%Y-%m"),
                    "observed_mm": float(row.observed_mm),
                    "climatology_mm": float(row.climatology_mm),
                    "anomaly_mm": float(row.anomaly_mm),
                    "percent_normal": float(row.percent_normal),
                }
                for row in site.rainfall.itertuples(index=False)
            ],
            "soil_moisture_mean": [
                {"date": pd.Timestamp(date).strftime("%Y-%m-%d"), "m3_m3": round(float(value), 4)}
                for date, value in zip(soil_mean.time.values, soil_mean.values, strict=True)
            ],
            "risk_class_counts": {
                labels[value]: int(np.count_nonzero(latest_classes == value))
                for value in labels
            },
        }
    return result


def write_summary(path: str | Path = "exports/summary.json") -> Path:
    """Write :func:`build_summary` output and return the resolved path."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build_summary(), indent=2) + "\n", encoding="utf-8")
    return output
