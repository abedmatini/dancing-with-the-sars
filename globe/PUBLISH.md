# Publish the globe

The 3D globe is a static site built from `globe/web`. Abed publishes it himself from Cursor's Preview / Publish tray. This file does not publish anything.

Suggested public slug: `sars-globe`.

The existing Streamlit app and the static dashboard under `web/` stay as they are. Do not replace the `web` process in the `Procfile`.

## Paste this prompt into a new Cursor agent

```text
Publish the 3D globe in this repository to Cursor Apps. Do not modify the Streamlit app, and do not change the existing static dashboard under web/.

1. From the repository root, install and build only the globe frontend:
   cd globe/web
   npm ci
   npm run build
   The production files are in globe/web/dist.

2. Publish that dist directory with Cursor's Preview / Publish tray (Cursor Apps, *.apps.grok.bot). Use the slug sars-globe. Do not connect a new GitHub repository and do not deploy anywhere else.

3. If the publisher asks for a process instead of a static directory, run it from the repository root with:
   PORT="$PORT" bash scripts/start_globe.sh
   That serves globe/web/dist on $PORT. Leave the Procfile `web` entry pointed at scripts/start_static.sh.

4. Open the published URL and confirm the page loads: a dark globe, the title "Drought and runoff globe", and a Guided tour button. Also open /health.html and confirm the body says ok.

5. Reply with the public URL. Do not change application code unless the build itself fails.
```

Set `VITE_API_BASE` before `npm run build` when the free API below is already deployed. A rebuild is required after changing it, because Vite bakes the value into the static files. If it is unset, the built site calls `http://127.0.0.1:8091` and, when that is unreachable, uses `globe/web/public/demo.json`.

```bash
# example, from globe/web, before npm run build
echo 'VITE_API_BASE=https://sars-globe-api.onrender.com' > .env.local
```

On the API host, set `CORS_ORIGINS` to `*` or to the published origin, for example `https://sars-globe.apps.grok.bot`.

## Free API on Render

`render.yaml` at the repository root describes a free Python web service.

1. Create a Render account and a new Blueprint from this repository, or a new Web Service with root directory `/`.
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn globe.api.main:app --host 0.0.0.0 --port $PORT`
4. Plan: Free.
5. Environment variables:
   - `CORS_ORIGINS` = `*` (or the published globe origin)
   - `EARTHDATA_TOKEN` = optional, only if NASA granule downloads should run
   - `ANTHROPIC_API_KEY` = optional. Without it, `/summary` and `/chat` use the on-page template.
   - `ANTHROPIC_MODEL` = optional
6. After the service is live, set `VITE_API_BASE` to that URL and rebuild `globe/web`.

Mock mode does not need either secret. The first request after a free-tier sleep can take a minute.

## Free API on a Hugging Face Space

Use `globe/Dockerfile`. The build context is the repository root, because the API imports `drought_monitor`.

1. Create a new Docker Space (free hardware).
2. Point it at this repository. If the Space only reads a root `Dockerfile`, copy `globe/Dockerfile` to `Dockerfile` in the Space, or set the Space to build with `docker build -f globe/Dockerfile .`.
3. The container listens on port `7860`, which Spaces expect. `CORS_ORIGINS` defaults to `*`.
4. In Space settings, add `EARTHDATA_TOKEN` and `ANTHROPIC_API_KEY` only if you want live NASA downloads or Claude. Leave them empty for the mock demo.
5. Set `VITE_API_BASE` to the Space URL, including `https://`, and rebuild the frontend.

## Run it locally

API, from the repository root, after `pip install -r requirements.txt`:

```bash
uvicorn globe.api.main:app --host 127.0.0.1 --port 8091
```

Web:

```bash
cd globe/web
npm ci
npm run dev
```

Open `http://127.0.0.1:4178`. Optional `globe/web/.env.local`:

```bash
VITE_API_BASE=http://127.0.0.1:8091
VITE_CESIUM_ION_TOKEN=
```

Leave `VITE_CESIUM_ION_TOKEN` empty. The globe then uses the WGS84 ellipsoid and NASA GIBS imagery, with OpenStreetMap as a switchable fallback. No Cesium ion account is required.
