#!/usr/bin/env bash
set -euo pipefail

name="${1:-}"
ts="$(date +%Y%m%d-%H%M%S)"

slugify() {
  tr '[:upper:]' '[:lower:]' <<<"$1" | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g'
}

if [[ -n "$name" ]]; then
  slug="$(slugify "$name")"
  branch="pr/${ts}-${slug}"
else
  branch="pr/${ts}"
fi

current="$(git rev-parse --abbrev-ref HEAD)"

if [[ "$current" != "main" && "$current" != "master" ]]; then
  echo "Currently on '$current'. Creating branch from current HEAD."
fi

git switch -c "$branch"
echo "✅ Created and switched to: $branch"
