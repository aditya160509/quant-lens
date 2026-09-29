#!/bin/bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

BASE_DIR="/Users/adityabalaji/Downloads/quant  2"
BACKEND_DIR="$BASE_DIR/backend"
FRONTEND_DIR="$BASE_DIR/frontend"
PYTHON_BIN="$BACKEND_DIR/venv/bin/python"
UVICORN_BIN="$BACKEND_DIR/venv/bin/uvicorn"
NPM_BIN="$(command -v npm || true)"

if [ -z "$NPM_BIN" ]; then
  echo "ERROR: npm not found in PATH"
  exit 1
fi

if [ ! -x "$PYTHON_BIN" ] || [ ! -x "$UVICORN_BIN" ]; then
  echo "ERROR: backend venv missing. Expected: $BACKEND_DIR/venv"
  echo "Create it with: python3 -m venv backend/venv && backend/venv/bin/pip install -r backend/requirements.txt"
  exit 1
fi

echo "Cleaning up ports 3000 and 8000..."
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
sleep 1

echo "Starting backend (uvicorn on 127.0.0.1:8000)..."
cd "$BACKEND_DIR"
nohup "$UVICORN_BIN" main:app --host 127.0.0.1 --port 8000 > "$BASE_DIR/backend.log" 2>&1 < /dev/null &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$BASE_DIR/.backend.pid"
disown "$BACKEND_PID" 2>/dev/null || true

echo "Starting frontend (Next.js on 127.0.0.1:3000)..."
cd "$FRONTEND_DIR"
if [ ! -d "node_modules" ]; then
  "$NPM_BIN" install --legacy-peer-deps --silent
fi
nohup "$NPM_BIN" run dev -- --hostname 127.0.0.1 --port 3000 > "$BASE_DIR/frontend.log" 2>&1 < /dev/null &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$BASE_DIR/.frontend.pid"
disown "$FRONTEND_PID" 2>/dev/null || true

echo "Waiting for services to bind..."
for _ in $(seq 1 30); do
  FRONT_OK=0
  BACK_OK=0
  if lsof -nP -iTCP:3000 -sTCP:LISTEN >/dev/null 2>&1; then FRONT_OK=1; fi
  if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then BACK_OK=1; fi
  if [ "$FRONT_OK" -eq 1 ] && [ "$BACK_OK" -eq 1 ]; then
    break
  fi
  sleep 1
done

echo "----------------------------------------"
echo "Backend PID:  $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo "Frontend URL: http://127.0.0.1:3000"
echo "Backend URL:  http://127.0.0.1:8000"
echo "Logs: $BASE_DIR/backend.log, $BASE_DIR/frontend.log"
echo "----------------------------------------"

echo "Port check -> frontend:$FRONT_OK backend:$BACK_OK"
if [ "$FRONT_OK" -ne 1 ]; then
  echo "Frontend failed to bind. Tail frontend.log:"
  tail -n 80 "$BASE_DIR/frontend.log" || true
fi
if [ "$BACK_OK" -ne 1 ]; then
  echo "Backend failed to bind. Tail backend.log:"
  tail -n 120 "$BASE_DIR/backend.log" || true
fi

if [ "$FRONT_OK" -ne 1 ] || [ "$BACK_OK" -ne 1 ]; then
  exit 1
fi
