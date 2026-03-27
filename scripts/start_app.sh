#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
RUN_DIR="$ROOT/.run"
mkdir -p "$RUN_DIR"

BACKEND_PID="$RUN_DIR/backend.pid"
FRONTEND_PID="$RUN_DIR/frontend.pid"
BACKEND_LOG="$RUN_DIR/backend.log"
FRONTEND_LOG="$RUN_DIR/frontend.log"

is_running() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] || return 1
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

if is_running "$BACKEND_PID"; then
  echo "Backend already running (pid $(cat "$BACKEND_PID"))"
else
  echo "Starting backend..."
  (
    cd "$BACKEND_DIR"
    source .venv/bin/activate
    nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 --timeout-keep-alive 30 >"$BACKEND_LOG" 2>&1 &
    echo $! > "$BACKEND_PID"
  )
fi

if is_running "$FRONTEND_PID"; then
  echo "Frontend already running (pid $(cat "$FRONTEND_PID"))"
else
  echo "Starting frontend..."
  (
    cd "$FRONTEND_DIR"
    nohup npm run dev >"$FRONTEND_LOG" 2>&1 &
    echo $! > "$FRONTEND_PID"
  )
fi

echo "Done."
echo "Backend log:  $BACKEND_LOG"
echo "Frontend log: $FRONTEND_LOG"
echo "Health check:"
curl -sS -o /dev/null -w "Backend livez %{http_code}\n" http://127.0.0.1:8000/livez || true
curl -sS -o /dev/null -w "Backend readyz %{http_code}\n" http://127.0.0.1:8000/readyz || true
curl -sS -o /dev/null -w "Frontend readyz %{http_code}\n" http://127.0.0.1:3000/readyz || true
