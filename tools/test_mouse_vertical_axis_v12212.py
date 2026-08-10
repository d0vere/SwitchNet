#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]

for rel in (
    "client-python-linux/keyboard_mouse_backend.py",
    "client-python-windows/keyboard_mouse_backend.py",
):
    text = (root / rel).read_text(encoding="utf-8")

    assert (
        'ry=max(-32768,min(32767,round(float(mouse_dy)*sens))),' in text
    ), rel

    assert (
        'ry=max(-32768,min(32767,round(-float(mouse_dy)*sens))),' not in text
    ), rel

# Raw/evdev convention: mouse up = negative delta Y.
# SwitchNet right-stick convention must preserve that sign:
# negative stick Y = camera up.
def mouse_to_ry(mouse_dy, sensitivity=6500):
    return max(-32768, min(32767, round(float(mouse_dy) * sensitivity)))

assert mouse_to_ry(-1) < 0   # mouse up -> camera up
assert mouse_to_ry(+1) > 0   # mouse down -> camera down

print("OK: mouse vertical axis matches camera direction")
