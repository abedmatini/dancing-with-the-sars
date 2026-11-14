# Publish with Cursor Apps

Suggested URL slug: `dancing-with-the-sars`

Paste this exact one-paragraph prompt into a new Cursor cloud agent started on
this Origin repository:

> Publish this repository to Cursor Apps at the suggested slug `dancing-with-the-sars`, producing a public `*.apps.grok.bot` URL. Deploy the static site from `web/` (its committed `data/` assets are already built); if the publisher requires a process, use `bash scripts/start_static.sh`, which binds to `$PORT`, and use `/health.html` as the health check. Do not modify the app, do not connect or mirror to GitHub, do not deploy to any other provider, and after publishing verify the exact public URL with an HTTP fetch and report its status.

The static app has no secrets, build-time environment variables, database, or
server-side state. Regenerate its committed data before publishing only when the
mock data module has changed:

```bash
python3 scripts/build_web_data.py
```
