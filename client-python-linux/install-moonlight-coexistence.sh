#!/usr/bin/env bash
set -euo pipefail

PAIR="0x057e/0x2069"
APPID="com.moonlight_stream.Moonlight"
LOCAL_APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$LOCAL_APPS"

echo "SwitchNet: configuring Moonlight to ignore only Nintendo 057e:2069"
echo "This does not disable video streaming and does not disable other gamepads."

did_any=0

# Flatpak: the cleanest path because the override follows launches from the GUI.
if command -v flatpak >/dev/null 2>&1 && flatpak info "$APPID" >/dev/null 2>&1; then
  flatpak override --user \
    --env=SDL_GAMECONTROLLER_IGNORE_DEVICES="$PAIR" \
    --env=SDL_HIDAPI_IGNORE_DEVICES="$PAIR" \
    "$APPID"
  echo "Configured Flatpak Moonlight override."
  did_any=1
fi

# Native/package launcher: create a user-level .desktop override with env vars.
candidates=(
  "/usr/share/applications/com.moonlight_stream.Moonlight.desktop"
  "/usr/local/share/applications/com.moonlight_stream.Moonlight.desktop"
  "/usr/share/applications/moonlight.desktop"
  "/usr/local/share/applications/moonlight.desktop"
)

for src in "${candidates[@]}"; do
  [[ -f "$src" ]] || continue
  name="$(basename "$src")"
  dst="$LOCAL_APPS/$name"
  awk -v pair="$PAIR" '
    /^Exec=/ && $0 !~ /SDL_GAMECONTROLLER_IGNORE_DEVICES=/ {
      sub(/^Exec=/,
          "Exec=/usr/bin/env SDL_GAMECONTROLLER_IGNORE_DEVICES=" pair " SDL_HIDAPI_IGNORE_DEVICES=" pair " ")
    }
    { print }
  ' "$src" > "$dst"
  chmod 0644 "$dst"
  echo "Installed user desktop override: $dst"
  did_any=1
done

# Always provide a wrapper for terminal/manual launch.
wrapper="${XDG_BIN_HOME:-$HOME/.local/bin}/moonlight-switchnet"
mkdir -p "$(dirname "$wrapper")"
cat > "$wrapper" <<'EOF'
#!/usr/bin/env bash
set -e
export SDL_GAMECONTROLLER_IGNORE_DEVICES="0x057e/0x2069"
export SDL_HIDAPI_IGNORE_DEVICES="0x057e/0x2069"

if command -v flatpak >/dev/null 2>&1 && flatpak info com.moonlight_stream.Moonlight >/dev/null 2>&1; then
  exec flatpak run com.moonlight_stream.Moonlight "$@"
elif command -v moonlight >/dev/null 2>&1; then
  exec moonlight "$@"
elif command -v moonlight-qt >/dev/null 2>&1; then
  exec moonlight-qt "$@"
else
  echo "Moonlight executable not found." >&2
  exit 127
fi
EOF
chmod +x "$wrapper"
echo "Installed wrapper: $wrapper"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$LOCAL_APPS" >/dev/null 2>&1 || true
fi

echo
echo "Done."
echo "IMPORTANT: fully exit the currently running Moonlight process once, then reopen it."
echo "After that, Moonlight may remain open while SwitchNet initializes the controller."
if [[ "$did_any" -eq 0 ]]; then
  echo "No known Moonlight desktop/Flatpak install was detected; launch it with:"
  echo "  $wrapper"
fi
