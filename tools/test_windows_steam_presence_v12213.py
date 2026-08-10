#!/usr/bin/env python3
from pathlib import Path

root=Path(__file__).resolve().parents[1]
text=(root/"client-python-windows"/"switchnet_client.py").read_text()

for item in (
    "FILE_FLAG_OVERLAPPED",
    "def read_timeout",
    "def _steam_probe_controller_online",
    "_steam_presence_mark",
    "_steam_presence_is_active",
    "controller_online=_steam_probe_controller_online",
    "if not controller_online:",
    "controller online",
    "remove_after=2",
):
    assert item in text,item

start=text.index("def discover_supported_controllers_windows")
end=text.index("class SteamHidReader:",start)
discovery=text[start:end]

assert "if not controller_online" in discovery
assert "continue" in discovery
assert "logical_key" in discovery

print("OK: Steam receiver presence is distinct from controller presence")
