"""Write the bundled globe demo from the mock loaders."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from globe.api.serialize import locate, preset_catalog, risk_grid, scene_payload

OUT = ROOT / "globe" / "web" / "public" / "demo.json"


def main() -> None:
    catalog = preset_catalog()
    scenes = {}
    for group in catalog["groups"]:
        for site in group["sites"]:
            loaded = locate(site["lat"], site["lon"], "mock")
            payload = scene_payload(loaded, "mock", None)
            scenes[site["id"]] = {
                "scene": payload,
                "grids": {date: risk_grid(loaded, date) for date in payload["dates"]},
            }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"sites": catalog, "scenes": scenes}, separators=(",", ":")))
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes, {len(scenes)} sites)")


if __name__ == "__main__":
    main()
