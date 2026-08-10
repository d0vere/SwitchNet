#!/usr/bin/env python3
import importlib.util,struct
from pathlib import Path
root=Path(__file__).resolve().parents[1];p=root/"client-python-windows"/"switch2_pro_windows.py"
spec=importlib.util.spec_from_file_location("s2",p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def pack12(b,o,x,y):b[o]=x&255;b[o+1]=((x>>8)&15)|((y&15)<<4);b[o+2]=(y>>4)&255
r=bytearray(64);r[0]=5;r[5]|=8;r[6]|=32;r[7]|=2;pack12(r,11,2048,2048);pack12(r,14,2048,2048)
struct.pack_into("<I",r,0x2b,1000000);struct.pack_into("<h",r,0x31,0);struct.pack_into("<h",r,0x33,-4096);struct.pack_into("<h",r,0x35,0)
struct.pack_into("<h",r,0x37,100);struct.pack_into("<h",r,0x39,200);struct.pack_into("<h",r,0x3b,300)
st=m.parse_report05(bytes(r),m.SensorClock());assert st and "A" in st["buttons"] and "CAPTURE" in st["buttons"] and "UP" in st["buttons"];assert st["az"]==4096
wave=m.encode_hd_rumble(0x187,29000,0x112,29000);f=m.build_pro_rumble_frame(7,65535,65535)
assert len(f)==64 and f[0]==2 and f[1]==0x57 and f[0x11]==0x57 and f[2:7]==wave and f[0x12:0x17]==wave
assert any(len(c)>=12 and c[0]==3 and c[3]==10 and c[8]==5 for c in m.EXTENDED_INIT_SEQUENCE)
print("OK: v1.24.0 Switch2 Pro 0x05 IMU + SDL HD rumble")
