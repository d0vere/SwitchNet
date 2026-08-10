#!/usr/bin/env python3
import re

def _windows_hid_physical_key(path):
    low=str(path or "").casefold()
    parts=low.split("#")
    if len(parts)<3:
        return re.sub(r"&col[0-9a-f]+","",low)
    hardware=parts[1]
    instance=parts[2]
    hardware=re.sub(r"&col[0-9a-f]+","",hardware)
    instance=re.sub(r"&col[0-9a-f]+","",instance)
    instance=re.sub(r"&[0-9a-f]{4}$","",instance)
    return hardware+"#"+instance

p1=r"\\?\hid#vid_28de&pid_1302&mi_00#7&abcdef&0&0000#{guid}"
p2=r"\\?\hid#vid_28de&pid_1302&mi_00#7&abcdef&0&0001#{guid}"
assert _windows_hid_physical_key(p1) == _windows_hid_physical_key(p2)
print("OK: regex dependency loaded and Steam HID physical grouping executable")
