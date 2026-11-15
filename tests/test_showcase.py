"""Radar showcase: small stored pictures, Claude only with a key."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from globe.api.main import app

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1] / "globe" / "web" / "public" / "showcase" / "western-cape"


def test_ten_spots_stay_small():
    index = json.loads((ROOT.parent / "index.json").read_text())
    spots = index["spots"]
    assert len(spots) == 10
    assert [spot["id"] for spot in spots] == [
        "western-cape",
        "okavango",
        "luxor",
        "central-valley",
        "sylhet",
        "manaus",
        "ilulissat",
        "rotterdam",
        "punjab",
        "los-angeles",
    ]
    files = list(ROOT.parent.rglob("*.jpg"))
    assert all(5 <= len(spot["frames"]) <= 7 for spot in spots)
    assert sum(path.stat().st_size for path in files) < 2_000_000
    assert all(path.stat().st_size < 80_000 for path in files)


def test_western_cape_pictures_are_few_and_small():
    files = sorted(ROOT.glob("*.jpg"))
    assert [path.name for path in files] == [
        "2026-06.jpg",
        "2026-07.jpg",
        "2026-08.jpg",
        "2026-09.jpg",
        "2026-10.jpg",
        "2026-11.jpg",
    ]
    assert sum(path.stat().st_size for path in files) < 250_000
    assert all(path.stat().st_size < 80_000 for path in files)


def test_showcase_read_without_a_key_does_not_call_claude(monkeypatch):
    monkeypatch.setattr("globe.api.showcase._setting", lambda _name: None)
    called = {"n": 0}

    def explode(*_args, **_kwargs):
        called["n"] += 1
        raise AssertionError("Claude was called without a key")

    monkeypatch.setattr("globe.api.showcase._post_json", explode)
    response = client.post("/showcase/read", json={"id": "western-cape"})
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "none"
    assert "ANTHROPIC_API_KEY" in body["answer"]
    assert called["n"] == 0


def test_showcase_read_sends_the_stored_pictures(monkeypatch):
    monkeypatch.setattr(
        "globe.api.showcase._setting",
        lambda name: "test-key" if name == "ANTHROPIC_API_KEY" else None,
    )
    seen = {}

    def capture(url, body, headers):
        seen["url"] = url
        seen["images"] = [block for block in body["messages"][0]["content"] if block["type"] == "image"]
        seen["key"] = headers["x-api-key"]
        return {"content": [{"type": "text", "text": "The Karoo stays gold."}]}

    monkeypatch.setattr("globe.api.showcase._post_json", capture)
    response = client.post("/showcase/read", json={"id": "western-cape"})
    assert response.status_code == 200
    assert response.json()["answer"] == "The Karoo stays gold."
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["key"] == "test-key"
    assert len(seen["images"]) == 6


def test_unknown_showcase_is_missing():
    response = client.post("/showcase/read", json={"id": "not-a-place"})
    assert response.status_code == 404
