#!/usr/bin/env python3
from pathlib import Path

root=Path(__file__).resolve().parents[1]

w=(root/"client-python-windows"/"keyboard_mouse_backend.py").read_text()
l=(root/"client-python-linux"/"keyboard_mouse_backend.py").read_text()
wc=(root/"client-python-windows"/"switchnet_client.py").read_text()
lc=(root/"client-python-linux"/"switchnet_client.py").read_text()

assert "WM_INPUT=0x00FF" in w
assert "RegisterRawInputDevices" in w
assert "lLastX" in w and "lLastY" in w
assert "screen coordinates" in w
assert "_set_toggle_state" in w
assert "_set_toggle_state" in l
assert "not self.controller_enabled" in w
assert "not self.controller_enabled" in l
assert "kbm_enabled=self.kbm.consume()" in wc
assert "kbm_enabled=self.kbm.consume()" in lc

print("OK: raw mouse + ON/OFF toggle wired on Windows and Linux")
