#!/usr/bin/env python3
import ast
from pathlib import Path
root=Path(__file__).resolve().parents[1]
s=(root/"client-python-linux"/"switchnet_client.py").read_text()

assert 'APP_VERSION = "1.26.2"' in s
assert "def resolve_evdev_controller_path(" in s
assert "controller_vendor=int(cfg.get(" in s
assert "controller_product=int(cfg.get(" in s
assert "current_path=resolve_evdev_controller_path(" in s
assert '"controller_vendor":int(d.get("vendor",0) or 0)' in s
assert '"controller_product":int(d.get("product",0) or 0)' in s
assert 'placeholder="usb:057e:2069:switch2pro"' in s
assert 'switch2_real["key"] if key==placeholder else key' in s

# Five roster slots.
assert "while len(self.controller_slots)<5" in s
assert "while len(slots)<5" in s
assert "Slots 3 to 5 remain detected but inactive." in s

# DualSense v1.26.1 fix retained.
assert "has_motion_axes=motion_axes.issubset(abses)" in s

ast.parse(s)
print("OK: Switch 2 Pro dynamic evdev re-enumeration and five-slot roster")
