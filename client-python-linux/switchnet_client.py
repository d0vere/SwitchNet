#!/usr/bin/env python3
from __future__ import annotations

import configparser
import ctypes
import fcntl
import json
import os
import random
import select
import socket
import struct
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from keyboard_mouse_backend import (
    KEYBOARD_ACTIONS, KEYBOARD_KEY_CHOICES, DEFAULT_KEYBOARD_MAPPING,
    RELEASE_KEY_CHOICES, DEFAULT_RELEASE_KEY,
    normalized_keyboard_mapping, normalized_release_key,
    mapping_without_release_conflict, keyboard_mouse_values,
    LinuxKeyboardMouseReader,
)

from switch2_pro_linux import Switch2ProHidraw, enumerate_switch2_pro_hidraw

try:
    from evdev import InputDevice, ecodes, ff, list_devices
except ImportError:
    InputDevice = None
    ecodes = None
    ff = None
    list_devices = None

try:
    import usb.core as pyusb_core
    import usb.util as pyusb_util
except ImportError:
    pyusb_core = None
    pyusb_util = None

APP_VERSION = "1.26.4"
DEFAULT_PORT = 5454
CLIENT_API_HOST = "127.0.0.1"
CLIENT_API_PORT = 5455
HAT_NEUTRAL = 8

BTN_A = 1 << 0
BTN_B = 1 << 1
BTN_X = 1 << 2
BTN_Y = 1 << 3
BTN_L = 1 << 4
BTN_R = 1 << 5
BTN_BACK = 1 << 6
BTN_START = 1 << 7
BTN_LS = 1 << 8
BTN_RS = 1 << 9
BTN_GUIDE = 1 << 10
BTN_CAPTURE = 1 << 11

STEAM_PROFILE_NAMES = ("Default", "Custom 1", "Custom 2", "Custom 3")
STEAM_SOURCE_BUTTONS = (
    ("a", "A"), ("b", "B"), ("x", "X"), ("y", "Y"),
    ("lb", "L1"), ("rb", "R1"), ("back", "View / Back"),
    ("start", "Menu / Start"), ("ls", "L3"), ("rs", "R3"),
    ("guide", "Steam"), ("qam", "…"),
    ("l4", "L4"), ("l5", "L5"), ("r4", "R4"), ("r5", "R5"),
    ("up", "D-Pad Up"), ("down", "D-Pad Down"),
    ("left", "D-Pad Left"), ("right", "D-Pad Right"),
)
STEAM_MAPPING_SOURCES = STEAM_SOURCE_BUTTONS + (("l5+r5", "L5 + R5"),)
STEAM_TARGETS = (
    "None", "A", "B", "X", "Y", "L", "R", "ZL", "ZR",
    "-", "+", "L3", "R3", "HOME", "CAPTURE",
    "D-Pad Up", "D-Pad Down", "D-Pad Left", "D-Pad Right",
)
STEAM_TARGET_BUTTON_BITS = {
    "A": BTN_A, "B": BTN_B, "X": BTN_X, "Y": BTN_Y,
    "L": BTN_L, "R": BTN_R, "-": BTN_BACK, "+": BTN_START,
    "L3": BTN_LS, "R3": BTN_RS, "HOME": BTN_GUIDE, "CAPTURE": BTN_CAPTURE,
}

def default_steam_mapping(labels=False):
    # Stable positional default. Universal per-controller profiles replace the
    # historical global Button layout setting.
    face = {"a":"B","b":"A","x":"Y","y":"X"}
    return {
        **face, "lb":"L", "rb":"R", "back":"-", "start":"+",
        "ls":"L3", "rs":"R3", "guide":"HOME", "qam":"CAPTURE",
        "l4":"None", "l5":"None", "r4":"None", "r5":"None",
        "up":"D-Pad Up", "down":"D-Pad Down", "left":"D-Pad Left", "right":"D-Pad Right",
        "l5+r5":"None",
    }


CONTROLLER_PROFILE_SLOTS = ("Default","Custom 1","Custom 2","Custom 3")

LINUX_MAPPING_SPECS = {
    "dualsense": {
        "title":"DualSense",
        "sources":(
            ("south","Cross"),("east","Circle"),("west","Square"),("north","Triangle"),
            ("l","L1"),("r","R1"),("zl","L2"),("zr","R2"),
            ("minus","Create"),("plus","Options"),("l3","L3"),("r3","R3"),
            ("home","PS"),("capture","Touchpad"),
            ("up","D-Pad Up"),("down","D-Pad Down"),
            ("left","D-Pad Left"),("right","D-Pad Right"),
        ),
    },
    "stadia": {
        "title":"Google Stadia Controller",
        "sources":(
            ("south","A"),("east","B"),("west","X"),("north","Y"),
            ("l","L1"),("r","R1"),("zl","L2"),("zr","R2"),
            ("minus","Options / Back"),("plus","Menu / Start"),
            ("l3","L3"),("r3","R3"),("home","Stadia"),("capture","Capture"),
            ("up","D-Pad Up"),("down","D-Pad Down"),
            ("left","D-Pad Left"),("right","D-Pad Right"),
        ),
    },
    "switchpro": {
        "title":"Nintendo Switch Pro Controller",
        "sources":(
            ("south","B"),("east","A"),("west","Y"),("north","X"),
            ("l","L"),("r","R"),("zl","ZL"),("zr","ZR"),
            ("minus","-"),("plus","+"),("l3","L3"),("r3","R3"),
            ("home","HOME"),("capture","CAPTURE"),
            ("up","D-Pad Up"),("down","D-Pad Down"),
            ("left","D-Pad Left"),("right","D-Pad Right"),
        ),
    },
    "switch2pro": {
        "title":"Nintendo Switch 2 Pro Controller",
        "sources":(
            ("south","B"),("east","A"),("west","Y"),("north","X"),
            ("l","L"),("r","R"),("zl","ZL"),("zr","ZR"),
            ("minus","-"),("plus","+"),("l3","L3"),("r3","R3"),
            ("home","HOME"),("capture","CAPTURE"),
            ("c","C"),("gl","GL"),("gr","GR"),
            ("up","D-Pad Up"),("down","D-Pad Down"),
            ("left","D-Pad Left"),("right","D-Pad Right"),
        ),
    },
    "xinput": {
        "title":"XInput / Xbox",
        "sources":(
            ("south","A"),("east","B"),("west","X"),("north","Y"),
            ("l","LB"),("r","RB"),("zl","LT"),("zr","RT"),
            ("minus","Back"),("plus","Start"),("l3","L3"),("r3","R3"),
            ("home","Guide"),
            ("up","D-Pad Up"),("down","D-Pad Down"),
            ("left","D-Pad Left"),("right","D-Pad Right"),
        ),
    },
    "generic": {
        "title":"Generic evdev",
        "sources":(
            ("south","South"),("east","East"),("west","West"),("north","North"),
            ("l","L"),("r","R"),("zl","ZL"),("zr","ZR"),
            ("minus","Back"),("plus","Start"),("l3","L3"),("r3","R3"),
            ("home","Guide"),("capture","Capture"),
            ("up","D-Pad Up"),("down","D-Pad Down"),
            ("left","D-Pad Left"),("right","D-Pad Right"),
        ),
    },
}

CONTROLLER_DEADZONE_SPECS = {
    "steam":"Steam Controller 2026",
    "dualsense":"DualSense",
    "stadia":"Google Stadia Controller",
    "switchpro":"Nintendo Switch Pro Controller",
    "switch2pro":"Nintendo Switch 2 Pro Controller",
    "xinput":"XInput / Xbox",
    "generic":"Generic evdev",
}

def default_linux_mapping(family):
    family=str(family or "generic")
    # Linux evdev names face buttons by physical position. These defaults
    # reproduce SwitchNet's established positional behavior.
    mapping={
        "south":"B","east":"A","west":"Y","north":"X",
        "l":"L","r":"R","zl":"ZL","zr":"ZR",
        "minus":"-","plus":"+","l3":"L3","r3":"R3",
        "home":"HOME","capture":"CAPTURE",
        "c":"None","gl":"None","gr":"None",
        "up":"D-Pad Up","down":"D-Pad Down",
        "left":"D-Pad Left","right":"D-Pad Right",
    }
    # Preserve the Linux xpad behavior already validated by SwitchNet.
    if family=="xinput":
        mapping.update({"south":"B","east":"A","west":"X","north":"Y"})
    return mapping

def apply_switch_mapping(active_sources,mapping,strengths=None):
    strengths=strengths or {}
    out=0
    lt=rt=0
    up=down=left=right=False
    for source in active_sources:
        target=mapping.get(source,"None")
        strength=max(0,min(65535,int(strengths.get(source,65535))))
        bit=STEAM_TARGET_BUTTON_BITS.get(target)
        if bit is not None:
            out|=bit
        elif target=="ZL":
            lt=max(lt,strength)
        elif target=="ZR":
            rt=max(rt,strength)
        elif target=="D-Pad Up":up=True
        elif target=="D-Pad Down":down=True
        elif target=="D-Pad Left":left=True
        elif target=="D-Pad Right":right=True
    return out,lt,rt,hat_from_dirs(up,down,left,right)

def switch2pro_native_values(raw,dz,mapping=None):
    if raw is None:return neutral_values()
    mapping=mapping or default_linux_mapping("switch2pro")
    buttons=set(raw.get("buttons") or ())
    conv={"B":"south","A":"east","Y":"west","X":"north","L":"l","R":"r","ZL":"zl","ZR":"zr",
          "MINUS":"minus","PLUS":"plus","L3":"l3","R3":"r3","HOME":"home","CAPTURE":"capture",
          "C":"c","GL":"gl","GR":"gr","UP":"up","DOWN":"down","LEFT":"left","RIGHT":"right"}
    active={conv[x] for x in buttons if x in conv}
    out,lt,rt,hat=apply_switch_mapping(active,mapping,{"zl":65535 if "ZL" in buttons else 0,"zr":65535 if "ZR" in buttons else 0})
    cl=lambda v:max(-32768,min(32767,int(v)))
    return dict(buttons=out,lx=dead(cl(raw.get("lx",0)),dz),ly=dead(cl(raw.get("ly",0)),dz),
        rx=dead(cl(raw.get("rx",0)),dz),ry=dead(cl(raw.get("ry",0)),dz),lt=lt,rt=rt,hat=hat,
        ax=cl(raw.get("ax",0)),ay=cl(raw.get("ay",0)),az=cl(raw.get("az",4096)),
        gx=cl(raw.get("gx",0)),gy=cl(raw.get("gy",0)),gz=cl(raw.get("gz",0)),
        imu_ts=int(raw.get("imu_timestamp",0))&0xffffffff)

def linux_controller_family(vendor,product,name=""):
    vendor=int(vendor or 0);product=int(product or 0)
    name=str(name or "").lower()
    if vendor==0x054c and ("dualsense" in name or product==0x0ce6):
        return "dualsense"
    if vendor==0x18d1 or "stadia" in name:
        return "stadia"
    if vendor==0x057e and product==0x2069:
        return "switch2pro"
    if vendor==0x057e:
        return "switchpro"
    if vendor==0x045e or "xbox" in name or "x-box" in name or "xinput" in name:
        return "xinput"
    return "generic"

VALVE_VID = 0x28DE
STEAM_PIDS = (0x1302, 0x1303, 0x1304, 0x1305)
STEAM_REPORT_STATE = (0x42, 0x45)

NINTENDO_VID = 0x057E
SWITCH2_PRO_PID = 0x2069
SWITCH2_PRO_VENDOR_INTERFACE = 1

# SDL2 constants used by the lightweight ctypes binding.
SDL_INIT_GAMECONTROLLER = 0x00002000
SDL_INIT_HAPTIC = 0x00001000
SDL_INIT_SENSOR = 0x00008000
SDL_CONTROLLER_AXIS_LEFTX = 0
SDL_CONTROLLER_AXIS_LEFTY = 1
SDL_CONTROLLER_AXIS_RIGHTX = 2
SDL_CONTROLLER_AXIS_RIGHTY = 3
SDL_CONTROLLER_AXIS_TRIGGERLEFT = 4
SDL_CONTROLLER_AXIS_TRIGGERRIGHT = 5
SDL_CONTROLLER_BUTTON_A = 0
SDL_CONTROLLER_BUTTON_B = 1
SDL_CONTROLLER_BUTTON_X = 2
SDL_CONTROLLER_BUTTON_Y = 3
SDL_CONTROLLER_BUTTON_BACK = 4
SDL_CONTROLLER_BUTTON_GUIDE = 5
SDL_CONTROLLER_BUTTON_START = 6
SDL_CONTROLLER_BUTTON_LEFTSTICK = 7
SDL_CONTROLLER_BUTTON_RIGHTSTICK = 8
SDL_CONTROLLER_BUTTON_LEFTSHOULDER = 9
SDL_CONTROLLER_BUTTON_RIGHTSHOULDER = 10
SDL_CONTROLLER_BUTTON_DPAD_UP = 11
SDL_CONTROLLER_BUTTON_DPAD_DOWN = 12
SDL_CONTROLLER_BUTTON_DPAD_LEFT = 13
SDL_CONTROLLER_BUTTON_DPAD_RIGHT = 14
SDL_CONTROLLER_BUTTON_MISC1 = 15
SDL_CONTROLLER_BUTTON_TOUCHPAD = 20
SDL_SENSOR_ACCEL = 1
SDL_SENSOR_GYRO = 2


def app_config_dir() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / "SwitchNet"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cfg_path() -> Path:
    return app_config_dir() / "client-linux.ini"


def log_path() -> Path:
    return app_config_dir() / "client-linux.log"


def log_exception(context, exc):
    try:
        with log_path().open("a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {context}: {exc!r}\n")
            f.write(traceback.format_exc())
    except Exception:
        pass


def autostart_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart"
    base.mkdir(parents=True, exist_ok=True)
    return base / "switchnet-client.desktop"


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}" --startup'
    return f'"{Path(sys.executable).resolve()}" "{Path(__file__).resolve()}" --startup'


def set_autostart(enabled: bool):
    path = autostart_path()
    if not enabled:
        try: path.unlink()
        except FileNotFoundError: pass
        return
    path.write_text(
        "[Desktop Entry]\nType=Application\nName=SwitchNet Client\n"
        f"Exec={startup_command()}\nTerminal=false\nX-GNOME-Autostart-enabled=true\n"
        "Comment=SwitchNet controller client\n",
        encoding="utf-8",
    )


def autostart_enabled() -> bool:
    return autostart_path().exists()





SWITCHNET_DISCOVERY_PORT = 5455
SWITCHNET_DISCOVERY_MAGIC = b"SWITCHNET_DISCOVER_V1"
SWITCHNET_DISCOVERY_REPLY = "SWITCHNET_HERE_V1|"

def discover_switchnet(timeout=0.8):
    """Discover SwitchNet on the current LAN without requiring mDNS."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)
        sock.bind(("", 0))

        targets = [("255.255.255.255", SWITCHNET_DISCOVERY_PORT)]

        # Also broadcast to interface-specific networks when available.
        try:
            hostname = socket.gethostname()
            for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
                ip = info[4][0]
                parts = ip.split(".")
                if len(parts) == 4 and not ip.startswith("127."):
                    targets.append((
                        ".".join(parts[:3] + ["255"]),
                        SWITCHNET_DISCOVERY_PORT,
                    ))
        except Exception:
            pass

        sent = set()
        for target in targets:
            if target in sent:
                continue
            sent.add(target)
            try:
                sock.sendto(SWITCHNET_DISCOVERY_MAGIC, target)
            except OSError:
                pass

        deadline = time.monotonic() + timeout
        found = []

        while time.monotonic() < deadline:
            try:
                data, addr = sock.recvfrom(512)
            except socket.timeout:
                break
            except OSError:
                break

            try:
                message = data.decode("utf-8", "replace")
            except Exception:
                continue

            if not message.startswith(SWITCHNET_DISCOVERY_REPLY):
                continue

            parts = message.split("|")
            if len(parts) < 5:
                continue

            item = {
                "ip": parts[1] or addr[0],
                "hostname": parts[2] or "switchnet.local",
                "version": parts[3],
                "udp_port": int(parts[4]),
            }

            if not any(x["ip"] == item["ip"] for x in found):
                found.append(item)

        if found:
            return found[0]

        # mDNS/system resolver fallback.
        try:
            ip = socket.gethostbyname("switchnet.local")
            return {
                "ip": ip,
                "hostname": "switchnet.local",
                "version": "",
                "udp_port": 5454,
            }
        except OSError:
            return None
    finally:
        sock.close()



class Switch2ProUsbEnabler:
    """Enable persistent HID mode on a wired Switch 2 Pro Controller.

    The controller remains visible on the USB bus as 057e:2069 when its
    transient Linux hidraw/evdev nodes disappear.  The vendor-specific USB
    interface (interface 1, bulk OUT/IN) accepts Nintendo's initialization
    sequence and makes the standard HID interface usable again.
    """

    COMMANDS = (
        bytes([0x03,0x91,0x00,0x0D,0x00,0x08,0x00,0x00,0x01,0x00,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF]),
        bytes([0x07,0x91,0x00,0x01,0x00,0x00,0x00,0x00]),
        bytes([0x16,0x91,0x00,0x01,0x00,0x00,0x00,0x00]),
        bytes([0x15,0x91,0x00,0x01,0x00,0x0E,0x00,0x00,0x00,0x02,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF]),
        bytes([0x15,0x91,0x00,0x02,0x00,0x11,0x00,0x00,0x00,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF]),
        bytes([0x15,0x91,0x00,0x03,0x00,0x01,0x00,0x00,0x00]),
        bytes([0x09,0x91,0x00,0x07,0x00,0x08,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00]),
        bytes([0x0C,0x91,0x00,0x02,0x00,0x04,0x00,0x00,0x27,0x00,0x00,0x00]),
        bytes([0x11,0x91,0x00,0x03,0x00,0x00,0x00,0x00]),
        bytes([0x0A,0x91,0x00,0x08,0x00,0x14,0x00,0x00,0x01,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0x35,0x00,0x46,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00]),
        bytes([0x0C,0x91,0x00,0x04,0x00,0x04,0x00,0x00,0x27,0x00,0x00,0x00]),
        bytes([0x03,0x91,0x00,0x0A,0x00,0x04,0x00,0x00,0x09,0x00,0x00,0x00]),
        bytes([0x10,0x91,0x00,0x01,0x00,0x00,0x00,0x00]),
        bytes([0x01,0x91,0x00,0x0C,0x00,0x00,0x00,0x00]),
        bytes([0x03,0x91,0x00,0x01,0x00,0x00,0x00]),
        bytes([0x0A,0x91,0x00,0x02,0x00,0x04,0x00,0x00,0x03,0x00,0x00]),
        bytes([0x09,0x91,0x00,0x07,0x00,0x08,0x00,0x00,0x01,0x00,0x00,0x00,0x00,0x00,0x00,0x00]),
    )

    def __init__(self):
        self.last_attempt = 0.0
        self.last_status = "Not checked"
        self.bus = None
        self.address = None

    @staticmethod
    def dependency_available():
        return pyusb_core is not None and pyusb_util is not None

    @staticmethod
    def find_device():
        if not Switch2ProUsbEnabler.dependency_available():
            return None
        return pyusb_core.find(
            idVendor=NINTENDO_VID,
            idProduct=SWITCH2_PRO_PID,
        )

    @staticmethod
    def usb_present():
        try:
            return Switch2ProUsbEnabler.find_device() is not None
        except Exception:
            return False

    @staticmethod
    def evdev_present():
        if InputDevice is None:
            return False
        for path in list_devices() or []:
            d=None
            try:
                d=InputDevice(path)
                if (
                    int(d.info.vendor)==NINTENDO_VID and
                    int(d.info.product)==SWITCH2_PRO_PID and
                    EvdevGamepad._is_gamepad(d)
                ):
                    return True
            except Exception:
                pass
            finally:
                if d is not None:
                    try:d.close()
                    except Exception:pass
        return False

    def initialize(self):
        self.last_attempt=time.monotonic()

        if not self.dependency_available():
            self.last_status="PyUSB missing (install python-pyusb)"
            return False,self.last_status

        helper=Path(__file__).resolve().with_name(
            "switch2_pro_usb_init.py"
        )

        if not helper.exists():
            self.last_status="Switch 2 Pro USB helper missing"
            return False,self.last_status

        try:
            result=subprocess.run(
                [sys.executable,str(helper)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=7.0,
                check=False,
            )

            output=(result.stdout or "").strip()
            payload={}

            if output:
                try:
                    payload=json.loads(output.splitlines()[-1])
                except Exception:
                    payload={}

            if result.returncode==0 and payload.get("ok"):
                self.last_status=payload.get(
                    "message",
                    "HID initialization sent"
                )
                return True,self.last_status

            message=payload.get("error")
            if not message:
                message=(result.stderr or output or
                         f"helper exit {result.returncode}").strip()

            phase=payload.get("phase")
            hint=payload.get("hint")
            detail=f"Initialization failed"
            if phase:
                detail+=f" [{phase}]"
            detail+=f": {message}"
            if hint:
                detail+=f" — {hint}"
            self.last_status=detail
            return False,self.last_status

        except subprocess.TimeoutExpired:
            self.last_status=(
                "Initialization timed out after 7 s; USB helper was terminated"
            )
            return False,self.last_status
        except Exception as exc:
            self.last_status=f"Initialization failed: {exc}"
            return False,self.last_status


class EvdevImu:
    """Companion motion-sensor node created by Linux hid-nintendo."""

    def __init__(self):
        self.dev = None
        self.path = ""
        self.name = ""
        self.axis = {}
        self.absinfo = {}
        self.source_family = "generic"
        self.last_timestamp_us = 0
        self.last_report_at = 0.0
        self.reports_total = 0
        self.last_error = ""

    def close(self):
        if self.dev is not None:
            try:
                self.dev.close()
            except Exception:
                pass
        self.dev = None
        self.path = ""
        self.name = ""
        self.axis = {}
        self.absinfo = {}
        self.source_family = "generic"
        self.last_timestamp_us = 0
        self.last_report_at = 0.0

    @staticmethod
    def _same_identity(gamepad, candidate):
        try:
            same_phys = bool(gamepad.phys) and gamepad.phys == candidate.phys
            same_uniq = bool(gamepad.uniq) and gamepad.uniq == candidate.uniq
            same_id = (
                gamepad.info.bustype == candidate.info.bustype and
                gamepad.info.vendor == candidate.info.vendor and
                gamepad.info.product == candidate.info.product
            )
            return same_phys or same_uniq or same_id
        except Exception:
            return False

    def attach_for_gamepad(self, gamepad):
        self.close()
        if InputDevice is None or gamepad is None:
            return False

        gamepad_name=(gamepad.name or "")
        gamepad_vendor=int(getattr(gamepad.info,"vendor",0) or 0)
        expected = gamepad_name + " (IMU)"
        matches = []
        for path in sorted(list_devices() or []):
            d = None
            try:
                d = InputDevice(path)
                name = d.name or ""
                lname=name.lower()
                caps=d.capabilities(absinfo=False)
                abses=set(caps.get(ecodes.EV_ABS,[]))
                motion_axes={
                    ecodes.ABS_X,ecodes.ABS_Y,ecodes.ABS_Z,
                    ecodes.ABS_RX,ecodes.ABS_RY,ecodes.ABS_RZ,
                }
                has_motion_axes=motion_axes.issubset(abses)
                is_motion_node=(
                    "(imu)" in lname
                    or "motion sensors" in lname
                    or (
                        int(getattr(gamepad.info,"vendor",0) or 0)==0x054c
                        and has_motion_axes
                        and not EvdevGamepad._is_gamepad(d)
                    )
                )
                if not is_motion_node or not self._same_identity(gamepad, d):
                    d.close()
                    continue
                score = 0
                if name == expected:
                    score += 30
                if "motion sensors" in lname and gamepad_vendor==0x054c:
                    score += 30
                if gamepad.phys and d.phys == gamepad.phys:
                    score += 20
                if gamepad.uniq and d.uniq == gamepad.uniq:
                    score += 10
                matches.append((score, path, d))
            except Exception:
                if d is not None:
                    try:
                        d.close()
                    except Exception:
                        pass

        if not matches:
            self.last_error = "IMU not found"
            return False

        matches.sort(key=lambda x: x[0], reverse=True)
        _, self.path, self.dev = matches[0]
        for _, _, d in matches[1:]:
            try:
                d.close()
            except Exception:
                pass
        self.name = self.dev.name or Path(self.path).name
        self.last_error = ""

        vendor=int(getattr(gamepad.info,"vendor",0) or 0)
        lname=self.name.lower()
        if vendor==0x054c or "motion sensors" in lname:
            self.source_family="playstation"
        elif vendor==0x057e or "(imu)" in lname:
            self.source_family="nintendo"
        else:
            self.source_family="generic"

        self.absinfo={}
        for code in (
            ecodes.ABS_X, ecodes.ABS_Y, ecodes.ABS_Z,
            ecodes.ABS_RX, ecodes.ABS_RY, ecodes.ABS_RZ,
        ):
            try:
                info = self.dev.absinfo(code)
                if info is not None:
                    self.absinfo[code]=info
                    self.axis[code] = int(info.value)
            except Exception:
                pass
        return True

    def poll(self, max_batches=8):
        if self.dev is None:
            return 0
        count = 0
        batches = 0
        try:
            while batches < max_batches:
                try:
                    events = self.dev.read()
                    batches += 1
                    for ev in events:
                        if ev.type == ecodes.EV_ABS:
                            self.axis[ev.code] = int(ev.value)
                            count += 1
                        elif (
                            ev.type == ecodes.EV_MSC and
                            ev.code == getattr(ecodes, "MSC_TIMESTAMP", 5)
                        ):
                            self.last_timestamp_us = int(ev.value) & 0xffffffff
                except BlockingIOError:
                    break
            if count:
                self.reports_total += count
                self.last_report_at = time.monotonic()
            return count
        except OSError as exc:
            if getattr(exc, "errno", None) == 11:
                return count
            self.last_error = f"IMU READ ERROR: {exc}"
            self.close()
            return 0

    def values(self, do_poll=True):
        if do_poll:
            self.poll()
        if self.dev is None:
            return None

        def clamp16(v):
            return max(-32768,min(32767,int(round(v))))

        def resolution(code,fallback):
            info=self.absinfo.get(code)
            try:
                r=int(getattr(info,"resolution",0) or 0)
            except Exception:
                r=0
            return r if r>0 else fallback

        raw_ax=self.axis.get(ecodes.ABS_X,0)
        raw_ay=self.axis.get(ecodes.ABS_Y,0)
        raw_az=self.axis.get(ecodes.ABS_Z,0)
        raw_gx=self.axis.get(ecodes.ABS_RX,0)
        raw_gy=self.axis.get(ecodes.ABS_RY,0)
        raw_gz=self.axis.get(ecodes.ABS_RZ,0)

        if self.source_family=="playstation":
            # hid-playstation already publishes factory-calibrated motion in
            # the DualSense coordinate frame. Match the Windows client that
            # was previously validated against Nintendo motion controls:
            #
            #   Switch X <- +Sony Y
            #   Switch Y <- -Sony X
            #   Switch Z <- +Sony Z
            #
            # Apply that proper rotation to BOTH acceleration and angular
            # velocity, while converting calibrated Linux units into Nintendo
            # Pro-controller units.
            arx=resolution(ecodes.ABS_X,8192)
            ary=resolution(ecodes.ABS_Y,8192)
            arz=resolution(ecodes.ABS_Z,8192)
            grx=resolution(ecodes.ABS_RX,1024)
            gry=resolution(ecodes.ABS_RY,1024)
            grz=resolution(ecodes.ABS_RZ,1024)

            sony_ax=raw_ax*(4096.0/arx)
            sony_ay=raw_ay*(4096.0/ary)
            sony_az=raw_az*(4096.0/arz)
            sony_gx=raw_gx*(16.384/grx)
            sony_gy=raw_gy*(16.384/gry)
            sony_gz=raw_gz*(16.384/grz)

            ax=clamp16(+sony_ay)
            ay=clamp16(-sony_ax)
            az=clamp16(+sony_az)

            gx=clamp16(+sony_gy)
            gy=clamp16(-sony_gx)
            gz=clamp16(+sony_gz)
        elif self.source_family=="nintendo":
            ax=clamp16(raw_ax)
            ay=clamp16(raw_ay)
            az=clamp16(raw_az if raw_az else 4096)
            gx=clamp16(raw_gx/1000.0)
            gy=clamp16(raw_gy/1000.0)
            gz=clamp16(raw_gz/1000.0)
        else:
            arx=resolution(ecodes.ABS_X,4096)
            ary=resolution(ecodes.ABS_Y,4096)
            arz=resolution(ecodes.ABS_Z,4096)
            grx=resolution(ecodes.ABS_RX,16)
            gry=resolution(ecodes.ABS_RY,16)
            grz=resolution(ecodes.ABS_RZ,16)
            ax=clamp16(raw_ax*(4096.0/arx))
            ay=clamp16(raw_ay*(4096.0/ary))
            az=clamp16(raw_az*(4096.0/arz))
            gx=clamp16(raw_gx*(16.384/grx))
            gy=clamp16(raw_gy*(16.384/gry))
            gz=clamp16(raw_gz*(16.384/grz))

        ts=self.last_timestamp_us or (
            int(time.monotonic_ns()/1000)&0xffffffff
        )
        return dict(
            ax=ax,ay=ay,az=az,
            gx=gx,gy=gy,gz=gz,
            imu_ts=ts,
        )


class EvdevTouchpadButton:
    """Companion evdev device for PlayStation touchpad click.

    hid-playstation creates a separate "... Touchpad" input node and reports
    the physical pad click as BTN_LEFT. Keep its state independently and merge
    it into the logical gamepad state as Nintendo Capture.
    """

    def __init__(self):
        self.dev = None
        self.path = ""
        self.name = ""
        self.pressed = False
        self.last_error = ""
        self.reports_total = 0

    def close(self):
        if self.dev is not None:
            try:
                self.dev.close()
            except Exception:
                pass
        self.dev = None
        self.path = ""
        self.name = ""
        self.pressed = False

    @staticmethod
    def _same_identity(gamepad, candidate):
        try:
            same_phys = bool(gamepad.phys) and gamepad.phys == candidate.phys
            same_uniq = bool(gamepad.uniq) and gamepad.uniq == candidate.uniq
            same_id = (
                gamepad.info.bustype == candidate.info.bustype and
                gamepad.info.vendor == candidate.info.vendor and
                gamepad.info.product == candidate.info.product
            )
            return same_phys or same_uniq or same_id
        except Exception:
            return False

    def attach_for_gamepad(self, gamepad):
        self.close()
        if InputDevice is None or gamepad is None:
            return False

        matches = []
        for path in sorted(list_devices() or []):
            d = None
            try:
                d = InputDevice(path)
                name = d.name or ""
                caps = d.capabilities(absinfo=False)
                keys = set(caps.get(ecodes.EV_KEY, []))
                if (
                    "touchpad" not in name.lower()
                    or getattr(ecodes, "BTN_LEFT", 0x110) not in keys
                    or not self._same_identity(gamepad, d)
                ):
                    d.close()
                    continue
                score = 0
                if gamepad.phys and d.phys == gamepad.phys:
                    score += 20
                if gamepad.uniq and d.uniq == gamepad.uniq:
                    score += 10
                if "dualsense" in name.lower():
                    score += 5
                matches.append((score, path, d))
            except Exception:
                if d is not None:
                    try:
                        d.close()
                    except Exception:
                        pass

        if not matches:
            self.last_error = "Touchpad button device not found"
            return False

        matches.sort(key=lambda x: x[0], reverse=True)
        _, self.path, self.dev = matches[0]
        for _, _, d in matches[1:]:
            try:
                d.close()
            except Exception:
                pass

        self.name = self.dev.name or Path(self.path).name
        try:
            self.pressed = getattr(ecodes, "BTN_LEFT", 0x110) in set(self.dev.active_keys())
        except Exception:
            self.pressed = False
        self.last_error = ""
        return True

    def poll(self, max_batches=4):
        if self.dev is None:
            return 0
        reports = 0
        batches = 0
        try:
            while batches < max_batches:
                try:
                    events = self.dev.read()
                    batches += 1
                    for ev in events:
                        if ev.type == ecodes.EV_KEY and ev.code == getattr(ecodes, "BTN_LEFT", 0x110):
                            self.pressed = bool(ev.value)
                        elif ev.type == ecodes.EV_SYN and ev.code == getattr(ecodes, "SYN_REPORT", 0):
                            reports += 1
                except BlockingIOError:
                    break
            self.reports_total += reports
            return reports
        except OSError as exc:
            if getattr(exc, "errno", None) == 11:
                return reports
            self.last_error = f"TOUCHPAD READ ERROR: {exc}"
            self.close()
            return reports



def resolve_evdev_controller_path(vendor,product,family="generic",preferred_path=""):
    """Return the current usable evdev node for a physical controller.

    /dev/input/eventN is not a stable identifier. Nintendo Switch 2 Pro USB
    initialization can re-enumerate the HID interface and replace eventN while
    the logical controller remains the same.
    """
    if InputDevice is None:
        return ""

    vendor=int(vendor or 0)
    product=int(product or 0)
    family=str(family or "generic")
    preferred_path=str(preferred_path or "")

    candidates=[]
    for path in sorted(list_devices() or []):
        dev=None
        try:
            dev=InputDevice(path)
            dv=int(getattr(dev.info,"vendor",0) or 0)
            dp=int(getattr(dev.info,"product",0) or 0)
            if vendor and dv!=vendor:
                continue
            if product and dp!=product:
                continue
            if not EvdevGamepad._is_gamepad(dev):
                continue

            score=0
            if path==preferred_path:
                score+=100
            detected_family=linux_controller_family(
                dv,dp,dev.name or ""
            )
            if detected_family==family:
                score+=40

            # Prefer the collection that exposes both sticks when multiple
            # 057e:2069 evdev collections are present.
            caps=dev.capabilities(absinfo=False)
            abses=set(caps.get(ecodes.EV_ABS,[]))
            if {
                getattr(ecodes,"ABS_X",-1),
                getattr(ecodes,"ABS_Y",-1),
            }.issubset(abses):
                score+=20
            if {
                getattr(ecodes,"ABS_RX",-1),
                getattr(ecodes,"ABS_RY",-1),
            }.issubset(abses):
                score+=20

            candidates.append((score,path))
        except Exception:
            pass
        finally:
            if dev is not None:
                try:dev.close()
                except Exception:pass

    if not candidates:
        return ""
    candidates.sort(key=lambda item:(item[0],item[1]),reverse=True)
    return candidates[0][1]


class EvdevGamepad:
    """Persistent evdev backend selected by exact /dev/input/event* path."""

    def __init__(self):
        self.dev = None
        self.path = ""
        self.name = ""
        self.absinfo = {}
        self.axis = {}
        self.keys = set()
        self.ff_effect_id = None
        self.last_rumble = (0, 0)
        self.imu = EvdevImu()
        self.touchpad = EvdevTouchpadButton()
        self.last_open_attempt = 0.0
        self.last_error = ""
        self.last_input_at = 0.0
        self.reports_total = 0

    @staticmethod
    def _is_gamepad(dev):
        try:
            caps = dev.capabilities(absinfo=False)
            keys = set(caps.get(ecodes.EV_KEY, []))
            abses = set(caps.get(ecodes.EV_ABS, []))
            gamepad_keys = {
                getattr(ecodes, "BTN_GAMEPAD", -1),
                getattr(ecodes, "BTN_SOUTH", -1),
                getattr(ecodes, "BTN_A", -1),
            }
            if bool(keys & gamepad_keys) and bool(abses):
                return True
            vendor=int(getattr(dev.info,"vendor",0) or 0)
            product=int(getattr(dev.info,"product",0) or 0)
            if vendor==NINTENDO_VID and product==SWITCH2_PRO_PID:
                stick_or_hat={
                    getattr(ecodes,"ABS_X",-1),getattr(ecodes,"ABS_Y",-1),
                    getattr(ecodes,"ABS_HAT0X",-1),getattr(ecodes,"ABS_HAT0Y",-1),
                }
                return bool(keys) and bool(abses & stick_or_hat)
            return False
        except Exception:
            return False

    @classmethod
    def controllers(cls):
        if InputDevice is None:
            return []
        out = []
        for path in sorted(list_devices() or []):
            try:
                d = InputDevice(path)
                if cls._is_gamepad(d):
                    out.append((path, d.name or Path(path).name))
                d.close()
            except Exception:
                pass
        return out

    def _classify_error(self, exc):
        if isinstance(exc, PermissionError):
            return f"PERMISSION DENIED: {self.path or '?'}"
        if isinstance(exc, FileNotFoundError):
            return f"DISCONNECTED: {self.path or '?'}"
        return f"OPEN/READ ERROR: {exc}"

    def open_path(self, path):
        self.close(clear_path=False)
        self.path = str(path or "")
        self.last_open_attempt = time.monotonic()
        if not self.path:
            self.last_error = "No evdev controller selected"
            return False
        try:
            self.dev = InputDevice(self.path)
            if not self._is_gamepad(self.dev):
                raise RuntimeError("the selected device is not a gamepad")
            self.name = self.dev.name or Path(self.path).name
            self.absinfo = {}
            for code in self.dev.capabilities(absinfo=False).get(ecodes.EV_ABS, []):
                try:
                    self.absinfo[code] = self.dev.absinfo(code)
                except Exception:
                    pass
            self.axis = {}
            self.keys = set()
            try:
                self.keys.update(self.dev.active_keys())
            except Exception:
                pass
            for code, info in self.absinfo.items():
                self.axis[code] = int(info.value)
            self.last_error = ""
            self.last_input_at = time.monotonic()
            self.imu.attach_for_gamepad(self.dev)
            try:
                touchpad=getattr(self,"touchpad",None)
                if touchpad is None:
                    self.touchpad=EvdevTouchpadButton()
                    touchpad=self.touchpad
                touchpad.attach_for_gamepad(self.dev)
            except Exception as exc:
                # Capture support is optional and must not take down normal
                # controller input if the companion node cannot be opened.
                self.last_error=f"Touchpad companion unavailable: {exc}"
            return True
        except Exception as exc:
            self.last_error = self._classify_error(exc)
            if self.dev is not None:
                try:
                    self.dev.close()
                except Exception:
                    pass
            self.dev = None
            return False

    def ensure_path(self, path):
        path = str(path or "")
        if self.dev is not None and self.path == path:
            return True
        if self.dev is not None and self.path != path:
            self.close(clear_path=False)
        now = time.monotonic()
        if now - self.last_open_attempt < 1.0:
            return False
        return self.open_path(path)

    def close(self, clear_path=True):
        if self.dev is not None:
            try:
                if self.ff_effect_id is not None:
                    self.dev.erase_effect(self.ff_effect_id)
            except Exception:
                pass
            try:
                self.dev.close()
            except Exception:
                pass
        self.dev = None
        self.name = ""
        self.ff_effect_id = None
        self.last_rumble = (0, 0)
        try:
            self.imu.close()
        except Exception:
            pass
        try:
            touchpad=getattr(self,"touchpad",None)
            if touchpad is not None:
                touchpad.close()
        except Exception:
            pass
        if clear_path:
            self.path = ""

    def _resync_state(self):
        """Re-read kernel state after SYN_DROPPED to prevent stuck buttons."""
        if self.dev is None:
            return
        try:
            self.keys=set(self.dev.active_keys())
        except Exception:
            pass
        for code in list(self.absinfo.keys()):
            try:
                info=self.dev.absinfo(code)
                if info is not None:
                    self.absinfo[code]=info
                    self.axis[code]=int(info.value)
            except Exception:
                pass

    def poll(self):
        """Drain pending evdev events and keep only the newest full state."""
        if self.dev is None:
            return 0
        reports=0
        changed=False
        dropped=False
        try:
            while True:
                try:
                    events=self.dev.read()
                    for ev in events:
                        if ev.type==ecodes.EV_SYN:
                            if ev.code==getattr(ecodes,"SYN_DROPPED",3):
                                dropped=True
                            elif ev.code==getattr(ecodes,"SYN_REPORT",0):
                                reports+=1
                            continue
                        if ev.type==ecodes.EV_KEY:
                            changed=True
                            if ev.value:
                                self.keys.add(ev.code)
                            else:
                                self.keys.discard(ev.code)
                        elif ev.type==ecodes.EV_ABS:
                            changed=True
                            self.axis[ev.code]=int(ev.value)
                except BlockingIOError:
                    break

            if dropped:
                self._resync_state()
                changed=True
                reports=max(1,reports)

            if changed:
                self.last_input_at=time.monotonic()
            if reports:
                self.reports_total+=reports
            elif changed:
                # Some devices don't emit the expected SYN_REPORT through
                # every driver path. Count a state transition as one report.
                self.reports_total+=1
                reports=1
            return reports
        except BlockingIOError:
            return reports
        except OSError as exc:
            if getattr(exc,"errno",None)==11:
                return reports
            self.last_error=self._classify_error(exc)
            self.close(clear_path=False)
            return 0

    def input_age_ms(self):
        if not self.last_input_at:
            return -1
        return max(0, int((time.monotonic() - self.last_input_at) * 1000))

    def status(self):
        if self.dev is not None:
            return f"OPEN: {self.path}"
        return self.last_error or f"DISCONNECTED: {self.path or '?'}"

    def _pressed(self, *names):
        for name in names:
            code = getattr(ecodes, name, None)
            if code is not None and code in self.keys:
                return True
        return False

    def _signed_axis(self, name):
        code = getattr(ecodes, name, None)
        if code is None or code not in self.axis:
            return 0
        raw = self.axis.get(code, 0)
        info = self.absinfo.get(code)
        if info is None or info.max == info.min:
            return max(-32768, min(32767, raw))
        center = (info.min + info.max) / 2.0
        span = max(1.0, (info.max - info.min) / 2.0)
        v = int(round((raw - center) / span * 32767.0))
        return max(-32768, min(32767, v))

    def _trigger(self, *names):
        for name in names:
            code = getattr(ecodes, name, None)
            if code is None or code not in self.axis:
                continue
            raw = self.axis.get(code, 0)
            info = self.absinfo.get(code)
            if info is None or info.max == info.min:
                continue
            # A trigger is an unsigned/non-negative range. Signed Z/RZ axes on
            # generic HID gamepads are usually the right stick, not triggers.
            if info.min < 0:
                continue
            f = (raw - info.min) / float(info.max - info.min)
            return max(0, min(65535, int(round(f * 65535.0))))
        return 0

    def controller_family(self):
        name=self.name or ""
        try:
            vendor=int(self.dev.info.vendor) if self.dev is not None else 0
            product=int(self.dev.info.product) if self.dev is not None else 0
        except Exception:
            vendor=product=0
        return linux_controller_family(vendor,product,name)

    def values(self, dz, labels=False, do_poll=True, mapping=None, family=None):
        if do_poll:
            self.poll()
        if self.dev is None:
            return neutral_values()

        family=family or self.controller_family()
        mapping=mapping or default_linux_mapping(family)
        active=set()
        strengths={}

        if self._pressed("BTN_SOUTH"):active.add("south")
        if self._pressed("BTN_EAST"):active.add("east")
        if self._pressed("BTN_WEST"):active.add("west")
        if self._pressed("BTN_NORTH"):active.add("north")

        if self._pressed("BTN_TL"):active.add("l")
        if self._pressed("BTN_TR"):active.add("r")
        if self._pressed("BTN_SELECT","BTN_BACK"):active.add("minus")
        if self._pressed("BTN_START"):active.add("plus")
        if self._pressed("BTN_THUMBL"):active.add("l3")
        if self._pressed("BTN_THUMBR"):active.add("r3")
        if self._pressed("BTN_MODE","BTN_GUIDE"):active.add("home")

        touchpad_pressed=bool(
            getattr(getattr(self,"touchpad",None),"pressed",False)
        )
        if (
            touchpad_pressed
            or self._pressed("BTN_TOUCHPAD","BTN_TOUCH","BTN_MISC","BTN_Z")
        ):
            active.add("capture")

        lt=self._trigger("ABS_BRAKE","ABS_Z")
        rt=self._trigger("ABS_GAS","ABS_RZ")
        if self._pressed("BTN_TL2"):lt=65535
        if self._pressed("BTN_TR2"):rt=65535
        if lt>4096:
            active.add("zl");strengths["zl"]=lt
        if rt>4096:
            active.add("zr");strengths["zr"]=rt

        hx=self.axis.get(getattr(ecodes,"ABS_HAT0X",-999),0)
        hy=self.axis.get(getattr(ecodes,"ABS_HAT0Y",-999),0)
        if hy<0 or self._pressed("BTN_DPAD_UP"):active.add("up")
        if hy>0 or self._pressed("BTN_DPAD_DOWN"):active.add("down")
        if hx<0 or self._pressed("BTN_DPAD_LEFT"):active.add("left")
        if hx>0 or self._pressed("BTN_DPAD_RIGHT"):active.add("right")

        # Best-effort Switch 2 Pro extras. Kernel mappings may evolve; these
        # are intentionally family-gated to avoid stealing generic buttons.
        if family=="switch2pro":
            if self._pressed("BTN_C"):active.add("c")
            if self._pressed("BTN_TRIGGER_HAPPY1"):active.add("gl")
            if self._pressed("BTN_TRIGGER_HAPPY2"):active.add("gr")

        out,mapped_lt,mapped_rt,hat=apply_switch_mapping(
            active,mapping,strengths
        )

        imu=self.imu.values(do_poll=do_poll)
        if imu is None:
            imu=dict(
                ax=0,ay=0,az=4096,
                gx=0,gy=0,gz=0,
                imu_ts=int(time.monotonic_ns()/1000)&0xffffffff,
            )

        return dict(
            buttons=out,
            lx=dead(self._signed_axis("ABS_X"),dz),
            ly=dead(self._signed_axis("ABS_Y"),dz),
            rx=dead(
                self._signed_axis("ABS_RX")
                if getattr(ecodes,"ABS_RX",-1) in self.axis
                else self._signed_axis("ABS_Z"),dz),
            ry=dead(
                self._signed_axis("ABS_RY")
                if getattr(ecodes,"ABS_RY",-1) in self.axis
                else self._signed_axis("ABS_RZ"),dz),
            lt=mapped_lt,rt=mapped_rt,hat=hat,
            **imu,
        )

    def rumble(self, left, right, ms=100):
        if self.dev is None or ff is None:
            return False
        left = max(0, min(65535, int(left)))
        right = max(0, min(65535, int(right)))
        try:
            caps = self.dev.capabilities(absinfo=False)
            if ecodes.EV_FF not in caps or ecodes.FF_RUMBLE not in caps.get(ecodes.EV_FF, []):
                return False
            if self.ff_effect_id is not None:
                try:
                    self.dev.erase_effect(self.ff_effect_id)
                except Exception:
                    pass
                self.ff_effect_id = None
            effect = ff.Effect(
                ecodes.FF_RUMBLE, -1, 0,
                ff.Trigger(0, 0),
                ff.Replay(max(1, int(ms)), 0),
                ff.EffectType(ff_rumble_effect=ff.Rumble(
                    strong_magnitude=left, weak_magnitude=right)),
            )
            self.ff_effect_id = self.dev.upload_effect(effect)
            self.dev.write(ecodes.EV_FF, self.ff_effect_id, 1)
            self.dev.syn()
            self.last_rumble = (left, right)
            return True
        except Exception:
            return False


class SdlRumbleOutput:
    """SDL2 is used only as an output fallback for rumble.

    Input remains pure evdev/hidraw. This avoids reintroducing SDL event-pump
    latency while taking advantage of SDL's controller-specific haptic backends.
    """
    SDL_INIT_GAMECONTROLLER = 0x00002000
    SDL_INIT_HAPTIC = 0x00001000

    def __init__(self):
        self.lib=None
        self.handle=None
        self.index=-1
        self.name=""
        self.last_error=""
        self.available=False
        self._load()

    def _load(self):
        import ctypes
        import ctypes.util
        path=ctypes.util.find_library("SDL2-2.0") or ctypes.util.find_library("SDL2")
        if not path:
            self.last_error="SDL2 not found"
            return
        try:
            lib=ctypes.CDLL(path)
            lib.SDL_InitSubSystem.argtypes=[ctypes.c_uint32]
            lib.SDL_InitSubSystem.restype=ctypes.c_int
            lib.SDL_NumJoysticks.restype=ctypes.c_int
            lib.SDL_IsGameController.argtypes=[ctypes.c_int]
            lib.SDL_IsGameController.restype=ctypes.c_int
            lib.SDL_GameControllerOpen.argtypes=[ctypes.c_int]
            lib.SDL_GameControllerOpen.restype=ctypes.c_void_p
            lib.SDL_GameControllerClose.argtypes=[ctypes.c_void_p]
            lib.SDL_GameControllerName.argtypes=[ctypes.c_void_p]
            lib.SDL_GameControllerName.restype=ctypes.c_char_p
            lib.SDL_GameControllerRumble.argtypes=[
                ctypes.c_void_p,ctypes.c_uint16,ctypes.c_uint16,ctypes.c_uint32
            ]
            lib.SDL_GameControllerRumble.restype=ctypes.c_int
            lib.SDL_GetError.restype=ctypes.c_char_p
            if lib.SDL_InitSubSystem(
                self.SDL_INIT_GAMECONTROLLER|self.SDL_INIT_HAPTIC
            )!=0:
                err=lib.SDL_GetError()
                self.last_error=err.decode(errors="replace") if err else "SDL_InitSubSystem"
                return
            self.lib=lib
            self.available=True
        except Exception as exc:
            self.last_error=f"SDL2 load: {exc}"
            self.lib=None
            self.available=False

    def _error(self):
        if self.lib is None:
            return self.last_error
        try:
            raw=self.lib.SDL_GetError()
            return raw.decode(errors="replace") if raw else "SDL2 error"
        except Exception:
            return "SDL2 error"

    def close(self):
        if self.handle and self.lib:
            try:self.lib.SDL_GameControllerRumble(self.handle,0,0,0)
            except Exception:pass
            try:self.lib.SDL_GameControllerClose(self.handle)
            except Exception:pass
        self.handle=None
        self.index=-1
        self.name=""

    @staticmethod
    def _norm(s):
        return "".join(ch.lower() for ch in (s or "") if ch.isalnum())

    def ensure_for_name(self,evdev_name):
        if not self.available or self.lib is None:
            return False

        target=self._norm(evdev_name)
        if self.handle is not None:
            # Keep an already-open matching output handle.
            if not target or target in self._norm(self.name) or self._norm(self.name) in target:
                return True
            self.close()

        try:
            count=self.lib.SDL_NumJoysticks()
            best=None
            for idx in range(max(0,count)):
                if not self.lib.SDL_IsGameController(idx):
                    continue
                h=self.lib.SDL_GameControllerOpen(idx)
                if not h:
                    continue
                raw=self.lib.SDL_GameControllerName(h)
                name=raw.decode(errors="replace") if raw else f"Controller {idx}"
                norm=self._norm(name)
                score=0
                if target and norm==target: score=100
                elif target and (target in norm or norm in target): score=80
                elif "nintendo" in target and ("nintendo" in norm or "procontroller" in norm): score=60
                elif ("xbox" in target or "xbox360" in target) and ("xbox" in norm or "x-box" in name.lower()): score=60

                if best is None or score>best[0]:
                    if best is not None:
                        self.lib.SDL_GameControllerClose(best[2])
                    best=(score,idx,h,name)
                else:
                    self.lib.SDL_GameControllerClose(h)

            if best is None:
                self.last_error="no SDL2 controller available"
                return False

            self.index=best[1]
            self.handle=best[2]
            self.name=best[3]
            self.last_error=""
            return True
        except Exception as exc:
            self.last_error=f"SDL2 open: {exc}"
            self.close()
            return False

    def rumble(self,left,right,ms=120):
        if self.handle is None or self.lib is None:
            return False
        try:
            rc=self.lib.SDL_GameControllerRumble(
                self.handle,
                max(0,min(65535,int(left))),
                max(0,min(65535,int(right))),
                max(1,int(ms))
            )
            if rc==0:
                self.last_error=""
                return True
            self.last_error=f"SDL rumble: {self._error()}"
            return False
        except Exception as exc:
            self.last_error=f"SDL rumble: {exc}"
            return False

class EvdevRumbleOutput:
    """Independent force-feedback output fd with explicit capability diagnostics."""

    def __init__(self):
        self.dev=None
        self.path=""
        self.effect_id=None
        self.last_error=""
        self.last_values=(-1,-1)
        self.ff_supported=False
        self.ff_caps=[]

    def close(self):
        if self.dev is not None:
            if self.effect_id is not None:
                try:
                    self.dev.write(ecodes.EV_FF,self.effect_id,0)
                    self.dev.syn()
                except Exception:
                    pass
                try:self.dev.erase_effect(self.effect_id)
                except Exception:pass
            try:self.dev.close()
            except Exception:pass
        self.dev=None
        self.path=""
        self.effect_id=None
        self.last_values=(-1,-1)
        self.ff_supported=False
        self.ff_caps=[]

    def ensure_path(self,path):
        path=str(path or "")
        if self.dev is not None and self.path==path:
            return self.ff_supported

        self.close()
        if not path or InputDevice is None:
            self.last_error="no evdev path"
            return False

        try:
            d=InputDevice(path)
            caps=d.capabilities(absinfo=False)
            ff_caps=list(caps.get(ecodes.EV_FF,[]))
            self.ff_caps=ff_caps
            if ecodes.FF_RUMBLE not in ff_caps:
                d.close()
                self.last_error=(
                    "FF_RUMBLE unavailable on input device "
                    f"({Path(path).name}); caps={ff_caps}"
                )
                return False
            self.dev=d
            self.path=path
            self.ff_supported=True
            self.last_error=""
            return True
        except Exception as exc:
            self.last_error=f"FF open: {exc}"
            self.close()
            return False

    def _effect(self,left,right):
        return ff.Effect(
            ecodes.FF_RUMBLE,
            self.effect_id if self.effect_id is not None else -1,
            0,
            ff.Trigger(0,0),
            ff.Replay(500,0),
            ff.EffectType(ff_rumble_effect=ff.Rumble(
                strong_magnitude=max(0,min(65535,int(left))),
                weak_magnitude=max(0,min(65535,int(right)))
            ))
        )

    def rumble(self,left,right):
        if self.dev is None or not self.ff_supported:
            return False

        left=max(0,min(65535,int(left)))
        right=max(0,min(65535,int(right)))

        try:
            if left==0 and right==0:
                if self.effect_id is not None:
                    self.dev.write(ecodes.EV_FF,self.effect_id,0)
                    self.dev.syn()
                self.last_values=(0,0)
                self.last_error=""
                return True

            self.effect_id=self.dev.upload_effect(self._effect(left,right))
            self.dev.write(ecodes.EV_FF,self.effect_id,1)
            self.dev.syn()
            self.last_values=(left,right)
            self.last_error=""
            return True
        except Exception as exc:
            self.last_error=f"FF_RUMBLE runtime: {exc}"
            self.effect_id=None
            return False



class SteamRumbleOutput:
    """Independent hidraw write fd, isolated from the Steam input reader."""
    def __init__(self):
        self.fd=None
        self.path=""

    def close(self):
        if self.fd is not None:
            try:os.close(self.fd)
            except OSError:pass
        self.fd=None
        self.path=""

    def ensure_path(self,path):
        path=str(path or "")
        if self.fd is not None and self.path==path:
            return True
        self.close()
        if not path:
            return False
        try:
            self.fd=os.open(path,os.O_RDWR|os.O_NONBLOCK)
            self.path=path
            return True
        except OSError:
            self.close()
            return False

    def rumble(self,left,right):
        if self.fd is None:
            return False
        ok=True
        left=round(max(0,min(65535,int(left)))*0.45)
        right=round(max(0,min(65535,int(right)))*0.45)
        for actuator,strength in ((2,left),(4,right)):
            data=bytearray(64);data[0]=0x83;data[1]=actuator
            if strength<=0:
                data[2]=0x80;data[6]=0x80
            else:
                gain=max(-127,min(127,round((strength/65535.0)*255.0-128.0)))
                freq=113
                data[2]=gain&0xff;data[3]=freq&0xff;data[4]=(freq>>8)&0xff
                data[5]=0xff;data[6]=0x7f
            try:
                ok=(os.write(self.fd,data)==64) and ok
            except OSError:
                ok=False
        return ok


def _IOC(direction, type_, nr, size):
    return (direction << 30) | (ord(type_) << 8) | nr | (size << 16)

def HIDIOCSFEATURE(length): return _IOC(3, 'H', 0x06, length)


def enumerate_hidraw(vid=None, pids=()):
    result = []
    for entry in Path("/sys/class/hidraw").glob("hidraw*"):
        try:
            text = (entry / "device" / "uevent").read_text(errors="ignore")
        except Exception:
            continue
        props = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
        hid_id = props.get("HID_ID", "")
        parts = hid_id.split(":")
        if len(parts) != 3: continue
        try:
            v = int(parts[1], 16); p = int(parts[2], 16)
        except ValueError: continue
        if vid is not None and v != vid: continue
        if pids and p not in pids: continue
        result.append((f"/dev/{entry.name}", v, p, props.get("HID_NAME", "HID")))
    return result


def _linux_evdev_identity(dev):
    """Stable-ish physical identity, independent from /dev/input/eventN."""
    info=getattr(dev,"info",None)
    vendor=int(getattr(info,"vendor",0) or 0)
    product=int(getattr(info,"product",0) or 0)
    uniq=str(getattr(dev,"uniq","") or "").strip()
    phys=str(getattr(dev,"phys","") or "").strip()
    name=str(getattr(dev,"name","") or "Gamepad").strip()
    anchor=uniq or phys or name
    return f"evdev:{vendor:04x}:{product:04x}:{anchor}"


def _steam_physical_anchor(props, path):
    """Group the several hidraw interfaces exposed by one Steam device.

    A Steam Controller / receiver exposes multiple HID collections.  Only one
    of them carries the state reports SwitchNet wants, so the roster must model
    the *physical controller* rather than a particular /dev/hidrawN node.
    """
    uniq=(props.get("HID_UNIQ","") or "").strip()
    phys=(props.get("HID_PHYS","") or "").strip()
    if uniq:
        return "uniq:"+uniq
    if phys:
        # Typical values end in /input0, /input1, ... for HID collections of
        # the same USB device. Strip that collection suffix.
        base=re.sub(r"/input\d+$","",phys)
        return "phys:"+base
    # Last-resort stable-enough anchor when the kernel exposes neither value.
    return "path:"+str(Path(path).parent)


def discover_supported_controllers_linux(include_keyboard=False):
    """Return every supported physical controller as a unified descriptor.

    Steam controllers are represented as logical devices containing every
    matching hidraw collection for the same physical USB receiver/controller.
    The Steam backend then probes those candidates and opens the collection
    that actually emits Steam state reports.

    Other Linux gamepads use evdev. Valve evdev nodes are intentionally skipped
    to avoid exposing the same physical Steam device twice.
    """
    found=[]
    seen=set()
    steam_groups={}

    for entry in sorted(Path('/sys/class/hidraw').glob('hidraw*')):
        try:
            text=(entry/'device'/'uevent').read_text(errors='ignore')
            props=dict(line.split('=',1) for line in text.splitlines() if '=' in line)
            parts=props.get('HID_ID','').split(':')
            if len(parts)!=3:
                continue
            vid=int(parts[1],16); pid=int(parts[2],16)
        except Exception:
            continue
        if vid!=VALVE_VID or pid not in STEAM_PIDS:
            continue

        path=f'/dev/{entry.name}'
        anchor=_steam_physical_anchor(props,path)
        group_key=(vid,pid,anchor)
        g=steam_groups.setdefault(group_key,{
            "paths":[],
            "names":[],
            "vid":vid,
            "pid":pid,
            "anchor":anchor,
        })
        if path not in g["paths"]:
            g["paths"].append(path)
        name=(props.get('HID_NAME','') or '').strip()
        if name:
            g["names"].append(name)

    for (vid,pid,anchor),g in sorted(steam_groups.items(),key=lambda kv:kv[0][2]):
        paths=sorted(g["paths"])
        # "Puck" is a receiver/interface label, not the logical controller
        # name users should configure. Prefer a non-Puck name when available.
        names=[n for n in g["names"] if "puck" not in n.lower()]
        name=(names[0] if names else "Steam Controller")
        key=f"steam:{vid:04x}:{pid:04x}:{anchor}"
        if key in seen:
            continue
        seen.add(key)
        found.append(dict(
            key=key,
            name=name,
            backend='steam_passive',
            family='steam',
            vendor=vid,
            product=pid,
            path=paths[0] if paths else "",
            paths=paths,
            index=-1,
            detail=f"Steam HID · {len(paths)} candidate node{'s' if len(paths)!=1 else ''}",
        ))

    for device in enumerate_switch2_pro_hidraw():
        key=device["key"]
        if key in seen:continue
        seen.add(key);paths=list(device.get("paths") or [])
        found.append(dict(key=key,name="Nintendo Switch 2 Pro Controller",
            backend="switch2pro_hidraw",family="switch2pro",
            vendor=NINTENDO_VID,product=SWITCH2_PRO_PID,
            path=paths[0] if paths else "",paths=paths,index=-1,
            detail=f"native HIDRaw · {len(paths)} candidate collection{'s' if len(paths)!=1 else ''}"))

    if InputDevice is not None:
        for path in sorted(list_devices() or []):
            try:
                dev=InputDevice(path)
                if not EvdevGamepad._is_gamepad(dev):
                    dev.close()
                    continue
                info=dev.info
                vendor=int(getattr(info,'vendor',0) or 0)
                product=int(getattr(info,'product',0) or 0)
                family=linux_controller_family(vendor,product,dev.name)
                if vendor==NINTENDO_VID and product==SWITCH2_PRO_PID:
                    dev.close()
                    continue
                # Prefer the dedicated Steam hidraw implementation.
                if vendor==VALVE_VID:
                    dev.close()
                    continue
                key=_linux_evdev_identity(dev)
                if key not in seen:
                    seen.add(key)
                    found.append(dict(
                        key=key,
                        name=dev.name or Path(path).name,
                        backend='evdev',
                        family=family,
                        vendor=vendor,
                        product=product,
                        path=path,
                        paths=[path],
                        index=-1,
                        detail=f'evdev · {Path(path).name} · {vendor:04x}:{product:04x}'
                    ))
                dev.close()
            except Exception:
                pass
    if not any(
        d.get("vendor")==NINTENDO_VID and d.get("product")==SWITCH2_PRO_PID
        for d in found
    ):
        usb_present=False
        try:
            for devdir in Path("/sys/bus/usb/devices").glob("*"):
                try:
                    vid=int((devdir/"idVendor").read_text().strip(),16)
                    pid=int((devdir/"idProduct").read_text().strip(),16)
                except Exception:
                    continue
                if vid==NINTENDO_VID and pid==SWITCH2_PRO_PID:
                    usb_present=True
                    break
        except Exception:
            pass
        if usb_present:
            found.append(dict(
                key="usb:057e:2069:switch2pro",
                name="Nintendo Switch 2 Pro Controller",
                backend="switch2pro_hidraw",family="switch2pro",
                vendor=NINTENDO_VID,product=SWITCH2_PRO_PID,
                path="",paths=[],index=-1,
                detail="USB detected · waiting for native HIDRaw interface",
                pending=True,
            ))

    if include_keyboard:
        found.append(dict(
            key="virtual:keyboard_mouse",
            name="Keyboard + Mouse",
            backend="keyboard_mouse",
            family="keyboard",
            path="",
            paths=[],
            index=-1,
            detail="background input · mouse = right stick",
            virtual=True,
        ))
    return found


class SteamHidReader:
    """Persistent Steam Controller hidraw backend.

    Device discovery happens at service start/reconnect only, never in the 250 Hz
    hot path. Once selected, the same fd is kept until a real read/disconnect error.
    """

    def __init__(self):
        self.fd = None
        self.path = ""
        self.active_mode = False
        self.latest = None
        self.status = "Steam HID inactive"
        self.reports = 0
        self.errors = 0
        self.last_report_at = 0.0
        self.last_connect_attempt = 0.0
        self.known_paths = []
        self.gyro_bias = [0,0,0]
        self._gyro_sum=[0,0,0]
        self._gyro_samples=0
        self.gyro_calibrated=False

    def start(self, active=False, initial_paths=None):
        self.stop()
        self.active_mode = active
        self.known_paths = list(initial_paths or [])
        self.status = "Steam HID waiting"
        self._connect(blocking_probe=True)

    def stop(self):
        if self.active_mode:
            self._restore_lizard()
        self._close()
        self.latest = None
        self.status = "Steam HID inactive"

    def _close(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
        self.fd = None
        # Never keep replaying the last HID frame after a disconnect/read error.
        self.latest = None
        self.last_report_at = 0.0

    def snapshot(self):
        return {
            "state": dict(self.latest) if self.latest else None,
            "status": self.status,
            "reports": self.reports,
            "errors": self.errors,
            "path": self.path,
            "gyro_calibrated": self.gyro_calibrated,
            "input_age_ms": self.input_age_ms(),
        }

    def input_age_ms(self):
        if not self.last_report_at:
            return -1
        return max(0, int((time.monotonic() - self.last_report_at) * 1000))

    def state_is_fresh(self, max_age_ms=120):
        age = self.input_age_ms()
        return self.fd is not None and age >= 0 and age <= max_age_ms

    @staticmethod
    def _feature(cmd,payload=b""):
        b=bytearray(64);b[0]=1;b[1]=cmd;b[2]=len(payload);b[3:3+len(payload)]=payload;return b

    def _set_feature(self,data):
        if self.fd is None:return False
        try:
            buf=bytearray(data);fcntl.ioctl(self.fd,HIDIOCSFEATURE(len(buf)),buf,True);return True
        except OSError:return False

    def _enable_imu(self):
        return self._set_feature(self._feature(0x87,bytes((0x30,0x18,0))))

    def _disable_lizard(self):
        ok=self._set_feature(self._feature(0x81))
        ok=self._enable_imu() and ok
        ok=self._set_feature(self._feature(0x87,bytes((0x08,0,0,0x07,0,0)))) and ok
        return ok

    def _restore_lizard(self):
        if self.fd is None:return
        self._set_feature(self._feature(0x85))
        self._set_feature(self._feature(0x8E))

    def _parse(self,report):
        if len(report)<30 or report[0] not in STEAM_REPORT_STATE:return None
        b0,b1,b2,flags=report[2],report[3],report[4],report[5]
        buttons={"a":bool(b0&1),"b":bool(b0&2),"x":bool(b0&4),"y":bool(b0&8),
                 "qam":bool(b0&0x10),"rs":bool(b0&0x20),"start":bool(b0&0x40),
                 "r4":bool(b0&0x80),"r5":bool(b1&1),"rb":bool(b1&2),
                 "down":bool(b1&4),"right":bool(b1&8),"left":bool(b1&0x10),
                 "up":bool(b1&0x20),"back":bool(b1&0x40),"ls":bool(b1&0x80),
                 "guide":bool(b2&1),"l4":bool(b2&2),"l5":bool(b2&4),"lb":bool(b2&8)}
        i16=lambda o:struct.unpack_from("<h",report,o)[0]
        out={"buttons_raw":buttons,
             "lt_raw":max(0,min(32767,i16(6))),"rt_raw":max(0,min(32767,i16(8))),
             "lx":i16(10),"ly":i16(12),"rx":i16(14),"ry":i16(16),
             "imu_timestamp":0,"accel_x":0,"accel_y":0,"accel_z":16384,
             "gyro_x":0,"gyro_y":0,"gyro_z":0}
        if len(report)>=47:
            out.update(
                imu_timestamp=struct.unpack_from("<I",report,30)[0],
                accel_x=i16(34),accel_y=i16(36),accel_z=i16(38),
                gyro_x=i16(40),gyro_y=i16(42),gyro_z=i16(44))
        gx,gy,gz=out["gyro_x"],out["gyro_y"],out["gyro_z"]
        if not self.gyro_calibrated:
            ax,ay,az=out["accel_x"],out["accel_y"],out["accel_z"]
            n=ax*ax+ay*ay+az*az
            if max(abs(gx),abs(gy),abs(gz))<1500 and 12000*12000<n<21000*21000:
                self._gyro_sum[0]+=gx;self._gyro_sum[1]+=gy;self._gyro_sum[2]+=gz
                self._gyro_samples+=1
                if self._gyro_samples>=96:
                    self.gyro_bias=[round(x/self._gyro_samples) for x in self._gyro_sum]
                    self.gyro_calibrated=True
            else:
                self._gyro_sum=[0,0,0];self._gyro_samples=0
        if self.gyro_calibrated:
            out["gyro_x"]-=self.gyro_bias[0]
            out["gyro_y"]-=self.gyro_bias[1]
            out["gyro_z"]-=self.gyro_bias[2]
        return out

    def rumble(self,left,right):
        if self.fd is None:return False
        ok=True
        left=round(max(0,min(65535,int(left)))*0.45)
        right=round(max(0,min(65535,int(right)))*0.45)
        for actuator,strength in ((2,left),(4,right)):
            data=bytearray(64);data[0]=0x83;data[1]=actuator
            if strength<=0:
                data[2]=0x80;data[6]=0x80
            else:
                gain=max(-127,min(127,round((strength/65535.0)*255.0-128.0)))
                freq=113
                data[2]=gain&0xff;data[3]=freq&0xff;data[4]=(freq>>8)&0xff
                data[5]=0xff;data[6]=0x7f
            try:
                ok=(os.write(self.fd,data)==64) and ok
            except OSError:
                ok=False
        return ok

    def _candidate_paths(self, rescan=False):
        if rescan or not self.known_paths:
            self.known_paths=[x[0] for x in enumerate_hidraw(VALVE_VID,STEAM_PIDS)]
        return list(self.known_paths)

    def _probe_path(self,path,wait_seconds):
        fd=None
        try:
            try:
                fd=os.open(path,os.O_RDWR|os.O_NONBLOCK)
            except PermissionError:
                if self.active_mode:return None,None
                fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK)
            deadline=time.monotonic()+wait_seconds
            while time.monotonic()<deadline:
                try:
                    report=os.read(fd,64)
                except BlockingIOError:
                    time.sleep(0.005);continue
                if report and report[0] in STEAM_REPORT_STATE:
                    return fd,report
            os.close(fd)
        except OSError:
            if fd is not None:
                try:os.close(fd)
                except OSError:pass
        return None,None

    def _connect(self,blocking_probe=False):
        self.last_connect_attempt=time.monotonic()
        paths=self._candidate_paths(rescan=not bool(self.known_paths))
        # Blocking probing is only allowed while connecting/reconnecting, never
        # during healthy gameplay.
        wait=0.25 if blocking_probe else 0.03
        for path in paths:
            fd,pending=self._probe_path(path,wait)
            if fd is None:continue
            self.fd=fd;self.path=path
            if self.active_mode:self._disable_lizard()
            else:self._enable_imu()
            mode="Steam HID direct" if self.active_mode else "Steam HID passive"
            self.status=f"OPEN: {mode} · {Path(path).name}"
            if pending:
                parsed=self._parse(pending)
                if parsed:
                    self.latest=parsed;self.reports+=1;self.last_report_at=time.monotonic()
            return True
        self.status="DISCONNECTED: Steam Controller 2026"
        return False

    def poll(self):
        if self.fd is None:
            # Slow reconnect path only. Healthy playback never reaches this.
            if time.monotonic()-self.last_connect_attempt>=1.0:
                if not self._connect(blocking_probe=False):
                    # A physical reconnect may create a new hidraw path.
                    if time.monotonic()-self.last_connect_attempt>=0.9:
                        self.known_paths=[]
            return 0

        newest=None;count=0
        try:
            for _ in range(512):
                try:
                    report=os.read(self.fd,64)
                except BlockingIOError:
                    break
                if not report:break
                if report[0] in STEAM_REPORT_STATE:
                    newest=report;count+=1
            if newest is not None:
                parsed=self._parse(newest)
                if parsed:
                    self.latest=parsed
                    self.reports+=count
                    self.last_report_at=time.monotonic()
            return count
        except BlockingIOError:
            return count
        except OSError as exc:
            if getattr(exc, "errno", None) in (11,):
                return count
            self.errors+=1
            self.status=f"READ ERROR: {exc}"
            self._close()
            self.last_connect_attempt=time.monotonic()
            return 0

def dead(v,d): return 0 if abs(int(v))<=d else max(-32768,min(32767,int(v)))
def neutral_values(): return dict(buttons=0,lx=0,ly=0,rx=0,ry=0,lt=0,rt=0,hat=8,ax=0,ay=0,az=4096,gx=0,gy=0,gz=0,imu_ts=0)
def hat_from_dirs(u,d,l,r):
    if u and r:return 1
    if r and d:return 3
    if d and l:return 5
    if l and u:return 7
    if u:return 0
    if r:return 2
    if d:return 4
    if l:return 6
    return 8


def steam_values(raw,dz,labels,mapping=None,gyro_trim=False):
    if raw is None:return neutral_values()
    b=raw["buttons_raw"];mapping=mapping or default_steam_mapping(labels);out=0;u=d=l=r=False;force_l=force_r=False
    def apply(target):
        nonlocal out,u,d,l,r,force_l,force_r
        bit=STEAM_TARGET_BUTTON_BITS.get(target)
        if bit is not None:out|=bit
        elif target=="ZL":force_l=True
        elif target=="ZR":force_r=True
        elif target=="D-Pad Up":u=True
        elif target=="D-Pad Down":d=True
        elif target=="D-Pad Left":l=True
        elif target=="D-Pad Right":r=True
    for source,_ in STEAM_SOURCE_BUTTONS:
        if b.get(source):apply(mapping.get(source,"None"))
    if b.get("l5") and b.get("r5"):apply(mapping.get("l5+r5","None"))
    lt=min(65535,raw["lt_raw"]*2);rt=min(65535,raw["rt_raw"]*2)
    if force_l:lt=65535
    if force_r:rt=65535
    roll_scale=0.80 if gyro_trim else 1.0
    pitch_yaw_scale=0.90 if gyro_trim else 1.0
    return dict(buttons=out,lx=dead(raw["lx"],dz),ly=dead(-raw["ly"],dz),rx=dead(raw["rx"],dz),ry=dead(-raw["ry"],dz),lt=lt,rt=rt,hat=hat_from_dirs(u,d,l,r),
                ax=max(-32768,min(32767,round(raw.get("accel_y",0)/4))),ay=max(-32768,min(32767,round(-raw.get("accel_x",0)/4))),az=max(-32768,min(32767,round(raw.get("accel_z",16384)/4))),
                gx=max(-32768,min(32767,round(raw.get("gyro_y",0)*roll_scale))),gy=max(-32768,min(32767,round(-raw.get("gyro_x",0)*pitch_yaw_scale))),gz=max(-32768,min(32767,round(raw.get("gyro_z",0)*pitch_yaw_scale))),imu_ts=raw.get("imu_timestamp",0)&0xffffffff)



def pack_payload(vals):
    return struct.pack(
        "<IhhhhHHB3xhhhhhhI",
        vals["buttons"], vals["lx"], vals["ly"], vals["rx"], vals["ry"],
        vals["lt"], vals["rt"], vals["hat"],
        vals["ax"], vals["ay"], vals["az"],
        vals["gx"], vals["gy"], vals["gz"], vals["imu_ts"]
    )

def controller_slot_flags(slot):
    """Encode the controller slot exactly like firmware SwitchNetProtocol.h."""
    return 0x0100 if int(slot) == 1 else 0x0000


def pack_packet_from_payload(payload,session,seq,timestamp_us=None,slot=0):
    if timestamp_us is None:
        timestamp_us=int(time.monotonic_ns()/1000)&0xffffffff
    flags=controller_slot_flags(slot)
    header=struct.pack(
        "<IBBHHHIII",0x544E5753,3,1,24,36,flags,
        session,seq&0xffffffff,timestamp_us&0xffffffff
    )
    body=header+payload
    return body+struct.pack("<I",zlib.crc32(body)&0xffffffff)

def pack_packet(vals,session,seq,slot=0):
    return pack_packet_from_payload(pack_payload(vals),session,seq,slot=slot)


def decode_amp(m):
    if len(m)!=4:return 0
    idx=(m[1]&0xfe)>>1
    low=(0.0,0.007843,0.011823,0.014061,0.016720,0.019885,0.023648,0.028123,0.033442,0.039771,0.047296,0.056246,0.066886,0.079542,0.094592,0.112491)
    if idx<=0:a=0
    elif idx<16:a=low[idx]
    elif idx<32:a=(2.0**(idx/16.0))/17.0
    else:a=(2.0**(idx/32.0))/8.7
    return max(0,min(65535,round(min(1.0,a)*65535)))

def parse_rumble(data,session,slot=0):
    if len(data)!=40:return None
    magic,ver,typ,hs,ps,flags,sess,seq,ts=struct.unpack_from("<IBBHHHIII",data,0)
    expected_flags=0x0100 if int(slot)==1 else 0
    if magic!=0x544e5753 or ver!=3 or typ!=2 or hs!=24 or ps!=12 or sess!=session or (flags&0x0100)!=expected_flags:return None
    if zlib.crc32(data[:-4])&0xffffffff!=struct.unpack_from("<I",data,36)[0]:return None
    raw=data[24:32]
    gain_field=struct.unpack_from("<H",data,34)[0]
    gain=gain_field if 0<gain_field<=100 else 100
    left=round(decode_amp(raw[:4])*gain/100.0)
    right=round(decode_amp(raw[4:])*gain/100.0)
    return max(0,min(65535,left)),max(0,min(65535,right))


class ControllerWorker(QtCore.QObject):
    statusChanged=QtCore.Signal(dict)

    def __init__(self):
        super().__init__()
        self.stop_evt=threading.Event()
        self.rumble_evt=threading.Event()
        self.network_wake_evt=threading.Event()
        self.stats_lock=threading.Lock()
        self.rumble_lock=threading.Lock()
        self.pub_lock=threading.Lock()

        self.threads=[]
        self.running=False
        self.cfg={}
        self.snapshot_data={}

        self.steam=SteamHidReader()
        self.kbm=LinuxKeyboardMouseReader()
        self.evdev=EvdevGamepad()
        self.switch2pro=Switch2ProHidraw()
        self.evdev_rumble=EvdevRumbleOutput()
        self.sdl_rumble=SdlRumbleOutput()
        self.steam_rumble=SteamRumbleOutput()

        neutral=neutral_values()
        self._input_frame=(
            pack_payload(neutral), neutral, "None", "Inactive", "",
            -1, time.perf_counter_ns(), 0
        )
        self._generation=0
        self.input_reports_window=0
        self.input_reports_total=0

        self.rumble_pending=None
        self.rumble_received_total=0
        self.rumble_applied_total=0
        self.rumble_errors_total=0
        self.rumble_backend="none"
        self.rumble_output_error=""

    def start(self,cfg):
        self.stop()
        self.cfg=dict(cfg)
        self.stop_evt.clear()
        self.rumble_evt.clear()
        self.network_wake_evt.clear()
        self.running=True

        neutral=neutral_values()
        self._generation=0
        self._input_frame=(
            pack_payload(neutral), neutral, "None", "Starting...", "",
            -1, time.perf_counter_ns(), 0
        )
        with self.stats_lock:
            self.input_reports_window=0

        self.threads=[
            threading.Thread(target=self._input_loop_guarded,daemon=True,name="SwitchNet-Input-RT"),
            threading.Thread(target=self._network_loop,daemon=True,name="SwitchNet-Network-RT"),
            threading.Thread(target=self._rumble_loop,daemon=True,name="SwitchNet-Rumble"),
        ]
        for t in self.threads:t.start()

    def stop(self):
        self.stop_evt.set()
        self.rumble_evt.set()
        self.network_wake_evt.set()
        for t in list(self.threads):
            if t.is_alive() and t is not threading.current_thread():
                t.join(2.0)
        self.threads=[]
        self.running=False

        # All I/O owners are stopped before their descriptors are closed.
        try:self.steam.stop()
        except Exception:pass
        try:self.kbm.close()
        except Exception:pass
        try:self.evdev.close()
        except Exception:pass
        try:self.switch2pro.close()
        except Exception:pass
        self.evdev_rumble.close()
        self.sdl_rumble.close()
        self.steam_rumble.close()

        neutral=neutral_values()
        self._generation+=1
        self._input_frame=(
            pack_payload(neutral),neutral,"None","Service stopped","",
            -1,time.perf_counter_ns(),self._generation
        )

    def snapshot(self):
        with self.pub_lock:
            return dict(self.snapshot_data)

    def _publish(self,**kw):
        with self.pub_lock:
            self.snapshot_data.update(kw)
            snap=dict(self.snapshot_data)
        self.statusChanged.emit(snap)

    def _set_input_state(self,vals,controller,detail,kind,age_ms,reports_added=0,wake_network=True):
        if vals is None:
            vals=neutral_values()
        vals=dict(vals)
        self._generation+=1
        # CPython reference assignment is atomic. Network thread can read this
        # tuple without contending on a mutex in its 4-ms hot path.
        self._input_frame=(
            pack_payload(vals),vals,controller,detail,kind,age_ms,
            time.perf_counter_ns(),self._generation
        )
        # Discrete controls use the immediate fast path. High-rate IMU-only
        # updates intentionally do not wake the network thread: they are sampled
        # by the configured heartbeat (normally 250 Hz), preventing gyro motion
        # from creating unbounded immediate UDP bursts.
        if wake_network:
            self.network_wake_evt.set()
        if reports_added>0:
            with self.stats_lock:
                self.input_reports_window+=reports_added
                self.input_reports_total+=reports_added

    def _input_snapshot(self):
        return self._input_frame

    @staticmethod
    def _wait_readable(fds,timeout):
        fds=[fd for fd in fds if fd is not None and fd>=0]
        if not fds:
            time.sleep(min(timeout,0.02))
            return []
        try:
            ready,_,_=select.select(fds,[],[],timeout)
            return ready
        except (OSError,ValueError):
            return []

    def _input_loop_guarded(self):
        """Catch unexpected backend failures instead of killing input silently."""
        try:
            self._input_loop()
        except Exception as exc:
            import traceback
            tb=traceback.format_exc()
            try:
                snap=self.snapshot()
                self._publish(
                    controller="None",
                    detail=f"INPUT THREAD CRASH: {exc}",
                    errors=int(snap.get("errors",0))+1,
                    input_thread_crash=tb,
                )
            except Exception:
                pass
            print(tb, file=sys.stderr)

    def _input_loop(self):
        cfg=self.cfg
        requested_backend=cfg.get("backend","auto")
        controller_path=str(cfg.get("controller_path","") or "")
        controller_paths=[str(x) for x in (cfg.get("controller_paths") or []) if x]
        dz=int(cfg.get("deadzone",6000))
        labels=bool(cfg.get("labels",False))
        mapping=cfg.get("steam_mapping")
        controller_mapping=cfg.get("controller_mapping")
        controller_family=str(cfg.get("controller_family","generic") or "generic")
        controller_vendor=int(cfg.get("controller_vendor",0) or 0)
        controller_product=int(cfg.get("controller_product",0) or 0)
        gyro_trim=bool(cfg.get("steam_gyro_trim",False))
        keyboard_mapping=normalized_keyboard_mapping(cfg.get("keyboard_mapping"))
        keyboard_exclusive=bool(cfg.get("keyboard_exclusive",True))
        keyboard_release_key=normalized_release_key(cfg.get("keyboard_release_key",DEFAULT_RELEASE_KEY))
        mouse_sensitivity=int(cfg.get("mouse_sensitivity",6500))

        initial_steam_paths=(
            controller_paths
            if controller_paths and requested_backend in ("steam_passive","steam_direct")
            else [controller_path]
            if controller_path and requested_backend in ("steam_passive","steam_direct")
            else [x[0] for x in enumerate_hidraw(VALVE_VID,STEAM_PIDS)]
        )
        backend=(
            "evdev"
            if requested_backend=="auto" and controller_path
            else "steam_passive"
            if requested_backend=="auto" and initial_steam_paths
            else "evdev" if requested_backend=="auto"
            else requested_backend
        )

        if backend=="switch2pro_hidraw":
            self._publish(controller="None",detail="Initializing native Switch 2 Pro HIDRaw backend",worker_stage="switch2_native_init")
            if self.switch2pro.connect(controller_paths or ([controller_path] if controller_path else [])):
                ss=self.switch2pro.snapshot()
                self._set_input_state(switch2pro_native_values(ss["state"],dz,controller_mapping),
                    "Nintendo Switch 2 Pro Controller",ss["status"],"switch2pro_hidraw",ss.get("input_age_ms",-1),1)
                self._publish(worker_stage="switch2_native_motion" if ss.get("extended_seen") else "switch2_native_basic")
            else:
                self._publish(controller="None",detail=self.switch2pro.status,worker_stage="switch2_native_connect_failed")

        if backend=="keyboard_mouse":
            self.kbm.start(exclusive=keyboard_exclusive,release_key=keyboard_release_key)
            period=max(0.001,1.0/max(60,int(cfg.get("rate",250))))
            previous=None
            while not self.stop_evt.is_set():
                reports=self.kbm.poll()
                keys,dx,dy,status,exclusive,kbm_enabled=self.kbm.consume()
                vals=keyboard_mouse_values(
                    keys,dx,dy,keyboard_mapping,mouse_sensitivity,
                    BTN_A,BTN_B,BTN_X,BTN_Y,BTN_L,BTN_R,
                    BTN_BACK,BTN_START,BTN_LS,BTN_RS,BTN_GUIDE,BTN_CAPTURE,
                )
                if vals!=previous:
                    self._set_input_state(
                        vals,"Keyboard + Mouse",
                        status+(
                            " · enabled" if kbm_enabled else " · neutral"
                        ),
                        "keyboard_mouse",-1,reports,wake_network=True
                    )
                    previous=dict(vals)
                elif reports:
                    with self.stats_lock:
                        self.input_reports_window+=reports
                        self.input_reports_total+=reports
                self.stop_evt.wait(period)
            self.kbm.close()
            return

        if backend in ("steam_passive","steam_direct"):
            self.steam.start(
                backend=="steam_direct",initial_paths=initial_steam_paths)
        elif backend=="evdev":
            self._publish(
                controller="None",
                detail=(
                    f"Resolving evdev for {controller_vendor:04x}:"
                    f"{controller_product:04x} ({controller_family})"
                ),
                worker_stage="resolve_evdev",
            )
            resolved_path=resolve_evdev_controller_path(
                controller_vendor,controller_product,
                controller_family,controller_path,
            )
            if resolved_path:
                controller_path=resolved_path

            self._publish(
                controller="None",
                detail=f"Opening evdev {controller_path or '?'}",
                worker_stage="open_evdev",
            )

            opened=self.evdev.open_path(controller_path)
            if opened:
                self._publish(
                    controller="None",
                    detail=(
                        f"OPEN: {self.evdev.path} · waiting for first input report"
                    ),
                    worker_stage="waiting_first_report",
                )
            else:
                self._publish(
                    controller="None",
                    detail=self.evdev.status(),
                    worker_stage="evdev_open_failed",
                )

        last_steam_publish_ns=0
        evdev_missing_since=None
        EVDEV_HOLD_GRACE_S=0.75

        while not self.stop_evt.is_set():
            if backend=="switch2pro_hidraw":
                if self.switch2pro.fd is None:
                    self._publish(controller="None",detail="Reconnecting native Switch 2 Pro HIDRaw",worker_stage="switch2_native_reconnect")
                    if not self.switch2pro.connect(controller_paths or ([controller_path] if controller_path else [])):
                        self.stop_evt.wait(0.5);continue
                ready=self._wait_readable([self.switch2pro.fd],0.025)
                before=self.switch2pro.reports
                if ready:self.switch2pro.poll()
                after=self.switch2pro.reports;ss=self.switch2pro.snapshot()
                if ss.get("state") is not None and (ready or after!=before):
                    self._set_input_state(switch2pro_native_values(ss["state"],dz,controller_mapping),
                        "Nintendo Switch 2 Pro Controller",ss["status"],"switch2pro_hidraw",
                        ss.get("input_age_ms",-1),max(0,after-before))
                    self._publish(worker_stage="switch2_native_motion" if ss.get("extended_seen") else "switch2_native_basic")
                elif ss.get("input_age_ms",-1)>1000 and self.switch2pro.fd is not None:
                    self.switch2pro.close()
                continue

            if backend in ("steam_passive","steam_direct"):
                if self.steam.fd is None:
                    before=self.steam.reports
                    self.steam.poll()
                    after=self.steam.reports
                    ss=self.steam.snapshot()
                    if ss.get("state") and self.steam.state_is_fresh(40):
                        vals=steam_values(ss["state"],dz,labels,mapping)
                        detail=ss["status"]+(
                            " · gyro OK" if ss.get("gyro_calibrated")
                            else " · gyro calibration…")
                        self._set_input_state(
                            vals,"Steam Controller 2026",detail,"steam",
                            ss.get("input_age_ms",-1),max(0,after-before))
                    else:
                        # During initial probe there is no controller state yet.
                        # If a previously-open descriptor really disappeared,
                        # SteamHidReader closes it and this neutral state is the
                        # correct disconnect behavior.
                        self._set_input_state(
                            neutral_values(),"None",ss["status"],"",
                            ss.get("input_age_ms",-1),max(0,after-before))
                    self.stop_evt.wait(0.02)
                    continue

                fd=self.steam.fd
                ready=self._wait_readable([fd],0.025)
                before=self.steam.reports
                if ready:
                    self.steam.poll()
                after=self.steam.reports
                ss=self.steam.snapshot()
                age=ss.get("input_age_ms",-1)
                fresh=ss.get("state") is not None and self.steam.state_is_fresh(40)

                if fresh and (ready or after!=before):
                    vals=steam_values(ss["state"],dz,labels,mapping)
                    detail=ss["status"]+(
                        " · gyro OK" if ss.get("gyro_calibrated")
                        else " · gyro calibration…")
                    self._set_input_state(
                        vals,"Steam Controller 2026",detail,"steam",age,
                        max(0,after-before))
                    last_steam_publish_ns=time.perf_counter_ns()
                elif not fresh:
                    # IMPORTANT: no report is not a release.
                    #
                    # Steam reports are full-state packets, but HID scheduling,
                    # USB contention and system load can create short gaps. The
                    # previous 40-ms watchdog converted any such gap into a
                    # neutral frame, producing "phantom releases" while a
                    # physical button was still held.
                    #
                    # Keep the last published state for as long as the hidraw
                    # descriptor is alive. A real disconnect/read error closes
                    # the descriptor and is handled by the fd=None branch.
                    if self.steam.fd is not None:
                        prev_payload,prev_vals,prev_controller,_prev_detail,prev_kind,_prev_age,_prev_ns,_prev_gen=(
                            self._input_snapshot()
                        )
                        detail=(
                            f"{ss['status']} · waiting for HID report ({age} ms)"
                            if age > 100 else ss["status"]
                        )
                        # Publish diagnostic metadata without changing the
                        # controller state/generation. The network heartbeat
                        # continues retransmitting the last valid input frame.
                        if age > 1000:
                            self._publish(
                                input_hold_gap_ms=age,
                                input_hold_protected=True,
                            )
                    else:
                        self._set_input_state(
                            neutral_values(),"None",ss["status"],"",age,0)

            elif backend=="evdev":
                if self.evdev.dev is None:
                    if evdev_missing_since is None:
                        evdev_missing_since=time.monotonic()

                    current_path=resolve_evdev_controller_path(
                        controller_vendor,controller_product,
                        controller_family,controller_path,
                    )
                    if current_path:
                        controller_path=current_path

                    self._publish(
                        controller="None",
                        detail=f"Reopening evdev {controller_path or '?'}",
                        worker_stage="reopen_evdev",
                    )

                    if self.evdev.ensure_path(controller_path):
                        evdev_missing_since=None
                        self._publish(
                            controller="None",
                            detail=(
                                f"OPEN: {self.evdev.path} · waiting for input report"
                            ),
                            worker_stage="waiting_input_report",
                        )
                        self._set_input_state(
                            self.evdev.values(
                                dz,False,do_poll=False,
                                mapping=controller_mapping,
                                family=controller_family,
                            ),
                            self.evdev.name or "Controller evdev",
                            self.evdev.status(),"evdev",
                            self.evdev.input_age_ms(),0,
                            wake_network=True)
                    else:
                        gap=time.monotonic()-evdev_missing_since
                        prev=self._input_snapshot()
                        prev_kind=prev[4]
                        # A short kernel/HID reopen gap is not a button release.
                        # Keep retransmitting the last valid evdev state while
                        # trying to reopen. Confirmed/long disconnects still go
                        # neutral after the bounded grace period.
                        if prev_kind=="evdev" and gap < EVDEV_HOLD_GRACE_S:
                            self._publish(
                                evdev_reconnect_hold_ms=int(gap*1000),
                                evdev_reconnect_hold=True,
                            )
                        else:
                            self._set_input_state(
                                neutral_values(),"None",self.evdev.status(),"",-1,0,
                                wake_network=True)
                        self.stop_evt.wait(0.05)
                    continue

                game_fd=getattr(self.evdev.dev,"fd",None)
                imu_fd=(
                    getattr(self.evdev.imu.dev,"fd",None)
                    if self.evdev.imu.dev is not None else None
                )
                touchpad=getattr(self.evdev,"touchpad",None)
                touch_fd=(
                    getattr(touchpad.dev,"fd",None)
                    if touchpad is not None and touchpad.dev is not None else None
                )
                ready=self._wait_readable([game_fd,imu_fd,touch_fd],0.050)
                if not ready:
                    continue

                before=self.evdev.reports_total
                game_ready=game_fd in ready
                imu_ready=imu_fd is not None and imu_fd in ready
                touch_ready=touch_fd is not None and touch_fd in ready

                if game_ready:
                    self.evdev.poll()
                if touch_ready and touchpad is not None:
                    touchpad.poll()
                if imu_ready:
                    # Bounded drain: preserve time for gamepad + network threads.
                    self.evdev.imu.poll(max_batches=8)
                after=self.evdev.reports_total

                if self.evdev.dev is None:
                    if evdev_missing_since is None:
                        evdev_missing_since=time.monotonic()
                    # Do not neutralize immediately; next loop attempts reopen
                    # and applies EVDEV_HOLD_GRACE_S.
                    continue

                evdev_missing_since=None
                vals=self.evdev.values(
                    dz,False,do_poll=False,
                    mapping=controller_mapping,
                    family=controller_family,
                )
                imu_suffix=(
                    f" · IMU {self.evdev.imu.source_family} {self.evdev.imu.path}"
                    if self.evdev.imu.dev is not None else
                    f" · IMU unavailable ({self.evdev.imu.last_error or 'not found'})"
                )
                touchpad=getattr(self.evdev,"touchpad",None)
                touch_suffix=(
                    f" · Touchpad {touchpad.path}"
                    if touchpad is not None and touchpad.dev is not None else
                    " · Touchpad unavailable"
                )
                self._set_input_state(
                    vals,self.evdev.name or "Controller evdev",
                    self.evdev.status()+imu_suffix+touch_suffix,"evdev",
                    self.evdev.input_age_ms(),max(0,after-before),
                    wake_network=bool(game_ready or touch_ready))
            else:
                self._set_input_state(
                    neutral_values(),"None",
                    f"Unknown backend: {backend}","",-1,0)
                self.stop_evt.wait(0.1)

    def _queue_rumble(self,left,right):
        with self.rumble_lock:
            self.rumble_pending=(int(left),int(right))
        self.rumble_evt.set()

    def _rumble_loop(self):
        last_applied=(-1,-1)
        last_kind=""
        while not self.stop_evt.is_set():
            self.rumble_evt.wait(0.25)
            self.rumble_evt.clear()
            if self.stop_evt.is_set():break

            with self.rumble_lock:
                pending=self.rumble_pending
                self.rumble_pending=None
            if pending is None:continue

            _payload,_vals,_controller,_detail,kind,_age,_updated,_gen=self._input_snapshot()
            if pending==last_applied and kind==last_kind:
                continue

            ok=False
            try:
                if kind=="switch2pro_hidraw":
                    ok=self.switch2pro.rumble(*pending)
                    if ok:
                        self.rumble_backend="switch2pro_hidraw";self.rumble_output_error=""
                    else:self.rumble_output_error="native HIDRaw rumble write failed"
                elif kind=="steam":
                    path=self.steam.path
                    if self.steam_rumble.ensure_path(path):
                        ok=self.steam_rumble.rumble(*pending)
                        if ok:
                            self.rumble_backend="steam_hid"
                            self.rumble_output_error=""
                elif kind=="evdev":
                    path=self.evdev.path
                    # First use the kernel's native FF_RUMBLE if present.
                    if self.evdev_rumble.ensure_path(path):
                        ok=self.evdev_rumble.rumble(*pending)
                        if ok:
                            self.rumble_backend="evdev_ff"
                            self.rumble_output_error=""
                        else:
                            self.rumble_output_error=self.evdev_rumble.last_error

                    # Fallback only for OUTPUT. Input remains evdev and therefore
                    # retains the v1.8 low-latency path.
                    if not ok and self.sdl_rumble.ensure_for_name(self.evdev.name):
                        ok=self.sdl_rumble.rumble(*pending)
                        if ok:
                            self.rumble_backend="sdl2_output"
                            self.rumble_output_error=""
                        else:
                            self.rumble_output_error=self.sdl_rumble.last_error

                    if not ok and not self.rumble_output_error:
                        self.rumble_output_error=(
                            self.evdev_rumble.last_error or
                            self.sdl_rumble.last_error or
                            "rumble unavailable"
                        )
                else:
                    ok=True
            except Exception:
                ok=False

            if ok:
                last_applied=pending
                last_kind=kind
                self.rumble_applied_total+=1
            else:
                self.rumble_errors_total+=1

            # Coalesced newest-state feedback, max 100 physical updates/s.
            self.stop_evt.wait(0.010)

    def _network_loop(self):
        cfg=self.cfg
        host=cfg.get("host","192.168.0.53")
        port=int(cfg.get("port",5454))
        rate=max(30,min(250,int(cfg.get("rate",250))))
        controller_slot=1 if int(cfg.get("slot",0))==1 else 0

        session=random.getrandbits(32) or 1
        seq=0
        tx=errors=rx_window=0
        immediate_tx=0
        late_ticks=max_late_us=0
        last_stats=time.monotonic()
        last_gen=-1
        last_sent_gen=-1
        input_send_latency_us=0
        input_send_latency_max_us=0
        last_successful_send_ns=0
        max_send_gap_us=0

        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        sock.setblocking(False)
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,64*1024)
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,64*1024)
        try:sock.setsockopt(socket.IPPROTO_IP,socket.IP_TOS,0xB8)
        except OSError:pass
        try:sock.setsockopt(socket.SOL_SOCKET,socket.SO_PRIORITY,6)
        except (OSError,AttributeError):pass
        sock.connect((host,port))

        period_ns=max(1_000_000,int(1_000_000_000/rate))
        next_heartbeat_ns=time.perf_counter_ns()
        start_ns=next_heartbeat_ns

        def send_current(is_immediate=False):
            nonlocal seq,tx,errors,last_gen,last_sent_gen
            nonlocal input_send_latency_us,input_send_latency_max_us,immediate_tx
            nonlocal last_successful_send_ns,max_send_gap_us

            payload,vals,controller,detail,kind,input_age,updated_ns,generation=(
                self._input_snapshot()
            )
            send_ns=time.perf_counter_ns()

            if generation!=last_gen:
                input_send_latency_us=max(0,int((send_ns-updated_ns)/1000))
                input_send_latency_max_us=max(
                    input_send_latency_max_us,input_send_latency_us)
                last_gen=generation

            timestamp_us=((send_ns-start_ns)//1000)&0xffffffff
            pkt=pack_packet_from_payload(
                payload,session,seq,timestamp_us=timestamp_us,slot=controller_slot)
            seq=(seq+1)&0xffffffff
            try:
                sock.send(pkt)
                tx+=1
                if last_successful_send_ns:
                    max_send_gap_us=max(
                        max_send_gap_us,
                        int((send_ns-last_successful_send_ns)/1000)
                    )
                last_successful_send_ns=send_ns
                if is_immediate:
                    immediate_tx+=1
                last_sent_gen=generation
            except OSError:
                errors+=1

            return vals,controller,detail,kind,input_age,generation

        try:
            vals=neutral_values();controller="None";detail="";kind="";input_age=-1
            while not self.stop_evt.is_set():
                now_ns=time.perf_counter_ns()
                timeout_s=max(0.0,(next_heartbeat_ns-now_ns)/1_000_000_000)

                # Input changes wake this wait immediately; otherwise the
                # normal 250-Hz heartbeat deadline expires.
                woke=self.network_wake_evt.wait(timeout_s)
                self.network_wake_evt.clear()
                if self.stop_evt.is_set():
                    break

                now_ns=time.perf_counter_ns()
                current_gen=self._input_snapshot()[7]
                due_heartbeat=now_ns>=next_heartbeat_ns
                fresh_input=current_gen!=last_sent_gen

                # A state change is sent immediately. A heartbeat is still sent
                # every 4 ms for packet-loss resilience and client timeout logic.
                if fresh_input:
                    vals,controller,detail,kind,input_age,_=send_current(True)

                if due_heartbeat:
                    # Avoid duplicate packets at effectively the same instant if
                    # an immediate send already satisfied this deadline.
                    if not fresh_input or now_ns-next_heartbeat_ns>500_000:
                        vals,controller,detail,kind,input_age,_=send_current(False)

                    next_heartbeat_ns+=period_ns
                    late_ns=now_ns-next_heartbeat_ns
                    if late_ns>0:
                        late_ticks+=1
                        max_late_us=max(max_late_us,int(late_ns/1000))

                    # Never burst-replay old heartbeat slots.
                    if now_ns-next_heartbeat_ns>100_000_000:
                        next_heartbeat_ns=now_ns+period_ns

                while True:
                    try:fb=sock.recv(256)
                    except BlockingIOError:break
                    except OSError:break
                    r=parse_rumble(fb,session,controller_slot)
                    if r:
                        rx_window+=1
                        self.rumble_received_total+=1
                        self._queue_rumble(*r)

                now=time.monotonic()
                if now-last_stats>=1.0:
                    with self.stats_lock:
                        input_reports=self.input_reports_window
                        self.input_reports_window=0
                    self._publish(
                        running=True,controller=controller,detail=detail,
                        txps=tx,immediate_txps=immediate_tx,
                        errors=errors,rumble=rx_window,values=vals,
                        input_reports_s=input_reports,input_age_ms=input_age,
                        input_to_udp_us=input_send_latency_us,
                        input_to_udp_max_us=input_send_latency_max_us,
                        udp_late_ticks=late_ticks,
                        udp_max_late_us=max_late_us,
                        udp_max_send_gap_us=max_send_gap_us,
                        rumble_applied=self.rumble_applied_total,
                        rumble_errors=self.rumble_errors_total,
                        rumble_backend=self.rumble_backend,
                        rumble_output_error=self.rumble_output_error,
                        controller_path=(
                            self.steam.path if kind=="steam"
                            else self.evdev.path if kind=="evdev"
                            else ""),
                    )
                    tx=errors=rx_window=immediate_tx=late_ticks=max_late_us=0
                    input_send_latency_max_us=0
                    max_send_gap_us=0
                    last_stats=now

        finally:
            neutral_payload=pack_payload(neutral_values())
            for _ in range(8):
                try:
                    sock.send(pack_packet_from_payload(
                        neutral_payload,session,seq,0,slot=controller_slot))
                except OSError:
                    pass
                seq=(seq+1)&0xffffffff
                time.sleep(0.001)
            sock.close()
            self.running=False
            self._publish(
                running=False,controller="None",
                detail="Service stopped",txps=0,immediate_txps=0,
                input_reports_s=0,input_age_ms=-1,
                input_to_udp_us=0,input_to_udp_max_us=0,
                udp_late_ticks=0,udp_max_late_us=0)



class ApiServer:
    def __init__(self,app):self.app=app;self.httpd=None;self.thread=None
    def start(self):
        app=self.app
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def _txt(self,code,text):
                raw=text.encode();self.send_response(code);self.send_header("Content-Type","text/plain; charset=utf-8");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
            def _json(self,code,obj):
                raw=json.dumps(obj).encode();self.send_response(code);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
            def do_GET(self):
                if self.path=="/status":self._txt(200,"ON" if app.worker.running else "OFF")
                elif self.path=="/status/details":self._json(200,app.api_status())
                elif self.path=="/health":self._json(200,{"ok":True,"service":"SwitchNetClient","version":APP_VERSION})
                else:self._txt(404,"Not found")
            def do_POST(self):
                if self.path=="/start":QtCore.QMetaObject.invokeMethod(app,"start_service",QtCore.Qt.ConnectionType.QueuedConnection);self._json(200,{"ok":True})
                elif self.path=="/stop":QtCore.QMetaObject.invokeMethod(app,"stop_service",QtCore.Qt.ConnectionType.QueuedConnection);self._json(200,{"ok":True})
                else:self._txt(404,"Not found")
        class Server(ThreadingHTTPServer):allow_reuse_address=True
        self.httpd=Server((CLIENT_API_HOST,CLIENT_API_PORT),Handler);self.thread=threading.Thread(target=self.httpd.serve_forever,daemon=True,name="SwitchNet-HTTP-API");self.thread.start()
    def stop(self):
        if self.httpd:self.httpd.shutdown();self.httpd.server_close();self.httpd=None


class MappingDialog(QtWidgets.QDialog):
    saved=QtCore.Signal(str,str,dict)
    def __init__(self,parent,slot,label,mapping):
        super().__init__(parent);self.setWindowTitle("Steam Controller Profile");self.resize(520,680);self.slot=slot
        lay=QtWidgets.QVBoxLayout(self);form=QtWidgets.QFormLayout();self.name=QtWidgets.QLineEdit(label);form.addRow("Preset name",self.name);lay.addLayout(form)
        scroll=QtWidgets.QScrollArea();scroll.setWidgetResizable(True);body=QtWidgets.QWidget();grid=QtWidgets.QFormLayout(body);self.boxes={}
        for key,title in STEAM_MAPPING_SOURCES:
            box=QtWidgets.QComboBox();box.addItems(STEAM_TARGETS);box.setCurrentText(mapping.get(key,"None"));self.boxes[key]=box;grid.addRow(title,box)
        scroll.setWidget(body);lay.addWidget(scroll);buttons=QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Save|QtWidgets.QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self._save);buttons.rejected.connect(self.reject);lay.addWidget(buttons)
    def _save(self):self.saved.emit(self.slot,self.name.text().strip() or self.slot,{k:b.currentText() for k,b in self.boxes.items()});self.accept()



class ControllerRosterList(QtWidgets.QListWidget):
    """Deterministic controller-priority drag/drop.

    Qt's QListWidget.InternalMove mutates the GUI model while a drop is still
    being processed. SwitchNet also owns a persistent controller_slots model,
    so synchronizing during that transient Qt state could persist a list with
    a missing row.

    This widget never allows Qt to move rows itself. It only reports the source
    and final destination; MainWindow performs one atomic Python-list move and
    redraws the roster once.
    """
    reorderRequested = QtCore.Signal(int, int)
    dragStateChanged = QtCore.Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_row = -1
        self.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(
            QtWidgets.QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)

    def startDrag(self, supportedActions):
        self._drag_row = self.currentRow()
        if self._drag_row < 0:
            return
        self.dragStateChanged.emit(True)
        try:
            super().startDrag(QtCore.Qt.DropAction.MoveAction)
        finally:
            self.dragStateChanged.emit(False)
            self._drag_row = -1

    def dragEnterEvent(self, event):
        if event.source() is self:
            event.setDropAction(QtCore.Qt.DropAction.MoveAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.source() is self:
            event.setDropAction(QtCore.Qt.DropAction.MoveAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        source = self._drag_row
        if event.source() is not self or source < 0:
            event.ignore()
            return

        pos = event.position().toPoint()
        row = self.indexAt(pos).row()

        # Treat the drop location as an insertion boundary, so users can move a
        # controller naturally before/after a row including explicit None rows.
        if row < 0:
            insertion = self.count()
        else:
            rect = self.visualItemRect(self.item(row))
            insertion = row + (1 if pos.y() >= rect.center().y() else 0)

        insertion = max(0, min(insertion, self.count()))
        target = insertion - 1 if insertion > source else insertion
        target = max(0, min(target, self.count() - 1))

        event.setDropAction(QtCore.Qt.DropAction.MoveAction)
        event.accept()

        if target != source:
            self.reorderRequested.emit(source, target)



def roster_move(slots, source, target, minimum_slots=4):
    """Return a reordered copy of the logical controller roster.

    This function has no Qt dependencies and is the only primitive used by
    both drag/drop and Up/Down.
    """
    out=list(slots)
    while len(out)<minimum_slots:
        out.append("")

    source=int(source)
    target=int(target)

    if source<0 or target<0 or source>=len(out) or target>=len(out):
        return out
    if source==target:
        return out

    value=out.pop(source)
    out.insert(target,value)

    while len(out)<minimum_slots:
        out.append("")
    return out



def roster_target_from_boundary(source, boundary, count):
    """Convert a drop insertion boundary (0..count) to the final row index.

    The boundary is measured while the source row still exists. This makes the
    mapping symmetric for upward and downward drags.
    """
    source=int(source)
    boundary=max(0,min(int(boundary),int(count)))

    target=boundary
    if boundary>source:
        target-=1

    return max(0,min(target,int(count)-1))


class StableControllerRoster(QtWidgets.QListWidget):
    """Drag gesture adapter for the logical controller roster.

    Qt never reorders rows itself. The drag carries the source row explicitly,
    computes a pre-removal insertion boundary, then emits the final logical
    destination row. MainWindow uses the same move_controller_rows() path as
    the already-working Up/Down buttons.
    """

    reorderRequested = QtCore.Signal(int, int)
    dragActiveChanged = QtCore.Signal(bool)
    MIME_TYPE = "application/x-switchnet-controller-row"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(
            QtWidgets.QAbstractItemView.DragDropMode.DragDrop
        )
        self.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)

    def startDrag(self, supportedActions):
        source=self.currentRow()
        item=self.currentItem()
        if source<0 or item is None:
            return

        mime=QtCore.QMimeData()
        mime.setData(self.MIME_TYPE,str(source).encode("ascii"))
        mime.setText(item.text())

        drag=QtGui.QDrag(self)
        drag.setMimeData(mime)

        self.dragActiveChanged.emit(True)
        try:
            drag.exec(QtCore.Qt.DropAction.MoveAction)
        finally:
            self.dragActiveChanged.emit(False)

    def dragEnterEvent(self,event):
        if (
            event.source() is self and
            event.mimeData().hasFormat(self.MIME_TYPE)
        ):
            event.setDropAction(QtCore.Qt.DropAction.MoveAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self,event):
        if (
            event.source() is self and
            event.mimeData().hasFormat(self.MIME_TYPE)
        ):
            event.setDropAction(QtCore.Qt.DropAction.MoveAction)
            event.accept()
        else:
            event.ignore()

    def _drop_boundary(self,pos):
        count=self.count()
        if count<=0:
            return 0

        hovered=self.indexAt(pos).row()
        if hovered<0:
            first=self.visualItemRect(self.item(0))
            return 0 if pos.y()<first.top() else count

        rect=self.visualItemRect(self.item(hovered))
        return hovered if pos.y()<rect.center().y() else hovered+1

    def dropEvent(self,event):
        mime=event.mimeData()
        if (
            event.source() is not self or
            not mime.hasFormat(self.MIME_TYPE)
        ):
            event.ignore()
            return

        try:
            source=int(bytes(mime.data(self.MIME_TYPE)).decode("ascii"))
        except Exception:
            event.ignore()
            return

        boundary=self._drop_boundary(event.position().toPoint())
        target=roster_target_from_boundary(source,boundary,self.count())

        event.setDropAction(QtCore.Qt.DropAction.MoveAction)
        event.accept()

        if target!=source:
            # Do not modify the roster inside QDrag/dropEvent itself.
            QtCore.QTimer.singleShot(
                0,
                lambda s=source,t=target:self.reorderRequested.emit(s,t)
            )



class KeyboardMappingDialog(QtWidgets.QDialog):
    def __init__(self,parent,mapping,release_key):
        super().__init__(parent)
        self.setWindowTitle("Keyboard controller mapping")
        self.resize(470,620)
        self.release_key=normalized_release_key(release_key)
        self.mapping=mapping_without_release_conflict(mapping,self.release_key)
        layout=QtWidgets.QVBoxLayout(self)
        note=QtWidgets.QLabel(
            "Map each Nintendo control to a keyboard key. Mouse movement is always the right stick. "
            f"{self.release_key} is reserved as the emergency release key."
        )
        note.setWordWrap(True);layout.addWidget(note)
        scroll=QtWidgets.QScrollArea();scroll.setWidgetResizable(True)
        body=QtWidgets.QWidget();form=QtWidgets.QFormLayout(body)
        self.combos={}
        for action,label in KEYBOARD_ACTIONS:
            combo=QtWidgets.QComboBox();combo.addItems([k for k in KEYBOARD_KEY_CHOICES if k!=self.release_key])
            combo.setCurrentText(self.mapping[action]);self.combos[action]=combo
            form.addRow(label,combo)
        scroll.setWidget(body);layout.addWidget(scroll,1)
        row=QtWidgets.QHBoxLayout()
        defaults=QtWidgets.QPushButton("Defaults");save=QtWidgets.QPushButton("Save");cancel=QtWidgets.QPushButton("Cancel")
        defaults.clicked.connect(self.reset_defaults);save.clicked.connect(self.accept);cancel.clicked.connect(self.reject)
        row.addWidget(defaults);row.addStretch(1);row.addWidget(cancel);row.addWidget(save);layout.addLayout(row)

    def reset_defaults(self):
        for action,_ in KEYBOARD_ACTIONS:self.combos[action].setCurrentText(DEFAULT_KEYBOARD_MAPPING[action])

    def result_mapping(self):
        return {action:self.combos[action].currentText() for action,_ in KEYBOARD_ACTIONS}



class GenericMappingDialog(QtWidgets.QDialog):
    saved=QtCore.Signal(str,str,dict)

    def __init__(self,parent,family,slot,name,mapping):
        super().__init__(parent)
        self.family=family
        self.slot=slot
        self.spec=LINUX_MAPPING_SPECS[family]
        self.setWindowTitle(f"SwitchNet - {self.spec['title']} Profile")
        self.resize(500,650)
        layout=QtWidgets.QVBoxLayout(self)

        form=QtWidgets.QFormLayout()
        self.name_edit=QtWidgets.QLineEdit(name)
        form.addRow("Preset name",self.name_edit)
        layout.addLayout(form)

        scroll=QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        body=QtWidgets.QWidget()
        grid=QtWidgets.QFormLayout(body)
        self.combos={}
        for source,label in self.spec["sources"]:
            combo=QtWidgets.QComboBox()
            combo.addItems(STEAM_TARGETS)
            combo.setCurrentText(mapping.get(source,"None"))
            self.combos[source]=combo
            grid.addRow(label,combo)
        scroll.setWidget(body)
        layout.addWidget(scroll,1)

        row=QtWidgets.QHBoxLayout()
        defaults=QtWidgets.QPushButton("Defaults")
        cancel=QtWidgets.QPushButton("Cancel")
        save=QtWidgets.QPushButton("Save and use preset")
        defaults.clicked.connect(self.reset_defaults)
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        row.addWidget(defaults);row.addStretch(1)
        row.addWidget(cancel);row.addWidget(save)
        layout.addLayout(row)

    def reset_defaults(self):
        mapping=default_linux_mapping(self.family)
        for source,_ in self.spec["sources"]:
            self.combos[source].setCurrentText(mapping.get(source,"None"))

    def _save(self):
        name=self.name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self,"SwitchNet","Preset name cannot be empty.")
            return
        mapping={
            source:self.combos[source].currentText()
            for source,_ in self.spec["sources"]
        }
        self.saved.emit(self.slot,name,mapping)
        self.accept()


class KeyboardProfilesDialog(QtWidgets.QDialog):
    saved=QtCore.Signal(str,str,dict)

    def __init__(self,parent,slot,name,mapping,release_key):
        super().__init__(parent)
        self.slot=slot
        self.release_key=normalized_release_key(release_key)
        self.setWindowTitle("SwitchNet - Keyboard + Mouse Profile")
        self.resize(500,680)
        layout=QtWidgets.QVBoxLayout(self)

        form=QtWidgets.QFormLayout()
        self.name_edit=QtWidgets.QLineEdit(name)
        form.addRow("Preset name",self.name_edit)
        layout.addLayout(form)

        note=QtWidgets.QLabel(
            "Mouse movement is always the right stick. "
            f"{self.release_key} is reserved for emergency release."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        scroll=QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        body=QtWidgets.QWidget()
        grid=QtWidgets.QFormLayout(body)
        self.combos={}
        clean=mapping_without_release_conflict(mapping,self.release_key)
        for action,label in KEYBOARD_ACTIONS:
            combo=QtWidgets.QComboBox()
            combo.addItems([
                key for key in KEYBOARD_KEY_CHOICES
                if key!=self.release_key
            ])
            combo.setCurrentText(clean[action])
            self.combos[action]=combo
            grid.addRow(label,combo)
        scroll.setWidget(body)
        layout.addWidget(scroll,1)

        row=QtWidgets.QHBoxLayout()
        defaults=QtWidgets.QPushButton("Defaults")
        cancel=QtWidgets.QPushButton("Cancel")
        save=QtWidgets.QPushButton("Save and use preset")
        defaults.clicked.connect(self.reset_defaults)
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        row.addWidget(defaults);row.addStretch(1)
        row.addWidget(cancel);row.addWidget(save)
        layout.addLayout(row)

    def reset_defaults(self):
        for action,_ in KEYBOARD_ACTIONS:
            self.combos[action].setCurrentText(DEFAULT_KEYBOARD_MAPPING[action])

    def _save(self):
        name=self.name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self,"SwitchNet","Preset name cannot be empty.")
            return
        mapping=mapping_without_release_conflict(
            {
                action:self.combos[action].currentText()
                for action,_ in KEYBOARD_ACTIONS
            },
            self.release_key,
        )
        self.saved.emit(self.slot,name,mapping)
        self.accept()


class BlacklistDialog(QtWidgets.QDialog):
    restoreRequested=QtCore.Signal(str)

    def __init__(self,parent):
        super().__init__(parent)
        self.setWindowTitle("SwitchNet - Controller Blacklist")
        self.resize(460,340)
        layout=QtWidgets.QVBoxLayout(self)
        note=QtWidgets.QLabel(
            "Blacklisted controllers remain ignored until restored."
        )
        note.setWordWrap(True);layout.addWidget(note)
        self.list=QtWidgets.QListWidget()
        layout.addWidget(self.list,1)
        row=QtWidgets.QHBoxLayout()
        restore=QtWidgets.QPushButton("Restore selected")
        close=QtWidgets.QPushButton("Close")
        restore.clicked.connect(self._restore)
        close.clicked.connect(self.accept)
        row.addWidget(restore);row.addStretch(1);row.addWidget(close)
        layout.addLayout(row)

    def populate(self,blacklist,catalog):
        self.list.clear()
        for key in sorted(blacklist):
            item=QtWidgets.QListWidgetItem(catalog.get(key,{}).get("name",key))
            item.setData(QtCore.Qt.ItemDataRole.UserRole,key)
            self.list.addItem(item)

    def _restore(self):
        item=self.list.currentItem()
        if item is not None:
            self.restoreRequested.emit(
                str(item.data(QtCore.Qt.ItemDataRole.UserRole) or "")
            )

class MainWindow(QtWidgets.QMainWindow):
    wakeResult = QtCore.Signal(bool, str)
    discoveryResult = QtCore.Signal(object)
    switch2UsbInitResult = QtCore.Signal(bool, str)

    @QtCore.Slot()
    def start_service(self):
        self.save_config()
        active=self.active_controller_descriptors()
        self.worker.stop(); self.worker2.stop()
        if active[0] is not None and not active[0].get("pending"):
            self.worker.start(self.build_worker_config(0,active[0]))
        if active[1] is not None and not active[1].get("pending"):
            self.worker2.start(self.build_worker_config(1,active[1]))
        self.update_tray()
        self.update_service_controls()
    def stop_service(self):self.worker.stop();self.worker2.stop();self.update_tray();self.update_service_controls()
    def __init__(self):
        super().__init__();self.setWindowTitle(f"SwitchNet Client {APP_VERSION}");self.resize(780,720);self.setMinimumSize(560,480);self.settings=configparser.ConfigParser();self.load_config();self.worker=ControllerWorker();self.worker2=ControllerWorker();self.switch2_usb=Switch2ProUsbEnabler();self._switch2_init_running=False;self._switch2_init_slots=[];self._switch2_silent_since=None;self._last_roster_signature=None;self._controller_missing_counts={};self._controller_seen_counts={};self._last_active_keys=("","");self._restart_events=[];self._service_restart_timer=None;self._service_restart_reason="";self.worker.statusChanged.connect(self.on_status);self.worker2.statusChanged.connect(self.on_status);self.wakeResult.connect(self.on_wake_result);self.discoveryResult.connect(self._finish_discovery);self.switch2UsbInitResult.connect(self._finish_switch2_usb_init)
        self.api=ApiServer(self);self.api.start();self.build_ui();self.build_tray();self.refresh_controllers();self.timer=QtCore.QTimer(self);self.timer.timeout.connect(self.refresh_ui);self.timer.start(500);self.controller_scan_timer=QtCore.QTimer(self);self.controller_scan_timer.timeout.connect(self.refresh_controllers);self.controller_scan_timer.start(3000);QtCore.QTimer.singleShot(500,self._auto_discover_if_needed);self.switch2_usb_timer=QtCore.QTimer(self);self.switch2_usb_timer.timeout.connect(self._maybe_initialize_switch2_pro);self.switch2_usb_timer.start(3000)
        self.hide() if self.start_in_tray or "--startup" in sys.argv else self.show()
        if self.auto_start:QtCore.QTimer.singleShot(100,self.start_service)
    def closeEvent(self,event):
        event.ignore(); self.hide()
    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type()==QtCore.QEvent.Type.WindowStateChange and self.isMinimized():
            QtCore.QTimer.singleShot(0,self.hide)
    def load_config(self):
        p=cfg_path()
        self.settings.read(p,encoding="utf-8")
        g=self.settings["client"] if self.settings.has_section("client") else {}

        self.host=g.get("host","switchnet.local")
        self.port=int(g.get("port",5454))
        self.rate=int(g.get("rate",250))
        self.auto_start=str(g.get("auto_start","0")).lower() in ("1","true","yes")
        self.start_in_tray=str(g.get("start_in_tray","1")).lower() in ("1","true","yes")

        try:self.controller_slots=list(json.loads(g.get("controller_slots","[]")))
        except Exception:self.controller_slots=[]
        try:self.controller_blacklist=set(json.loads(g.get("controller_blacklist","[]")))
        except Exception:self.controller_blacklist=set()
        self.controller_slots=[str(x or "") for x in self.controller_slots][:16]
        while len(self.controller_slots)<5:self.controller_slots.append("")
        self.controller_catalog={}

        try:legacy_deadzone=int(g.get("deadzone",6000))
        except Exception:legacy_deadzone=6000
        legacy_deadzone=max(0,min(16000,legacy_deadzone))
        self.controller_deadzones={}
        for family in CONTROLLER_DEADZONE_SPECS:
            try:value=int(g.get(f"deadzone_{family}",legacy_deadzone))
            except Exception:value=legacy_deadzone
            self.controller_deadzones[family]=max(0,min(16000,value))

        self.keyboard_enabled=str(g.get("keyboard_enabled","0")).lower() in ("1","true","yes")
        self.keyboard_exclusive=str(g.get("keyboard_exclusive","1")).lower() in ("1","true","yes")
        self.keyboard_release_key=normalized_release_key(
            g.get("keyboard_release_key",DEFAULT_RELEASE_KEY)
        )
        self.mouse_sensitivity=int(g.get("mouse_sensitivity","6500"))

        self.keyboard_profile=g.get("keyboard_profile","Default")
        if self.keyboard_profile not in CONTROLLER_PROFILE_SLOTS:
            self.keyboard_profile="Default"
        self.keyboard_profile_names={
            slot:g.get(f"keyboard_profile_name_{i}",slot)
            for i,slot in enumerate(CONTROLLER_PROFILE_SLOTS[1:],1)
        }
        try:
            legacy_keyboard=mapping_without_release_conflict(
                json.loads(g.get("keyboard_mapping","{}")),
                self.keyboard_release_key,
            )
        except Exception:
            legacy_keyboard=None
        self.keyboard_profiles={}
        for slot in CONTROLLER_PROFILE_SLOTS[1:]:
            mapping=normalized_keyboard_mapping(None)
            sec=f"keyboard_profile:{slot}"
            if self.settings.has_section(sec):
                for action,_ in KEYBOARD_ACTIONS:
                    mapping[action]=self.settings[sec].get(action,mapping[action])
            elif slot=="Custom 1" and legacy_keyboard:
                mapping=dict(legacy_keyboard)
            self.keyboard_profiles[slot]=mapping_without_release_conflict(
                mapping,self.keyboard_release_key
            )

        self.steam_gyro_trim=str(g.get("steam_gyro_trim","0")).lower() in ("1","true","yes")
        self.profile_slot=g.get("steam_profile","Default")
        if self.profile_slot not in STEAM_PROFILE_NAMES:self.profile_slot="Default"
        self.profile_names={
            x:g.get(f"steam_profile_name_{i}",x)
            for i,x in enumerate(STEAM_PROFILE_NAMES[1:],1)
        }
        self.profiles={}
        for slot in STEAM_PROFILE_NAMES[1:]:
            sec=f"steam_profile:{slot}"
            base=default_steam_mapping(False)
            if self.settings.has_section(sec):
                for key in base:
                    value=self.settings[sec].get(key,base[key])
                    if value in STEAM_TARGETS:base[key]=value
            self.profiles[slot]=base

        self.controller_profile_slots={}
        self.controller_profile_names={}
        self.controller_profiles={}
        for family,spec in LINUX_MAPPING_SPECS.items():
            selected=g.get(f"{family}_profile","Default")
            if selected not in CONTROLLER_PROFILE_SLOTS:selected="Default"
            self.controller_profile_slots[family]=selected
            self.controller_profile_names[family]={
                slot:g.get(f"{family}_profile_name_{i}",slot)
                for i,slot in enumerate(CONTROLLER_PROFILE_SLOTS[1:],1)
            }
            self.controller_profiles[family]={}
            for slot in CONTROLLER_PROFILE_SLOTS[1:]:
                mapping=default_linux_mapping(family)
                sec=f"controller_profile:{family}:{slot}"
                if self.settings.has_section(sec):
                    for source,_ in spec["sources"]:
                        value=self.settings[sec].get(source,mapping.get(source,"None"))
                        if value in STEAM_TARGETS:mapping[source]=value
                self.controller_profiles[family][slot]=mapping
    def save_config(self):
        if not self.settings.has_section("client"):
            self.settings.add_section("client")
        g=self.settings["client"]

        g["host"]=self.host_edit.text().strip() if hasattr(self,"host_edit") else self.host
        g["port"]=str(self.port_spin.value() if hasattr(self,"port_spin") else self.port)
        g["rate"]=str(self.rate_spin.value() if hasattr(self,"rate_spin") else self.rate)
        g["controller_slots"]=json.dumps(self.controller_slots,separators=(",",":"))
        g["controller_blacklist"]=json.dumps(sorted(self.controller_blacklist),separators=(",",":"))
        g["auto_start"]="1" if (self.auto_check.isChecked() if hasattr(self,"auto_check") else self.auto_start) else "0"
        g["start_in_tray"]="1" if (self.tray_check.isChecked() if hasattr(self,"tray_check") else self.start_in_tray) else "0"
        g["layout"]="position"
        g["deadzone"]=str(self.controller_deadzones.get("xinput",6000))

        for family,value in self.controller_deadzones.items():
            g[f"deadzone_{family}"]=str(int(value))

        g["steam_profile"]=self.profile_slot
        g["steam_gyro_trim"]="1" if (
            self.steam_gyro_trim_check.isChecked()
            if hasattr(self,"steam_gyro_trim_check") else self.steam_gyro_trim
        ) else "0"
        for i,slot in enumerate(STEAM_PROFILE_NAMES[1:],1):
            g[f"steam_profile_name_{i}"]=self.profile_names.get(slot,slot)
        for slot,mapping in self.profiles.items():
            sec=f"steam_profile:{slot}"
            if not self.settings.has_section(sec):self.settings.add_section(sec)
            for key,value in mapping.items():self.settings[sec][key]=value

        for family,spec in LINUX_MAPPING_SPECS.items():
            g[f"{family}_profile"]=self.controller_profile_slots.get(family,"Default")
            for i,slot in enumerate(CONTROLLER_PROFILE_SLOTS[1:],1):
                g[f"{family}_profile_name_{i}"]=self.controller_profile_names[family].get(slot,slot)
            for slot,mapping in self.controller_profiles[family].items():
                sec=f"controller_profile:{family}:{slot}"
                if not self.settings.has_section(sec):self.settings.add_section(sec)
                for source,_ in spec["sources"]:
                    self.settings[sec][source]=mapping.get(source,"None")

        g["keyboard_enabled"]="1" if (
            self.keyboard_enabled_check.isChecked()
            if hasattr(self,"keyboard_enabled_check") else self.keyboard_enabled
        ) else "0"
        g["keyboard_exclusive"]="1" if (
            self.keyboard_exclusive_check.isChecked()
            if hasattr(self,"keyboard_exclusive_check") else self.keyboard_exclusive
        ) else "0"
        g["keyboard_release_key"]=(
            self.keyboard_release_combo.currentText()
            if hasattr(self,"keyboard_release_combo") else self.keyboard_release_key
        )
        g["mouse_sensitivity"]=str(
            self.mouse_sensitivity_spin.value()
            if hasattr(self,"mouse_sensitivity_spin") else self.mouse_sensitivity
        )
        g["keyboard_profile"]=self.keyboard_profile
        for i,slot in enumerate(CONTROLLER_PROFILE_SLOTS[1:],1):
            g[f"keyboard_profile_name_{i}"]=self.keyboard_profile_names.get(slot,slot)
        active_keyboard=self.active_keyboard_mapping()
        g["keyboard_mapping"]=json.dumps(active_keyboard,separators=(",",":"))
        for slot,mapping in self.keyboard_profiles.items():
            sec=f"keyboard_profile:{slot}"
            if not self.settings.has_section(sec):self.settings.add_section(sec)
            for action,_ in KEYBOARD_ACTIONS:
                self.settings[sec][action]=mapping.get(action,DEFAULT_KEYBOARD_MAPPING[action])

        for legacy in (
            "backend","controller","controller_path",
            "player2_enabled","backend2","controller2","controller2_path"
        ):
            g.pop(legacy,None)

        with cfg_path().open("w",encoding="utf-8") as f:
            self.settings.write(f)

        if hasattr(self,"autostart_check"):
            set_autostart(self.autostart_check.isChecked())
    def build_ui(self):
        self.resize(920,660)
        self.setMinimumSize(760,540)

        root=QtWidgets.QWidget()
        self.setCentralWidget(root)
        outer=QtWidgets.QVBoxLayout(root)
        outer.setContentsMargins(10,10,10,8)
        outer.setSpacing(7)

        tabs=QtWidgets.QTabWidget()
        outer.addWidget(tabs,1)

        # Controllers
        controllers=QtWidgets.QWidget()
        tabs.addTab(controllers,"Controllers")
        cv=QtWidgets.QVBoxLayout(controllers)

        hint=QtWidgets.QLabel(
            "Slots 1 and 2 are active P1/P2. Reorder by drag and drop or "
            "with Up / Down. Slots 3 to 5 remain detected but inactive."
        )
        hint.setWordWrap(True);cv.addWidget(hint)

        self.controller_list=StableControllerRoster()
        self._roster_drag_active=False
        self.controller_list.reorderRequested.connect(self.move_controller_rows)
        self.controller_list.dragActiveChanged.connect(self._set_roster_drag_active)
        self.controller_list.setAlternatingRowColors(True)
        cv.addWidget(self.controller_list,1)

        row=QtWidgets.QHBoxLayout()
        self.up_btn=QtWidgets.QPushButton("↑ Up")
        self.down_btn=QtWidgets.QPushButton("↓ Down")
        self.blacklist_btn=QtWidgets.QPushButton("Blacklist selected")
        manage_blacklist=QtWidgets.QPushButton("Manage blacklist…")
        self.refresh_btn=QtWidgets.QPushButton("Refresh")
        row.addWidget(self.up_btn);row.addWidget(self.down_btn)
        row.addWidget(self.blacklist_btn);row.addWidget(manage_blacklist)
        row.addStretch(1);row.addWidget(self.refresh_btn)
        cv.addLayout(row)
        self.up_btn.clicked.connect(lambda:self.move_controller(-1))
        self.down_btn.clicked.connect(lambda:self.move_controller(1))
        self.blacklist_btn.clicked.connect(self.blacklist_selected)
        manage_blacklist.clicked.connect(self.open_blacklist_dialog)
        self.refresh_btn.clicked.connect(lambda:self.refresh_controllers(force=True))

        # Mappings
        mappings=QtWidgets.QWidget()
        tabs.addTab(mappings,"Mappings")
        map_outer=QtWidgets.QVBoxLayout(mappings)
        scroll=QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        map_body=QtWidgets.QWidget()
        mv=QtWidgets.QVBoxLayout(map_body)
        scroll.setWidget(map_body);map_outer.addWidget(scroll)

        steam_box=QtWidgets.QGroupBox("Steam Controller 2026")
        sf=QtWidgets.QFormLayout(steam_box)
        self.profile_combo=QtWidgets.QComboBox()
        self.profile_combo.currentIndexChanged.connect(self.on_profile_changed)
        self.refresh_profile_combo()
        edit_steam=QtWidgets.QPushButton("Edit profiles…")
        edit_steam.clicked.connect(self.edit_profile)
        profile_row=QtWidgets.QHBoxLayout()
        profile_row.addWidget(self.profile_combo,1);profile_row.addWidget(edit_steam)
        sf.addRow("Mapping profile",profile_row)
        self.steam_gyro_trim_check=QtWidgets.QCheckBox(
            "Gyro trim (80% roll / 90% pitch-yaw)"
        )
        self.steam_gyro_trim_check.setChecked(self.steam_gyro_trim)
        sf.addRow("",self.steam_gyro_trim_check)
        mv.addWidget(steam_box)

        self.controller_profile_combos={}
        for family in ("dualsense","stadia","switchpro","switch2pro","xinput","generic"):
            box=QtWidgets.QGroupBox(LINUX_MAPPING_SPECS[family]["title"])
            form=QtWidgets.QFormLayout(box)
            combo=QtWidgets.QComboBox()
            self.controller_profile_combos[family]=combo
            self.refresh_controller_profile_combo(family)
            combo.currentIndexChanged.connect(
                lambda _idx,f=family:self.on_controller_profile_changed(f)
            )
            edit=QtWidgets.QPushButton("Edit profiles…")
            edit.clicked.connect(lambda _checked=False,f=family:self.edit_controller_profile(f))
            rr=QtWidgets.QHBoxLayout();rr.addWidget(combo,1);rr.addWidget(edit)
            form.addRow("Mapping profile",rr)
            if family=="switch2pro":
                note=QtWidgets.QLabel(
                    "C / GL / GR use the native Switch 2 Pro HID report and do "
                    "not depend on Linux evdev button numbering."
                )
                note.setWordWrap(True);form.addRow("",note)
            mv.addWidget(box)

        keyboard=QtWidgets.QGroupBox("Keyboard + Mouse Controller (experimental)")
        kf=QtWidgets.QFormLayout(keyboard)
        self.keyboard_enabled_check=QtWidgets.QCheckBox(
            "Show Keyboard + Mouse in controller roster"
        )
        self.keyboard_enabled_check.setChecked(self.keyboard_enabled)
        self.keyboard_enabled_check.toggled.connect(
            lambda _v:self._keyboard_controller_option_changed()
        )
        self.keyboard_exclusive_check=QtWidgets.QCheckBox(
            "Exclusive capture while active (recommended with Moonlight)"
        )
        self.keyboard_exclusive_check.setChecked(self.keyboard_exclusive)
        self.keyboard_release_combo=QtWidgets.QComboBox()
        self.keyboard_release_combo.addItems(RELEASE_KEY_CHOICES)
        self.keyboard_release_combo.setCurrentText(self.keyboard_release_key)
        self.keyboard_release_combo.currentTextChanged.connect(
            lambda _v:self._keyboard_release_key_changed()
        )
        self.mouse_sensitivity_spin=QtWidgets.QSpinBox()
        self.mouse_sensitivity_spin.setRange(100,20000)
        self.mouse_sensitivity_spin.setValue(self.mouse_sensitivity)
        self.keyboard_profile_combo=QtWidgets.QComboBox()
        self.refresh_keyboard_profile_combo()
        self.keyboard_profile_combo.currentIndexChanged.connect(
            self.on_keyboard_profile_changed
        )
        edit_keyboard=QtWidgets.QPushButton("Edit profiles…")
        edit_keyboard.clicked.connect(self.open_keyboard_mapping_editor)
        kr=QtWidgets.QHBoxLayout()
        kr.addWidget(self.keyboard_profile_combo,1);kr.addWidget(edit_keyboard)
        kf.addRow("",self.keyboard_enabled_check)
        kf.addRow("",self.keyboard_exclusive_check)
        kf.addRow("Emergency release",self.keyboard_release_combo)
        kf.addRow("Mouse sensitivity",self.mouse_sensitivity_spin)
        kf.addRow("Mapping profile",kr)
        mv.addWidget(keyboard)

        deadzones=QtWidgets.QGroupBox("Stick deadzones")
        df=QtWidgets.QGridLayout(deadzones)
        df.addWidget(QtWidgets.QLabel(
            "Independent deadzone for each controller family."
        ),0,0,1,3)
        self.deadzone_sliders={}
        self.deadzone_spins={}
        for row,family in enumerate(
            ("steam","dualsense","stadia","switchpro","switch2pro","xinput","generic"),
            start=1,
        ):
            label=QtWidgets.QLabel(CONTROLLER_DEADZONE_SPECS[family])
            slider=QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            slider.setRange(0,16000)
            slider.setValue(self.controller_deadzones[family])
            spin=QtWidgets.QSpinBox()
            spin.setRange(0,16000);spin.setSingleStep(100)
            spin.setValue(self.controller_deadzones[family])
            slider.valueChanged.connect(spin.setValue)
            spin.valueChanged.connect(slider.setValue)
            slider.sliderReleased.connect(
                lambda f=family:self.commit_deadzone(f)
            )
            spin.editingFinished.connect(
                lambda f=family:self.commit_deadzone(f)
            )
            self.deadzone_sliders[family]=slider
            self.deadzone_spins[family]=spin
            df.addWidget(label,row,0);df.addWidget(slider,row,1);df.addWidget(spin,row,2)
        df.setColumnStretch(1,1)
        mv.addWidget(deadzones)
        mv.addStretch(1)

        # Network
        network=QtWidgets.QWidget()
        tabs.addTab(network,"Network")
        nv=QtWidgets.QVBoxLayout(network)
        net=QtWidgets.QGroupBox("SwitchNet connection")
        nf=QtWidgets.QFormLayout(net)
        self.host_edit=QtWidgets.QLineEdit(self.host)
        self.port_spin=QtWidgets.QSpinBox();self.port_spin.setRange(1,65535);self.port_spin.setValue(self.port)
        self.rate_spin=QtWidgets.QSpinBox();self.rate_spin.setRange(30,1000);self.rate_spin.setValue(self.rate)
        self.discover_btn=QtWidgets.QPushButton("Discover SwitchNet")
        self.discover_btn.clicked.connect(self.discover_device)
        nf.addRow("SwitchNet IP / hostname",self.host_edit)
        nf.addRow("UDP port",self.port_spin)
        nf.addRow("UDP rate",self.rate_spin)
        nf.addRow("",self.discover_btn)
        nv.addWidget(net);nv.addStretch(1)

        # Extra
        extra=QtWidgets.QWidget()
        tabs.addTab(extra,"Extra")
        ev=QtWidgets.QVBoxLayout(extra)
        startup=QtWidgets.QGroupBox("Startup")
        exf=QtWidgets.QVBoxLayout(startup)
        self.auto_check=QtWidgets.QCheckBox("Start service automatically")
        self.auto_check.setChecked(self.auto_start)
        self.tray_check=QtWidgets.QCheckBox("Start in tray")
        self.tray_check.setChecked(self.start_in_tray)
        self.autostart_check=QtWidgets.QCheckBox("Start SwitchNet at login")
        self.autostart_check.setChecked(autostart_enabled())
        exf.addWidget(self.auto_check);exf.addWidget(self.tray_check);exf.addWidget(self.autostart_check)
        ev.addWidget(startup);ev.addStretch(1)

        # Diagnostics
        diagnostics=QtWidgets.QWidget()
        tabs.addTab(diagnostics,"Diagnostics")
        dv=QtWidgets.QVBoxLayout(diagnostics)
        self.detail_label=QtWidgets.QLabel("P1: None · P2: None")
        self.stats_label=QtWidgets.QLabel("")
        self.stats_label.setWordWrap(True)
        self.switch2_usb_status=QtWidgets.QLabel("Switch 2 Pro USB: idle")
        self.diagnostics_text=QtWidgets.QPlainTextEdit()
        self.diagnostics_text.setReadOnly(True)
        self.diagnostics_text.setLineWrapMode(
            QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap
        )
        dv.addWidget(self.detail_label)
        dv.addWidget(self.stats_label)
        dv.addWidget(self.switch2_usb_status)
        dv.addWidget(self.diagnostics_text,1)

        # Fixed bottom status bar.
        line=QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        outer.addWidget(line)
        bar=QtWidgets.QHBoxLayout()
        self.service_dot=QtWidgets.QLabel("●")
        self.status_label=QtWidgets.QLabel("Service stopped")
        self.service_toggle=QtWidgets.QPushButton("Start")
        self.service_toggle.clicked.connect(self.toggle_service)
        self.wake_btn=QtWidgets.QPushButton("Wake Switch 2")
        self.wake_btn.clicked.connect(self.wake_switch2)
        hide_btn=QtWidgets.QPushButton("Hide to tray")
        hide_btn.clicked.connect(self.hide)
        self.close_btn=QtWidgets.QPushButton("Close")
        self.close_btn.clicked.connect(self.exit_app)
        bar.addWidget(self.service_dot)
        bar.addWidget(self.status_label,1)
        bar.addWidget(self.service_toggle)
        bar.addWidget(self.wake_btn)
        bar.addWidget(hide_btn)
        bar.addWidget(self.close_btn)
        outer.addLayout(bar)
        self.update_service_controls()
    def active_keyboard_mapping(self):
        if self.keyboard_profile=="Default":
            mapping=normalized_keyboard_mapping(None)
        else:
            mapping=dict(
                self.keyboard_profiles.get(
                    self.keyboard_profile,
                    normalized_keyboard_mapping(None),
                )
            )
        return mapping_without_release_conflict(
            mapping,self.keyboard_release_key
        )

    def refresh_keyboard_profile_combo(self):
        if not hasattr(self,"keyboard_profile_combo"):return
        self.keyboard_profile_combo.blockSignals(True)
        self.keyboard_profile_combo.clear()
        for slot in CONTROLLER_PROFILE_SLOTS:
            label="Default" if slot=="Default" else self.keyboard_profile_names.get(slot,slot)
            self.keyboard_profile_combo.addItem(label,slot)
        pos=self.keyboard_profile_combo.findData(self.keyboard_profile)
        self.keyboard_profile_combo.setCurrentIndex(pos if pos>=0 else 0)
        self.keyboard_profile_combo.blockSignals(False)

    def on_keyboard_profile_changed(self,*_args):
        if not hasattr(self,"keyboard_profile_combo"):return
        slot=self.keyboard_profile_combo.currentData()
        if not slot or slot==self.keyboard_profile:return
        self.keyboard_profile=slot
        self.save_config()
        for index,d in enumerate(self.active_controller_descriptors()):
            worker=self.worker if index==0 else self.worker2
            if d and d.get("backend")=="keyboard_mouse" and worker.running:
                self.restart_slot(index,"keyboard mapping profile changed")

    def _keyboard_controller_option_changed(self):
        self.keyboard_enabled=bool(self.keyboard_enabled_check.isChecked())
        self.save_config()
        self._last_roster_signature=None
        self.refresh_controllers(force=True)
        self.schedule_service_restart("Keyboard+Mouse roster changed")

    def _keyboard_release_key_changed(self):
        self.keyboard_release_key=normalized_release_key(
            self.keyboard_release_combo.currentText()
        )
        for slot,mapping in list(self.keyboard_profiles.items()):
            self.keyboard_profiles[slot]=mapping_without_release_conflict(
                mapping,self.keyboard_release_key
            )
        self.save_config()
        for index,d in enumerate(self.active_controller_descriptors()):
            worker=self.worker if index==0 else self.worker2
            if d and d.get("backend")=="keyboard_mouse" and worker.running:
                self.restart_slot(index,"keyboard release key changed")

    def open_keyboard_mapping_editor(self):
        slot=self.keyboard_profile if self.keyboard_profile!="Default" else "Custom 1"
        mapping=self.keyboard_profiles.get(slot,normalized_keyboard_mapping(None))
        dlg=KeyboardProfilesDialog(
            self,slot,self.keyboard_profile_names.get(slot,slot),
            mapping,self.keyboard_release_combo.currentText()
        )
        dlg.saved.connect(self.save_keyboard_profile)
        dlg.exec()

    def save_keyboard_profile(self,slot,name,mapping):
        self.keyboard_profile_names[slot]=name
        self.keyboard_profiles[slot]=mapping_without_release_conflict(
            mapping,self.keyboard_release_key
        )
        self.keyboard_profile=slot
        self.refresh_keyboard_profile_combo()
        self.save_config()
        for index,d in enumerate(self.active_controller_descriptors()):
            worker=self.worker if index==0 else self.worker2
            if d and d.get("backend")=="keyboard_mouse" and worker.running:
                self.restart_slot(index,"keyboard mapping profile saved")

    def refresh_controller_profile_combo(self,family):
        combo=getattr(self,"controller_profile_combos",{}).get(family)
        if combo is None:return
        combo.blockSignals(True);combo.clear()
        selected=self.controller_profile_slots.get(family,"Default")
        for slot in CONTROLLER_PROFILE_SLOTS:
            label="Default" if slot=="Default" else self.controller_profile_names[family].get(slot,slot)
            combo.addItem(label,slot)
        pos=combo.findData(selected)
        combo.setCurrentIndex(pos if pos>=0 else 0)
        combo.blockSignals(False)

    def on_controller_profile_changed(self,family):
        combo=self.controller_profile_combos.get(family)
        if combo is None:return
        slot=combo.currentData()
        if not slot or slot==self.controller_profile_slots.get(family):return
        self.controller_profile_slots[family]=slot
        self.save_config()
        for index,d in enumerate(self.active_controller_descriptors()):
            worker=self.worker if index==0 else self.worker2
            if d and d.get("family","generic")==family and worker.running:
                self.restart_slot(index,f"{family} mapping profile changed")

    def edit_controller_profile(self,family):
        selected=self.controller_profile_slots.get(family,"Default")
        slot=selected if selected!="Default" else "Custom 1"
        mapping=self.controller_profiles[family].get(
            slot,default_linux_mapping(family)
        )
        dlg=GenericMappingDialog(
            self,family,slot,
            self.controller_profile_names[family].get(slot,slot),
            mapping,
        )
        dlg.saved.connect(
            lambda saved_slot,name,new_mapping,f=family:
                self.save_controller_profile(f,saved_slot,name,new_mapping)
        )
        dlg.exec()

    def save_controller_profile(self,family,slot,name,mapping):
        self.controller_profile_names[family][slot]=name
        self.controller_profiles[family][slot]=dict(mapping)
        self.controller_profile_slots[family]=slot
        self.refresh_controller_profile_combo(family)
        self.save_config()
        for index,d in enumerate(self.active_controller_descriptors()):
            worker=self.worker if index==0 else self.worker2
            if d and d.get("family","generic")==family and worker.running:
                self.restart_slot(index,f"{family} mapping profile saved")

    def commit_deadzone(self,family):
        spin=self.deadzone_spins[family]
        self.controller_deadzones[family]=max(0,min(16000,spin.value()))
        self.save_config()
        for index,d in enumerate(self.active_controller_descriptors()):
            worker=self.worker if index==0 else self.worker2
            if d and d.get("family","generic")==family and worker.running:
                self.restart_slot(index,f"{family} deadzone changed")

    def open_blacklist_dialog(self):
        dlg=BlacklistDialog(self)
        dlg.populate(self.controller_blacklist,self.controller_catalog)
        def restore(key):
            if key:
                self.controller_blacklist.discard(key)
                self.save_config()
                self._last_roster_signature=None
                self.refresh_controllers(force=True)
                dlg.populate(self.controller_blacklist,self.controller_catalog)
                self.schedule_service_restart("controller restored")
        dlg.restoreRequested.connect(restore)
        dlg.exec()

    def update_service_controls(self):
        running=bool(self.worker.running or self.worker2.running)
        if hasattr(self,"service_toggle"):
            self.service_toggle.setText("Stop" if running else "Start")
        if hasattr(self,"service_dot"):
            self.service_dot.setStyleSheet(
                "color:#2e7d32;font-size:18px;" if running
                else "color:#c62828;font-size:18px;"
            )
    def build_tray(self):
        self.tray=QtWidgets.QSystemTrayIcon(self);self.icon_on=self.make_icon(QtGui.QColor("#27ae60"));self.icon_off=self.make_icon(QtGui.QColor("#7f8c8d"));self.tray.setIcon(self.icon_off);self.tray.setToolTip("SwitchNet");m=QtWidgets.QMenu();self.tray_status=m.addAction("Service: Stopped");self.tray_status.setEnabled(False);self.tray_controller=m.addAction("Controller: None");self.tray_controller.setEnabled(False);m.addSeparator();op=m.addAction("Open SwitchNet");op.triggered.connect(self.show_normal);self.tray_toggle=m.addAction("Start service");self.tray_toggle.triggered.connect(self.toggle_service);self.tray_wake=m.addAction("Wake Switch 2");self.tray_wake.triggered.connect(self.wake_switch2);m.addSeparator();ex=m.addAction("Exit");ex.triggered.connect(self.exit_app);self.tray.setContextMenu(m);self._tray_last_trigger=0.0;self.tray.activated.connect(self.tray_activated);self.tray.show()
    def make_icon(self,color):
        p=QtGui.QPixmap(64,64);p.fill(QtCore.Qt.GlobalColor.transparent);q=QtGui.QPainter(p);q.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing);q.setBrush(color);q.setPen(QtGui.QPen(QtGui.QColor("white"),4));q.drawRoundedRect(6,6,52,52,14,14);q.drawText(p.rect(),QtCore.Qt.AlignmentFlag.AlignCenter,"S");q.end();return QtGui.QIcon(p)
    def tray_activated(self,reason):
        # Plasma's StatusNotifierItem backend may expose a double click as
        # two Trigger activations rather than QSystemTrayIcon.DoubleClick.
        now=time.monotonic()
        if reason==QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick:
            self._tray_last_trigger=0.0
            self.show_normal()
        elif reason==QtWidgets.QSystemTrayIcon.ActivationReason.Trigger:
            if now-self._tray_last_trigger<=0.45:
                self._tray_last_trigger=0.0
                self.show_normal()
            else:
                self._tray_last_trigger=now

    def _auto_discover_if_needed(self):
        self.discover_device()

    @QtCore.Slot()
    def discover_device(self):
        if hasattr(self,"discover_btn"):
            self.discover_btn.setEnabled(False)
        self.status_label.setText("Discovering SwitchNet…")
        threading.Thread(
            target=self._discover_device_thread,
            name="SwitchNet-Discovery",
            daemon=True,
        ).start()

    def _discover_device_thread(self):
        result=discover_switchnet(timeout=1.2)
        self.discoveryResult.emit(result)

    def _finish_discovery(self,result):
        if hasattr(self,"discover_btn"):
            self.discover_btn.setEnabled(True)
        if result:
            self.host_edit.setText(result["ip"])
            self.status_label.setText(
                f'Discovered SwitchNet {result["version"] or ""} at {result["ip"]}'
            )
            self.save_config()
        else:
            self.status_label.setText(
                "SwitchNet discovery failed; enter the IP or use switchnet.local"
            )

    @QtCore.Slot()
    def wake_switch2(self):
        host=self.host_edit.text().strip()
        if not host:
            self.status_label.setText("Wake error: SwitchNet host is empty")
            return
        self.wake_btn.setEnabled(False)
        self.status_label.setText("Sending Switch 2 wake beacon…")
        threading.Thread(
            target=self._wake_request_thread,
            args=(host,),
            name="SwitchNet-Wake",
            daemon=True,
        ).start()

    def _wake_request_thread(self,host):
        try:
            base=host.rstrip("/")
            if not base.startswith(("http://","https://")):
                base="http://"+base
            req=urllib.request.Request(
                base+"/api/wake",
                data=b"",
                method="POST",
                headers={"Accept":"application/json"},
            )
            with urllib.request.urlopen(req,timeout=4.0) as response:
                payload=json.loads(response.read().decode("utf-8"))
            if not payload.get("ok"):
                raise RuntimeError(payload.get("error","wake request rejected"))
            self.wakeResult.emit(True,"Switch 2 wake beacon started")
        except Exception as exc:
            self.wakeResult.emit(False,f"Wake error: {exc}")

    @QtCore.Slot(bool,str)
    def on_wake_result(self,ok,message):
        self.wake_btn.setEnabled(True)
        self.status_label.setText(message)

    def show_normal(self):
        self.showNormal()
        self.setWindowState(
            self.windowState() & ~QtCore.Qt.WindowState.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()
        handle=self.windowHandle()
        if handle is not None:
            try:
                handle.requestActivate()
            except Exception:
                pass
    def toggle_service(self):self.stop_service() if (self.worker.running or self.worker2.running) else self.start_service()
    def exit_app(self):
        self.save_config()
        try:
            if hasattr(self,"switch2_usb_timer"):
                self.switch2_usb_timer.stop()
        except Exception:
            pass
        self.worker.stop()
        self.worker2.stop()
        self.api.stop()
        self.tray.hide()
        QtWidgets.QApplication.quit()
    def update_tray(self):
        running=bool(self.worker.running or self.worker2.running)
        snap=self.worker.snapshot();snap2=self.worker2.snapshot()
        self.tray.setIcon(self.icon_on if running else self.icon_off)
        self.tray_status.setText("Service: Running" if running else "Service: Stopped")
        self.tray_controller.setText(
            "Controllers: P1 "+str(snap.get("controller","None") if self.worker.running else "None")
            +" · P2 "+str(snap2.get("controller","None") if self.worker2.running else "None")
        )
        self.tray_toggle.setText("Stop service" if running else "Start service")
        self.update_service_controls()
    def _controller_roster_signature(self):
        catalog_sig=[]
        for key in self.controller_slots:
            d=self.controller_catalog.get(key)
            if d:
                catalog_sig.append((
                    key,d.get("name",""),d.get("detail",""),
                    tuple(d.get("paths") or ()),d.get("path","")
                ))
            else:
                catalog_sig.append((key,"","","",""))
        return (
            tuple(self.controller_slots),
            tuple(catalog_sig),
            tuple(sorted(self.controller_blacklist)),
        )

    def _selected_controller_identity(self):
        if not hasattr(self,"controller_list"):
            return "",-1
        row=self.controller_list.currentRow()
        item=self.controller_list.currentItem()
        key=str(item.data(QtCore.Qt.ItemDataRole.UserRole) or "") if item else ""
        return key,row

    def schedule_service_restart(self,reason="controller roster changed"):
        if not (self.worker.running or self.worker2.running):
            return
        self._service_restart_reason=str(reason or "controller roster changed")
        if self._service_restart_timer is None:
            self._service_restart_timer=QtCore.QTimer(self)
            self._service_restart_timer.setSingleShot(True)
            self._service_restart_timer.timeout.connect(
                self._perform_scheduled_service_restart
            )
        self._service_restart_timer.start(350)

    def _perform_scheduled_service_restart(self):
        reason=self._service_restart_reason or "controller roster changed"
        self._service_restart_reason=""
        if not (self.worker.running or self.worker2.running):
            return
        self.stop_service()
        QtCore.QTimer.singleShot(
            120,
            lambda:self._finish_scheduled_service_restart(reason)
        )

    def _finish_scheduled_service_restart(self,reason):
        self.start_service()
        if hasattr(self,"status"):
            self.status.setText(f"Service restarted: {reason}")

    def refresh_controllers(self,force=False):
        """Refresh discovery without destabilizing active realtime workers.

        Discovery is not authoritative for a single scan. A device must be
        absent for 3 consecutive scans (~9 s) before its logical roster entry
        is removed. New devices must be seen twice before they are allowed to
        auto-fill an active empty slot while the service is running.
        """
        if not hasattr(self,"controller_list"):
            return

        # Hot-plug discovery must never rebuild the view during an active drag.
        if not force and getattr(self,"_roster_drag_active",False):
            return

        selected_key,selected_row=self._selected_controller_identity()
        old_catalog=dict(self.controller_catalog)
        old_catalog_keys=set(old_catalog.keys())
        old_slots=tuple(self.controller_slots)
        old_active=tuple(
            (self.controller_slots+["",""])[:2]
        )

        discovered=discover_supported_controllers_linux(self.keyboard_enabled_check.isChecked())

        # A Switch 2 Pro may enter the roster first as a USB placeholder and
        # then reappear with a real evdev identity after Nintendo USB
        # initialization. Promote the slot atomically instead of treating this
        # as a different newly connected controller.
        switch2_real=next(
            (
                d for d in discovered
                if d.get("family")=="switch2pro"
                and d.get("backend")=="switch2pro_hidraw"
                and not d.get("pending")
                and d.get("path")
            ),
            None,
        )
        if switch2_real is not None:
            placeholder="usb:057e:2069:switch2pro"
            self.controller_slots=[
                switch2_real["key"] if key==placeholder else key
                for key in self.controller_slots
            ]

        current={d["key"]:d for d in discovered}

        # Update stable-seen counters.
        for key in current:
            self._controller_seen_counts[key]=self._controller_seen_counts.get(key,0)+1
            self._controller_missing_counts[key]=0

        # Retain descriptors through transient enumeration misses.
        merged=dict(current)
        protected_keys=set(k for k in self.controller_slots if k)
        for key,d in old_catalog.items():
            if key in current:
                continue
            misses=self._controller_missing_counts.get(key,0)+1
            self._controller_missing_counts[key]=misses
            if key in protected_keys and misses < 3:
                merged[key]=d

        self.controller_catalog=merged

        # Remove a roster entry only after confirmed absence. Active P1/P2 are
        # protected even longer while their worker is running; the worker's own
        # fd/read path is the authority for a real disconnect.
        slots=list(self.controller_slots)
        while len(slots)<5:
            slots.append("")
        if not self.keyboard_enabled_check.isChecked():
            slots=["" if k=="virtual:keyboard_mouse" else k for k in slots]

        for i,key in enumerate(list(slots)):
            if not key or key in self.controller_blacklist:
                if key in self.controller_blacklist:
                    slots[i]=""
                continue
            if key in current:
                continue
            misses=self._controller_missing_counts.get(key,0)
            worker_running=(i==0 and self.worker.running) or (i==1 and self.worker2.running)
            threshold=5 if worker_running else 3
            if misses >= threshold:
                slots[i]=""

        # Add newly discovered controllers. While gaming, require two stable
        # scans before filling P1/P2 automatically.
        assigned={k for k in slots if k}
        service_running=self.worker.running or self.worker2.running
        for d in discovered:
            key=d["key"]
            if key in self.controller_blacklist or key in assigned:
                continue
            seen=self._controller_seen_counts.get(key,0)
            candidate_indices=(list(range(2,len(slots))) if d.get("virtual") else list(range(len(slots))))
            if d.get("virtual") and len(slots)<5:
                candidate_indices+=list(range(len(slots),5))
            placed=False
            for i in candidate_indices:
                if slots[i]!="":
                    continue
                if service_running and i<2 and seen<2:
                    continue
                slots[i]=key
                assigned.add(key)
                placed=True
                break
            if not placed:
                slots.append(key)
                assigned.add(key)

        while len(slots)<5:
            slots.append("")
        self.controller_slots=slots

        signature=self._controller_roster_signature()
        if force or signature!=self._last_roster_signature:
            self._render_controller_roster(selected_key,selected_row)
            self._last_roster_signature=self._controller_roster_signature()

        new_active=tuple((self.controller_slots+["",""])[:2])
        topology_changed=set(current.keys())!=old_catalog_keys
        roster_changed=tuple(self.controller_slots)!=old_slots

        if service_running and not force and (topology_changed or roster_changed):
            self.schedule_service_restart(
                "controller connected/removed"
                if topology_changed else
                "controller roster changed"
            )

    def _render_controller_roster(self,selected_key=None,selected_row=None):
        if selected_key is None or selected_row is None:
            selected_key,selected_row=self._selected_controller_identity()

        self.controller_list.blockSignals(True)
        self.controller_list.clear()
        restore_row=-1
        for i,key in enumerate(self.controller_slots):
            d=self.controller_catalog.get(key)
            if d:
                state="P1" if i==0 else "P2" if i==1 else "inactive"
                item=QtWidgets.QListWidgetItem(
                    f"{i+1} — {d['name']}   [{state}]   {d.get('detail','')}")
                item.setData(QtCore.Qt.ItemDataRole.UserRole,key)
                item.setToolTip(d.get("detail",""))
                if selected_key and key==selected_key:
                    restore_row=i
            else:
                item=QtWidgets.QListWidgetItem(f"{i+1} — None")
                item.setData(QtCore.Qt.ItemDataRole.UserRole,"")
                if not selected_key and i==selected_row:
                    restore_row=i
            item.setFlags(
                (item.flags() | QtCore.Qt.ItemFlag.ItemIsDragEnabled)
                & ~QtCore.Qt.ItemFlag.ItemIsDropEnabled
            )
            self.controller_list.addItem(item)

        if restore_row<0 and selected_row is not None and 0<=selected_row<self.controller_list.count():
            restore_row=selected_row
        if restore_row>=0:
            self.controller_list.setCurrentRow(restore_row)
        self.controller_list.blockSignals(False)

        # Blacklist is managed in a dedicated dialog in the parity UI.

    def active_controller_descriptors(self):
        slots=list(self.controller_slots)+["",""]
        return [self.controller_catalog.get(slots[0]),self.controller_catalog.get(slots[1])]

    def _set_roster_drag_active(self,active):
        self._roster_drag_active=bool(active)

    def move_controller_rows(self,source,target):
        """Atomically reorder one logical controller slot."""
        source=int(source)
        target=int(target)

        if source<0 or target<0:
            return
        if source>=len(self.controller_slots) or target>=len(self.controller_slots):
            return
        if source==target:
            return

        selected_key=self.controller_slots[source]
        before=tuple((self.controller_slots+["",""])[:2])

        self.controller_slots=roster_move(
            self.controller_slots,source,target,minimum_slots=4
        )
        after=tuple((self.controller_slots+["",""])[:2])

        self._last_roster_signature=None
        self._render_controller_roster(selected_key,target)
        self._last_roster_signature=self._controller_roster_signature()
        self.save_config()

        if before!=after and (self.worker.running or self.worker2.running):
            self.schedule_service_restart("controller roster reordered")

    def move_controller(self,delta):
        row=self.controller_list.currentRow()
        target=row+int(delta)
        if row<0 or target<0 or target>=len(self.controller_slots):
            return
        self.move_controller_rows(row,target)

    def blacklist_selected(self):
        item=self.controller_list.currentItem()
        if item is None:return
        key=str(item.data(QtCore.Qt.ItemDataRole.UserRole) or "")
        if not key:return
        self.controller_blacklist.add(key);self.controller_slots=["" if x==key else x for x in self.controller_slots];self.save_config();self._last_roster_signature=None;self.refresh_controllers(force=True)
        self.schedule_service_restart("controller blacklisted")

    def unblacklist_selected(self):
        self.open_blacklist_dialog()

    def _switch2_active_slots(self):
        result=[]
        active=self.active_controller_descriptors()
        for index,descriptor in enumerate(active):
            if (
                descriptor is not None
                and descriptor.get("family")=="switch2pro"
            ):
                result.append(index)
        return result

    def _switch2_slot_streaming(self,slot):
        worker=self.worker if int(slot)==0 else self.worker2
        if not worker.running:
            return False
        try:
            _payload,_vals,controller,_detail,kind,_age,_stamp,generation=(
                worker._input_snapshot()
            )
            return (
                int(generation)>0
                and str(kind) in ("evdev","switch2pro_hidraw")
                and str(controller or "None")!="None"
            )
        except Exception:
            return False

    def _switch2_is_functional(self):
        slots=self._switch2_active_slots()
        if not slots:
            return False
        return any(self._switch2_slot_streaming(slot) for slot in slots)

    def _maybe_initialize_switch2_pro(self):
        if not hasattr(self,"switch2_usb"):
            return
        if self._switch2_init_running:
            return

        usb_present=Switch2ProUsbEnabler.usb_present()
        evdev_present=Switch2ProUsbEnabler.evdev_present()
        active_slots=self._switch2_active_slots()
        functional=self._switch2_is_functional()

        native_slots=[
            slot for slot in active_slots
            if (
                self.active_controller_descriptors()[slot] is not None
                and self.active_controller_descriptors()[slot].get("backend")=="switch2pro_hidraw"
                and not self.active_controller_descriptors()[slot].get("pending")
            )
        ]
        if native_slots:
            statuses=[]
            for slot in native_slots:
                worker=self.worker if slot==0 else self.worker2
                statuses.append(worker.switch2pro.snapshot().get("status","native HIDRaw"))
            if hasattr(self,"switch2_usb_status"):
                self.switch2_usb_status.setText("Switch 2 Pro USB: "+" · ".join(statuses))
            return

        if functional:
            self._switch2_silent_since=None
            if hasattr(self,"switch2_usb_status"):
                self.switch2_usb_status.setText(
                    "Switch 2 Pro USB: ready · input streaming"
                )
            return

        if not usb_present:
            self._switch2_silent_since=None
            if hasattr(self,"switch2_usb_status"):
                self.switch2_usb_status.setText(
                    "Switch 2 Pro USB: not connected"
                )
            return

        now=time.monotonic()
        if self._switch2_silent_since is None:
            self._switch2_silent_since=now

        silent_for=now-self._switch2_silent_since

        # An evdev node existing is not proof that Nintendo HID mode is active.
        # Give a newly-created node a short opportunity to stream, then
        # reinitialize if it remains silent.
        grace=2.5 if evdev_present else 0.5
        if silent_for<grace:
            if hasattr(self,"switch2_usb_status"):
                self.switch2_usb_status.setText(
                    "Switch 2 Pro USB: evdev present · waiting for input"
                    if evdev_present else
                    "Switch 2 Pro USB: USB present · waiting for HID interface"
                )
            return

        # Avoid hammering the vendor interface, but recover much sooner than
        # the old 15-second false-ready path.
        if now-self.switch2_usb.last_attempt<6.0:
            return

        # Release active evdev file descriptors before running the vendor USB
        # helper. This avoids the Linux input stack holding a stale/silent
        # collection while the controller changes mode.
        self._switch2_init_slots=list(active_slots)
        for slot in self._switch2_init_slots:
            worker=self.worker if slot==0 else self.worker2
            if worker.running:
                self._record_restart(
                    slot,"Switch 2 Pro silent-input USB reinitialization"
                )
                worker.stop()

        if hasattr(self,"switch2_usb_status"):
            self.switch2_usb_status.setText(
                "Switch 2 Pro USB: silent input · reinitializing HID mode..."
            )

        self._switch2_init_running=True
        threading.Thread(
            target=self._switch2_usb_init_thread,
            daemon=True,
            name="SwitchNet-Switch2Pro-USB-Init",
        ).start()

    def _switch2_usb_init_thread(self):
        ok,message=self.switch2_usb.initialize()
        self.switch2UsbInitResult.emit(ok,message)

    @QtCore.Slot(bool,str)
    def _finish_switch2_usb_init(self,ok,message):
        self._switch2_init_running=False
        slots=list(self._switch2_init_slots)
        self._switch2_init_slots=[]

        if hasattr(self,"switch2_usb_status"):
            self.switch2_usb_status.setText(
                "Switch 2 Pro USB: "+message
            )

        def refresh_and_restart():
            self._last_roster_signature=None
            self.refresh_controllers(force=True)

            for slot in slots:
                active=self.active_controller_descriptors()
                descriptor=active[slot] if slot<len(active) else None
                if (
                    descriptor is not None
                    and descriptor.get("family")=="switch2pro"
                    and not descriptor.get("pending")
                ):
                    self.restart_slot(
                        slot,
                        "Switch 2 Pro USB initialization completed",
                    )

            # Require a real input report before declaring readiness.
            self._switch2_silent_since=time.monotonic()

        # Re-enumeration can happen on both success and a partially-successful
        # helper exit, so always rescan after an initialization attempt.
        QtCore.QTimer.singleShot(
            1800,
            refresh_and_restart,
        )

    def current_controller_path(self):
        d=self.active_controller_descriptors()[0];return d.get("path","") if d else ""
    def current_controller_index(self):
        d=self.active_controller_descriptors()[0];return int(d.get("index",0)) if d else 0
    def current_controller2_path(self):
        d=self.active_controller_descriptors()[1];return d.get("path","") if d else ""
    def current_controller2_index(self):
        d=self.active_controller_descriptors()[1];return int(d.get("index",1)) if d else 1
    def refresh_profile_combo(self):
        if not hasattr(self,"profile_combo"):return
        self.profile_combo.blockSignals(True);self.profile_combo.clear();
        for slot in STEAM_PROFILE_NAMES:self.profile_combo.addItem(slot if slot=="Default" else self.profile_names.get(slot,slot),slot)
        pos=self.profile_combo.findData(self.profile_slot);self.profile_combo.setCurrentIndex(pos if pos>=0 else 0);self.profile_combo.blockSignals(False)
    def on_profile_changed(self,*_args):
        slot=self.profile_combo.currentData();
        if not slot or slot==self.profile_slot:return
        self.profile_slot=slot;self.save_config();
        if self.worker.running:
            QtCore.QTimer.singleShot(10,lambda:self.restart_slot(0,"Steam profile change"))
        if self.worker2.running:
            QtCore.QTimer.singleShot(10,lambda:self.restart_slot(1,"Steam profile change"))

    def on_layout_changed(self,*_args):
        # Compatibility shim for old signal connections/configurations.
        return

    def _record_restart(self,slot,reason):
        now=time.monotonic()
        self._restart_events.append((now,int(slot),str(reason)))
        self._restart_events=self._restart_events[-20:]

    def restart_slot(self,slot,reason="configuration change"):
        """Restart only one player worker; never interrupt the other player."""
        slot=int(slot)
        active=self.active_controller_descriptors()
        worker=self.worker if slot==0 else self.worker2
        self._record_restart(slot,reason)
        worker.stop()
        d=active[slot] if slot < len(active) else None
        if d is not None and not d.get("pending"):
            worker.start(self.build_worker_config(slot,d))
        self.update_tray()

    def restart_service(self):
        """Explicit full restart for global settings only."""
        self._record_restart(-1,"explicit/global configuration")
        self.stop_service()
        QtCore.QTimer.singleShot(80,self.start_service)
    def edit_profile(self):
        slot=self.profile_slot if self.profile_slot!="Default" else "Custom 1";dlg=MappingDialog(self,slot,self.profile_names.get(slot,slot),self.profiles.get(slot,default_steam_mapping(False)))
        dlg.saved.connect(self.save_profile);dlg.exec()
    def save_profile(self,slot,name,mapping):
        self.profile_names[slot]=name
        self.profiles[slot]=mapping
        self.profile_slot=slot
        self.refresh_profile_combo()
        self.save_config()
        for index,d in enumerate(self.active_controller_descriptors()):
            worker=self.worker if index==0 else self.worker2
            if d and d.get("backend") in ("steam_passive","steam_direct") and worker.running:
                self.restart_slot(index,"Steam profile saved")
    def build_worker_config(self,slot=0,descriptor=None):
        d=descriptor or self.active_controller_descriptors()[slot]
        backend=d.get("backend","evdev") if d else "evdev"
        family=d.get("family","generic") if d else "generic"

        steam_mapping=None
        if self.profile_slot!="Default":
            steam_mapping=dict(
                self.profiles.get(
                    self.profile_slot,default_steam_mapping(False)
                )
            )

        controller_mapping=None
        selected=self.controller_profile_slots.get(family,"Default")
        if family in self.controller_profiles and selected!="Default":
            controller_mapping=dict(
                self.controller_profiles[family].get(
                    selected,default_linux_mapping(family)
                )
            )

        deadzone=self.controller_deadzones.get(
            "steam" if backend in ("steam_passive","steam_direct") else family,
            6000,
        )

        return {
            "host":self.host_edit.text().strip(),
            "port":self.port_spin.value(),
            "rate":self.rate_spin.value(),
            "deadzone":deadzone,
            "labels":False,
            "backend":backend,
            "controller":int(d.get("index",slot)) if d else slot,
            "controller_path":d.get("path","") if d else "",
            "controller_paths":list(
                d.get("paths") or ([d.get("path")] if d and d.get("path") else [])
            ) if d else [],
            "controller_family":family,
            "controller_vendor":int(d.get("vendor",0) or 0) if d else 0,
            "controller_product":int(d.get("product",0) or 0) if d else 0,
            "controller_mapping":controller_mapping,
            "steam_mapping":steam_mapping,
            "steam_gyro_trim":self.steam_gyro_trim_check.isChecked(),
            "keyboard_mapping":self.active_keyboard_mapping(),
            "keyboard_exclusive":self.keyboard_exclusive_check.isChecked(),
            "keyboard_release_key":self.keyboard_release_combo.currentText(),
            "mouse_sensitivity":self.mouse_sensitivity_spin.value(),
            "slot":slot,
        }
    def on_status(self,s):self.update_tray()
    def refresh_ui(self):
        snap=self.worker.snapshot()
        snap2=self.worker2.snapshot()
        running=bool(self.worker.running or self.worker2.running)
        self.status_label.setText(
            "Service running" if running else "Service stopped"
        )
        self.update_service_controls()

        self.detail_label.setText(
            f"P1: {snap.get('controller','None') if self.worker.running else 'None'} · "
            f"P2: {snap2.get('controller','None') if self.worker2.running else 'None'}"
        )

        recent=""
        if self._restart_events:
            when,slot,reason=self._restart_events[-1]
            age=time.monotonic()-when
            if age<15:
                who="all" if slot<0 else f"P{slot+1}"
                recent=f" · restart {who} {age:.1f}s ago ({reason})"

        self.stats_label.setText(
            f"P1 TX {snap.get('txps',0)}/s input {snap.get('input_reports_s',0)}/s "
            f"age {snap.get('input_age_ms',-1)} ms · "
            f"P2 TX {snap2.get('txps',0) if self.worker2.running else 0}/s "
            f"input {snap2.get('input_reports_s',0) if self.worker2.running else 0}/s · "
            f"UDP late P1/P2 {snap.get('udp_late_ticks',0)}/"
            f"{snap2.get('udp_late_ticks',0) if self.worker2.running else 0}"
            f"{recent}"
        )

        if hasattr(self,"diagnostics_text"):
            active=self.active_controller_descriptors()
            lines=[
                f"SwitchNet Client {APP_VERSION}",
                f"Host: {self.host_edit.text().strip()}:{self.port_spin.value()} @ {self.rate_spin.value()} Hz",
                f"P1 worker: {'running' if self.worker.running else 'stopped'} · error {snap.get('worker_error','-') or '-'}",
                f"P2 worker: {'running' if self.worker2.running else 'stopped'} · error {snap2.get('worker_error','-') or '-'}",
                f"P1 input: {snap.get('controller','None')} · {snap.get('detail','')}",
                f"P1 stage: {snap.get('worker_stage','-')}",
                f"P2 input: {snap2.get('controller','None')} · {snap2.get('detail','')}",
                f"P2 stage: {snap2.get('worker_stage','-')}",
                f"P1 rumble: {snap.get('rumble_backend','none')} · errors {snap.get('rumble_errors',0)}",
                f"P2 rumble: {snap2.get('rumble_backend','none')} · errors {snap2.get('rumble_errors',0)}",
                "Deadzones: "+", ".join(
                    f"{family}={value}"
                    for family,value in self.controller_deadzones.items()
                ),
                f"Steam profile: {self.profile_slot}",
                "Profiles: "+", ".join(
                    f"{family}={slot}"
                    for family,slot in self.controller_profile_slots.items()
                ),
                f"Keyboard profile: {self.keyboard_profile}",
                (
                    "Switch 2 USB: "
                    + (
                        self.switch2_usb_status.text()
                        if hasattr(self,"switch2_usb_status") else "-"
                    )
                ),
                f"Config: {cfg_path()}",
            ]
            self.diagnostics_text.setPlainText("\\n".join(lines))

        self.update_tray()
    def api_status(self):
        s=self.worker.snapshot();return {"service":"SwitchNetClient","version":APP_VERSION,"running":self.worker.running,"controller_connected":s.get("controller","None")!="None","controller":s.get("controller","None"),"controller_detail":s.get("detail",""),"backend":s.get("backend",""),"controller_path":s.get("controller_path",""),"tx_per_second":s.get("txps",0),"immediate_tx_per_second":s.get("immediate_txps",0),"input_reports_per_second":s.get("input_reports_s",0),"input_age_ms":s.get("input_age_ms",-1),"input_to_udp_us":s.get("input_to_udp_us",0),"input_to_udp_max_us":s.get("input_to_udp_max_us",0),"udp_late_ticks":s.get("udp_late_ticks",0),"udp_max_late_us":s.get("udp_max_late_us",0),"udp_max_send_gap_us":s.get("udp_max_send_gap_us",0),"errors_per_second":s.get("errors",0),"rumble_packets_received":s.get("rumble",0),"rumble_applied":s.get("rumble_applied",0),"rumble_errors":s.get("rumble_errors",0),"rumble_backend":s.get("rumble_backend","none"),"rumble_output_error":s.get("rumble_output_error","")}


def main():
    app=QtWidgets.QApplication(sys.argv);app.setQuitOnLastWindowClosed(False)
    if InputDevice is None:
        QtWidgets.QMessageBox.critical(None,"SwitchNet",
            "python-evdev is missing. On CachyOS install it with:\n\nsudo pacman -S python-evdev")
        return 1
    w=MainWindow()
    code=app.exec()
    w.worker.stop();w.worker2.stop();w.api.stop()
    return code

if __name__=="__main__":raise SystemExit(main())
