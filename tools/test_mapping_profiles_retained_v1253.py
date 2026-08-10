#!/usr/bin/env python3
from pathlib import Path

root=Path(__file__).resolve().parents[1]
client=(root/"client-python-windows"/"switchnet_client.py").read_text()
for cid in ("dualsense","stadia","switchpro","switch2pro","xinput"):
    assert f'"{cid}": {{' in client

assert 'CONTROLLER_PROFILE_SLOTS = ("Default", "Custom 1", "Custom 2", "Custom 3")' in client
assert "open_controller_mapping_editor" in client
assert '("gl","GL"),("gr","GR")' in client
assert 'face=positional_face' in client
assert 'face = {"a": "B", "b": "A", "x": "Y", "y": "X"}' in client

bat=(root/"client-python-windows"/"build-exe.bat").read_text()
assert 'rmdir /s /q "%~dp0build"' in bat
assert 'rmdir /s /q "%~dp0dist"' in bat
assert 'del /f /q "%~dp0SwitchNetClient.spec"' in bat
print("OK: v1.25.2 universal mapping profiles retained")
