#!/usr/bin/env python3
import ast
from pathlib import Path

root=Path(__file__).resolve().parents[1]
s=(root/"client-python-linux"/"switchnet_client.py").read_text()

assert 'APP_VERSION = "1.26.3"' in s
assert "def _switch2_slot_streaming(self,slot):" in s
assert "def _switch2_is_functional(self):" in s
assert 'int(generation)>0' in s
assert 'str(kind)=="evdev"' in s
assert '"Switch 2 Pro USB: ready · input streaming"' in s
assert '"Switch 2 Pro USB: silent input · reinitializing HID mode..."' in s
assert "worker.stop()" in s
assert "now-self.switch2_usb.last_attempt<6.0" in s
assert 'worker_stage="waiting_first_report"' in s
assert 'f"P1 stage: {snap.get(' in s
assert "refresh_and_restart" in s
assert "Switch 2 Pro USB initialization completed" in s

# Previous fixes remain.
assert "resolve_evdev_controller_path" in s
assert "while len(self.controller_slots)<5" in s
assert "has_motion_axes=motion_axes.issubset(abses)" in s

ast.parse(s)
print("OK: Switch 2 Pro readiness requires real input and auto-recovers silent evdev")
