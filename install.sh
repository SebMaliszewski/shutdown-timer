#!/usr/bin/env bash
# Shutdown Timer installer (per-user, no sudo required)
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/share/shutdown-timer"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
DESK_DIR="$HOME/.local/share/applications"
BIN_DIR="$HOME/.local/bin"

echo "==> Checking dependencies"
if ! command -v python3 >/dev/null 2>&1 || \
   ! python3 -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk" >/dev/null 2>&1; then
  echo "ERROR: python3 with PyGObject (GTK 3) is required." >&2
  echo "Install it with:  sudo apt install python3-gi gir1.2-gtk-3.0 libnotify-bin" >&2
  exit 1
fi
command -v notify-send >/dev/null 2>&1 || echo "WARN: notify-send not found (1-minute warning disabled). Install libnotify-bin."

echo "==> Installing app to $APP_DIR"
mkdir -p "$APP_DIR/assets" "$ICON_DIR" "$DESK_DIR" "$BIN_DIR"
if [ "$(realpath "$SRC")" != "$(realpath "$APP_DIR")" ]; then
  install -m 755 "$SRC/shutdown_timer.py" "$APP_DIR/shutdown_timer.py"
  install -m 644 "$SRC/assets/girl.png" "$SRC/assets/icon.png" "$APP_DIR/assets/"
fi
chmod +x "$APP_DIR/shutdown_timer.py"

echo "==> Installing icon"
install -m 644 "$SRC/assets/icon.png" "$ICON_DIR/shutdown-timer.png"

echo "==> Creating start-menu entry"
sed "s|@APP_PATH@|$APP_DIR/shutdown_timer.py|g" "$SRC/shutdown-timer.desktop" > "$DESK_DIR/shutdown-timer.desktop"
chmod 644 "$DESK_DIR/shutdown-timer.desktop"

echo "==> Creating command wrapper $BIN_DIR/shutdown-timer"
ln -sf "$APP_DIR/shutdown_timer.py" "$BIN_DIR/shutdown-timer"

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$DESK_DIR" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true

CAN="$(busctl call org.freedesktop.login1 /org/freedesktop/login1 org.freedesktop.login1.Manager CanPowerOff 2>/dev/null | awk '{print $2}' | tr -d '"' || true)"
if [ "$CAN" != "yes" ]; then
  echo "WARN: logind CanPowerOff = '${CAN:-unknown}'. 'systemctl poweroff' may require authentication on this system."
fi

echo "Done. Launch 'Shutdown Timer' from your application menu or run: shutdown-timer"
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) echo "Note: $BIN_DIR is not in PATH.";; esac
