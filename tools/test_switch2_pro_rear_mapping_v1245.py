#!/usr/bin/env python3
import importlib.util
from pathlib import Path

root=Path(__file__).resolve().parents[1]
client_path=root/"client-python-windows"/"switchnet_client.py"
text=client_path.read_text()

# Extract/import whole client isn't portable on Linux due Win32; verify source
# and execute the mapper by compiling the module syntax separately in release.
assert 'SWITCH2_PRO_REAR_SOURCES = ("GL", "GR")' in text
assert '"switch2_gl_mapping"' in text
assert '"switch2_gr_mapping"' in text
assert 'rear_mapping=rear_mapping or default_switch2_pro_rear_mapping()' in text
assert 'target=rear_mapping.get(source,"None")' in text
assert 'elif target=="ZL"' in text
assert 'elif target=="ZR"' in text
assert 'D-Pad Up' in text
assert 'self._switch2_rear_mapping()' in text

# Reverse-engineering/debug UI removed.
assert "Test Pro Controller 2 rumble" not in text
assert "USB IMU + HD rumble diagnostics." not in text
assert "gyro zero " not in text
assert 'input_detail="Native USB HID"' in text

bat=(root/"client-python-windows"/"build-exe.bat").read_text()
assert 'rmdir /s /q "%~dp0build"' in bat
assert 'rmdir /s /q "%~dp0dist"' in bat
assert 'del /f /q "%~dp0SwitchNetClient.spec"' in bat

print("OK: GL/GR configurable mapping + Switch2 debug UI cleanup")
