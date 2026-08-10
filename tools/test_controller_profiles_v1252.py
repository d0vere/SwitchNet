#!/usr/bin/env python3
import ast
from pathlib import Path

root=Path(__file__).resolve().parents[1]
client=(root/"client-python-windows"/"switchnet_client.py").read_text()

for cid in ("dualsense","stadia","switchpro","switch2pro","xinput"):
    assert f'"{cid}": {{' in client

assert 'CONTROLLER_PROFILE_SLOTS = ("Default", "Custom 1", "Custom 2", "Custom 3")' in client
assert "def default_controller_mapping" in client
assert "def _mapped_switch_controls" in client
assert "def open_controller_mapping_editor" in client
assert "def _build_mapping_profile_box" in client
assert "def _controller_mapping_for_backend" in client

# All relevant mappers accept a custom mapping.
for func in (
    "switchpro_values","switch2pro_values",
    "dualsense_values","stadia_values","xinput_values",
):
    marker=f"def {func}("
    pos=client.index(marker)
    sig=client[pos:client.index("):",pos)+2]
    assert "mapping" in sig

# Pro 2 GL/GR are part of the full profile now.
assert '("gl","GL"),("gr","GR")' in client

# Default profiles remain dynamic / backward-compatible.
assert 'mapping=mapping or default_controller_mapping("dualsense",labels)' in client
assert 'mapping=mapping or default_controller_mapping("xinput",labels)' in client
assert '"switch2pro",labels,rear_mapping' in client

ast.parse(client)
print("OK: five controller families have Default + three custom mapping profiles")
