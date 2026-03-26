#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p .run

SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

BACKEND_PID_FILE=".run/backend.pid"
FRONTEND_PID_FILE=".run/frontend.pid"
BACKEND_LOG=".run/backend.log"
FRONTEND_LOG=".run/frontend.log"

NEW_BACKEND_PID=""
NEW_FRONTEND_PID=""

is_running() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] || return 1
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

wait_http_ok() {
  local url="$1"
  local tries="${2:-60}"
  local sleep_s="${3:-0.5}"
  for _ in $(seq 1 "$tries"); do
    if curl -sSf "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$sleep_s"
  done
  return 1
}

pid_on_port() {
  local port="$1"
  ss -ltnp 2>/dev/null | awk -v p=":${port}" '$4 ~ p {print $NF}' | sed -E 's/.*pid=([0-9]+).*/\1/' | head -n1 || true
}

terminate_pid_graceful() {
  local pid="$1"
  local name="$2"
  [[ -n "$pid" ]] || return 0
  if ! kill -0 "$pid" 2>/dev/null; then
    return 0
  fi

  echo "Stopping $name gracefully (pid $pid)..."
  kill "$pid" 2>/dev/null || true

  for _ in $(seq 1 40); do
    if ! kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    sleep 0.25
  done

  echo "Force killing $name (pid $pid) after grace timeout..."
  kill -9 "$pid" 2>/dev/null || true
}

stop_graceful() {
  local pid_file="$1"
  local name="$2"
  local port="$3"

  local file_pid=""
  if [[ -f "$pid_file" ]]; then
    file_pid="$(cat "$pid_file" 2>/dev/null || true)"
  fi

  terminate_pid_graceful "$file_pid" "$name"

  # Also stop any listener on target port (handles stale pid-file cases).
  local port_pid
  port_pid="$(pid_on_port "$port")"
  if [[ -n "$port_pid" && "$port_pid" != "$file_pid" ]]; then
    terminate_pid_graceful "$port_pid" "$name"
  fi

  rm -f "$pid_file"
}

start_backend_prod() {
  nohup bash -lc 'cd backend && source .venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8000' >"$BACKEND_LOG" 2>&1 &
  NEW_BACKEND_PID="$!"
  echo "$NEW_BACKEND_PID" > "$BACKEND_PID_FILE"
}

start_frontend_prod() {
  nohup bash -lc 'cd frontend && BACKEND_ORIGIN=http://127.0.0.1:8000 npm run start -- --hostname 127.0.0.1 --port 3000' >"$FRONTEND_LOG" 2>&1 &
  NEW_FRONTEND_PID="$!"
  echo "$NEW_FRONTEND_PID" > "$FRONTEND_PID_FILE"
}

rollback_to_safe_runtime() {
  echo "⚠️ Runtime sync failed. Rolling back to safe runtime..."

  [[ -n "$NEW_FRONTEND_PID" ]] && kill "$NEW_FRONTEND_PID" 2>/dev/null || true
  [[ -n "$NEW_BACKEND_PID" ]] && kill "$NEW_BACKEND_PID" 2>/dev/null || true
  rm -f "$FRONTEND_PID_FILE" "$BACKEND_PID_FILE"

  # Fallback to the standard dev runtime starter used by local ops.
  ./scripts/start_app.sh >/tmp/fpl-runtime-rollback.log 2>&1 || true

  if wait_http_ok "http://127.0.0.1:8000/health" 40 0.5 && wait_http_ok "http://127.0.0.1:3000" 50 0.5; then
    echo "✅ Rollback successful (app reachable)."
    return 0
  fi

  echo "❌ Rollback could not recover app automatically."
  return 1
}

# 1) Build frontend first while old runtime is still live (minimize downtime).
echo "Building frontend artifacts before restart..."
(
  cd frontend
  BACKEND_ORIGIN=http://127.0.0.1:8000 npm run build >/tmp/fpl_front_sync.log 2>&1
)

# 2) Restart backend + frontend gracefully.
stop_graceful "$FRONTEND_PID_FILE" "frontend" 3000
stop_graceful "$BACKEND_PID_FILE" "backend" 8000

start_backend_prod
sleep 0.5
if ! kill -0 "$NEW_BACKEND_PID" 2>/dev/null || ! wait_http_ok "http://127.0.0.1:8000/health" 60 0.5; then
  rollback_to_safe_runtime
  exit 1
fi

start_frontend_prod
sleep 0.5
if ! kill -0 "$NEW_FRONTEND_PID" 2>/dev/null || ! wait_http_ok "http://127.0.0.1:3000" 80 0.5; then
  rollback_to_safe_runtime
  exit 1
fi

# 3) Verify key endpoints and record runtime alignment.
ROOT_CODE="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/)"
BRIEF_CODE="$(curl -s -o /dev/null -w '%{http_code}' 'http://127.0.0.1:3000/api/fpl/weekly-brief?mode=balanced&model_version=xgb_hist_v1')"

BUILD_ID=""
if [[ -f frontend/.next/BUILD_ID ]]; then
  BUILD_ID="$(cat frontend/.next/BUILD_ID)"
fi

cat > .run/runtime-alignment.json <<JSON
{
  "timestampUtc": "${TS}",
  "gitSha": "${SHA}",
  "frontendBuildId": "${BUILD_ID}",
  "backendPid": ${NEW_BACKEND_PID},
  "frontendPid": ${NEW_FRONTEND_PID},
  "checks": {
    "root": ${ROOT_CODE},
    "weeklyBriefApi": ${BRIEF_CODE}
  }
}
JSON

echo "✅ Runtime aligned to commit ${SHA}"
echo "   root=${ROOT_CODE}, weeklyBriefApi=${BRIEF_CODE}"
echo "   details: .run/runtime-alignment.json"
