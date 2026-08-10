#!/usr/bin/env python3
import ast
from pathlib import Path

root=Path(__file__).resolve().parents[1]
linux=(root/"client-python-linux"/"switchnet_client.py").read_text()

assert 'APP_VERSION = "1.26.0"' in linux
assert "QtWidgets.QTabWidget()" in linux
for tab in ("Controllers","Mappings","Network","Extra","Diagnostics"):
    assert f'addTab(' in linux and f'"{tab}"' in linux

assert "CONTROLLER_PROFILE_SLOTS" in linux
for family in ("dualsense","stadia","switchpro","switch2pro","xinput","generic"):
    assert f'"{family}"' in linux

assert "KeyboardProfilesDialog" in linux
assert "GenericMappingDialog" in linux
assert "BlacklistDialog" in linux
assert "controller_profile_slots" in linux
assert "controller_deadzones" in linux
assert "active_keyboard_mapping" in linux
assert "Gyro trim (80% roll / 90% pitch-yaw)" in linux
assert "OpenPuck corrected gyro trim" not in linux

assert "left=round(max(0,min(65535,int(left)))*0.45)" in linux
assert "right=round(max(0,min(65535,int(right)))*0.45)" in linux

assert "StableControllerRoster" in linux
assert "schedule_service_restart" in linux
assert "Switch2ProUsbEnabler" in linux
assert "discover_switchnet" in linux
assert "wake_switch2" in linux
assert "LinuxKeyboardMouseReader" in linux

assert 'text="Button layout"' not in linux
assert "layout_combo" not in linux

ast.parse(linux)
print("OK: Linux parity structure through v1.25.7 is present")
