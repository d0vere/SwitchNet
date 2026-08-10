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

def packet(ax=32,ay=-720,az=4136,gx=0,gy=0,gz=0):
    r=bytearray(64)
    r[0]=5
    pack12(r,11,2048,2048)
    pack12(r,14,2048,2048)
    struct.pack_into("<I",r,0x2b,1000000)
    struct.pack_into("<h",r,0x31,ax)
    struct.pack_into("<h",r,0x33,ay)
    struct.pack_into("<h",r,0x35,az)
    struct.pack_into("<h",r,0x37,gx)
    struct.pack_into("<h",r,0x39,gy)
    struct.pack_into("<h",r,0x3b,gz)
    return bytes(r)

clock=m.SensorClock()
clock.bias_ready=True
clock.bias=[0.0,0.0,0.0]

# Real stationary sample: rotate XY, preserve gravity Z.
st=m.parse_report05(packet(),clock)
assert st["ax"]==-720
assert st["ay"]==-32
assert st["az"]==4136
assert abs(st["az"]) > 5*max(abs(st["ax"]),abs(st["ay"]))

# A source-Y motion maps to Nintendo X for BOTH accel and gyro.
sy=m.parse_report05(
    packet(ax=0,ay=1500,az=3800,gy=5000),
    clock
)
assert sy["ax"]==1500
assert sy["ay"]==0
assert abs(sy["gx"])>100
assert abs(sy["gy"])<10

# A source-X motion maps to -Nintendo Y for BOTH accel and gyro.
sx=m.parse_report05(
    packet(ax=1500,ay=0,az=3800,gx=5000),
    clock
)
assert sx["ay"]==-1500
assert sx["ax"]==0
assert abs(sx["gy"])>100
assert abs(sx["gx"])<10

print("OK: Switch 2 Pro accel+gyro share one coherent Nintendo frame")
