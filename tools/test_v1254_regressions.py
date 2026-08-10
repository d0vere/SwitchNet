#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
client=(root/"client-python-windows"/"switchnet_client.py").read_text()
assert 'APP_VERSION = "1.25.4"' in client
assert 'text="Stick deadzones"' in client
assert 'text="Button layout"' not in client
assert "SwitchProReader" in client
assert "Switch2ProReader" in client
assert "SteamHidReader" in client
assert "DualSenseReader" in client
assert "StadiaReader" in client
assert '("gl","GL"),("gr","GR")' in client
bat=(root/"client-python-windows"/"build-exe.bat").read_text()
assert 'rmdir /s /q "%~dp0build"' in bat
assert 'rmdir /s /q "%~dp0dist"' in bat
assert 'del /f /q "%~dp0SwitchNetClient.spec"' in bat
print("OK: v1.25.3 deadzones and controller support retained")
