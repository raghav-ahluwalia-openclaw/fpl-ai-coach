#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MONITOR_SCRIPT="$ROOT/scripts/monitor_stack.sh"

if [[ ! -x "$MONITOR_SCRIPT" ]]; then
  echo "Monitor script not executable: $MONITOR_SCRIPT"
  exit 1
fi

CRON_LINE="* * * * * $MONITOR_SCRIPT >/dev/null 2>&1"

TMP_CRON="$(mktemp)"
(crontab -l 2>/dev/null || true) | grep -v "monitor_stack.sh" > "$TMP_CRON"
echo "$CRON_LINE" >> "$TMP_CRON"
crontab "$TMP_CRON"
rm -f "$TMP_CRON"

echo "Installed cron watchdog: $CRON_LINE"
