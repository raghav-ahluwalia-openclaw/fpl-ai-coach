#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT/.run"
BACKEND_PID="$RUN_DIR/backend.pid"
FRONTEND_PID="$RUN_DIR/frontend.pid"

stop_pid() {
  local pid_file="$1"
  local name="$2"
  if [[ ! -f "$pid_file" ]]; then
    echo "$name not running (no pid file)"
    return
  fi
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "Stopping $name ($pid)..."
    kill "$pid" || true
  else
    echo "$name not running"
  fi
  rm -f "$pid_file"
}

stop_pid "$BACKEND_PID" "backend"
stop_pid "$FRONTEND_PID" "frontend"
