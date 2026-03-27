#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT/.run"
mkdir -p "$RUN_DIR"

STATE_FILE="$RUN_DIR/monitor_state.env"
LOG_FILE="$RUN_DIR/monitor.log"

BACKEND_HEALTH_URL="${BACKEND_HEALTH_URL:-http://127.0.0.1:8000/readyz}"
FRONTEND_HEALTH_URL="${FRONTEND_HEALTH_URL:-http://127.0.0.1:3000/readyz}"
FAIL_THRESHOLD="${FAIL_THRESHOLD:-3}"

backend_code="$(curl -sS -m 5 -o /dev/null -w "%{http_code}" "$BACKEND_HEALTH_URL" || echo 000)"
frontend_code="$(curl -sS -m 5 -o /dev/null -w "%{http_code}" "$FRONTEND_HEALTH_URL" || echo 000)"

ok=1
[[ "$backend_code" == "200" ]] || ok=0
[[ "$frontend_code" == "200" ]] || ok=0

consecutive_failures=0
if [[ -f "$STATE_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$STATE_FILE"
fi

if [[ "$ok" -eq 1 ]]; then
  consecutive_failures=0
  echo "$(date -Is) OK backend=$backend_code frontend=$frontend_code" >> "$LOG_FILE"
else
  consecutive_failures=$((consecutive_failures + 1))
  echo "$(date -Is) FAIL#$consecutive_failures backend=$backend_code frontend=$frontend_code" >> "$LOG_FILE"
fi

echo "consecutive_failures=$consecutive_failures" > "$STATE_FILE"

if [[ "$consecutive_failures" -ge "$FAIL_THRESHOLD" ]]; then
  echo "$(date -Is) restarting app stack after $consecutive_failures failures" >> "$LOG_FILE"
  "$ROOT/scripts/stop_app.sh" >> "$LOG_FILE" 2>&1 || true
  "$ROOT/scripts/start_app.sh" >> "$LOG_FILE" 2>&1 || true
  echo "consecutive_failures=0" > "$STATE_FILE"
fi
