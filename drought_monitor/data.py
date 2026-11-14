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


SITE_CONFIGS: dict[str, dict[str, Any]] = {
    "table_mountain": {
        "name": "Table Mountain / Cape Peninsula",
        "short_name": "Table Mountain",
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
        "center": (-34.0850, 18.4230),
        "description": "Steep fynbos headwaters draining toward False Bay.",
        "extent": (18.390, -34.115, 18.456, -34.055),
        "slope_range": (12.0, 42.0),
        "soil_base": 0.220,
        "rain_factor": 1.12,
        "burn_fraction": 0.34,
        "pumping_stress": False,
    },
}

SEEDS = {"table_mountain": 2601, "cape_flats": 2602, "silvermine": 2603}
RAINFALL_MONTHS = pd.date_range("2026-01-01", "2026-11-01", freq="MS")
CLIMATOLOGY_MM = np.array([15, 17, 22, 52, 108, 142, 126, 108, 62, 35, 24], dtype=float)
ACTUAL_RATIOS = np.array([0.78, 0.70, 0.64, 0.82, 0.91, 0.76, 0.68, 0.72, 0.58, 0.49, 0.43])
GRID_SHAPE = (36, 42)


def list_sites() -> dict[str, str]:
    """Return site IDs and display names without exposing loader internals."""

    return {site_id: config["name"] for site_id, config in SITE_CONFIGS.items()}


def load_site_data(
    site_id: str, source: Literal["mock", "earthdata"] = "mock"
) -> SiteData:
    """Load one site's complete data bundle.

    This is the single integration boundary used by the UI. When real files
    arrive, implement ``_load_earthdata`` while preserving the returned shapes,
    variables, units, CRS metadata, and table columns.
    """

    if site_id not in SITE_CONFIGS:
        raise ValueError(f"Unknown site_id {site_id!r}. Choose from {list(SITE_CONFIGS)}")
    if source == "mock":
        return _load_mock(site_id)
    if source == "earthdata":
        return _load_earthdata(site_id)
    raise ValueError(f"Unsupported source: {source!r}")


def _load_mock(site_id: str) -> SiteData:
    config = SITE_CONFIGS[site_id]
    rng = np.random.default_rng(SEEDS[site_id])
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
    wetness_factor = np.clip((soil["soil_moisture"] - 0.10) / 0.24, 0.0, 1.0)
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
    """Load real products and normalize them to ``SiteData``.

    Implementation seam for production:

    * NISAR GCOV/SME2 HDF5: open groups with ``h5py`` or ``xarray``; rename
      dimensions to ``time, y, x`` and soil moisture to ``soil_moisture``.
    * DEM/slope GeoTIFF: read values, CRS and affine transform with ``rasterio``.
    * CHIRPS precipitation: read NetCDF/GeoTIFF and aggregate over the boundary,
      returning the same five rainfall columns as ``_mock_rainfall``.
    * Boundaries: read GeoJSON/GPKG with ``geopandas`` and reproject to EPSG:4326.

    No dashboard code should need to change when this function is implemented.
    """

    raise NotImplementedError(
        f"Earthdata loading is not configured for {site_id!r}. "
        "Add file paths and normalization logic in drought_monitor/data.py."
    )


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
