"""Read a stored NISAR showcase with Claude, when a key is set."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from fastapi import HTTPException

from drought_monitor.assistant import DEFAULT_ANTHROPIC_MODEL, _post_json, _setting

_PUBLIC = Path(__file__).resolve().parents[2] / "globe" / "web" / "public"


def _prompt(manifest: dict) -> str:
    place = f"{manifest.get('name', 'this place')}, {manifest.get('region', '')}".strip().rstrip(",")
    story = manifest.get("story") or "how the radar picture changes over these months"
    return (
        f"These are public NISAR L2 radar browse pictures of {place}, in date order. "
        f"The story to look for is: {story} "
        "Green is vegetation. Gold and orange are sparse or hard ground. "
        "Blue is a weak return, such as smooth water or ice. "
        "Empty dark ground means the satellite did not image that spot. "
        "Say what stays the same and what changes across these months, in plain "
        "language. Do not invent fires, floods, rainfall totals, or soil-moisture "
        "numbers. This is not the NISAR soil-moisture product. Keep it under 150 words."
    )


def read_showcase(spot_id: str) -> dict:
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
    content.append({"type": "text", "text": _prompt(manifest)})
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
