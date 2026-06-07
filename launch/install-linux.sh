#!/usr/bin/env bash
# Install MayBot as a clickable Linux app (a desktop icon you double-click).
#
#   launch/install-linux.sh            # install the app launcher
#   launch/install-linux.sh --autostart  # also start MayBot automatically on login
#
# Re-run any time the repo moves; it rewrites the launcher with the new path.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

EXEC="$HERE/maybot.sh"
ICON="$ROOT/maybot_control_center/static/assets/sect/hq.png"
APPS="$HOME/.local/share/applications"
DESKTOP="$APPS/MayBot.desktop"

chmod +x "$HERE/maybot.sh" "$HERE/stop.sh" 2>/dev/null || true
mkdir -p "$APPS"

# Render the template with this machine's absolute paths.
sed -e "s|__EXEC__|$EXEC|g" -e "s|__ICON__|$ICON|g" \
    "$HERE/MayBot.desktop.template" > "$DESKTOP"
chmod +x "$DESKTOP"

# Best-effort: mark trusted / refresh the menu so it shows up immediately.
command -v gio >/dev/null 2>&1 && gio set "$DESKTOP" "metadata::trusted" true 2>/dev/null || true
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" 2>/dev/null || true

echo "Installed: \"MayBot Control Center\" (search your apps menu)."
echo "  launcher: $DESKTOP"

if [ "${1:-}" = "--autostart" ]; then
  mkdir -p "$HOME/.config/autostart"
  cp "$DESKTOP" "$HOME/.config/autostart/MayBot.desktop"
  echo "Autostart enabled: MayBot will start on login."
fi

echo "Done. Double-click MayBot to launch the dashboard."
