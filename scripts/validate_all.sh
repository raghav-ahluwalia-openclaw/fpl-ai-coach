#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "▶ Backend + Frontend validation (parallel)"
"$ROOT/scripts/validate_backend.py" &
PID_BACKEND=$!
"$ROOT/scripts/validate_frontend.sh" &
PID_FRONTEND=$!

wait "$PID_BACKEND"
wait "$PID_FRONTEND"

echo "▶ Integration validation"
"$ROOT/scripts/validate_integration.py"

# Integration validation builds frontend with an ephemeral backend port.
# Restore local runtime build so `npm run start` always targets the default backend.
if [[ "${SKIP_POST_VALIDATE_RESTORE:-0}" != "1" ]]; then
  DEFAULT_BACKEND_ORIGIN="${DEFAULT_BACKEND_ORIGIN:-http://127.0.0.1:8000}"
  echo "▶ Restoring frontend build for local runtime (BACKEND_ORIGIN=${DEFAULT_BACKEND_ORIGIN})"
  (
    cd "$ROOT/frontend"
    BACKEND_ORIGIN="$DEFAULT_BACKEND_ORIGIN" npm run build
  )
fi

echo "✅ All validations passed"
