#!/usr/bin/env python3
from evdev import InputDevice, ecodes, list_devices

for path in sorted(list_devices()):
    try:
        d=InputDevice(path)
        caps=d.capabilities(absinfo=False)
        keys=set(caps.get(ecodes.EV_KEY,[]))
        if not (ecodes.BTN_GAMEPAD in keys or ecodes.BTN_SOUTH in keys):
            d.close();continue
        ff_caps=caps.get(ecodes.EV_FF,[])
        print(f"{path}: {d.name}")
        print(f"  FF_RUMBLE: {'YES' if ecodes.FF_RUMBLE in ff_caps else 'NO'}")
        print(f"  EV_FF capabilities: {ff_caps}")
        d.close()
    except Exception as exc:
        print(path,exc)

print()
print("Nota: SwitchNet v1.8.3 usa SDL2 solo come fallback di OUTPUT")
print("when FF_RUMBLE is unavailable or not working through evdev.")
