#!/usr/bin/env python3
import importlib.util
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
module_path=root/"client-python-windows"/"switch2_pro_windows.py"

spec=importlib.util.spec_from_file_location("switch2_pro_windows_test",module_path)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def pack12(x,y):
    return bytes([
        x & 0xff,
        ((x >> 8) & 0x0f) | ((y & 0x0f) << 4),
        (y >> 4) & 0xff,
    ])

r=bytearray(64)
r[0]=0x09
r[1]=7
r[2]=0x23
r[3]|=(1<<1)       # A
r[4]|=(1<<3)       # UP
r[5]|=(1<<0)       # HOME
r[5]|=(1<<2)       # GR
r[6:9]=pack12(2048,2048)
r[9:12]=pack12(2048,2048)

state=mod.parse_report09(bytes(r))
assert state is not None
assert "A" in state["buttons"]
assert "UP" in state["buttons"]
assert "HOME" in state["buttons"]
assert "GR" in state["buttons"]
assert state["report_id"]==0x09
assert "GR" in state["extra_buttons"]

assert mod.parse_report09(bytes([0x05])+bytes(63)) is None
assert len(mod.WAKE_SEQUENCE)==5

print("OK: Switch 2 Pro report 0x09 parser and wake sequence")
