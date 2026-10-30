#!/usr/bin/env bash
# Shutdown Timer uninstaller. Use --purge to also remove settings.
set -euo pipefail
rm -rf "$HOME/.local/share/shutdown-timer"
rm -f "$HOME/.local/share/icons/hicolor/256x256/apps/shutdown-timer.png" \
      "$HOME/.local/share/applications/shutdown-timer.desktop"
if [ -L "$HOME/.local/bin/shutdown-timer" ]; then rm -f "$HOME/.local/bin/shutdown-timer"; fi
if [ "${1:-}" = "--purge" ]; then rm -rf "$HOME/.config/shutdown-timer"; echo "Settings removed."; else echo "Settings kept in ~/.config/shutdown-timer (use --purge to remove)."; fi
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
echo "Shutdown Timer uninstalled."
