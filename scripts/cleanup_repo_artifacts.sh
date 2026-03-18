#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Cleaning local runtime/build artifacts from repo scope..."

# Safe local deletes (re-creatable artifacts only)
rm -rf \
  backend/.venv \
  backend/app/__pycache__ \
  frontend/.next \
  frontend/node_modules

# Optional: keep local sqlite file unless user explicitly wants deletion.
if [[ "${1:-}" == "--delete-db" ]]; then
  rm -f backend/fpl.db
  echo "Deleted backend/fpl.db"
fi

echo "Done. Reinstall deps when needed:"
echo "  cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
echo "  cd frontend && npm ci"
