#!/usr/bin/env bash
set -euo pipefail

SECRETS_FILE="${SECRETS_FILE:-$HOME/.openclaw/secrets.json}"
SECRET_KEY="${SECRET_KEY:-/infra/cloudflared/fplLabTunnelToken}"
LOG_FILE="${LOG_FILE:-/tmp/fpl-cloudflared-named.log}"

if [[ ! -f "$SECRETS_FILE" ]]; then
  echo "❌ secrets file not found: $SECRETS_FILE" >&2
  exit 1
fi

TOKEN="$(python3 - <<'PY'
import json, os, sys
path=os.environ.get('SECRETS_FILE')
key=os.environ.get('SECRET_KEY')
with open(path) as f:
    d=json.load(f)
# try slash path first
v=d.get(key)
if isinstance(v,str) and v.strip():
    print(v.strip())
    raise SystemExit(0)
# fallback nested
v=d
for p in ['infra','cloudflared','fplLabTunnelToken']:
    if not isinstance(v,dict):
        v=None
        break
    v=v.get(p)
if isinstance(v,str) and v.strip():
    print(v.strip())
    raise SystemExit(0)
print('', end='')
PY
)"

if [[ -z "$TOKEN" ]]; then
  echo "❌ tunnel token missing in secrets" >&2
  exit 1
fi

# stop existing tunnel connector(s)
pkill -f "cloudflared tunnel run --token" || true
sleep 1

# start connector in background
nohup /home/openclawuser/.local/bin/cloudflared tunnel run --token "$TOKEN" > "$LOG_FILE" 2>&1 &
sleep 3

# quick verification
if ps -ef | grep -F "/home/openclawuser/.local/bin/cloudflared tunnel run --token" | grep -v grep >/dev/null; then
  echo "✅ tunnel restarted"
  echo "log: $LOG_FILE"
  curl -I -sS https://fpl-lab.aihackworks.com | head -n 1 || true
else
  echo "❌ failed to restart tunnel" >&2
  tail -n 40 "$LOG_FILE" || true
  exit 1
fi
