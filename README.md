# Dancing with the SARs

A small, runnable drought and runoff-risk monitoring dashboard for three Cape
Town study sites. It is a NASA Space Apps 2026 hackathon prototype showing how
NISAR L-band radar soil-moisture observations can be combined with rainfall,
terrain and recent fire information.

> The default view is deterministic **mock data**. The sidebar can switch to
> NASA Earthdata. Neither view is for operational decisions.

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

**Ask about this data** opens a chat about the current site, slider date, and
metrics. **Summarize this view** writes four to six sentences. Both work with
no API key. A key is optional; see the secrets table below.

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

## NASA Earthdata in the app

The sidebar has a **Mock / NASA Earthdata** toggle. Both paths return the same
`SiteData` contract from `load_site_data(site_id, source=...)`.

Without a token, Earthdata mode uses:

- Rainfall: [NASA POWER](https://power.larc.nasa.gov/api/) `PRECTOTCORR`, converted from mm/day to a monthly total, compared with the POWER climatology
- Soil moisture: NASA POWER `GWETTOP` (MERRA-2 surface wetness), sampled every 12 days
- Slope: Copernicus DEM GLO-30 from the public AWS COG bucket
- Burn mask: the seeded mock layer, labeled as mock

`NISAR_L3_SME2_PROVISIONAL_V1` granules do intersect the Cape Town sites. ASF
serves those HDF5 files only with an Earthdata bearer token. When
`EARTHDATA_TOKEN` is set, the loader downloads up to six scenes about 12 days
apart and reads the soil-moisture dataset with `h5py`. If that read fails, or
there is no token, the page keeps the POWER wetness series and explains why.

If the whole Earthdata load fails, the page falls back to mock data and shows
a warning.

### Add a free Earthdata token

1. Create a free account at [https://urs.earthdata.nasa.gov/users/new](https://urs.earthdata.nasa.gov/users/new).
2. In the Earthdata profile, open **Applications** and approve **Alaska Satellite Facility (ASF)** and **LP DAAC** (needed for NISAR granules and, later, MODIS burned area).
3. Open **Generate Token** and copy the token.
4. For a local run, export it before starting Streamlit:

```bash
export EARTHDATA_TOKEN="paste-token-here"
streamlit run app.py
```

5. On Streamlit Community Cloud, open the app, then **Settings** (or **Manage app**) → **Secrets**, and save:

```toml
EARTHDATA_TOKEN = "paste-token-here"
```

Reboot the app after saving the secret. Do not commit the token.

### Secrets

| Name | Where it is used |
| --- | --- |
| `EARTHDATA_TOKEN` | NISAR HDF5 downloads. Without it, Earthdata mode keeps public POWER and Copernicus layers and a mock burn mask. |
| `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD` | Optional pair. If both are set, the missing-token banner stays hidden. Downloads in this app still use `EARTHDATA_TOKEN`. |
| `GEMINI_API_KEY` | Google Gemini answers for **Ask about this data** and **Summarize this view**. Optional `GEMINI_MODEL` (default `gemini-2.5-flash`). |
| `LLM_API_KEY` | OpenAI-compatible chat. Used instead of Gemini when set. |
| `LLM_BASE_URL` | Optional. Defaults to `https://api.openai.com/v1`. |
| `LLM_MODEL` | Optional. Defaults to `gpt-4o-mini`. |

Put the same names in `.streamlit/secrets.toml` locally, or in Streamlit Cloud under **App settings > Secrets**. With no language-model key, both buttons still answer from the numbers on the page.

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
tests/test_assistant.py   On-page summary and no-key chat fallback
requirements.txt          Open-source Python dependencies
```

The risk index is a transparent prototype calculation: 50% normalized slope,
32% soil wetness and 18% recent-burn flag. It is not a calibrated hazard model.
