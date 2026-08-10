# Keyboard + Mouse controller — SwitchNet v1.22.0

Keyboard + Mouse is a virtual controller in the same priority roster as physical
gamepads. Enabling it adds it to an inactive slot; it never auto-steals P1/P2.

## Default mapping

| PC input | Nintendo control |
|---|---|
| W / S / A / D | Left stick up / down / left / right |
| Q / O | ZL / ZR |
| Arrow keys | D-Pad |
| E / U | L / R |
| I / J / K / L | X / Y / B / A |
| X / M | L3 / R3 |
| Y / T | + / - |
| G / B | Capture / Home |
| Mouse movement | Right stick |

Every keyboard binding is editable in both clients. Mouse sensitivity is also
configurable.

## Background and exclusive capture

### Linux

SwitchNet reads `/dev/input/event*` directly, so the SwitchNet window does not
need focus. With Exclusive capture enabled it uses the evdev EVIOCGRAB ioctl on
the keyboard and relative mouse devices. Those input events are then delivered
only to SwitchNet until the grab is released.

If the desktop account cannot open the keyboard/mouse event devices, run the
optional `client-python-linux/install-keyboard-mouse-udev.sh` once.

### Windows

SwitchNet installs `WH_KEYBOARD_LL` and `WH_MOUSE_LL` hooks on a dedicated
message-loop thread. Mapped keyboard keys and mouse messages are suppressed when
exclusive capture is active while the main client may remain in the background.

This suppression is user-mode. Software that reads lower-level/raw device input
through a separate path may behave differently; no kernel filter driver is
installed by SwitchNet.

## Emergency release

**F10** (mappable) immediately releases exclusive capture.
