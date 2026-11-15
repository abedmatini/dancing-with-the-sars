# References

Sources, services, and a short journey log for Dancing with the SARs. Update this file when a source, layer, or product decision changes.

## Data sources in the current code

- NISAR L2 geocoded polarimetric covariance browse images, NASA GIBS layer `NISAR_L2_Geocoded_Polarimetric_Covariance`. The gold pins use saved crops of this browse. The SAR button stacks the public days 14 October, 15 October, and 2 November 2026.
- NASA GIBS Blue Marble, `MODIS_Terra_CorrectedReflectance_TrueColor` (the Clouds button, frozen days in October 2026), `MODIS_Terra_Thermal_Anomalies_All` (the fire button, frozen on 15 October 2026), and `SMAP_L4_Analyzed_Surface_Soil_Moisture` (the soil-moisture button, frozen on 16 May 2026).
- NASA POWER temporal API: `PRECTOTCORR` monthly rainfall and `GWETTOP` surface wetness from MERRA-2. The study box uses live `GWETTOP` when a click is not next to a saved pin and Earthdata has not already supplied NISAR soil.
- NASA Earthdata NISAR L3 `NISAR_L3_SME2_PROVISIONAL_V1` surface soil moisture, read through ASF when `EARTHDATA_TOKEN` is set and granules can be read. Without a token the study box does not invent a stand-in.
- Open-Meteo historical archive, saved in `globe/web/public/showcase/weather.json` (daily rain, mean temperature, and 0–7 cm soil moisture). Gold-pin captions read this file. A study-box click within about 40 km of a pin uses the same saved soil series. The showcase does not call Open-Meteo live.
- Copernicus DEM GLO-30 for slope on the Earthdata path.
- OpenStreetMap tiles and Esri World Imagery for the close-zoom photograph.
- Cesium for the globe.

These names were used in write-ups and are not called by the current code: `VIIRS_SNPP_CorrectedReflectance_TrueColor`, `MODIS_Terra_NDVI_8Day`, the FAO crop calendar, and GIEWS ASIS.

Wind arrows used live Open-Meteo (`archive-api.open-meteo.com` and `api.open-meteo.com`). River lines used the MERIT river runner and Overpass. Both were removed. Sentinel-1 and Landsat orbit drawings were removed. The orbit button now draws only an illustrated NISAR orbit (about 747 km, 98.4 degrees, 12-day repeat). It is not a live tracking feed.

## APIs and the app stack

- Claude, through `POST /showcase/read` on the globe API, which calls the Anthropic Messages API to read one NISAR picture. The prompt tells the model the weather numbers are Open-Meteo, not radar and not the NISAR soil-moisture product.
- The globe is React, Vite, and Cesium (Resium) in `globe/web`, with a FastAPI service in `globe/api`.
- NASA POWER `https://power.larc.nasa.gov/api/temporal`.
- NASA GIBS WMTS and WMS.
- NASA CMR and ASF for NISAR soil-moisture granules when a token is present.

## Journey log

Original gold pins: Western Cape, Okavango Delta, Luxor, California Central Valley, Sylhet, Manaus, Ilulissat Glacier, Rotterdam, Punjab, and Los Angeles.

Ten more pins, now on main: Pantanal, Tonle Sap, Menindee Lakes, Riau, Pine Island Glacier, Salar de Atacama, Sundarbans, Aral Sea, Lena Delta, and Kilauea. Lena’s winter 2025–26 frames and Kilauea’s October 2025 frames are omitted where GIBS had no local pixels. Pine Island’s earliest frames are coarse crops.

- Pull request 14 merged the first ten radar pins.
- Pull request 15 replaced live Open-Meteo pin calls with the saved `weather.json`.
- Pull request 16 added the weather trend strip.
- Pull request 17 hid far-side pins with an occluder and removed the cyan dots.
- Pull request 18 left only the NISAR orbit and turned that animation on when the globe loads.
- Pull request 19 added the short welcome above the map.
- Wind arrows and river paths were removed on main after that.
- The ten extra pins were applied from a local stash.
- The SAR button was applied from an older stash and kept the later decisions: NISAR orbit on, no wind, no rivers, no Sentinel-1, no Landsat.
- A Slideshow button sits beside AI and Close on a pin. Play steps the enlarged frames. Pause or Close stops on the current frame.
- The study box no longer shows the seeded soil series from `drought_monitor/data.py`. Soil is the saved Open-Meteo series near a pin, a live NASA POWER `GWETTOP` series, or a NISAR Earthdata scene when a token can read one. If none of those return data, the soil card and chart say “Data unavailable”. The SMAP button and `weather.json` stay. The globe opens asking for the Earthdata source. Rain, slope, and the runoff colors can still come from the loaded scene, including the seeded risk field when Earthdata cannot be read.

## Lessons

- At global zoom, a depth test does not hide a pin on the far side of the Earth. An occluder does.
- A GIBS pixel at zoom 8 is often on a neighboring tile, so a crop can look empty even when the pass exists.
- One MODIS day has orbit gaps. Empty ocean or land on that day is not a data failure.
- Open-Meteo for the showcase has to be a saved file. A live call on every pin is the wrong demo path.
- The NASA POWER window in this project is a fixed 2026 range, not “today”.
- An illustrated orbit has to start on the visible side of the home view or the moving point looks missing.
- A stash cut from an older main will try to put removed layers back. Keep the later product decisions when resolving it.

## Keeping this file current

Add a source when the app starts calling it. Remove a source when the app stops. If a layer is named in a slide or a form and the code does not call it, say so here.
