#!/usr/bin/env python3
from evdev import InputDevice, ecodes, list_devices

for path in sorted(list_devices()):
    try:
        d=InputDevice(path)
        caps=d.capabilities(absinfo=False)
        keys=set(caps.get(ecodes.EV_KEY,[]))
        if (ecodes.BTN_GAMEPAD in keys or ecodes.BTN_SOUTH in keys) and caps.get(ecodes.EV_ABS):
            print(f"{path}: {d.name}")
            print("  phys:", d.phys)
            print("  uniq:", d.uniq)
            print("  keys:", len(keys), "abs:", caps.get(ecodes.EV_ABS,[]))
        d.close()
    except Exception as e:
        print(path, e)
