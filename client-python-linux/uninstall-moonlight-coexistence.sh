#!/usr/bin/env bash
set -euo pipefail
APPID="com.moonlight_stream.Moonlight"
LOCAL_APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"

if command -v flatpak >/dev/null 2>&1 && flatpak info "$APPID" >/dev/null 2>&1; then
  flatpak override --user --unset-env=SDL_GAMECONTROLLER_IGNORE_DEVICES \
    --unset-env=SDL_HIDAPI_IGNORE_DEVICES "$APPID" || true
fi

rm -f "$LOCAL_APPS/com.moonlight_stream.Moonlight.desktop" \
      "$LOCAL_APPS/moonlight.desktop" \
      "${XDG_BIN_HOME:-$HOME/.local/bin}/moonlight-switchnet"

echo "SwitchNet Moonlight coexistence overrides removed."
