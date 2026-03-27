#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT/.run"
BACKEND_PID="$RUN_DIR/backend.pid"
FRONTEND_PID="$RUN_DIR/frontend.pid"

show_status() {
  local pid_file="$1"
  local name="$2"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "$name: running (pid $pid)"
      return
    fi
  fi
  echo "$name: not running"
}

show_status "$BACKEND_PID" "backend"
show_status "$FRONTEND_PID" "frontend"

curl -sS -o /dev/null -w "backend /livez: %{http_code}\n" http://127.0.0.1:8000/livez || true
curl -sS -o /dev/null -w "backend /readyz: %{http_code}\n" http://127.0.0.1:8000/readyz || true
curl -sS -o /dev/null -w "frontend /readyz: %{http_code}\n" http://127.0.0.1:3000/readyz || true
