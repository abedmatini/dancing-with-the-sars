"""Local secret file names stay documented and untracked."""

from pathlib import Path

from drought_monitor.env import load_local_env

ROOT = Path(__file__).resolve().parents[1]


def test_env_example_lists_empty_names():
    text = (ROOT / ".env.example").read_text()
    assert text == (
        "EARTHDATA_TOKEN=\n"
        "EARTHDATA_USERNAME=\n"
        "EARTHDATA_PASSWORD=\n"
        "ANTHROPIC_API_KEY=\n"
        "ANTHROPIC_MODEL=\n"
    )


def test_local_env_load_does_not_raise():
    assert load_local_env() is None
