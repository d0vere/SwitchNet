#!/usr/bin/env python3
import re

def physical(path):
    low=path.casefold()
    parts=low.split("#")
    hardware=re.sub(r"&col[0-9a-f]+","",parts[1])
    instance=re.sub(r"&col[0-9a-f]+","",parts[2])
    instance=re.sub(r"&[0-9a-f]{4}$","",instance)
    return hardware+"#"+instance

paths=[
r"\\?\hid#vid_28de&pid_1302&mi_00#7&abcdef&0&0000#{guid}",
r"\\?\hid#vid_28de&pid_1302&mi_00#7&abcdef&0&0001#{guid}",
r"\\?\hid#vid_28de&pid_1302&mi_00#7&abcdef&0&0002#{guid}",
r"\\?\hid#vid_28de&pid_1302&mi_00#7&abcdef&0&0003#{guid}",
]
assert len({physical(p) for p in paths})==1

def roster_move(slots,source,target):
    out=list(slots)
    value=out.pop(source)
    out.insert(target,value)
    return out

assert roster_move(["steam","dualsense","",""],0,2)==["dualsense","","steam",""]
assert roster_move(["steam","dualsense","",""],1,0)==["dualsense","steam","",""]
print("OK: Windows Steam grouping and roster moves")
