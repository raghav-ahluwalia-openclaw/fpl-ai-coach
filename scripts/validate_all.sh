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

echo "✅ All validations passed"
