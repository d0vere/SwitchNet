#!/usr/bin/env python3
from pathlib import Path

root=Path(__file__).resolve().parents[1]
text=(root/"client-python-windows"/"switchnet_client.py").read_text()

assert "Gyro trim (80% roll / 90% pitch-yaw)" in text
assert "OpenPuck corrected gyro trim" not in text
assert "left_scaled=round(max(0,min(65535,int(left))) * 0.45)" in text
assert "right_scaled=round(max(0,min(65535,int(right))) * 0.45)" in text

assert 'CONTROLLER_PROFILE_SLOTS = ("Default", "Custom 1", "Custom 2", "Custom 3")' in text
assert 'text="Stick deadzones"' in text
assert 'text="Button layout"' not in text
assert 'self.keyboard_profile=tk.StringVar(' in text
assert "SwitchProReader" in text
assert "Switch2ProReader" in text

bat=(root/"client-python-windows"/"build-exe.bat").read_text()
assert 'rmdir /s /q "%~dp0build"' in bat
assert 'rmdir /s /q "%~dp0dist"' in bat
assert 'del /f /q "%~dp0SwitchNetClient.spec"' in bat

print("OK: v1.25.6 behavior and prior GUI/profile features retained")
