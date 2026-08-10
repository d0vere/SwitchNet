#!/usr/bin/env python3
import ast, importlib.util
from pathlib import Path
root=Path(__file__).resolve().parents[1]
c=(root/"client-python-linux"/"switchnet_client.py").read_text()
bp=root/"client-python-linux"/"switch2_pro_linux.py"
b=bp.read_text()
assert 'APP_VERSION = "1.26.4"' in c
assert '"switch2pro_hidraw"' in c
assert "Switch2ProHidraw" in c
assert "enumerate_switch2_pro_hidraw" in c
assert "switch2pro_native_values" in c
assert 'kind=="switch2pro_hidraw"' in c
assert "parse_report05" in b and "parse_report09" in b and "build_pro_rumble_frame" in b
spec=importlib.util.spec_from_file_location("sp2",bp);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
r=bytearray(64);r[0]=9;r[3]|=1<<1;r[4]|=1<<3;r[5]|=1<<3
def pack(o,x,y):
    r[o]=x&255;r[o+1]=((x>>8)&15)|((y&15)<<4);r[o+2]=(y>>4)&255
pack(6,2048,2048);pack(9,2048,2048)
st=m.parse_report09(bytes(r))
assert {"A","UP","GL"} <= st["buttons"]
frame=m.build_pro_rumble_frame(3,65535,32768)
assert len(frame)==64 and frame[0]==2 and (frame[1]&15)==3
ast.parse(c);ast.parse(b)
print("OK: native Linux Switch 2 Pro parser, dedup and HD rumble")
