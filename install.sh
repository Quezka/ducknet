#!/usr/bin/env bash
# Installa DuckNet + Stagno solo per l'utente corrente: niente root, niente sudo.
#   ./install.sh            installa o aggiorna
#   ./uninstall.sh          rimuove tutto
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN="$HOME/.local/bin"
VENV="$DATA/stagno/venv"
APPS="$DATA/applications"
ICONS="$DATA/icons/hicolor/scalable/apps"

command -v python3 >/dev/null || { echo "Serve python3 (3.10 o più recente)." >&2; exit 1; }
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { echo "Serve Python 3.10 o più recente." >&2; exit 1; }

echo "→ Creo l'ambiente in $VENV"
python3 -m venv "$VENV" || {
  echo "Non riesco a creare un ambiente virtuale. Su Debian/Ubuntu serve: sudo apt install python3-venv" >&2
  exit 1
}
"$VENV/bin/python" -m pip install --quiet --upgrade pip
echo "→ Installo DuckNet e Stagno (scarica PySide6, circa 250 MB la prima volta)"
"$VENV/bin/python" -m pip install --quiet --upgrade "$HERE[browser]"

mkdir -p "$BIN" "$APPS" "$ICONS"
ln -sf "$VENV/bin/stagno" "$BIN/stagno"
ln -sf "$VENV/bin/ducknet" "$BIN/ducknet"
install -m 644 "$HERE/packaging/io.github.quezka.Stagno.svg" "$ICONS/io.github.quezka.Stagno.svg"
sed "s|^Exec=stagno|Exec=$VENV/bin/stagno|" "$HERE/packaging/io.github.quezka.Stagno.desktop" \
  > "$APPS/io.github.quezka.Stagno.desktop"
chmod 644 "$APPS/io.github.quezka.Stagno.desktop"

command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t "$DATA/icons/hicolor" 2>/dev/null || true
command -v xdg-mime >/dev/null && xdg-mime default io.github.quezka.Stagno.desktop x-scheme-handler/duck 2>/dev/null || true

echo "✓ Fatto. Apri «Stagno» dal menu delle applicazioni, oppure da terminale: stagno"
case ":$PATH:" in *":$BIN:"*) ;; *) echo "  (aggiungi $BIN al PATH per usare i comandi stagno e ducknet da terminale)";; esac
