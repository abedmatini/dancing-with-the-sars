"""Local summary and no-key chat fallbacks."""

import re

from drought_monitor.assistant import (
    NO_KEY_NOTICE,
    answer_question,
    build_context,
    earthdata_credentials_present,
    earthdata_token_notice,
    fallback_answer,
    llm_provider,
    summarize_view,
    template_summary,
)


def _context(**overrides):
    values = dict(
        site_name="Table Mountain / Cape Peninsula fynbos",
        slider_date="28 November 2026",
        rain_month="November 2026",
        percent_normal=72.0,
        anomaly_mm=-18.0,
        climatology_name="1991–2020 climatology",
        soil_value=0.18,
        soil_unit="m³/m³",
        soil_first=0.31,
        risk_score=58.0,
        risk_class="Medium",
        burned_percent=12.4,
        mean_slope=19.8,
        source_mode="mock",
        using_mock=True,
    )
    values.update(overrides)
    return build_context(**values)


def _sentences(text: str) -> list[str]:
    return [part for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part]


def test_template_summary_covers_the_view():
    context = _context()
    summary = template_summary(context)
    sentences = _sentences(summary)
    assert 4 <= len(sentences) <= 6
    assert "28 November 2026" in summary
    assert "72%" in summary
    assert "1991–2020 climatology" in summary
    assert "lower than the first scene" in summary
    assert "Medium" in summary
    assert "40–64.9" in summary
    assert "12.4%" in summary
    assert "sediment" in summary.lower()
    assert "mock data" in summary


def test_summary_without_a_key_uses_the_template(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    context = _context()
    text, provider = summarize_view(context)
    assert provider == "page"
    assert text == template_summary(context)
    assert llm_provider() is None


def test_chat_without_a_key_answers_from_the_page(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    context = _context()
    rain, provider = answer_question("How does rainfall compare with normal?", context)
    assert provider == "page"
    assert "72%" in rain
    assert "-18 mm" in rain
    assert "GEMINI_API_KEY" in NO_KEY_NOTICE
    assert "Streamlit Cloud > App settings > Secrets" in NO_KEY_NOTICE


def test_unknown_question_says_it_is_not_on_the_page():
    reply = fallback_answer("Who won the 2010 World Cup?", _context())
    assert "not known" in reply


def test_failed_model_call_falls_back(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def explode(*args, **kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr("drought_monitor.assistant._gemini", explode)
    text, provider = answer_question("What is the runoff risk?", _context())
    assert provider == "page"
    assert "Medium" in text
    summary, summary_provider = summarize_view(_context())
    assert summary_provider == "page"
    assert summary == template_summary(_context())


def test_token_notice_names_the_secret_and_signup(monkeypatch):
    monkeypatch.delenv("EARTHDATA_TOKEN", raising=False)
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    mock_notice = earthdata_token_notice(True)
    live_notice = earthdata_token_notice(False)
    assert "using mock data" in mock_notice
    assert "EARTHDATA_TOKEN" in mock_notice
    assert "https://urs.earthdata.nasa.gov" in mock_notice
    assert "App settings > Secrets" in mock_notice
    assert "mock data" not in live_notice.split(".")[0]
    assert "burn mask is still mock" in live_notice
    assert earthdata_credentials_present() is False
