"""HTTP API for the 3D globe. Loaders stay in drought_monitor."""

from __future__ import annotations

import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from drought_monitor.assistant import answer_question, podcast_script, summarize_view
from globe.api.rivers import downstream
from globe.api.serialize import context_for, locate, preset_catalog, risk_grid, scene_payload
from globe.api.showcase import read_showcase
from globe.api.store import stored_grid, stored_scene

app = FastAPI(title="Dancing with the SARs globe", version="1.0.0")

_origins = os.environ.get(
    "CORS_ORIGINS", "http://127.0.0.1:4178,http://localhost:4178"
).strip()
if _origins == "*":
    _allow = ["*"]
else:
    _allow = [item.strip() for item in _origins.split(",") if item.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    lat: float
    lon: float
    source: Literal["mock", "earthdata", "database"] = "mock"
    date: str | None = None
    question: str = Field(min_length=1, max_length=500)


class ShowcaseReadRequest(BaseModel):
    id: str = Field(min_length=1, max_length=80)


def _view(lat: float, lon: float, source: str, date: str | None) -> dict:
    if source not in {"mock", "earthdata", "database"}:
        raise HTTPException(status_code=422, detail="source must be mock, earthdata, or database")
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise HTTPException(status_code=422, detail="lat/lon out of range")
    if source == "database":
        payload = stored_scene(lat, lon, date)
        if payload is None:
            raise HTTPException(status_code=404, detail="Nothing is stored for this place.")
        return payload
    site = locate(lat, lon, source)
    return scene_payload(site, source, date)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/sites")
def sites() -> dict:
    return preset_catalog()


@app.get("/site")
def site(
    lat: float = Query(...),
    lon: float = Query(...),
    source: Literal["mock", "earthdata", "database"] = "mock",
    date: str | None = None,
) -> dict:
    return _view(lat, lon, source, date)


@app.get("/risk-grid")
def grid(
    lat: float = Query(...),
    lon: float = Query(...),
    source: Literal["mock", "earthdata", "database"] = "mock",
    date: str | None = None,
) -> dict:
    if source == "database":
        payload = stored_grid(lat, lon, date)
        if payload is None:
            raise HTTPException(status_code=404, detail="Nothing is stored for this place.")
        return payload
    located = locate(lat, lon, source)
    return risk_grid(located, date)


@app.get("/flow")
def flow(lat: float = Query(...), lon: float = Query(...)) -> dict:
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise HTTPException(status_code=422, detail="lat/lon out of range")
    return downstream(lat, lon)


@app.get("/summary")
def summary(
    lat: float = Query(...),
    lon: float = Query(...),
    source: Literal["mock", "earthdata", "database"] = "mock",
    date: str | None = None,
) -> dict:
    payload = _view(lat, lon, source, date)
    text, provider, error = summarize_view(context_for(payload))
    return {"text": text, "provider": provider, "error": error}


@app.get("/podcast")
def podcast(
    lat: float = Query(...),
    lon: float = Query(...),
    source: Literal["mock", "earthdata", "database"] = "mock",
    date: str | None = None,
) -> dict:
    payload = _view(lat, lon, source, date)
    text, provider, error = podcast_script(context_for(payload))
    return {"text": text, "provider": provider, "error": error}


@app.post("/showcase/read")
def showcase_read(body: ShowcaseReadRequest) -> dict:
    return read_showcase(body.id)


@app.post("/chat")
def chat(body: ChatRequest) -> dict:
    payload = _view(body.lat, body.lon, body.source, body.date)
    text, provider, error = answer_question(body.question, context_for(payload))
    return {"answer": text, "provider": provider, "error": error}
