#!/usr/bin/env bash
# Rimuove DuckNet + Stagno dall'utente corrente. Le impostazioni (~/.config/quezka/stagno.conf) restano.
set -euo pipefail
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
rm -rf "$DATA/stagno"
rm -f "$HOME/.local/bin/stagno" "$HOME/.local/bin/ducknet" \
      "$DATA/applications/io.github.quezka.Stagno.desktop" \
      "$DATA/icons/hicolor/scalable/apps/io.github.quezka.Stagno.svg"
command -v update-desktop-database >/dev/null && update-desktop-database "$DATA/applications" 2>/dev/null || true
echo "✓ Stagno rimosso."
