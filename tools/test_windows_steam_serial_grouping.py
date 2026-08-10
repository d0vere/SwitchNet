#!/usr/bin/env python3
import re

def group(path,serial):
    low=path.casefold()
    vid=re.search(r"vid_([0-9a-f]{4})",low)
    pid=re.search(r"pid_([0-9a-f]{4})",low)
    vp=(vid.group(1) if vid else "????")+"_"+(pid.group(1) if pid else "????")
    if serial:
        return f"valve:{vp}:serial:{serial.casefold()}"
    return f"valve:{vp}:noserial"

paths=[
 r"\\?\hid#vid_28de&pid_1302&mi_00#foo#{guid}",
 r"\\?\hid#vid_28de&pid_1302&mi_01#bar#{guid}",
 r"\\?\hid#vid_28de&pid_1302&mi_02#baz#{guid}",
 r"\\?\hid#vid_28de&pid_1302&mi_03#qux#{guid}",
]

# Arbitrarily different paths still collapse when serial is shared.
assert len({group(p,"SC2026-ABC123") for p in paths})==1

# No-serial fallback also collapses phantom multi-collection enumeration.
assert len({group(p,"") for p in paths})==1

# Different real serials remain distinguishable.
assert group(paths[0],"A") != group(paths[1],"B")

print("OK: Steam HID grouping is serial-first with no-serial fallback")
