#!/bin/bash
# Starts backend and frontend; Ctrl-C stops both.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
trap 'kill 0' EXIT
(cd "$ROOT/backend" && OMP_NUM_THREADS=1 .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000) &
(cd "$ROOT/frontend" && npm run dev -- --hostname 127.0.0.1 --port 3000) &
wait
