#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8080}"
exec python3 -m http.server "$PORT" --bind 0.0.0.0 --directory globe/web/dist
