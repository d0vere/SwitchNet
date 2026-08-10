#!/usr/bin/env python3
import ast
from pathlib import Path
root=Path(__file__).resolve().parents[1]
client=(root/"client-python-windows"/"switchnet_client.py").read_text()
assert 'APP_VERSION = "1.25.5"' in client
assert client.count('text="Stick deadzones"') == 1
steam=client.index('text="Steam Controller 2026"')
keyboard=client.index('text="Keyboard + Mouse Controller (experimental)"')
deadzone=client.index('text="Stick deadzones"')
network=client.index('# ---------------- Network ----------------')
assert steam < keyboard < deadzone < network
assert 'text="Mapping profile"' in client
assert 'text="Button layout"' not in client
assert 'def _deadzone_for_backend(self,backend):' in client
assert 'self._active_keyboard_mapping()' in client
ast.parse(client)
print("OK: Stick deadzones are at the bottom of the Mappings tab")
