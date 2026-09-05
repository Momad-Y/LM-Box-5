#!/usr/bin/env bash
# Give the Linux build an icon and a launcher entry.
#
#     ./scripts/install_linux_desktop.sh [path-to-executable]
#
# Windows embeds its icon in the .exe and macOS keeps one inside the .app,
# but a Linux ELF cannot carry an icon at all - PyInstaller says so when
# building ("Ignoring icon; supported only on Windows and macOS"). On Linux
# the icon lives in the icon theme and a .desktop entry points at it, which
# is what this installs, per-user, with no root needed.
#
# Uninstall by deleting the three files it reports.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ICON_SOURCE="$REPO_ROOT/gui/resources/images/5-lmbox-icon.png"

EXECUTABLE="${1:-}"
if [[ -z "$EXECUTABLE" ]]; then
    EXECUTABLE="$(ls -1 "$REPO_ROOT"/bin/LMBox5-*-linux-* 2>/dev/null | head -1 || true)"
fi
if [[ -z "$EXECUTABLE" || ! -f "$EXECUTABLE" ]]; then
    echo "No Linux executable found. Build one first:" >&2
    echo "    python scripts/build_executable.py" >&2
    echo "or pass its path: $0 /path/to/LMBox5-v1.0.0-linux-x86_64" >&2
    exit 1
fi
EXECUTABLE="$(cd "$(dirname "$EXECUTABLE")" && pwd)/$(basename "$EXECUTABLE")"

APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
mkdir -p "$APPS_DIR" "$ICON_DIR"

# Square it off the same way the .ico/.icns are squared: the source art is
# 6:5, and an icon theme expects a square file for a 256x256 directory.
if python3 - "$ICON_SOURCE" "$ICON_DIR/lmbox5.png" <<'PY' 2>/dev/null
import sys
from PIL import Image

source, target = sys.argv[1], sys.argv[2]
image = Image.open(source).convert("RGBA")
side = max(image.size)
canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
canvas.resize((256, 256), Image.LANCZOS).save(target)
PY
then
    echo "icon:    $ICON_DIR/lmbox5.png"
else
    cp "$ICON_SOURCE" "$ICON_DIR/lmbox5.png"
    echo "icon:    $ICON_DIR/lmbox5.png (unpadded - install Pillow for a square one)"
fi

sed -e "s|^Exec=.*|Exec=$EXECUTABLE|" \
    -e "s|^Icon=.*|Icon=$ICON_DIR/lmbox5.png|" \
    "$REPO_ROOT/packaging/lmbox5.desktop" > "$APPS_DIR/lmbox5.desktop"
chmod +x "$APPS_DIR/lmbox5.desktop"
echo "entry:   $APPS_DIR/lmbox5.desktop"
echo "runs:    $EXECUTABLE"

command -v update-desktop-database >/dev/null && update-desktop-database "$APPS_DIR" 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null &&
    gtk-update-icon-cache -f -t "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" 2>/dev/null || true

echo
echo "Installed. 'LM Box 5' should now appear in your application launcher."
