#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p .run

SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# Stop existing app processes on target ports
P8000="$(ss -ltnp 2>/dev/null | awk '/127.0.0.1:8000/ {print $NF}' | sed -E 's/.*pid=([0-9]+).*/\1/' | head -n1 || true)"
P3000="$(ss -ltnp 2>/dev/null | awk '/127.0.0.1:3000/ {print $NF}' | sed -E 's/.*pid=([0-9]+).*/\1/' | head -n1 || true)"
[[ -n "$P8000" ]] && kill -9 "$P8000" || true
[[ -n "$P3000" ]] && kill -9 "$P3000" || true
sleep 1

# Start backend
nohup bash -lc 'cd backend && source .venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8000' > .run/backend-8000.log 2>&1 &
B_PID=$!
echo "$B_PID" > .run/backend-8000.pid

for i in {1..50}; do
  if curl -sSf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    break
  fi
  sleep 0.4
done

# Build/start frontend pinned to backend 8000
cd frontend
BACKEND_ORIGIN=http://127.0.0.1:8000 npm run build >/tmp/fpl_front_sync.log 2>&1
cd "$ROOT"
nohup bash -lc 'cd frontend && BACKEND_ORIGIN=http://127.0.0.1:8000 npm run start -- --hostname 127.0.0.1 --port 3000' > .run/frontend-3000.log 2>&1 &
F_PID=$!
echo "$F_PID" > .run/frontend-3000.pid

for i in {1..80}; do
  if curl -sSf http://127.0.0.1:3000 >/dev/null 2>&1; then
    break
  fi
  sleep 0.4
done

# Verify key endpoints
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
  "backendPid": ${B_PID},
  "frontendPid": ${F_PID},
  "checks": {
    "root": ${ROOT_CODE},
    "weeklyBriefApi": ${BRIEF_CODE}
  }
}
JSON

echo "✅ Runtime aligned to commit ${SHA}"
echo "   root=${ROOT_CODE}, weeklyBriefApi=${BRIEF_CODE}"
echo "   details: .run/runtime-alignment.json"
