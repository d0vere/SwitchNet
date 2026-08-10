#!/usr/bin/env python3
"""Nintendo Switch 2 Pro Controller (057e:2069) USB HID-mode initializer.

SwitchNet v1.19.9 does not stop, suspend or terminate Moonlight. Coexistence is
implemented at Moonlight/SDL startup: Moonlight is configured to ignore only
057e:2069, leaving SwitchNet as the sole owner of that physical controller while
video streaming remains active.

The initializer follows the reference USB endpoint path and remains short-lived.
"""

import json
import time
import os
import sys

try:
    import usb.core
    import usb.util
except Exception as exc:
    print(json.dumps({"ok": False, "phase": "import", "error": f"PyUSB unavailable: {exc}"}))
    raise SystemExit(2)

VID = 0x057E
PID = 0x2069
INTERFACE = 1

# Sequences synchronized with the validated native Windows backend.
BASIC_COMMANDS=(
("init",bytes([0x03,0x91,0x00,0x0D,0x00,0x08,0x00,0x00,0x01,0x00,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF])),
("cmd-07",bytes([0x07,0x91,0x00,0x01,0x00,0x00,0x00,0x00])),
("cmd-16",bytes([0x16,0x91,0x00,0x01,0x00,0x00,0x00,0x00])),
("report-09",bytes([0x03,0x91,0x00,0x0A,0x00,0x04,0x00,0x00,0x09,0x00,0x00,0x00])),
("player-led",bytes([0x09,0x91,0x00,0x07,0x00,0x08,0x00,0x00,0x01,0,0,0,0,0,0,0])),
)
EXTENDED_COMMANDS=(
("cmd-07",bytes([0x07,0x91,0x00,0x01,0,0,0,0])),
("imu-02",bytes([0x0C,0x91,0,0x02,0,0x04,0,0,0x27,0,0,0])),
("cmd-11",bytes([0x11,0x91,0,0x01,0,0,0,0])),
("cmd-0a",bytes([0x0A,0x91,0,0x08,0,0x14,0,0,0x01,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0x35,0,0x46,0,0,0,0,0,0,0,0])),
("imu-04",bytes([0x0C,0x91,0,0x04,0,0x04,0,0,0x27,0,0,0])),
("cmd-01-0c",bytes([0x01,0x91,0,0x0C,0,0,0,0])),
("cmd-01-01",bytes([0x01,0x91,0,0x01,0,0,0,0])),
("cmd-08",bytes([0x08,0x91,0,0x02,0,0x04,0,0,0x01,0,0,0])),
("report-05",bytes([0x03,0x91,0,0x0A,0,0x04,0,0,0x05,0,0,0])),
("init",bytes([0x03,0x91,0,0x0D,0,0x08,0,0,0x01,0,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF])),
)


def emit(payload):
    print(json.dumps(payload, separators=(",", ":")), flush=True)


def usb_error_payload(exc, phase):
    errno = getattr(exc, "errno", None)
    text = str(exc)
    hint = None
    extra = {}
    if errno in (16, -6) or "busy" in text.lower():
        ml = moonlight_diagnostics()
        extra["moonlight"] = ml
        if ml:
            protected = any(
                "0x057e/0x2069" in (
                    m.get("sdl_gamecontroller_ignore", "") + "," +
                    m.get("sdl_hidapi_ignore", "")
                ).lower()
                for m in ml
            )
            if protected:
                hint = ("Moonlight is running with the SwitchNet SDL exclusion but USB is still busy; "
                        "reconnect the controller and retry.")
            else:
                hint = ("Moonlight is running without the SwitchNet controller exclusion. "
                        "Run install-moonlight-coexistence.sh once, then restart Moonlight.")
        else:
            hint = "USB device is busy; another userspace process may have the controller open."
    elif errno in (13, -3) or "access" in text.lower() or "permission" in text.lower():
        hint = "install/reload the SwitchNet udev rule, then reconnect the controller"
    return {"ok": False, "phase": phase, "errno": errno, "error": text, "hint": hint, **extra}


def _proc_cmdline(pid):
    try:
        raw = open(f"/proc/{pid}/cmdline", "rb").read()
        return raw.replace(b"\0", b" ").decode(errors="replace").strip()
    except Exception:
        return ""


def _proc_environ(pid):
    try:
        raw = open(f"/proc/{pid}/environ", "rb").read()
        env = {}
        for item in raw.split(b"\0"):
            if b"=" in item:
                k, v = item.split(b"=", 1)
                env[k.decode(errors="replace")] = v.decode(errors="replace")
        return env
    except Exception:
        return {}


def moonlight_diagnostics():
    """Read-only Moonlight diagnostics. Never signal/terminate Moonlight."""
    found = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        cmd = _proc_cmdline(entry)
        if not cmd or "moonlight" not in cmd.lower():
            continue
        env = _proc_environ(entry)
        found.append({
            "pid": int(entry),
            "cmd": cmd,
            "sdl_gamecontroller_ignore": env.get("SDL_GAMECONTROLLER_IGNORE_DEVICES", ""),
            "sdl_hidapi_ignore": env.get("SDL_HIDAPI_IGNORE_DEVICES", ""),
        })
    return found


def prepare_device_like_reference(dev):
    """Follow the known-working NSW2 Linux enabler USB ownership path.

    Do not explicitly claim interface 1.  Detach active kernel drivers,
    call set_configuration(), then let PyUSB/libusb acquire the interface
    implicitly when the endpoint is used.
    """
    detached = []
    cfg = dev.get_active_configuration()
    for interface in cfg:
        n = int(interface.bInterfaceNumber)
        try:
            if dev.is_kernel_driver_active(n):
                dev.detach_kernel_driver(n)
                detached.append(n)
        except (NotImplementedError, AttributeError):
            pass

    dev.set_configuration()
    cfg = dev.get_active_configuration()
    intf = cfg[(INTERFACE, 0)]

    ep_out = usb.util.find_descriptor(
        intf,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT,
    )
    ep_in = usb.util.find_descriptor(
        intf,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN,
    )
    if ep_out is None:
        raise RuntimeError("Vendor bulk OUT endpoint not found on interface 1")
    return detached, ep_out, ep_in

def main():
    extended="--extended" in sys.argv
    commands=EXTENDED_COMMANDS if extended else BASIC_COMMANDS
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        emit({"ok": False, "phase": "find", "error": "Switch 2 Pro Controller not found"})
        return 3

    detached_interfaces = []
    claimed = False
    responses = 0
    sent = 0
    claim_attempts = 0
    try:
        detached_interfaces, ep_out, ep_in = prepare_device_like_reference(dev)
        claim_attempts = 0
        claim_strategy = "implicit-endpoint"

        for name, command in commands:
            try:
                written = dev.write(int(ep_out.bEndpointAddress), command, timeout=650)
            except usb.core.USBError as exc:
                emit(usb_error_payload(exc, f"write:{name}") | {"sent": sent})
                return 5
            if int(written) != len(command):
                emit({"ok": False, "phase": f"write:{name}", "error": f"short USB write {written}/{len(command)}", "sent": sent})
                return 5
            sent += 1

            if ep_in is not None:
                try:
                    dev.read(int(ep_in.bEndpointAddress), 64, timeout=90)
                    responses += 1
                except usb.core.USBTimeoutError:
                    pass
                except usb.core.USBError as exc:
                    # Some firmware revisions do not answer every command.
                    # Non-timeout read failures are diagnostic, not fatal if
                    # writes continue to succeed.
                    if getattr(exc, "errno", None) not in (110, -7):
                        pass
            time.sleep(0.045)

        emit({
            "ok": True,
            "phase": "complete",
            "sent": sent,
            "responses": responses,
            "claim_attempts": claim_attempts,
            "detached_interfaces": detached_interfaces,
            "claim_strategy": claim_strategy,
            "message": f"Nintendo USB {'extended 0x05' if extended else 'basic 0x09'} sequence sent ({sent}/{len(commands)} commands)",
        })
        return 0

    except usb.core.USBError as exc:
        emit(usb_error_payload(exc, "usb-prepare"))
        return 5
    except Exception as exc:
        emit({"ok": False, "phase": "unexpected", "error": str(exc)})
        return 6
    finally:
        # Reattach exactly the kernel interfaces detached during preparation.
        for interface in reversed(detached_interfaces):
            try:
                dev.attach_kernel_driver(interface)
            except Exception:
                pass
        try:
            usb.util.dispose_resources(dev)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
