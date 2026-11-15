"""Read a stored NISAR showcase with Claude, when a key is set."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from fastapi import HTTPException

from drought_monitor.assistant import DEFAULT_ANTHROPIC_MODEL, _post_json, _setting

_PUBLIC = Path(__file__).resolve().parents[2] / "globe" / "web" / "public"
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _bounded(value: object, low: float, high: float) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number < low or number > high:
        return None
    return number


def weather_note(days: list[dict] | None) -> str:
    """Plain lines from Open-Meteo. Values outside a physical range are left out."""
    lines: list[str] = []
    for day in (days or [])[:16]:
        if not isinstance(day, dict):
            continue
        date = str(day.get("date") or "")
        if not _DATE.fullmatch(date):
            continue
        bits: list[str] = []
        rain = _bounded(day.get("rain_mm"), 0, 500)
        temperature = _bounded(day.get("temperature_c"), -80, 60)
        soil = _bounded(day.get("soil_moisture"), 0, 1)
        if rain is not None:
            bits.append(f"rain {rain:.1f} mm")
        if temperature is not None:
            bits.append(f"temperature {temperature:.1f} °C")
        if soil is not None:
            bits.append(f"soil moisture 0–7 cm {soil:.3f} m³/m³")
        if bits:
            lines.append(f"{date}: {', '.join(bits)}")
    if not lines:
        return "No Open-Meteo figures were supplied for these dates."
    return "Open-Meteo daily archive at this pin, for the radar dates:\n" + "\n".join(lines)


def _prompt(manifest: dict, days: list[dict] | None = None) -> str:
    place = f"{manifest.get('name', 'this place')}, {manifest.get('region', '')}".strip().rstrip(",")
    story = manifest.get("story") or "how the radar picture changes over these months"
    return (
        f"These are public NISAR L2 radar browse pictures of {place}, in date order. "
        f"The story to look for is: {story} "
        "Green is vegetation. Gold and orange are sparse or hard ground. "
        "Blue is a weak return, such as smooth water or ice. "
        "Empty dark ground means the satellite did not image that spot. "
        f"{weather_note(days)} "
        "These weather figures come from the Open-Meteo archive, not from the radar. "
        "Say what stays the same and what changes across these months, in plain "
        "language. Use the listed rain, temperature, and soil-moisture figures when "
        "they are present. Do not invent other rainfall totals or soil-moisture "
        "numbers. This is not the NISAR soil-moisture product. Keep it under 150 words."
    )


def read_showcase(spot_id: str, weather: list[dict] | None = None) -> dict:
    if not spot_id.replace("-", "").isalnum():
        raise HTTPException(status_code=404, detail="No radar showcase is stored for that place.")
    manifest_path = _PUBLIC / "showcase" / spot_id / "manifest.json"
    if not manifest_path.is_file():
        raise HTTPException(status_code=404, detail="No radar showcase is stored for that place.")
    manifest = json.loads(manifest_path.read_text())
    frames = manifest.get("frames") or []
    if not frames:
        raise HTTPException(status_code=404, detail="No radar pictures are stored for that place.")
    if not _setting("ANTHROPIC_API_KEY"):
        return {
            "provider": "none",
            "answer": (
                "A Claude key is not set on the globe API, so these pictures were not sent. "
                "Add ANTHROPIC_API_KEY to read them."
            ),
            "error": None,
        }
    content: list[dict] = []
    for frame in frames:
        src = str(frame.get("src") or "")
        path = _PUBLIC / src.lstrip("/")
        if not path.is_file():
            raise HTTPException(status_code=404, detail="A stored radar picture is missing.")
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.standard_b64encode(path.read_bytes()).decode(),
                },
            }
        )
        content.append({"type": "text", "text": str(frame.get("label") or frame.get("date") or "")})
    content.append({"type": "text", "text": _prompt(manifest, weather)})
    model = _setting("ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL
    try:
        payload = _post_json(
            "https://api.anthropic.com/v1/messages",
            {
                "model": model,
                "max_tokens": 500,
                "messages": [{"role": "user", "content": content}],
            },
            headers={
                "content-type": "application/json",
                "x-api-key": _setting("ANTHROPIC_API_KEY") or "",
                "anthropic-version": "2023-06-01",
            },
        )
    except RuntimeError as exc:
        return {"provider": "claude", "answer": "", "error": str(exc)}
    parts = [
        block.get("text", "")
        for block in payload.get("content", [])
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    text = "\n".join(part.strip() for part in parts if part.strip()).strip()
    if not text:
        return {"provider": "claude", "answer": "", "error": "Claude returned an empty answer."}
    return {"provider": "claude", "answer": text, "error": None}
