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

def packet(gx_raw=0,gy_raw=0,gz_raw=0):
    r=bytearray(64)
    r[0]=5
    pack12(r,11,2048,2048)
    pack12(r,14,2048,2048)
    struct.pack_into("<I",r,0x2b,1000000)

    # Controller resting flat: gravity on native Nintendo Z.
    struct.pack_into("<h",r,0x31,0)
    struct.pack_into("<h",r,0x33,0)
    struct.pack_into("<h",r,0x35,4096)

    struct.pack_into("<h",r,0x37,gx_raw)
    struct.pack_into("<h",r,0x39,gy_raw)
    struct.pack_into("<h",r,0x3b,gz_raw)
    return bytes(r)

# Bypass zero-bias learning for directional matrix tests.
clock=m.SensorClock()
clock.bias_ready=True
clock.bias=[0.0,0.0,0.0]

# Physical pitch is raw X. It must drive Nintendo Y, NOT steering X.
pitch=m.parse_report05(packet(gx_raw=5000),clock)
assert pitch is not None
assert abs(pitch["gy"])>100
assert abs(pitch["gx"])<10

# Physical wheel/roll is raw Y. It must drive Nintendo X steering.
roll=m.parse_report05(packet(gy_raw=5000),clock)
assert abs(roll["gx"])>100
assert abs(roll["gy"])<10

# Raw Z remains Nintendo Z.
yaw=m.parse_report05(packet(gz_raw=5000),clock)
assert abs(yaw["gz"])>100
assert abs(yaw["gx"])<10
assert abs(yaw["gy"])<10

# Accelerometer frame from v1.24.2 stays untouched.
stationary=m.parse_report05(packet(),clock)
assert stationary["ax"]==0
assert stationary["ay"]==0
assert stationary["az"]==4096

print("OK: pitch no longer steers; wheel/roll maps to Nintendo X")
