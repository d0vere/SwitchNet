#!/usr/bin/env python3
from evdev import InputDevice, ecodes, list_devices

imus=[]
for path in sorted(list_devices()):
    try:
        d=InputDevice(path)
        if "(IMU)" in (d.name or ""):
            imus.append((path,d))
        else:
            d.close()
    except Exception:
        pass

if not imus:
    print("No IMU device found.")
    raise SystemExit(1)

for path,d in imus:
    print(f"{path}: {d.name}")
    print(f"  phys={d.phys!r} uniq={d.uniq!r}")
    print("  Muovi il controller; Ctrl+C per uscire.")
    try:
        for ev in d.read_loop():
            if ev.type == ecodes.EV_ABS:
                print(f"  ABS code={ev.code:02d} value={ev.value:10d}")
            elif ev.type == ecodes.EV_MSC and ev.code == ecodes.MSC_TIMESTAMP:
                print(f"  timestamp={ev.value}")
    except KeyboardInterrupt:
        d.close()
        break
