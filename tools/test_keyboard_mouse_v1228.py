#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
for rel in [
    "client-python-linux/keyboard_mouse_backend.py",
    "client-python-windows/keyboard_mouse_backend.py",
]:
    t=(root/rel).read_text(encoding="utf-8")
    assert 'DEFAULT_RELEASE_KEY = "F10"' in t
    assert "class MouseStickFilter" in t
    assert "min(20000" in t
    assert "float(mouse_dx)" in t
    assert "range(1,13)" in t
for rel in [
    "client-python-linux/switchnet_client.py",
    "client-python-windows/switchnet_client.py",
]:
    t=(root/rel).read_text(encoding="utf-8")
    assert "keyboard_release_key" in t
    assert "6500" in t
    assert "20000" in t
print("OK: v1.22.8 keyboard/mouse settings wired on Linux and Windows")
