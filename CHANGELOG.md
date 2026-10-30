# Changelog

## [1.0.0] - 2026-10-30
### Added
- GTK3 shutdown timer with presets (30/60/90/120 min) and custom minutes.
- Mouse controls: wheel, Shift+wheel (x5), left-button drag up/down.
- Confirm/Cancel, live countdown and "Shutdown at HH:MM".
- Draggable always-on-top overlay timer with configurable colour and size (saved).
- Desktop notification 1 minute before shutdown.
- Shutdown via `systemctl poweroff` (logind, no sudo).
- Confirmation dialog when closing during a countdown.
- `install.sh` / `uninstall.sh` with start-menu entry and icon.
