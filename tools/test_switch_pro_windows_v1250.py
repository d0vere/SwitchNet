#!/usr/bin/env python3
import importlib.util
import struct
from pathlib import Path

root=Path(__file__).resolve().parents[1]
path=root/"client-python-windows"/"switch_pro_windows.py"
spec=importlib.util.spec_from_file_location("switchpro",path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def pack12(buf,off,x,y):
    buf[off]=x&0xFF
    buf[off+1]=((x>>8)&0x0F)|((y&0x0F)<<4)
    buf[off+2]=(y>>4)&0xFF

report=bytearray(64)
report[0]=0x30
report[3]|=0x08
report[3]|=0x80
report[4]|=0x20
report[5]|=0x02
report[5]|=0x40

pack12(report,6,2048,2048)
pack12(report,9,2048,2048)
struct.pack_into("<hhhhhh",report,13,20,-30,4090,120,-80,40)

gyro=module.GyroZero()
gyro.ready=True
state=module.parse_full_report(bytes(report),gyro)

assert state is not None
assert {"A","ZR","CAPTURE","UP","L"} <= state["buttons"]
assert abs(state["lx"])<32
assert abs(state["ly"])<32
assert state["az"]==4090
assert (state["gx"],state["gy"],state["gz"])==(120,-80,40)

assert module.encode_motor_rumble(0)==bytes((0,1,0x40,0x40))
assert module.encode_motor_rumble(65535)!=module.NEUTRAL_RUMBLE

rumble=module.build_rumble_report(7,65535,32768)
assert len(rumble)==10
assert rumble[0]==0x10
assert rumble[1]==7
assert rumble[2:6]!=rumble[6:10]

assert module.SWITCH_PRO_PID==0x2009
assert module.REPORT_FULL_STATE==0x30
assert module.SUBCMD_ENABLE_IMU==0x40
assert module.SUBCMD_ENABLE_VIBRATION==0x48

print("OK: original Switch Pro input, IMU and HD rumble framing")
