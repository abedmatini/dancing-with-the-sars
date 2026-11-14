# Dancing with the SARs

A small, runnable drought and runoff-risk monitoring dashboard for three Cape
Town study sites. It is a NASA Space Apps 2026 hackathon prototype showing how
NISAR L-band radar soil-moisture observations can be combined with rainfall,
terrain and recent fire information.

> Every value currently shown is deterministic **mock data**. The synthetic
> products are shaped and attributed like likely Earthdata inputs, but they
> must not be used for operational decisions.

## What is included

- Table Mountain / Cape Peninsula, Cape Flats Aquifer and Silvermine study sites
- Cape winter-rainfall seasonality, anomalies and percentage of normal
- NISAR L3 SME2-like `xarray.Dataset` (`time, y, x`) on a 12-day repeat
- Raster-compatible slope and fire layers with CRS and affine transform metadata
- Explainable runoff/erosion risk classes
- Interactive Folium map, Plotly trends, scene slider and downloadable GeoTIFF
- Reusable all-site summary at `exports/summary.json`

## Run locally

Requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Streamlit prints the local URL, normally `http://localhost:8501`.

The deployment-ready static edition uses the same generated mock data and needs
only Python's standard library to serve:

```bash
bash scripts/start_static.sh
```

Open `http://localhost:8000`. Hosts can set `PORT`; the script binds to
`0.0.0.0`. Its health check is `/health.html`. The `Procfile` uses this static
edition because it works on both process-based and static Cursor Apps hosting.

Run the data-contract tests with:

```bash
pytest -q
```

Regenerate the committed summary after changing mock generation:

```bash
python3 scripts/build_web_data.py
```

This refreshes `exports/summary.json` and the browser assets under `web/data/`.

## Swap in real Earthdata

The UI has one data boundary:

```python
load_site_data(site_id, source="mock")
```

Implement `_load_earthdata()` in `drought_monitor/data.py`, then switch the
source argument to `"earthdata"`. The stub documents the expected adapters:

- NISAR GCOV/SME2 HDF5 through `h5py`/`xarray`
- DEM or slope GeoTIFF through `rasterio`
- CHIRPS-style rainfall NetCDF/GeoTIFF
- Site boundary GeoJSON/GPKG through `geopandas`

The real loader must return the existing `SiteData` contract, so no map, chart
or dashboard logic needs source-specific changes.

## Project layout

```text
app.py                    Streamlit user interface
drought_monitor/data.py   Mock generator, data contract, real-loader seam
exports/summary.json      Reusable deterministic mock summary
web/                      Static Leaflet + Plotly dashboard for Cursor Apps
scripts/build_web_data.py Rebuild static data from the canonical loader
scripts/start_static.sh   PORT-aware static production start command
Procfile                  Process-host start declaration
PUBLISH.md                One-step Cursor Apps agent hand-off prompt
tests/test_data.py        Data shape, determinism and GeoTIFF tests
requirements.txt          Open-source Python dependencies
```

The risk index is a transparent prototype calculation: 50% normalized slope,
32% soil wetness and 18% recent-burn flag. It is not a calibrated hazard model.
