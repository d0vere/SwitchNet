#!/usr/bin/env python3
from pathlib import Path

root=Path(__file__).resolve().parents[1]
client=(root/"client-python-windows"/"switchnet_client.py").read_text()
backend=(root/"client-python-windows"/"switch_pro_windows.py").read_text()
bat=(root/"client-python-windows"/"build-exe.bat").read_text()

assert "SwitchProReader" in client
assert '"switchpro:057e:2009"' in client
assert '"switchpro_hid"' in client
assert "switchpro_values" in client
assert "self.switchpro.start" in client
assert "self.switchpro.rumble" in client
assert "self.switchpro.stop" in client

assert "PROP_HANDSHAKE" in backend
assert "PROP_HIGH_SPEED" in backend
assert "PROP_FORCE_USB" in backend
assert "REPORT_FULL_STATE" in backend
assert "build_rumble_report" in backend

assert 'rmdir /s /q "%~dp0build"' in bat
assert 'rmdir /s /q "%~dp0dist"' in bat
assert 'del /f /q "%~dp0SwitchNetClient.spec"' in bat

print("OK: original Switch Pro Windows integration and clean-build policy")
