#!/usr/bin/env python3
import re

def key(path):
    low=str(path).casefold()
    parts=low.split("#")
    hardware=parts[1] if len(parts)>1 else low
    instance=parts[2] if len(parts)>2 else ""
    vid=re.search(r"vid_([0-9a-f]{4})",hardware)
    pid=re.search(r"pid_([0-9a-f]{4})",hardware)
    hardware=re.sub(r"&mi_[0-9a-f]{2}","",hardware)
    hardware=re.sub(r"&col[0-9a-f]+","",hardware)
    instance=re.sub(r"&col[0-9a-f]+","",instance)
    instance=re.sub(r"&[0-9a-f]{4}$","",instance)
    instance=re.sub(r"&mi_[0-9a-f]{2}","",instance)
    vp=(vid.group(1) if vid else "????")+"_"+(pid.group(1) if pid else "????")
    return "valve:"+vp+"#"+instance

paths=[
 r"\\?\hid#vid_28de&pid_1302&mi_00#7&11111111&0&0000#{guid}",
 r"\\?\hid#vid_28de&pid_1302&mi_01#7&11111111&0&0001#{guid}",
 r"\\?\hid#vid_28de&pid_1302&mi_02#7&11111111&0&0002#{guid}",
 r"\\?\hid#vid_28de&pid_1302&mi_03#7&11111111&0&0003#{guid}",
]
assert len({key(p) for p in paths}) == 1, [key(p) for p in paths]

# Saved roster migration must leave exactly one Steam entry.
saved=["steam:a","steam:b","steam:c","steam:d"]
canonical="steam:canonical"
out=[];written=False
for old in saved:
    if old.startswith("steam:"):
        if not written:
            out.append(canonical);written=True
        else:
            out.append("")
    else:
        out.append(old)
assert out==[canonical,"","",""]

print("OK: Steam multi-interface collections collapse to one logical controller")
