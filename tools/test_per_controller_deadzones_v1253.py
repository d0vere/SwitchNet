#!/usr/bin/env python3
import ast
from pathlib import Path

root=Path(__file__).resolve().parents[1]
client=(root/"client-python-windows"/"switchnet_client.py").read_text()

for key in ("steam","dualsense","stadia","switchpro","switch2pro","xinput"):
    assert f'"{key}": {{' in client

assert "CONTROLLER_DEADZONE_SPECS" in client
assert "def _deadzone_for_backend" in client
assert "def _build_deadzone_row" in client
assert 'text="Stick deadzones"' in client
assert "ttk.Spinbox(" in client
assert "from_=0,to=16000" in client
assert '"<ButtonRelease-1>"' in client

assert 'text="Button layout"' not in client
assert "self.layout" not in client
assert "self.dz" not in client

assert 'legacy_deadzone=int(q.get("deadzone",6000))' in client
assert 'f"deadzone_{deadzone_id}"' in client
assert "self._deadzone_for_backend(" in client

ast.parse(client)
print("OK: per-controller deadzones + exact values + Button layout removed")
