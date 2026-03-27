#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SYSTEMD_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_DIR"

cp "$ROOT/scripts/systemd/fpl-backend.service" "$SYSTEMD_DIR/"
cp "$ROOT/scripts/systemd/fpl-frontend.service" "$SYSTEMD_DIR/"

systemctl --user daemon-reload
systemctl --user enable fpl-backend.service fpl-frontend.service

echo "Installed user services. Start with:"
echo "  systemctl --user start fpl-backend.service"
echo "  systemctl --user start fpl-frontend.service"
echo "Or both:"
echo "  systemctl --user start fpl-backend.service fpl-frontend.service"
