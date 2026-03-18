#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"

echo "▶ Frontend lint"
npm run lint

echo "▶ Frontend build"
npm run build

echo "✅ Frontend validation passed"
