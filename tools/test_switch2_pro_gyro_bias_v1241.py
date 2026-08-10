#!/usr/bin/env python3
import importlib.util,struct
from pathlib import Path

root=Path(__file__).resolve().parents[1]
p=root/"client-python-windows"/"switch2_pro_windows.py"
spec=importlib.util.spec_from_file_location("s2",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def pack12(b,o,x,y):
    b[o]=x&255
    b[o+1]=((x>>8)&15)|((y&15)<<4)
    b[o+2]=(y>>4)&255

def packet(gx=120,gy=-80,gz=60):
    r=bytearray(64)
    r[0]=5
    pack12(r,11,2048,2048)
    pack12(r,14,2048,2048)
    struct.pack_into("<I",r,0x2b,1000000)
    struct.pack_into("<h",r,0x31,0)
    struct.pack_into("<h",r,0x33,-4096)
    struct.pack_into("<h",r,0x35,0)
    struct.pack_into("<h",r,0x37,gx)
    struct.pack_into("<h",r,0x39,-gz)
    struct.pack_into("<h",r,0x3b,gy)
    return bytes(r)

clock=m.SensorClock()

for _ in range(130):
    state=m.parse_report05(packet(),clock)

assert clock.bias_ready
assert clock.bias_count>=120

state=m.parse_report05(packet(),clock)
assert abs(state["gx"])<=10
assert abs(state["gy"])<=10
assert abs(state["gz"])<=10

moving=m.parse_report05(packet(gx=2200),clock)
assert abs(moving["gx"])>100

print("OK: Switch 2 Pro stationary gyro bias removed, real motion preserved")
