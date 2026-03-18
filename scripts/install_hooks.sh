#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "❌ This folder is not a git repository: $ROOT"
  echo "Run: git init"
  echo "Then rerun: ./scripts/install_hooks.sh"
  exit 1
fi

chmod +x .githooks/pre-commit .githooks/post-commit

git config core.hooksPath .githooks

echo "✅ Git hooks installed"
echo "   hooksPath: $(git config core.hooksPath)"
echo "   pre-commit: .githooks/pre-commit"
echo "   post-commit: .githooks/post-commit (auto runtime sync)"
