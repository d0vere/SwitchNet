#!/usr/bin/env python3
import ast
from pathlib import Path
root=Path(__file__).resolve().parents[1]
client=(root/"client-python-windows"/"switchnet_client.py").read_text()

assert 'self.keyboard_profile=tk.StringVar(' in client
assert 'CONTROLLER_PROFILE_SLOTS' in client
assert 'self.keyboard_profiles={}' in client
assert 'self.keyboard_profile_names={' in client
assert 'def _active_keyboard_mapping(self):' in client
assert 'def _on_keyboard_profile_selected' in client
assert 'def _refresh_keyboard_profile_combo' in client
assert 'text="Mapping profile"' in client
assert 'text="Edit profiles…"' in client
assert 'win.title("SwitchNet - Keyboard + Mouse Profiles")' in client
assert 'section=f"keyboard_profile:{slot}"' in client
assert '"keyboard_profile": self.keyboard_profile.get()' in client
assert '"keyboard_profile_name_1"' in client
assert 'legacy_keyboard_mapping' in client
assert 'self._active_keyboard_mapping(),self.keyboard_exclusive.get()' in client
ast.parse(client)
print("OK: Keyboard + Mouse has Default + Custom 1/2/3 mapping profiles")
