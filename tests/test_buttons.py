"""AppTest clicks for the summary and the on-page chat."""

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


def _app(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    app = AppTest.from_file(APP, default_timeout=40)
    app.run()
    assert not app.exception, app.exception
    return app


def test_summarize_and_chat_without_a_key(monkeypatch):
    app = _app(monkeypatch)
    app.button(key="summarize_view").click().run()
    assert not app.exception, app.exception
    summary = app.session_state["view_summary"]
    assert "shown with" in summary
    assert app.session_state["summary_provider"] == "page"
    assert app.session_state["summary_error"] is None
    app.run()
    assert app.session_state["view_summary"] == summary
    assert any(summary[:40] in block.value for block in app.markdown)

    app.button(key="ask_about_data").click().run()
    assert not app.exception, app.exception
    assert any("ANTHROPIC_API_KEY" in note.value for note in app.info)
    app.chat_input(key="data_question").set_value(
        "How does rainfall compare with normal?"
    ).run()
    assert not app.exception, app.exception
    messages = app.session_state["qa_messages"]
    assert messages[-2]["role"] == "user"
    assert "rainfall" in messages[-1]["content"].lower()
    assert "%" in messages[-1]["content"]
    app.run()
    assert app.session_state["qa_messages"] == messages


def test_summary_clears_when_the_site_changes(monkeypatch):
    app = _app(monkeypatch)
    app.button(key="summarize_view").click().run()
    assert "Table Mountain" in app.session_state["view_summary"]
    app.selectbox[0].set_value("cape_flats").run()
    assert not app.exception, app.exception
    assert "view_summary" not in app.session_state


def test_buttons_show_a_mocked_claude_response(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {"content": [{"type": "text", "text": "Claude says this view is a watch."}]}
            ).encode()

    def fake_urlopen(request, timeout=25):
        assert request.get_header("X-api-key") == "test-key"
        assert request.get_header("Anthropic-version") == "2023-06-01"
        assert request.full_url == "https://api.anthropic.com/v1/messages"
        return _Response()

    monkeypatch.setattr("drought_monitor.assistant.urllib.request.urlopen", fake_urlopen)
    app = AppTest.from_file(APP, default_timeout=40)
    app.run()
    assert not app.exception, app.exception
    app.button(key="summarize_view").click().run()
    assert not app.exception, app.exception
    assert app.session_state["view_summary"] == "Claude says this view is a watch."
    assert app.session_state["summary_provider"] == "claude"
    assert any("Summary from Claude." in note.value for note in app.caption)

    app.button(key="ask_about_data").click().run()
    app.chat_input(key="data_question").set_value("What is the runoff risk?").run()
    assert not app.exception, app.exception
    assert app.session_state["qa_messages"][-1]["content"] == "Claude says this view is a watch."
