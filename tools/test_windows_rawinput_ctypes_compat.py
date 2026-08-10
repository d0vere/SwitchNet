#!/usr/bin/env python3
from pathlib import Path

root=Path(__file__).resolve().parents[1]
src=root/"client-python-windows"/"keyboard_mouse_backend.py"
text=src.read_text(encoding="utf-8")

for bad in (
    "wintypes.HCURSOR",
    "wintypes.HICON",
    "wintypes.HBRUSH",
    "wintypes.HRAWINPUT",
    "wintypes.HINSTANCE",
    "wintypes.HWND",
):
    assert bad not in text, bad

for required in (
    "HANDLE_T = ctypes.c_void_p",
    "HCURSOR_T = ctypes.c_void_p",
    "HRAWINPUT_T = ctypes.c_void_p",
    "class WNDCLASSW",
    "class RAWINPUTDEVICE",
    "CreateWindowExW.argtypes",
    "RegisterRawInputDevices.argtypes",
):
    assert required in text, required

print("OK: Windows Raw Input backend uses portable ctypes handle aliases")
