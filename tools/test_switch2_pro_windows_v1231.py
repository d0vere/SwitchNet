#!/usr/bin/env python3
import importlib.util
from pathlib import Path

root=Path(__file__).resolve().parents[1]
p=root/"client-python-windows"/"switch2_pro_windows.py"
spec=importlib.util.spec_from_file_location("s2p",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

r=bytearray(64)
r[0]=0x09
r[3]|=(1<<1)
assert m.parse_report09(bytes(r)) is not None

prefixed=bytes([0])+bytes(r)
assert m.parse_report09(prefixed) is None
assert m.parse_report09(prefixed[1:]) is not None

text=p.read_text()
assert "probing HID" in text
assert "no report 0x09" in text
assert "report[0]==0x00" in text
assert "report[1]==REPORT_ID" in text

print("OK: Switch 2 Pro HID auto-probe diagnostics")
