#!/usr/bin/env python3
import importlib.util
import struct
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

r=bytearray(64)
r[0]=5
pack12(r,11,2048,2048)
pack12(r,14,2048,2048)

struct.pack_into("<I",r,0x2b,1000000)

# Reconstructed raw stationary values from real hardware diagnostics:
# old mapping produced Accel 32, 4136, 720.
struct.pack_into("<h",r,0x31,32)
struct.pack_into("<h",r,0x33,-720)
struct.pack_into("<h",r,0x35,4136)

# stationary gyro
struct.pack_into("<h",r,0x37,0)
struct.pack_into("<h",r,0x39,0)
struct.pack_into("<h",r,0x3b,0)

state=m.parse_report05(bytes(r),m.SensorClock())

assert state is not None
assert state["ax"]==32
assert state["ay"]==-720
assert state["az"]==4136

# Gravity must be primarily on Nintendo Z, not Y.
assert abs(state["az"]) > 4*abs(state["ay"])
assert abs(state["az"]) > 3500

print("OK: Switch 2 Pro stationary gravity stays on Nintendo Z axis")
