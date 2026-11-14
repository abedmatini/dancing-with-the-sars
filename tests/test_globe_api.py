"""Globe API in mock mode. No NASA calls."""

from fastapi.testclient import TestClient

from drought_monitor.data import GRID_SHAPE
from globe.api.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_sites_are_grouped():
    payload = client.get("/sites").json()
    names = {group["name"]: {site["id"] for site in group["sites"]} for group in payload["groups"]}
    assert "jonkershoek" in names["Cape Town / Western Cape"]
    assert "palisades" in names["Global"]
    assert "attica" in names["Global"]
    cape = next(site for site in payload["groups"][0]["sites"] if site["id"] == "table_mountain")
    assert cape["lat"] == -33.9628


def test_preset_click_and_custom_five_kilometre_box():
    preset = client.get("/site", params={"lat": -33.9628, "lon": 18.4098, "source": "mock"})
    assert preset.status_code == 200
    body = preset.json()
    assert body["name"] == "Table Mountain / Cape Peninsula"
    assert body["layers"]["burn_mask"].startswith("MOCK")
    assert body["layers"]["rainfall"].startswith("MOCK")
    assert body["risk"]["ranges"].startswith("Low")
    assert body["dates"]
    assert len(body["soil_moisture"]) == len(body["dates"])
    assert body["rainfall"][-1]["percent_normal"] > 0

    custom = client.get("/site", params={"lat": 1.234, "lon": 36.543, "source": "mock"}).json()
    assert custom["name"] == "Custom location"
    assert custom["lat"] == 1.23
    assert custom["lon"] == 36.54
    width = (custom["east"] - custom["west"]) * 111.0
    assert width < 12


def test_risk_grid_summary_and_chat_without_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    grid = client.get(
        "/risk-grid",
        params={"lat": -33.9628, "lon": 18.4098, "source": "mock", "date": "2026-11-28"},
    ).json()
    assert grid["rows"] == GRID_SHAPE[0]
    assert grid["cols"] == GRID_SHAPE[1]
    assert len(grid["values"]) == GRID_SHAPE[0]
    assert len(grid["values"][0]) == GRID_SHAPE[1]

    summary = client.get(
        "/summary", params={"lat": -33.9628, "lon": 18.4098, "source": "mock"}
    ).json()
    assert summary["provider"] == "page"
    assert "Table Mountain" in summary["text"]
    assert summary["error"] is None

    chat = client.post(
        "/chat",
        json={
            "lat": -33.9628,
            "lon": 18.4098,
            "source": "mock",
            "question": "How does rainfall compare with normal?",
        },
    ).json()
    assert chat["provider"] == "page"
    assert "%" in chat["answer"]
    briefing = client.get(
        "/podcast", params={"lat": -33.9628, "lon": 18.4098, "source": "mock"}
    ).json()
    assert briefing["provider"] == "page"
    assert "land buyer" in briefing["text"]
    assert "fire crew" in briefing["text"]
    assert "not a forecast" in briefing["text"]

    unknown = client.post(
        "/chat",
        json={"lat": 1.0, "lon": 36.0, "source": "mock", "question": "Who won the 2010 World Cup?"},
    ).json()
    assert "not known" in unknown["answer"]
