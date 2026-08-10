#!/usr/bin/env python3
from __future__ import annotations

import configparser
import json
import re
import ctypes
import traceback
import os
import random
import socket
import struct
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import time
import urllib.error
import urllib.request
import tkinter as tk
import winreg
import zlib
from ctypes import wintypes
from tkinter import ttk, messagebox

from keyboard_mouse_backend import (
    KEYBOARD_ACTIONS, KEYBOARD_KEY_CHOICES, DEFAULT_KEYBOARD_MAPPING,
    RELEASE_KEY_CHOICES, DEFAULT_RELEASE_KEY,
    normalized_keyboard_mapping, normalized_release_key,
    mapping_without_release_conflict, keyboard_mouse_values,
    WindowsKeyboardMouseReader,
)
from switch2_pro_windows import (
    NINTENDO_VID, SWITCH2_PRO_PID,
    enumerate_switch2_pro_hid, Switch2ProReader,
)
from switch_pro_windows import (
    SWITCH_PRO_PID,
    enumerate_switch_pro_hid, SwitchProReader,
)


APP_VERSION = "1.26.0"
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
STEAM_COMBO_SOURCES = (("l5+r5", "L5 + R5"),)
STEAM_SOURCE_BUTTONS = (
    ("a", "A"), ("b", "B"), ("x", "X"), ("y", "Y"),
    ("lb", "L1"), ("rb", "R1"), ("back", "View / Back"),
    ("start", "Menu / Start"), ("ls", "L3"), ("rs", "R3"),
    ("guide", "Steam"), ("qam", "…"),
    ("l4", "L4"), ("l5", "L5"), ("r4", "R4"), ("r5", "R5"),
    ("up", "D-Pad Up"), ("down", "D-Pad Down"),
    ("left", "D-Pad Left"), ("right", "D-Pad Right"),
)
STEAM_MAPPING_SOURCES = STEAM_SOURCE_BUTTONS + STEAM_COMBO_SOURCES

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

SWITCH2_PRO_REAR_SOURCES = ("GL", "GR")
SWITCH2_PRO_REAR_TARGETS = STEAM_TARGETS

def default_switch2_pro_rear_mapping():
    return {"GL": "None", "GR": "None"}


def default_steam_mapping(labels=False):
    # The Default profile uses SwitchNet's established positional mapping.
    # Complete per-controller profiles replace the old global Button layout.
    face = {"a": "B", "b": "A", "x": "Y", "y": "X"}
    return {
        **face, "lb": "L", "rb": "R", "back": "-", "start": "+",
        "ls": "L3", "rs": "R3", "guide": "HOME", "qam": "CAPTURE",
        "l4": "None", "l5": "None", "r4": "None", "r5": "None",
        "up": "D-Pad Up", "down": "D-Pad Down",
        "left": "D-Pad Left", "right": "D-Pad Right",
        "l5+r5": "None",
    }

CONTROLLER_PROFILE_SLOTS = ("Default", "Custom 1", "Custom 2", "Custom 3")

CONTROLLER_DEADZONE_SPECS = {
    "steam": {"title":"Steam Controller 2026","backends":("steam_passive","steam_direct")},
    "dualsense": {"title":"DualSense","backends":("dualsense_hid",)},
    "stadia": {"title":"Google Stadia Controller","backends":("stadia_hid",)},
    "switchpro": {"title":"Nintendo Switch Pro Controller","backends":("switchpro_hid",)},
    "switch2pro": {"title":"Nintendo Switch 2 Pro Controller","backends":("switch2pro_hid",)},
    "xinput": {"title":"XInput","backends":("xinput",)},
}

def controller_deadzone_key_for_backend(backend):
    backend=str(backend or "")
    for key,spec in CONTROLLER_DEADZONE_SPECS.items():
        if backend in spec["backends"]:
            return key
    return "xinput"


CONTROLLER_MAPPING_SPECS = {
    "dualsense": {
        "title": "DualSense",
        "backends": ("dualsense_hid",),
        "sources": (
            ("cross","Cross"),("circle","Circle"),("square","Square"),
            ("triangle","Triangle"),("l1","L1"),("r1","R1"),
            ("l2","L2"),("r2","R2"),("create","Create"),
            ("options","Options"),("l3","L3"),("r3","R3"),
            ("ps","PS"),("touchpad","Touchpad"),
            ("up","D-Pad Up"),("down","D-Pad Down"),
            ("left","D-Pad Left"),("right","D-Pad Right"),
        ),
    },
    "stadia": {
        "title": "Google Stadia Controller",
        "backends": ("stadia_hid",),
        "sources": (
            ("a","A"),("b","B"),("x","X"),("y","Y"),
            ("l1","L1"),("r1","R1"),("l2","L2"),("r2","R2"),
            ("l3","L3"),("r3","R3"),("back","Options / Back"),
            ("start","Menu / Start"),("home","Stadia"),
            ("assistant","Assistant"),("capture","Capture"),
            ("up","D-Pad Up"),("down","D-Pad Down"),
            ("left","D-Pad Left"),("right","D-Pad Right"),
        ),
    },
    "switchpro": {
        "title": "Nintendo Switch Pro Controller",
        "backends": ("switchpro_hid",),
        "sources": (
            ("a","A"),("b","B"),("x","X"),("y","Y"),
            ("l","L"),("r","R"),("zl","ZL"),("zr","ZR"),
            ("minus","-"),("plus","+"),("l3","L3"),("r3","R3"),
            ("home","HOME"),("capture","CAPTURE"),
            ("up","D-Pad Up"),("down","D-Pad Down"),
            ("left","D-Pad Left"),("right","D-Pad Right"),
        ),
    },
    "switch2pro": {
        "title": "Nintendo Switch 2 Pro Controller",
        "backends": ("switch2pro_hid",),
        "sources": (
            ("a","A"),("b","B"),("x","X"),("y","Y"),
            ("l","L"),("r","R"),("zl","ZL"),("zr","ZR"),
            ("minus","-"),("plus","+"),("l3","L3"),("r3","R3"),
            ("home","HOME"),("capture","CAPTURE"),("c","C"),
            ("gl","GL"),("gr","GR"),
            ("up","D-Pad Up"),("down","D-Pad Down"),
            ("left","D-Pad Left"),("right","D-Pad Right"),
        ),
    },
    "xinput": {
        "title": "XInput",
        "backends": ("xinput",),
        "sources": (
            ("a","A"),("b","B"),("x","X"),("y","Y"),
            ("lb","LB"),("rb","RB"),("lt","LT"),("rt","RT"),
            ("back","Back"),("start","Start"),("l3","L3"),("r3","R3"),
            ("guide","Guide"),
            ("up","D-Pad Up"),("down","D-Pad Down"),
            ("left","D-Pad Left"),("right","D-Pad Right"),
        ),
    },
}

def default_controller_mapping(controller_id,labels=False,switch2_rear_mapping=None):
    positional_face={"a":"B","b":"A","x":"Y","y":"X"}
    label_face={"a":"A","b":"B","x":"X","y":"Y"}

    if controller_id=="dualsense":
        return {
            "cross":"B","circle":"A","square":"Y","triangle":"X",
            "l1":"L","r1":"R","l2":"ZL","r2":"ZR",
            "create":"-","options":"+","l3":"L3","r3":"R3",
            "ps":"HOME","touchpad":"CAPTURE",
            "up":"D-Pad Up","down":"D-Pad Down",
            "left":"D-Pad Left","right":"D-Pad Right",
        }

    if controller_id=="stadia":
        face=positional_face
        return {
            **face,"l1":"L","r1":"R","l2":"ZL","r2":"ZR",
            "l3":"L3","r3":"R3","back":"-","start":"+",
            "home":"HOME","assistant":"None","capture":"CAPTURE",
            "up":"D-Pad Up","down":"D-Pad Down",
            "left":"D-Pad Left","right":"D-Pad Right",
        }

    if controller_id in ("switchpro","switch2pro"):
        mapping={
            "a":"A","b":"B","x":"X","y":"Y",
            "l":"L","r":"R","zl":"ZL","zr":"ZR",
            "minus":"-","plus":"+","l3":"L3","r3":"R3",
            "home":"HOME","capture":"CAPTURE",
            "up":"D-Pad Up","down":"D-Pad Down",
            "left":"D-Pad Left","right":"D-Pad Right",
        }
        if controller_id=="switch2pro":
            rear=switch2_rear_mapping or default_switch2_pro_rear_mapping()
            mapping.update({
                "c":"None",
                "gl":rear.get("GL","None"),
                "gr":rear.get("GR","None"),
            })
        return mapping

    if controller_id=="xinput":
        face=positional_face
        return {
            **face,"lb":"L","rb":"R","lt":"ZL","rt":"ZR",
            "back":"-","start":"+","l3":"L3","r3":"R3",
            "guide":"HOME",
            "up":"D-Pad Up","down":"D-Pad Down",
            "left":"D-Pad Left","right":"D-Pad Right",
        }

    return {}

def _mapped_switch_controls(active_sources,mapping,strengths=None):
    strengths=strengths or {}
    out=0
    lt=rt=0
    dpad_up=dpad_down=dpad_left=dpad_right=False

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
        elif target=="D-Pad Up":
            dpad_up=True
        elif target=="D-Pad Down":
            dpad_down=True
        elif target=="D-Pad Left":
            dpad_left=True
        elif target=="D-Pad Right":
            dpad_right=True

    return out,lt,rt,hat_from_dirs(
        dpad_up,dpad_down,dpad_left,dpad_right
    )

UP = 0x0001
DOWN = 0x0002
LEFT = 0x0004
RIGHT = 0x0008
START = 0x0010
BACK = 0x0020
LTHUMB = 0x0040
RTHUMB = 0x0080
LSHOULDER = 0x0100
RSHOULDER = 0x0200
GUIDE = 0x0400
A = 0x1000
B = 0x2000
X = 0x4000
Y = 0x8000

VALVE_VID = 0x28DE
STEAM_PIDS = (0x1302, 0x1303, 0x1304, 0x1305)
STEAM_REPORT_STATE = (0x42, 0x45)
STEAM_PRESENCE_FRESH_SECONDS = 1.25
_STEAM_PRESENCE_LOCK = threading.Lock()
_STEAM_PRESENCE_LAST = {}
_STEAM_ACTIVE_KEYS = set()

def _steam_presence_mark(key):
    if not key:
        return
    with _STEAM_PRESENCE_LOCK:
        _STEAM_PRESENCE_LAST[str(key)] = time.monotonic()

def _steam_presence_is_fresh(key,max_age=STEAM_PRESENCE_FRESH_SECONDS):
    if not key:
        return False
    with _STEAM_PRESENCE_LOCK:
        ts=_STEAM_PRESENCE_LAST.get(str(key),0.0)
    return ts>0.0 and (time.monotonic()-ts)<=float(max_age)

def _steam_presence_set_active(key,active):
    if not key:
        return
    with _STEAM_PRESENCE_LOCK:
        if active:
            _STEAM_ACTIVE_KEYS.add(str(key))
        else:
            _STEAM_ACTIVE_KEYS.discard(str(key))

def _steam_presence_is_active(key):
    with _STEAM_PRESENCE_LOCK:
        return str(key) in _STEAM_ACTIVE_KEYS

SONY_VID = 0x054C
DUALSENSE_PIDS = (0x0CE6, 0x0DF2)
STADIA_VID = 0x18D1
STADIA_PIDS = (0x9400,)

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
FILE_FLAG_OVERLAPPED = 0x40000000
ERROR_IO_PENDING = 997
WAIT_OBJECT_0 = 0
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
DIGCF_PRESENT = 0x00000002
DIGCF_DEVICEINTERFACE = 0x00000010


AUTOSTART_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_VALUE_NAME = "SwitchNetClient"


def resource_path(relative: str) -> str:
    """Resolve a bundled PyInstaller resource or a development-tree file."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def windows_startup_command() -> str:
    """Command stored in HKCU Run. Frozen builds use the EXE directly."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --startup'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    runner = pythonw if os.path.exists(pythonw) else sys.executable
    return f'"{runner}" "{os.path.abspath(__file__)}" --startup'


def windows_startup_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_REG_PATH, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, AUTOSTART_VALUE_NAME)
        return str(value).strip().casefold() == windows_startup_command().strip().casefold()
    except FileNotFoundError:
        return False
    except OSError:
        return False


def set_windows_startup(enabled: bool) -> None:
    """Register/unregister SwitchNet in the current user's Windows startup."""
    if enabled:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, AUTOSTART_REG_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(
                key, AUTOSTART_VALUE_NAME, 0, winreg.REG_SZ, windows_startup_command()
            )
    else:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, AUTOSTART_REG_PATH, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, AUTOSTART_VALUE_NAME)
        except FileNotFoundError:
            pass



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


class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", wintypes.WORD),
        ("bLeftTrigger", wintypes.BYTE),
        ("bRightTrigger", wintypes.BYTE),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [("dwPacketNumber", wintypes.DWORD), ("Gamepad", XINPUT_GAMEPAD)]


class XINPUT_VIBRATION(ctypes.Structure):
    _fields_ = [("wLeftMotorSpeed", wintypes.WORD), ("wRightMotorSpeed", wintypes.WORD)]


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", wintypes.USHORT), ("UsagePage", wintypes.USHORT),
        ("InputReportByteLength", wintypes.USHORT),
        ("OutputReportByteLength", wintypes.USHORT),
        ("FeatureReportByteLength", wintypes.USHORT),
        ("Reserved", wintypes.USHORT * 17),
        ("NumberLinkCollectionNodes", wintypes.USHORT),
        ("NumberInputButtonCaps", wintypes.USHORT),
        ("NumberInputValueCaps", wintypes.USHORT),
        ("NumberInputDataIndices", wintypes.USHORT),
        ("NumberOutputButtonCaps", wintypes.USHORT),
        ("NumberOutputValueCaps", wintypes.USHORT),
        ("NumberOutputDataIndices", wintypes.USHORT),
        ("NumberFeatureButtonCaps", wintypes.USHORT),
        ("NumberFeatureValueCaps", wintypes.USHORT),
        ("NumberFeatureDataIndices", wintypes.USHORT),
    ]


class XInput:
    def __init__(self):
        self.dll = None
        self.dll_name = "unavailable"
        self.get = None
        self.set = None
        for name in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
            try:
                self.dll = ctypes.WinDLL(name)
                self.dll_name = name
                self.get = self.dll.XInputGetState
                self.get.argtypes = [wintypes.DWORD, ctypes.POINTER(XINPUT_STATE)]
                self.get.restype = wintypes.DWORD
                self.set = self.dll.XInputSetState
                self.set.argtypes = [wintypes.DWORD, ctypes.POINTER(XINPUT_VIBRATION)]
                self.set.restype = wintypes.DWORD
                break
            except OSError:
                pass

    def state(self, index: int):
        if self.get is None:
            return None
        state = XINPUT_STATE()
        return state if self.get(index, ctypes.byref(state)) == 0 else None

    def rumble(self, index: int, left: int, right: int):
        if self.set is None:
            return False
        vib = XINPUT_VIBRATION(
            max(0, min(65535, int(left))),
            max(0, min(65535, int(right)))
        )
        return self.set(index, ctypes.byref(vib)) == 0


class OVERLAPPED(ctypes.Structure):
    _fields_=[
        ("Internal",ctypes.c_size_t),
        ("InternalHigh",ctypes.c_size_t),
        ("Offset",wintypes.DWORD),
        ("OffsetHigh",wintypes.DWORD),
        ("hEvent",wintypes.HANDLE),
    ]


class SteamHidApi:
    """Minimal Win32 HID layer using only Windows system DLLs."""

    def __init__(self):
        self.hid = ctypes.WinDLL("hid.dll")
        self.setupapi = ctypes.WinDLL("setupapi.dll")
        self.kernel32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)

        self.hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
        self.hid.HidD_GetSerialNumberString.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG
        ]
        self.hid.HidD_GetSerialNumberString.restype = wintypes.BOOLEAN
        self.hid.HidD_SetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
        self.hid.HidD_SetFeature.restype = wintypes.BOOLEAN
        self.hid.HidD_SetOutputReport.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
        self.hid.HidD_SetOutputReport.restype = wintypes.BOOLEAN
        self.hid.HidD_GetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
        self.hid.HidD_GetFeature.restype = wintypes.BOOLEAN
        self.hid.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
        self.hid.HidD_GetPreparsedData.restype = wintypes.BOOLEAN
        self.hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
        self.hid.HidD_FreePreparsedData.restype = wintypes.BOOLEAN
        self.hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
        self.hid.HidP_GetCaps.restype = ctypes.c_long

        self.setupapi.SetupDiGetClassDevsW.argtypes = [
            ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD
        ]
        self.setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
        self.setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID), wintypes.DWORD,
            ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)
        ]
        self.setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
        self.setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), ctypes.c_void_p,
            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p
        ]
        self.setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
        self.setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
        self.setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL

        self.kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
        ]
        self.kernel32.CreateFileW.restype = wintypes.HANDLE
        self.kernel32.ReadFile.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p
        ]
        self.kernel32.ReadFile.restype = wintypes.BOOL
        self.kernel32.WriteFile.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p
        ]
        self.kernel32.WriteFile.restype = wintypes.BOOL
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel32.CloseHandle.restype = wintypes.BOOL
        self.kernel32.CancelIoEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        self.kernel32.CancelIoEx.restype = wintypes.BOOL
        self.kernel32.CreateEventW.argtypes=[
            ctypes.c_void_p,wintypes.BOOL,wintypes.BOOL,wintypes.LPCWSTR
        ]
        self.kernel32.CreateEventW.restype=wintypes.HANDLE
        self.kernel32.WaitForSingleObject.argtypes=[
            wintypes.HANDLE,wintypes.DWORD
        ]
        self.kernel32.WaitForSingleObject.restype=wintypes.DWORD
        self.kernel32.GetOverlappedResult.argtypes=[
            wintypes.HANDLE,ctypes.POINTER(OVERLAPPED),
            ctypes.POINTER(wintypes.DWORD),wintypes.BOOL
        ]
        self.kernel32.GetOverlappedResult.restype=wintypes.BOOL

    def enumerate_matching_paths(self, vid: int, pids, usage_page=None, usage=None):
        """Enumerate matching HID top-level collections without external modules.

        The previous implementation mixed path extraction and Steam-specific
        filtering. This generic version validates every buffer size before
        reading DevicePath and isolates malformed/unrelated HID interfaces.
        """
        guid = GUID()
        self.hid.HidD_GetHidGuid(ctypes.byref(guid))
        info = self.setupapi.SetupDiGetClassDevsW(
            ctypes.byref(guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
        )
        if info in (None, INVALID_HANDLE_VALUE):
            return []
        paths = []
        try:
            index = 0
            while True:
                data = SP_DEVICE_INTERFACE_DATA()
                data.cbSize = ctypes.sizeof(data)
                if not self.setupapi.SetupDiEnumDeviceInterfaces(
                    info, None, ctypes.byref(guid), index, ctypes.byref(data)
                ):
                    break
                index += 1
                needed = wintypes.DWORD(0)
                self.setupapi.SetupDiGetDeviceInterfaceDetailW(
                    info, ctypes.byref(data), None, 0, ctypes.byref(needed), None
                )
                if needed.value < 8 or needed.value > 65536:
                    continue
                buf = ctypes.create_string_buffer(needed.value)
                cb_size = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
                ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = cb_size
                if not self.setupapi.SetupDiGetDeviceInterfaceDetailW(
                    info, ctypes.byref(data), buf, needed.value,
                    ctypes.byref(needed), None
                ):
                    continue
                try:
                    # DevicePath starts immediately after the DWORD cbSize.
                    path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
                except (ValueError, OSError):
                    continue
                low = path.lower()
                if f"vid_{vid:04x}" not in low:
                    continue
                if pids and not any(f"pid_{pid:04x}" in low for pid in pids):
                    continue
                if usage_page is not None or usage is not None:
                    try:
                        caps = self.caps(path)
                    except Exception:
                        caps = None
                    if not caps:
                        continue
                    if usage_page is not None and caps.UsagePage != usage_page:
                        continue
                    if usage is not None and caps.Usage != usage:
                        continue
                paths.append(path)
        finally:
            self.setupapi.SetupDiDestroyDeviceInfoList(info)
        return paths

    def enumerate_paths(self):
        return self.enumerate_matching_paths(
            VALVE_VID, STEAM_PIDS, usage_page=0xFF00, usage=0x0001
        )

    def open(
        self,path: str,write: bool=False,query_only: bool=False,
        overlapped: bool=False
    ):
        access=0 if query_only else (
            GENERIC_READ | (GENERIC_WRITE if write else 0)
        )
        flags=FILE_ATTRIBUTE_NORMAL
        if overlapped and not query_only:
            flags|=FILE_FLAG_OVERLAPPED
        handle=self.kernel32.CreateFileW(
            path,access,FILE_SHARE_READ | FILE_SHARE_WRITE,None,
            OPEN_EXISTING,flags,None
        )
        if handle == INVALID_HANDLE_VALUE:
            return None
        return handle

    def close(self, handle):
        if handle not in (None, INVALID_HANDLE_VALUE):
            self.kernel32.CloseHandle(handle)

    def read(self, handle, size=64):
        buf = (ctypes.c_ubyte * size)()
        got = wintypes.DWORD(0)
        ok = self.kernel32.ReadFile(handle, buf, size, ctypes.byref(got), None)
        if not ok or got.value == 0:
            return b""
        return bytes(buf[:got.value])

    def read_timeout(self,handle,size=64,timeout_ms=35):
        """Bounded overlapped HID read used only by passive presence probing."""
        if not handle:
            return b""

        event=self.kernel32.CreateEventW(None,True,False,None)
        if not event:
            return b""

        ov=OVERLAPPED()
        ov.hEvent=event
        buf=(ctypes.c_ubyte * max(1,int(size)))()
        got=wintypes.DWORD(0)

        try:
            ok=self.kernel32.ReadFile(
                handle,buf,len(buf),ctypes.byref(got),ctypes.byref(ov)
            )
            if ok:
                return bytes(buf[:got.value]) if got.value else b""

            if ctypes.get_last_error()!=ERROR_IO_PENDING:
                return b""

            wait=self.kernel32.WaitForSingleObject(
                event,max(1,int(timeout_ms))
            )
            if wait!=WAIT_OBJECT_0:
                try:
                    self.kernel32.CancelIoEx(handle,ctypes.byref(ov))
                except Exception:
                    pass
                self.kernel32.WaitForSingleObject(event,50)
                return b""

            if not self.kernel32.GetOverlappedResult(
                handle,ctypes.byref(ov),ctypes.byref(got),False
            ):
                return b""

            return bytes(buf[:got.value]) if got.value else b""
        finally:
            self.kernel32.CloseHandle(event)

    def cancel(self, handle):
        if handle not in (None, INVALID_HANDLE_VALUE):
            try:
                self.kernel32.CancelIoEx(handle, None)
            except Exception:
                pass

    def caps(self, path: str):
        handle = self.open(path, query_only=True)
        if not handle:
            return None
        ppd = ctypes.c_void_p()
        try:
            if not self.hid.HidD_GetPreparsedData(handle, ctypes.byref(ppd)):
                return None
            caps = HIDP_CAPS()
            if self.hid.HidP_GetCaps(ppd, ctypes.byref(caps)) < 0:
                return None
            return caps
        finally:
            if ppd.value:
                self.hid.HidD_FreePreparsedData(ppd)
            self.close(handle)

    def serial_string(self, path: str):
        """Read the physical HID serial shared by all top-level collections."""
        handle=self.open(path,query_only=True)
        if not handle:
            return ""
        try:
            buf=ctypes.create_unicode_buffer(256)
            ok=self.hid.HidD_GetSerialNumberString(
                handle,
                ctypes.cast(buf,ctypes.c_void_p),
                ctypes.sizeof(buf),
            )
            if not ok:
                return ""
            return str(buf.value or "").strip()
        except Exception:
            return ""
        finally:
            self.close(handle)

    def set_feature(self, handle, data: bytes):
        raw = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        return bool(self.hid.HidD_SetFeature(handle, raw, len(data)))

    def set_output_report(self, handle, data: bytes):
        if not handle:
            return False
        raw = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        return bool(self.hid.HidD_SetOutputReport(handle, raw, len(data)))

    def get_feature(self, handle, report_id: int, size: int):
        if not handle or size <= 0:
            return None
        raw = (ctypes.c_ubyte * size)()
        raw[0] = report_id & 0xFF
        if not self.hid.HidD_GetFeature(handle, raw, size):
            return None
        return bytes(raw)

    def write(self, handle, data: bytes):
        if not handle:
            return False
        raw = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        written = wintypes.DWORD(0)
        return bool(self.kernel32.WriteFile(handle, raw, len(data), ctypes.byref(written), None)) and written.value == len(data)



def _windows_hid_physical_key(path):
    """Return a stable physical identity for a Windows HID path.

    A single Steam Controller can appear through several Windows HID
    top-level collections and USB interfaces. Those paths may differ in:
      - &colXX collection suffixes
      - &mi_XX interface suffixes
      - final &0000 / &0001 style collection instance numbers

    For SwitchNet roster purposes all of those belong to one physical device.
    """
    low=str(path or "").casefold()
    parts=low.split("#")

    if len(parts)<3:
        low=re.sub(r"&col[0-9a-f]+","",low)
        low=re.sub(r"&mi_[0-9a-f]{2}","",low)
        low=re.sub(r"&[0-9a-f]{4}(?=[#\\{]|$)","",low)
        return low

    hardware=parts[1]
    instance=parts[2]

    hardware=re.sub(r"&col[0-9a-f]+","",hardware)
    hardware=re.sub(r"&mi_[0-9a-f]{2}","",hardware)

    instance=re.sub(r"&col[0-9a-f]+","",instance)
    # Windows commonly appends collection/interface ordinals at the end.
    instance=re.sub(r"&[0-9a-f]{4}$","",instance)

    return hardware+"#"+instance


def _windows_steam_group_key(api,path):
    """Physical Steam Controller identity.

    All HID collections of one physical device share the HID serial string.
    This is considerably more reliable than parsing collection/interface
    decorations from the Windows device path.

    Some Valve receivers/controllers expose no serial at all. In that case
    SwitchNet deliberately groups by VID/PID rather than presenting several
    phantom controllers. Multi-device no-serial Valve setups remain an edge
    case and are surfaced in diagnostics.
    """
    serial=""
    try:
        serial=api.serial_string(path)
    except Exception:
        serial=""

    low=str(path or "").casefold()
    vid=re.search(r"vid_([0-9a-f]{4})",low)
    pid=re.search(r"pid_([0-9a-f]{4})",low)
    vp=(vid.group(1) if vid else "????")+"_"+(pid.group(1) if pid else "????")

    if serial:
        return f"valve:{vp}:serial:{serial.casefold()}"

    return f"valve:{vp}:noserial"



def _steam_collection_score(api,path):
    """Prefer the Valve HID collection that can actually carry state reports."""
    try:
        caps=api.caps(path)
    except Exception:
        caps=None
    if not caps:
        return (0,0,0,str(path).casefold())

    input_len=int(getattr(caps,"InputReportByteLength",0) or 0)
    feature_len=int(getattr(caps,"FeatureReportByteLength",0) or 0)
    output_len=int(getattr(caps,"OutputReportByteLength",0) or 0)

    # State reports need at least the Triton payload length. Prefer larger
    # input-report collections while retaining feature/output capability.
    usable=1 if input_len>=47 else 0
    return (usable,input_len,feature_len+output_len,str(path).casefold())


def _steam_probe_controller_online(api,paths,total_budget_ms=120):
    """Return True only when the Valve receiver emits a real controller state."""
    candidates=sorted(
        list(dict.fromkeys(paths or [])),
        key=lambda p:_steam_collection_score(api,p),
        reverse=True,
    )
    if not candidates:
        return False

    deadline=time.monotonic()+(max(20,int(total_budget_ms))/1000.0)

    for path in candidates:
        remaining=int((deadline-time.monotonic())*1000)
        if remaining<=0:
            break

        caps=api.caps(path)
        report_size=int(
            getattr(caps,"InputReportByteLength",64) or 64
        ) if caps else 64
        if report_size<30:
            continue

        handle=api.open(path,write=False,overlapped=True)
        if not handle:
            continue

        try:
            for _ in range(2):
                remaining=int((deadline-time.monotonic())*1000)
                if remaining<=0:
                    break
                report=api.read_timeout(
                    handle,max(30,min(256,report_size)),
                    min(35,remaining)
                )
                if (
                    len(report)>=30 and
                    report[0] in STEAM_REPORT_STATE
                ):
                    return True
        finally:
            try:
                api.cancel(handle)
            except Exception:
                pass
            api.close(handle)

    return False


def discover_supported_controllers_windows(xi, include_keyboard=False):
    """Enumerate logical physical controllers, not individual HID collections."""
    api=SteamHidApi()
    out=[]
    seen=set()

    def add(key,name,backend,path="",index=-1,detail="",paths=None,virtual=False):
        if key in seen:
            return
        seen.add(key)
        out.append(dict(
            key=key,name=name,backend=backend,path=path,index=index,
            detail=detail,paths=list(paths or ([path] if path else [])),
            virtual=bool(virtual),
        ))

    # Steam Controller 2026 exposes several top-level HID collections on
    # Windows. Group them by physical instance before creating roster entries.
    steam_groups={}
    for path in api.enumerate_paths():
        physical=_windows_steam_group_key(api,path)
        steam_groups.setdefault(physical,[]).append(path)

    for physical,paths in sorted(steam_groups.items()):
        candidates=sorted(
            paths,
            key=lambda p:_steam_collection_score(api,p),
            reverse=True,
        )
        preferred=candidates[0] if candidates else ""
        identity_detail=(
            "serial" if ":serial:" in physical else "VID/PID fallback"
        )
        logical_key="steam:"+physical

        # A puck/receiver is transport, not proof that the controller is online.
        # While gameplay owns the HID reader, use its last-state timestamp so
        # discovery never competes for reports.
        if _steam_presence_is_active(logical_key):
            controller_online=_steam_presence_is_fresh(logical_key)
        elif _steam_presence_is_fresh(logical_key):
            controller_online=True
        else:
            controller_online=_steam_probe_controller_online(
                api,candidates
            )
            if controller_online:
                _steam_presence_mark(logical_key)

        if not controller_online:
            continue

        add(
            logical_key,
            "Steam Controller 2026",
            "steam_passive",
            preferred,
            -1,
            f"native HID · controller online · grouped {len(candidates)} collection(s) · {identity_detail}",
            candidates,
        )

    # Original Nintendo Switch Pro Controller (057E:2009).
    # Multiple Windows paths map to one stable physical roster identity.
    switch_pro_candidates=[]
    try:
        switch_pro_candidates=api.enumerate_matching_paths(
            NINTENDO_VID,{SWITCH_PRO_PID}
        )
    except Exception:
        switch_pro_candidates=[]

    try:
        dedicated_switch_pro=enumerate_switch_pro_hid()
    except Exception:
        dedicated_switch_pro=[]

    for device in dedicated_switch_pro:
        path=device.get("path","")
        if path and not any(
            path.casefold()==candidate.casefold()
            for candidate in switch_pro_candidates
        ):
            switch_pro_candidates.append(path)

    if switch_pro_candidates:
        preferred=sorted(
            switch_pro_candidates,
            key=lambda path:(
                1 if "00001124" not in path.casefold() else 0,
                path.casefold(),
            ),
            reverse=True,
        )[0]

        connection=(
            "Bluetooth"
            if "00001124" in preferred.casefold()
            else "USB"
        )

        add(
            "switchpro:057e:2009",
            "Nintendo Switch Pro Controller",
            "switchpro_hid",
            preferred,
            -1,
            f"{connection} 057E:2009 · native HID",
            list(dict.fromkeys(switch_pro_candidates)),
        )

    # Switch 2 Pro Controller: expose exactly ONE stable logical identity.
    #
    # Multiple HID top-level collections must never create multiple roster
    # identities, because roster topology drives the automatic full-service
    # restart. A changing collection key would otherwise produce restart loops.
    switch2_candidates=[]
    try:
        switch2_candidates=api.enumerate_matching_paths(
            NINTENDO_VID,{SWITCH2_PRO_PID}
        )
    except Exception:
        switch2_candidates=[]

    # Dedicated backend remains the fallback because it is the path already
    # hardware-confirmed in v1.23.1.
    dedicated=[]
    try:
        dedicated=enumerate_switch2_pro_hid()
    except Exception:
        dedicated=[]

    for d in dedicated:
        p=d.get("path","")
        if p and not any(
            p.casefold()==x.casefold()
            for x in switch2_candidates
        ):
            switch2_candidates.append(p)

    if switch2_candidates:
        # Choose a deterministic preferred path but NEVER use it in the roster
        # key. All collections of 057E:2069 map to this single physical identity.
        preferred=sorted(
            switch2_candidates,
            key=lambda p:(
                0 if "&col" in p.casefold() else 1,
                p.casefold()
            ),
            reverse=True,
        )[0]

        add(
            "switch2pro:057e:2069",
            "Nintendo Switch 2 Pro Controller",
            "switch2pro_hid",
            preferred,
            -1,
            f"USB 057E:2069 · {len(switch2_candidates)} HID collection(s) · stable identity · auto WinUSB wake",
            list(dict.fromkeys(switch2_candidates)),
        )

    for path in api.enumerate_matching_paths(
        SONY_VID,DUALSENSE_PIDS,usage_page=0x01,usage=0x05
    ):
        key="dualsense:"+_windows_hid_physical_key(path)
        add(
            key,"DualSense / DualSense Edge","dualsense_hid",path,-1,
            "native HID",[path]
        )

    for path in api.enumerate_matching_paths(
        STADIA_VID,STADIA_PIDS,usage_page=0x01,usage=0x05
    ):
        key="stadia:"+_windows_hid_physical_key(path)
        add(
            key,"Google Stadia Controller","stadia_hid",path,-1,
            "native HID",[path]
        )

    for i in range(4):
        try:
            state=xi.state(i)
        except Exception:
            state=None
        if state is not None:
            add(f"xinput:{i}",f"XInput Controller {i}","xinput","",i,"XInput")

    if include_keyboard:
        add(
            "virtual:keyboard_mouse",
            "Keyboard + Mouse",
            "keyboard_mouse",
            "",
            -1,
            "background hooks · mouse = right stick",
            [],
            True,
        )

    return out


class SteamHidReader:
    def __init__(self):
        self.api = SteamHidApi()
        self.lock = threading.Lock()
        self.stop_evt = threading.Event()
        self.thread = None
        self.handle = None
        self.write_handle = None
        self.path = ""
        self.active_mode = False
        self.latest = None
        self.last_report = 0
        self.reports = 0
        self.errors = 0
        self.status = "Steam HID inactive"
        self.gyro_bias = [0, 0, 0]
        self._gyro_sum = [0, 0, 0]
        self._gyro_cal_samples = 0
        self.gyro_calibrated = False
        self.preferred_paths = []
        self._candidate_paths = []
        self._candidate_index = 0
        self._invalid_reports = 0
        self._valid_reports_on_path = 0
        self.presence_key=""

    def start(self, active_mode: bool, preferred_path: str = "", preferred_paths=None):
        self.stop()
        self.stop_evt.clear()
        self.preferred_path = str(preferred_path or "")
        self.preferred_paths = [
            str(p) for p in (preferred_paths or []) if p
        ]
        self._candidate_paths=[]
        self._candidate_index=0
        self._invalid_reports=0
        self._valid_reports_on_path=0
        self.active_mode = active_mode
        identity_path=(
            self.preferred_path or
            (self.preferred_paths[0] if self.preferred_paths else "")
        )
        self.presence_key=(
            "steam:"+_windows_steam_group_key(self.api,identity_path)
            if identity_path else ""
        )
        _steam_presence_set_active(self.presence_key,True)
        self.gyro_bias = [0, 0, 0]
        self._gyro_sum = [0, 0, 0]
        self._gyro_cal_samples = 0
        self.gyro_calibrated = False
        self.thread = threading.Thread(target=self._run, name="SwitchNet-SteamHID", daemon=True)
        self.thread.start()

    def _close_handles(self):
        read_handle, write_handle = self.handle, self.write_handle
        self.handle = None
        self.write_handle = None
        if read_handle:
            self.api.close(read_handle)
        if write_handle and write_handle != read_handle:
            self.api.close(write_handle)

    def stop(self):
        self.stop_evt.set()
        # Never CloseHandle while another thread is blocked in ReadFile: that can
        # race inside hid.dll/kernel32 and terminate the Python process. Cancel the
        # pending I/O first and let the reader thread own handle destruction.
        self.api.cancel(self.handle)
        thread = self.thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(2.0)
        if not thread or not thread.is_alive():
            self._close_handles()
            self.thread = None
            _steam_presence_set_active(self.presence_key,False)
        with self.lock:
            self.latest = None
            self.status = "Steam HID inactive" if not thread or not thread.is_alive() else "Steam HID: stopping"

    def snapshot(self):
        with self.lock:
            return {
                "state": dict(self.latest) if self.latest else None,
                "status": self.status,
                "reports": self.reports,
                "errors": self.errors,
                "report_id": self.last_report,
                "path": self.path,
                "gyro_calibrated": self.gyro_calibrated,
                "gyro_bias": tuple(self.gyro_bias),
            }

    @staticmethod
    def _feature(cmd: int, payload=b""):
        buf = bytearray(64)
        buf[0] = 0x01
        buf[1] = cmd & 0xFF
        buf[2] = len(payload) & 0xFF
        buf[3:3 + len(payload)] = payload
        return bytes(buf)

    def _enable_imu(self):
        if not self.write_handle:
            return False
        return self.api.set_feature(self.write_handle, self._feature(0x87, bytes((0x30, 0x18, 0x00))))

    def _disable_lizard(self):
        if not self.write_handle:
            return False
        ok = self.api.set_feature(self.write_handle, self._feature(0x81))
        # IMU raw gyro+accelerometer enabled; left and right trackpads raw/none. These are the same command
        # channel and settings used by the current SteamlessController research.
        ok = self._enable_imu() and ok
        ok = self.api.set_feature(
            self.write_handle, self._feature(0x87, bytes((0x08, 0, 0, 0x07, 0, 0)))
        ) and ok
        return ok

    def _restore_lizard(self):
        if not self.write_handle:
            return
        try:
            self.api.set_feature(self.write_handle, self._feature(0x85))
            self.api.set_feature(self.write_handle, self._feature(0x8E))
        except Exception:
            pass

    def _candidate_collection_paths(self):
        all_paths=self.api.enumerate_paths()
        preferred=[]

        for p in getattr(self,"preferred_paths",[]) or []:
            if any(p.casefold()==x.casefold() for x in all_paths):
                preferred.append(p)

        single=getattr(self,"preferred_path","")
        if (
            single and
            not any(single.casefold()==p.casefold() for p in preferred) and
            any(single.casefold()==x.casefold() for x in all_paths)
        ):
            preferred.insert(0,single)

        paths=preferred or all_paths

        # Deterministic ranking only decides probe order. It no longer decides
        # permanently which collection is the state interface.
        return sorted(
            list(dict.fromkeys(paths)),
            key=lambda p:_steam_collection_score(self.api,p),
            reverse=True,
        )

    def _open_live_interface(self):
        if not self._candidate_paths:
            self._candidate_paths=self._candidate_collection_paths()
            self._candidate_index=0

        if not self._candidate_paths:
            return None

        attempts=len(self._candidate_paths)
        while attempts>0:
            path=self._candidate_paths[
                self._candidate_index % len(self._candidate_paths)
            ]
            self._candidate_index=(
                self._candidate_index+1
            ) % len(self._candidate_paths)
            attempts-=1

            handle=self.api.open(path,write=False)
            if not handle:
                continue

            caps=self.api.caps(path)
            input_len=int(
                getattr(caps,"InputReportByteLength",0) or 0
            ) if caps else 0

            # Steam state payload must fit. Short collections are feature-only.
            if input_len and input_len<30:
                self.api.close(handle)
                continue

            self.path=path
            self._invalid_reports=0
            self._valid_reports_on_path=0
            return handle

        return None

    def _advance_collection(self, reason):
        old_path=self.path
        self._close_handles()
        self.path=""
        self._invalid_reports=0
        self._valid_reports_on_path=0
        with self.lock:
            self.latest=None
            short=old_path[-28:] if old_path else "?"
            self.status=(
                f"Steam HID: collection rejected ({reason}); "
                f"probing next · …{short}"
            )

    def _open_feature_interface(self):
        """Find a collection that accepts Steam feature commands.

        Input and feature/output collections need not be the same Windows HID
        top-level collection.
        """
        candidates=[]
        if self.path:
            candidates.append(self.path)
        candidates.extend(self._candidate_paths or self._candidate_collection_paths())

        seen=set()
        for path in candidates:
            key=path.casefold()
            if key in seen:
                continue
            seen.add(key)
            handle=self.api.open(path,write=True)
            if not handle:
                continue

            # Probe the feature command channel with IMU-enable. Keep the first
            # collection that accepts it.
            old=self.write_handle
            self.write_handle=handle
            try:
                if self._enable_imu():
                    if old and old!=handle:
                        self.api.close(old)
                    return True
            except Exception:
                pass

            self.write_handle=old
            self.api.close(handle)

        return False


    def _parse(self, report: bytes):
        if len(report) < 30 or report[0] not in STEAM_REPORT_STATE:
            return None
        b0, b1, b2, flags = report[2], report[3], report[4], report[5]
        buttons = {
            "a": bool(b0 & 0x01), "b": bool(b0 & 0x02),
            "x": bool(b0 & 0x04), "y": bool(b0 & 0x08),
            "qam": bool(b0 & 0x10), "rs": bool(b0 & 0x20), "start": bool(b0 & 0x40),
            "rb": bool(b1 & 0x02), "down": bool(b1 & 0x04),
            "right": bool(b1 & 0x08), "left": bool(b1 & 0x10),
            "up": bool(b1 & 0x20), "back": bool(b1 & 0x40),
            "ls": bool(b1 & 0x80), "guide": bool(b2 & 0x01),
            "lb": bool(b2 & 0x08),
            "r4": bool(b0 & 0x80), "r5": bool(b1 & 0x01),
            "l4": bool(b2 & 0x02), "l5": bool(b2 & 0x04),
            "rt_full": bool(b2 & 0x80),
            "lt_touch": bool(flags & 0x02), "rt_touch": bool(b2 & 0x20),
        }
        def i16(off):
            return struct.unpack_from("<h", report, off)[0]
        lt = max(0, min(32767, i16(6)))
        rt = max(0, min(32767, i16(8)))
        # Triton IMU block: after report ID, offset 29 contains a u32
        # timestamp, followed by accel XYZ and gyro XYZ int16 values.
        imu = dict(imu_timestamp=0, accel_x=0, accel_y=0, accel_z=16384,
                   gyro_x=0, gyro_y=0, gyro_z=0)
        if len(report) >= 47:
            imu.update(
                imu_timestamp=struct.unpack_from("<I", report, 30)[0],
                accel_x=i16(34), accel_y=i16(36), accel_z=i16(38),
                gyro_x=i16(40), gyro_y=i16(42), gyro_z=i16(44),
            )
        return {
            "buttons_raw": buttons,
            "lx": i16(10), "ly": i16(12),
            "rx": i16(14), "ry": i16(16),
            "lt_raw": lt, "rt_raw": rt,
            **imu,
        }

    def _calibrate_and_correct_gyro(self, parsed):
        if not parsed:
            return parsed
        gx, gy, gz = parsed["gyro_x"], parsed["gyro_y"], parsed["gyro_z"]
        if not self.gyro_calibrated:
            # Calibrate only while the controller is visibly still. A short
            # stationary window removes unit-specific zero-rate bias without
            # baking intentional motion into the offset.
            ax, ay, az = parsed["accel_x"], parsed["accel_y"], parsed["accel_z"]
            accel_norm2 = ax*ax + ay*ay + az*az
            still = max(abs(gx), abs(gy), abs(gz)) < 1500 and (12000*12000) < accel_norm2 < (21000*21000)
            if still:
                self._gyro_sum[0] += gx
                self._gyro_sum[1] += gy
                self._gyro_sum[2] += gz
                self._gyro_cal_samples += 1
                if self._gyro_cal_samples >= 96:
                    self.gyro_bias = [round(v / self._gyro_cal_samples) for v in self._gyro_sum]
                    self.gyro_calibrated = True
            else:
                self._gyro_sum = [0, 0, 0]
                self._gyro_cal_samples = 0
        if self.gyro_calibrated:
            parsed["gyro_x"] -= self.gyro_bias[0]
            parsed["gyro_y"] -= self.gyro_bias[1]
            parsed["gyro_z"] -= self.gyro_bias[2]
        return parsed

    def _ensure_write_handle(self):
        if self.write_handle:
            return True
        return self._open_feature_interface()

    def _haptic(self, actuator: int, strength: int):
        # Steam Controller 2026 (Triton) LRA command, documented by
        # SteamHapticsSinger. Back-rumble actuators are IDs 2 (left) and 4 (right).
        if not self._ensure_write_handle():
            return False
        data = bytearray(64)
        data[0] = 0x83
        data[1] = actuator & 0xFF
        if strength <= 0:
            data[2] = 0x80
            data[6] = 0x80
        else:
            # Direct velocity/gain uses signed -128..127 encoded as one byte.
            gain = max(-127, min(127, round((strength / 65535.0) * 255.0 - 128.0)))
            freq = 113  # ~110 Hz back-rumble carrier, stable across Triton units.
            data[2] = gain & 0xFF
            data[3] = freq & 0xFF
            data[4] = (freq >> 8) & 0xFF
            data[5] = 0xFF
            data[6] = 0x7F
        return self.api.write(self.write_handle, bytes(data))

    def rumble(self, left: int, right: int):
        try:
            # Triton's LRAs are strong relative to the other supported
            # controllers. Attenuate only at the Steam hardware boundary.
            left_scaled=round(max(0,min(65535,int(left))) * 0.45)
            right_scaled=round(max(0,min(65535,int(right))) * 0.45)
            left_ok = self._haptic(2, left_scaled)
            right_ok = self._haptic(4, right_scaled)
            return left_ok and right_ok
        except Exception:
            return False

    def _run(self):
        last_keepalive = 0.0
        while not self.stop_evt.is_set():
            try:
                if not self.handle:
                    self.handle = self._open_live_interface()
                    if not self.handle:
                        with self.lock:
                            self.status = "Steam Controller 2026 not found"
                        time.sleep(1.0)
                        continue
                    # Feature/output can live on another collection.
                    self._ensure_write_handle()
                    if self.write_handle and self.active_mode:
                        self._disable_lizard()
                    with self.lock:
                        self.status=(
                            "Steam HID direct · probing state collection"
                            if self.active_mode else
                            "Steam HID passive · probing state collection"
                        )

                report_size=64
                try:
                    caps=self.api.caps(self.path)
                    report_size=max(
                        30,
                        min(256,int(
                            getattr(caps,"InputReportByteLength",64) or 64
                        ))
                    )
                except Exception:
                    pass

                report=self.api.read(self.handle,report_size)
                if not report:
                    raise OSError("HID read ended")

                raw_parsed=self._parse(report)
                if raw_parsed is None:
                    self._invalid_reports+=1

                    # A real state interface produces recognized Steam reports
                    # immediately and continuously. Reject a noisy non-state
                    # collection after a small bounded sample.
                    if self._invalid_reports>=12:
                        rid=report[0] if report else -1
                        self._advance_collection(
                            f"12 non-state reports, last 0x{rid:02X}"
                        )
                    continue

                self._invalid_reports=0
                self._valid_reports_on_path+=1
                parsed=self._calibrate_and_correct_gyro(raw_parsed)

                if parsed:
                    _steam_presence_mark(self.presence_key)
                    with self.lock:
                        self.latest=parsed
                        self.reports+=1
                        self.last_report=report[0]
                        if self._valid_reports_on_path==1:
                            idx=max(
                                1,
                                self._candidate_paths.index(self.path)+1
                                if self.path in self._candidate_paths else 1
                            )
                            self.status=(
                                f"Steam HID state OK · collection "
                                f"{idx}/{len(self._candidate_paths) or 1} · "
                                f"report 0x{report[0]:02X}"
                            )
                if self.active_mode and self.write_handle and time.monotonic() - last_keepalive >= 0.8:
                    self._disable_lizard()
                    last_keepalive = time.monotonic()
            except Exception as exc:
                with self.lock:
                    self.errors += 1
                    self.status = f"Steam HID: {exc}"
                if self.active_mode:
                    self._restore_lizard()
                self._close_handles()
                if self.stop_evt.wait(0.5):
                    break
        if self.active_mode:
            self._restore_lizard()
        self._close_handles()



class DualSenseReader:
    """Direct DualSense/Edge HID input reader for Windows (USB and Bluetooth)."""
    def __init__(self):
        self.api = SteamHidApi()
        self.lock = threading.Lock()
        self.stop_evt = threading.Event()
        self.thread = None
        self.handle = None
        self.write_handle = None
        self.path = ""
        self.transport = "usb"
        self.output_seq = 0
        self.use_vibration_v2 = True
        self.write_lock = threading.Lock()
        self.latest = None
        self.reports = 0
        self.errors = 0
        self.status = "DualSense HID inactive"
        self.calibration = None
        self.calibration_status = "non letta"
        self.fallback_gyro_bias = [0, 0, 0]
        self.fallback_gyro_sum = [0, 0, 0]
        self.fallback_gyro_samples = 0
        self.fallback_gyro_calibrated = False

    def start(self, preferred_path: str = ""):
        self.stop()
        self.stop_evt.clear()
        self.preferred_path = str(preferred_path or "")
        self.calibration = None
        self.calibration_status = "non letta"
        self.fallback_gyro_bias = [0, 0, 0]
        self.fallback_gyro_sum = [0, 0, 0]
        self.fallback_gyro_samples = 0
        self.fallback_gyro_calibrated = False
        self.thread = threading.Thread(target=self._run, name="SwitchNet-DualSenseHID", daemon=True)
        self.thread.start()

    def _close_handle(self):
        handle = self.handle
        write_handle = self.write_handle
        self.handle = None
        self.write_handle = None
        if handle:
            self.api.close(handle)
        if write_handle and write_handle != handle:
            self.api.close(write_handle)

    def stop(self):
        self.stop_evt.set()
        self.api.cancel(self.handle)
        thread = self.thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(2.0)
        if not thread or not thread.is_alive():
            self._close_handle()
            self.thread = None
        with self.lock:
            self.latest = None
            self.status = "DualSense HID inactive" if not thread or not thread.is_alive() else "DualSense HID: stopping"

    def snapshot(self):
        with self.lock:
            return {
                "state": dict(self.latest) if self.latest else None,
                "status": self.status,
                "reports": self.reports,
                "errors": self.errors,
                "path": self.path,
                "calibration_status": self.calibration_status,
            }

    @staticmethod
    def _s16(report, off):
        return struct.unpack_from("<h", report, off)[0]

    def _read_calibration(self):
        # Sony's official hid-playstation driver obtains factory calibration
        # from feature report 0x05 (41 bytes). Keep the exact integer model:
        # calibrated = (raw - bias) * sens_numer / sens_denom.
        data = self.api.get_feature(self.handle, 0x05, 41)
        if not data or len(data) < 35 or data[0] != 0x05:
            self.calibration = None
            self.calibration_status = "fallback raw"
            return

        def s16(off):
            return struct.unpack_from("<h", data, off)[0]

        gp_bias = [s16(1), s16(3), s16(5)]
        gp_plus = [s16(7), s16(11), s16(15)]
        gp_minus = [s16(9), s16(13), s16(17)]
        speed_2x = s16(19) + s16(21)
        acc_plus = [s16(23), s16(27), s16(31)]
        acc_minus = [s16(25), s16(29), s16(33)]

        gyro = []
        accel = []
        valid = speed_2x != 0
        for axis in range(3):
            # Match Linux hid-playstation exactly. The factory gyro bias values
            # define the positive/negative calibration span; they are NOT a
            # zero-rate offset to subtract from live samples. Live gyro is
            # already centered around zero.
            denom = abs(gp_plus[axis] - gp_bias[axis]) + abs(gp_minus[axis] - gp_bias[axis])
            if denom == 0:
                valid = False
                break
            gyro.append((0, speed_2x * 1024, denom))

        if valid:
            for axis in range(3):
                range_2g = acc_plus[axis] - acc_minus[axis]
                if range_2g == 0:
                    valid = False
                    break
                bias = acc_plus[axis] - int(range_2g / 2)
                accel.append((bias, 2 * 8192, range_2g))

        if valid:
            self.calibration = {"gyro": gyro, "accel": accel}
            self.calibration_status = "factory OK"
        else:
            self.calibration = None
            self.calibration_status = "factory non valida"

    def _read_firmware_info(self):
        data = self.api.get_feature(self.handle, 0x20, 64)
        if not data or len(data) < 46 or data[0] != 0x20:
            self.use_vibration_v2 = True
            return
        update_version = struct.unpack_from("<H", data, 44)[0]
        # Original DualSense gained vibration-v2 at feature version 2.21;
        # DualSense Edge supports it from the start. Prefer v2 for unknown/new units.
        is_edge = "pid_0df2" in self.path.lower()
        self.use_vibration_v2 = is_edge or update_version >= 0x0215

    def _ensure_write_handle(self):
        if self.write_handle:
            return True
        if not self.path:
            return False
        self.write_handle = self.api.open(self.path, write=True)
        return bool(self.write_handle)

    def rumble(self, left: int, right: int):
        try:
            if not self._ensure_write_handle():
                return False
            l = max(0, min(255, round(int(left) * 255 / 65535)))
            r = max(0, min(255, round(int(right) * 255 / 65535)))
            with self.write_lock:
                if self.transport == "bt":
                    data = bytearray(78)
                    data[0] = 0x31
                    data[1] = (self.output_seq & 0x0F) << 4
                    self.output_seq = (self.output_seq + 1) & 0x0F
                    data[2] = 0x10
                    common = 3
                    data[common + 0] = 0x02  # HAPTICS_SELECT
                    if self.use_vibration_v2:
                        data[common + 38] = 0x04
                    else:
                        data[common + 0] |= 0x01
                    data[common + 2] = r
                    data[common + 3] = l
                    crc = zlib.crc32(bytes((0xA2,)) + data[:-4]) & 0xFFFFFFFF
                    struct.pack_into("<I", data, 74, crc)
                else:
                    data = bytearray(63)
                    data[0] = 0x02
                    common = 1
                    data[common + 0] = 0x02  # HAPTICS_SELECT
                    if self.use_vibration_v2:
                        data[common + 38] = 0x04
                    else:
                        data[common + 0] |= 0x01
                    data[common + 2] = r
                    data[common + 3] = l
                return self.api.write(self.write_handle, bytes(data))
        except Exception:
            return False

    @staticmethod
    def _apply_calibration(raw_value, entry):
        bias, numer, denom = entry
        if denom == 0:
            return int(raw_value)
        return int(round((int(raw_value) - int(bias)) * int(numer) / int(denom)))

    def _calibrate_motion(self, parsed):
        if not parsed:
            return parsed
        raw_gyro = (parsed["gyro_x"], parsed["gyro_y"], parsed["gyro_z"])
        raw_accel = (parsed["accel_x"], parsed["accel_y"], parsed["accel_z"])
        if self.calibration:
            calibrated_gyro = [self._apply_calibration(raw_gyro[i], self.calibration["gyro"][i]) for i in range(3)]
            calibrated_accel = [self._apply_calibration(raw_accel[i], self.calibration["accel"][i]) for i in range(3)]
            parsed["gyro_x"], parsed["gyro_y"], parsed["gyro_z"] = calibrated_gyro
            parsed["accel_x"], parsed["accel_y"], parsed["accel_z"] = calibrated_accel
            parsed["motion_calibrated"] = True
            return parsed

        # Fallback for devices/paths where feature report 0x05 is unavailable:
        # learn only the zero-rate gyro offset while the controller is still.
        gx, gy, gz = raw_gyro
        ax, ay, az = raw_accel
        norm2 = ax*ax + ay*ay + az*az
        still = max(abs(gx), abs(gy), abs(gz)) < 5000 and (5000*5000) < norm2 < (14000*14000)
        if not self.fallback_gyro_calibrated:
            if still:
                self.fallback_gyro_sum[0] += gx
                self.fallback_gyro_sum[1] += gy
                self.fallback_gyro_sum[2] += gz
                self.fallback_gyro_samples += 1
                if self.fallback_gyro_samples >= 96:
                    self.fallback_gyro_bias = [round(v / self.fallback_gyro_samples) for v in self.fallback_gyro_sum]
                    self.fallback_gyro_calibrated = True
                    self.calibration_status = "bias fallback OK"
            else:
                self.fallback_gyro_sum = [0, 0, 0]
                self.fallback_gyro_samples = 0
        if self.fallback_gyro_calibrated:
            parsed["gyro_x"] -= self.fallback_gyro_bias[0]
            parsed["gyro_y"] -= self.fallback_gyro_bias[1]
            parsed["gyro_z"] -= self.fallback_gyro_bias[2]
        return parsed

    def _parse(self, report: bytes):
        # Full reports: USB 0x01/64 bytes, Bluetooth 0x31/78 bytes.
        if len(report) >= 64 and report[0] == 0x01:
            c = 1
            self.transport = "usb"
        elif len(report) >= 78 and report[0] == 0x31:
            c = 3
            self.transport = "bt"
        else:
            return None

        x, y, rx, ry, lt, rt = report[c:c+6]
        buttons0, buttons1, buttons2 = report[c+7], report[c+8], report[c+9]
        hat = buttons0 & 0x0F
        if hat > 8:
            hat = 8

        gyro_off = c + 15
        accel_off = c + 21
        ts_off = c + 27
        gx = self._s16(report, gyro_off + 0)
        gy = self._s16(report, gyro_off + 2)
        gz = self._s16(report, gyro_off + 4)
        ax = self._s16(report, accel_off + 0)
        ay = self._s16(report, accel_off + 2)
        az = self._s16(report, accel_off + 4)
        timestamp = struct.unpack_from("<I", report, ts_off)[0]

        return {
            "lx_u8": x, "ly_u8": y, "rx_u8": rx, "ry_u8": ry,
            "lt_u8": lt, "rt_u8": rt, "hat": hat,
            "square": bool(buttons0 & 0x10), "cross": bool(buttons0 & 0x20),
            "circle": bool(buttons0 & 0x40), "triangle": bool(buttons0 & 0x80),
            "l1": bool(buttons1 & 0x01), "r1": bool(buttons1 & 0x02),
            "create": bool(buttons1 & 0x10), "options": bool(buttons1 & 0x20),
            "l3": bool(buttons1 & 0x40), "r3": bool(buttons1 & 0x80),
            "ps": bool(buttons2 & 0x01), "touchpad": bool(buttons2 & 0x02),
            "gyro_x": gx, "gyro_y": gy, "gyro_z": gz,
            "accel_x": ax, "accel_y": ay, "accel_z": az,
            "imu_timestamp": timestamp,
        }

    def _run(self):
        while not self.stop_evt.is_set():
            try:
                if not self.handle:
                    paths = self.api.enumerate_matching_paths(
                        SONY_VID, DUALSENSE_PIDS, usage_page=0x01, usage=0x05
                    )
                    if getattr(self,"preferred_path",""):
                        paths=[p for p in paths if p.casefold()==self.preferred_path.casefold()]
                    if not paths:
                        with self.lock:
                            self.status = "DualSense not found"
                        time.sleep(1.0)
                        continue
                    self.path = paths[0]
                    self.handle = self.api.open(self.path, write=False)
                    if not self.handle:
                        with self.lock:
                            self.status = "DualSense: unable to open HID"
                        time.sleep(0.5)
                        continue
                    self._read_calibration()
                    self._read_firmware_info()
                    self.write_handle = self.api.open(self.path, write=True)
                    with self.lock:
                        self.status = f"DualSense HID ({self.calibration_status})"

                report = self.api.read(self.handle, 78)
                if not report:
                    raise OSError("HID read ended")
                parsed = self._calibrate_motion(self._parse(report))
                if parsed:
                    with self.lock:
                        self.latest = parsed
                        self.reports += 1
            except Exception as exc:
                with self.lock:
                    self.errors += 1
                    self.status = f"DualSense HID: {exc}"
                self._close_handle()
                if self.stop_evt.wait(0.5):
                    break
        self._close_handle()



class StadiaReader:
    """Native Google Stadia Controller HID reader for Windows.

    Works with the controller's standard Game Pad top-level collection
    (VID 18D1, PID 9400) over USB and Bluetooth. No virtual controller or
    extra driver is required.
    """
    def __init__(self):
        self.api = SteamHidApi()
        self.lock = threading.Lock()
        self.stop_evt = threading.Event()
        self.thread = None
        self.handle = None
        self.write_handle = None
        self.path = ""
        self.latest = None
        self.reports = 0
        self.errors = 0
        self.status = "Stadia HID inactive"
        self.report_size = 64

    def start(self, preferred_path: str = ""):
        self.stop()
        self.stop_evt.clear()
        self.preferred_path = str(preferred_path or "")
        self.thread = threading.Thread(target=self._run, name="SwitchNet-StadiaHID", daemon=True)
        self.thread.start()

    def _close_handles(self):
        read_handle, write_handle = self.handle, self.write_handle
        self.handle = None
        self.write_handle = None
        if read_handle:
            self.api.close(read_handle)
        if write_handle and write_handle != read_handle:
            self.api.close(write_handle)

    def stop(self):
        self.stop_evt.set()
        self.api.cancel(self.handle)
        thread = self.thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(2.0)
        if not thread or not thread.is_alive():
            self._close_handles()
            self.thread = None
        with self.lock:
            self.latest = None
            self.status = "Stadia HID inactive" if not thread or not thread.is_alive() else "Stadia HID: stopping"

    def snapshot(self):
        with self.lock:
            return {
                "state": dict(self.latest) if self.latest else None,
                "status": self.status,
                "reports": self.reports,
                "errors": self.errors,
                "path": self.path,
            }

    @staticmethod
    def _parse(report: bytes):
        # Stadia's standard gamepad report is ID 0x03. The HID descriptor
        # defines: hat nibble, 15 buttons, X/Y/Z/Rz, Brake/Accelerator.
        if len(report) < 10 or report[0] != 0x03:
            return None
        hat = report[1] & 0x0F
        if hat > 7:
            hat = HAT_NEUTRAL
        # The Stadia report does NOT store buttons in SDL b0..b14 order.
        # Decode the actual HID packet used by Google's firmware, then build a
        # canonical bitfield matching the logical Stadia controls expected by
        # stadia_values():
        #   b0 A, b1 B, b2 X, b3 Y, b4 L1, b5 R1, b6 L3, b7 R3,
        #   b8 Back/Options, b9 Start/Menu, b10 Stadia/Home,
        #   b13 Assistant, b14 Capture/Share.
        meta = int(report[2])
        face = int(report[3])
        buttons = 0
        if face & 0x40: buttons |= 1 << 0   # A
        if face & 0x20: buttons |= 1 << 1   # B
        if face & 0x10: buttons |= 1 << 2   # X
        if face & 0x08: buttons |= 1 << 3   # Y
        if face & 0x04: buttons |= 1 << 4   # L1
        if face & 0x02: buttons |= 1 << 5   # R1
        if face & 0x01: buttons |= 1 << 6   # L3
        if meta & 0x80: buttons |= 1 << 7   # R3
        if meta & 0x40: buttons |= 1 << 8   # Options / Back
        if meta & 0x20: buttons |= 1 << 9   # Menu / Start
        if meta & 0x10: buttons |= 1 << 10  # Stadia / Home
        if meta & 0x02: buttons |= 1 << 13  # Google Assistant
        if meta & 0x01: buttons |= 1 << 14  # Capture / Share
        return {
            "hat": hat,
            "buttons": buttons,
            "lx_u8": report[4], "ly_u8": report[5],
            "rx_u8": report[6], "ry_u8": report[7],
            "lt_u8": report[8], "rt_u8": report[9],
        }

    def _ensure_write_handle(self):
        if self.write_handle:
            return True
        if not self.path:
            return False
        self.write_handle = self.api.open(self.path, write=True)
        return bool(self.write_handle)

    def rumble(self, left: int, right: int):
        # Report 0x05 contains two little-endian 16-bit actuator values.
        # Linux's hid-google-stadiaff uses field[0]=strong and field[1]=weak.
        # Windows supports this reliably over USB. On Bluetooth some Windows
        # builds reject output reports; try WriteFile first, then the HID
        # control-transfer API as a best-effort fallback.
        try:
            if not self._ensure_write_handle():
                return False
            data = bytearray(5)
            data[0] = 0x05
            struct.pack_into("<HH", data, 1,
                             max(0, min(65535, int(left))),
                             max(0, min(65535, int(right))))
            packet = bytes(data)
            if self.api.write(self.write_handle, packet):
                return True
            return self.api.set_output_report(self.write_handle, packet)
        except Exception:
            return False

    def _run(self):
        while not self.stop_evt.is_set():
            try:
                if not self.handle:
                    paths = self.api.enumerate_matching_paths(
                        STADIA_VID, STADIA_PIDS, usage_page=0x01, usage=0x05
                    )
                    if getattr(self,"preferred_path",""):
                        paths=[p for p in paths if p.casefold()==self.preferred_path.casefold()]
                    if not paths:
                        with self.lock:
                            self.status = "Stadia Controller not found"
                        if self.stop_evt.wait(0.8):
                            break
                        continue
                    self.path = paths[0]
                    caps = self.api.caps(self.path)
                    if caps and caps.InputReportByteLength:
                        self.report_size = max(10, int(caps.InputReportByteLength))
                    self.handle = self.api.open(self.path, write=False)
                    if not self.handle:
                        with self.lock:
                            self.status = "Stadia: unable to open HID"
                        if self.stop_evt.wait(0.5):
                            break
                        continue
                    self.write_handle = self.api.open(self.path, write=True)
                    with self.lock:
                        self.status = "Native Stadia HID"

                report = self.api.read(self.handle, self.report_size)
                if not report:
                    raise OSError("HID read ended")
                parsed = self._parse(report)
                if parsed:
                    with self.lock:
                        self.latest = parsed
                        self.reports += 1
            except Exception as exc:
                with self.lock:
                    self.errors += 1
                    self.status = f"Stadia HID: {exc}"
                self._close_handles()
                if self.stop_evt.wait(0.5):
                    break
        self._close_handles()


def _u8_axis(v: int) -> int:
    return max(-32768, min(32767, (int(v) - 128) * 257))


def switchpro_values(raw,dz,labels,mapping=None):
    if raw is None:
        return neutral_values()

    mapping=mapping or default_controller_mapping("switchpro",labels)
    buttons=set(raw.get("buttons") or ())
    source_names={
        "A":"a","B":"b","X":"x","Y":"y",
        "L":"l","R":"r","ZL":"zl","ZR":"zr",
        "MINUS":"minus","PLUS":"plus","L3":"l3","R3":"r3",
        "HOME":"home","CAPTURE":"capture",
        "UP":"up","DOWN":"down","LEFT":"left","RIGHT":"right",
    }
    active={source_names[name] for name in buttons if name in source_names}
    out,lt,rt,hat=_mapped_switch_controls(active,mapping)

    return dict(
        buttons=out,
        lx=dead(int(raw.get("lx",0)),dz),
        ly=dead(int(raw.get("ly",0)),dz),
        rx=dead(int(raw.get("rx",0)),dz),
        ry=dead(int(raw.get("ry",0)),dz),
        lt=lt,rt=rt,hat=hat,
        ax=max(-32768,min(32767,int(raw.get("ax",0)))),
        ay=max(-32768,min(32767,int(raw.get("ay",0)))),
        az=max(-32768,min(32767,int(raw.get("az",4096)))),
        gx=max(-32768,min(32767,int(raw.get("gx",0)))),
        gy=max(-32768,min(32767,int(raw.get("gy",0)))),
        gz=max(-32768,min(32767,int(raw.get("gz",0)))),
        imu_ts=int(raw.get("imu_timestamp",0))&0xFFFFFFFF,
    )

def switch2pro_values(raw,dz,labels,rear_mapping=None,mapping=None):
    if raw is None:
        return neutral_values()

    mapping=mapping or default_controller_mapping(
        "switch2pro",labels,rear_mapping
    )
    buttons=set(raw.get("buttons") or ())
    source_names={
        "A":"a","B":"b","X":"x","Y":"y",
        "L":"l","R":"r","ZL":"zl","ZR":"zr",
        "MINUS":"minus","PLUS":"plus","L3":"l3","R3":"r3",
        "HOME":"home","CAPTURE":"capture","C":"c","GL":"gl","GR":"gr",
        "UP":"up","DOWN":"down","LEFT":"left","RIGHT":"right",
    }
    active={source_names[name] for name in buttons if name in source_names}
    out,lt,rt,hat=_mapped_switch_controls(active,mapping)

    return dict(
        buttons=out,
        lx=dead(int(raw.get("lx",0)),dz),
        ly=dead(int(raw.get("ly",0)),dz),
        rx=dead(int(raw.get("rx",0)),dz),
        ry=dead(int(raw.get("ry",0)),dz),
        lt=lt,rt=rt,hat=hat,
        ax=max(-32768,min(32767,int(raw.get("ax",0)))),
        ay=max(-32768,min(32767,int(raw.get("ay",0)))),
        az=max(-32768,min(32767,int(raw.get("az",4096)))),
        gx=max(-32768,min(32767,int(raw.get("gx",0)))),
        gy=max(-32768,min(32767,int(raw.get("gy",0)))),
        gz=max(-32768,min(32767,int(raw.get("gz",0)))),
        imu_ts=int(raw.get("imu_timestamp",0))&0xffffffff,
    )

def dualsense_values(raw,dz,labels,mapping=None):
    if raw is None:
        return neutral_values()

    mapping=mapping or default_controller_mapping("dualsense",labels)
    active=set()
    for source in (
        "cross","circle","square","triangle","l1","r1",
        "create","options","l3","r3","ps","touchpad"
    ):
        if raw.get(source,False):
            active.add(source)

    lt_strength=int(raw["lt_u8"])*257
    rt_strength=int(raw["rt_u8"])*257
    if lt_strength>4096:
        active.add("l2")
    if rt_strength>4096:
        active.add("r2")

    hat=int(raw.get("hat",8))
    if hat in (0,1,7):active.add("up")
    if hat in (3,4,5):active.add("down")
    if hat in (5,6,7):active.add("left")
    if hat in (1,2,3):active.add("right")

    out,lt,rt,mapped_hat=_mapped_switch_controls(
        active,mapping,
        {"l2":lt_strength,"r2":rt_strength},
    )

    return dict(
        buttons=out,
        lx=dead(_u8_axis(raw["lx_u8"]),dz),
        ly=dead(_u8_axis(raw["ly_u8"]),dz),
        rx=dead(_u8_axis(raw["rx_u8"]),dz),
        ry=dead(_u8_axis(raw["ry_u8"]),dz),
        lt=lt,rt=rt,hat=mapped_hat,
        ax=max(-32768,min(32767,round(raw["accel_y"]/2))),
        ay=max(-32768,min(32767,round(-raw["accel_x"]/2))),
        az=max(-32768,min(32767,round(raw["accel_z"]/2))),
        gx=max(-32768,min(32767,round(raw["gyro_y"]*(16.384/1024.0)))),
        gy=max(-32768,min(32767,round(-raw["gyro_x"]*(16.384/1024.0)))),
        gz=max(-32768,min(32767,round(raw["gyro_z"]*(16.384/1024.0)))),
        imu_ts=raw["imu_timestamp"]&0xFFFFFFFF,
    )

def log_path():
    directory = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "SwitchNet")
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, "client.log")


def log_exception(context, exc):
    try:
        with open(log_path(), "a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {context}: {exc!r}\n")
            f.write(traceback.format_exc())
    except Exception:
        pass


def cfg_path():
    directory = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "SwitchNet")
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, "client.ini")


def dead(v, d):
    return 0 if abs(v) <= d else max(-32768, min(32767, v))


def hat_from_xinput(b):
    u, d, l, r = bool(b & UP), bool(b & DOWN), bool(b & LEFT), bool(b & RIGHT)
    return hat_from_dirs(u, d, l, r)


def hat_from_dirs(u, d, l, r):
    if u and r: return 1
    if r and d: return 3
    if d and l: return 5
    if l and u: return 7
    if u: return 0
    if r: return 2
    if d: return 4
    if l: return 6
    return 8


def neutral_values():
    return dict(buttons=0, lx=0, ly=0, rx=0, ry=0, lt=0, rt=0, hat=8,
                ax=0, ay=0, az=4096, gx=0, gy=0, gz=0, imu_ts=0)


def xinput_values(st,dz,labels,mapping=None):
    if st is None:
        return neutral_values()

    mapping=mapping or default_controller_mapping("xinput",labels)
    g=st.Gamepad
    src=int(g.wButtons)
    active=set()

    for source,mask in (
        ("a",A),("b",B),("x",X),("y",Y),
        ("lb",LSHOULDER),("rb",RSHOULDER),
        ("back",BACK),("start",START),
        ("l3",LTHUMB),("r3",RTHUMB),("guide",GUIDE),
        ("up",UP),("down",DOWN),("left",LEFT),("right",RIGHT),
    ):
        if src&mask:
            active.add(source)

    lt_strength=int(g.bLeftTrigger)*257
    rt_strength=int(g.bRightTrigger)*257
    if lt_strength>4096:active.add("lt")
    if rt_strength>4096:active.add("rt")

    out,lt,rt,hat=_mapped_switch_controls(
        active,mapping,
        {"lt":lt_strength,"rt":rt_strength},
    )

    return dict(
        buttons=out,
        lx=dead(int(g.sThumbLX),dz),ly=dead(-int(g.sThumbLY),dz),
        rx=dead(int(g.sThumbRX),dz),ry=dead(-int(g.sThumbRY),dz),
        lt=lt,rt=rt,hat=hat,
        ax=0,ay=0,az=4096,gx=0,gy=0,gz=0,imu_ts=0,
    )

def steam_values(raw, dz, labels, steam_mapping=None, gyro_trim=False):
    if raw is None:
        return neutral_values()
    b = raw["buttons_raw"]

    # "Default" preserves the historical SwitchNet behavior (including the
    # global position/labels option). Custom Steam profiles pass an explicit
    # source->Switch target map here.
    mapping = steam_mapping or default_steam_mapping(labels)
    out = 0
    dpad_up = dpad_down = dpad_left = dpad_right = False
    force_zl = force_zr = False

    for source, _label in STEAM_SOURCE_BUTTONS:
        if not b.get(source, False):
            continue
        target = mapping.get(source, "None")

        bit = STEAM_TARGET_BUTTON_BITS.get(target)
        if bit is not None:
            out |= bit
        elif target == "ZL":
            force_zl = True
        elif target == "ZR":
            force_zr = True
        elif target == "D-Pad Up":
            dpad_up = True
        elif target == "D-Pad Down":
            dpad_down = True
        elif target == "D-Pad Left":
            dpad_left = True
        elif target == "D-Pad Right":
            dpad_right = True

    # Profile-level chord mapping. This is intentionally represented as a
    # normal mapping source ("L5 + R5") instead of a global toggle, so each
    # custom preset can decide independently whether the chord means Capture
    # or any other Switch command. The physical ... button remains separately
    # assignable (set it to None when the chord should replace it).
    if b.get("l5", False) and b.get("r5", False):
        target = mapping.get("l5+r5", "None")
        bit = STEAM_TARGET_BUTTON_BITS.get(target)
        if bit is not None:
            out |= bit
        elif target == "ZL":
            force_zl = True
        elif target == "ZR":
            force_zr = True
        elif target == "D-Pad Up":
            dpad_up = True
        elif target == "D-Pad Down":
            dpad_down = True
        elif target == "D-Pad Left":
            dpad_left = True
        elif target == "D-Pad Right":
            dpad_right = True

    lt = min(65535, raw["lt_raw"] * 2)
    rt = min(65535, raw["rt_raw"] * 2)
    if force_zl:
        lt = 65535
    if force_zr:
        rt = 65535

    return dict(
        buttons=out,
        lx=dead(raw["lx"], dz), ly=dead(-raw["ly"], dz),
        rx=dead(raw["rx"], dz), ry=dead(-raw["ry"], dz),
        lt=lt, rt=rt,
        hat=hat_from_dirs(dpad_up, dpad_down, dpad_left, dpad_right),
        # Triton -> Nintendo motion coordinates. Keep accel and gyro in the
        # same proper rotation (det +1), matching OpenPuck's console-tested
        # mapping: Switch X <- +SC Y, Y <- -SC X, Z <- +SC Z.
        # Triton accel is 16384 count/g; Nintendo expects 4096 count/g.
        ax=max(-32768, min(32767, round(raw.get("accel_y", 0) / 4))),
        ay=max(-32768, min(32767, round(-raw.get("accel_x", 0) / 4))),
        az=max(-32768, min(32767, round(raw.get("accel_z", 16384) / 4))),
        gx=max(-32768, min(32767, round(raw.get("gyro_y", 0) * (0.80 if gyro_trim else 1.0)))),
        gy=max(-32768, min(32767, round(-raw.get("gyro_x", 0) * (0.90 if gyro_trim else 1.0)))),
        gz=max(-32768, min(32767, round(raw.get("gyro_z", 0) * (0.90 if gyro_trim else 1.0)))),
        imu_ts=raw.get("imu_timestamp", 0) & 0xFFFFFFFF,
    )


def stadia_values(raw,dz,labels,mapping=None):
    if raw is None:
        return neutral_values()

    mapping=mapping or default_controller_mapping("stadia",labels)
    bits=int(raw["buttons"])
    active=set()

    for source,bit in (
        ("a",0),("b",1),("x",2),("y",3),
        ("l1",4),("r1",5),("l3",6),("r3",7),
        ("back",8),("start",9),("home",10),
        ("r2",11),("l2",12),("assistant",13),("capture",14),
    ):
        if bits&(1<<bit):
            active.add(source)

    lt_strength=int(raw["lt_u8"])*257
    rt_strength=int(raw["rt_u8"])*257
    if lt_strength>4096:active.add("l2")
    if rt_strength>4096:active.add("r2")

    hat0=int(raw.get("hat",8))
    if hat0 in (0,1,7):active.add("up")
    if hat0 in (3,4,5):active.add("down")
    if hat0 in (5,6,7):active.add("left")
    if hat0 in (1,2,3):active.add("right")

    out,lt,rt,hat=_mapped_switch_controls(
        active,mapping,
        {"l2":lt_strength,"r2":rt_strength},
    )

    return dict(
        buttons=out,
        lx=dead(_u8_axis(raw["lx_u8"]),dz),
        ly=dead(_u8_axis(raw["ly_u8"]),dz),
        rx=dead(_u8_axis(raw["rx_u8"]),dz),
        ry=dead(_u8_axis(raw["ry_u8"]),dz),
        lt=lt,rt=rt,hat=hat,
        ax=0,ay=0,az=4096,gx=0,gy=0,gz=0,imu_ts=0,
    )

def pack_payload(vals):
    return struct.pack(
        "<IhhhhHHB3xhhhhhhI", vals["buttons"], vals["lx"], vals["ly"], vals["rx"], vals["ry"],
        vals["lt"], vals["rt"], vals["hat"], vals["ax"], vals["ay"], vals["az"],
        vals["gx"], vals["gy"], vals["gz"], vals["imu_ts"]
    )


def controller_slot_flags(slot):
    """Encode the controller slot exactly like firmware SwitchNetProtocol.h."""
    return 0x0100 if int(slot) == 1 else 0x0000


def make_packet(payload, session, seq, us, slot=0):
    flags = controller_slot_flags(slot)
    header = struct.pack("<IBBHHHIII", 0x544E5753, 3, 1, 24, 36, flags,
                         session, seq & 0xFFFFFFFF, us & 0xFFFFFFFF)
    body = header + payload
    return body + struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF)



RUMBLE_PACKET_SIZE = 40
RUMBLE_TYPE = 2
_LOW_AMPLITUDES = (
    0.0, 0.007843, 0.011823, 0.014061, 0.016720, 0.019885, 0.023648, 0.028123,
    0.033442, 0.039771, 0.047296, 0.056246, 0.066886, 0.079542, 0.094592, 0.112491,
)

def _decode_hd_amp(motor4: bytes) -> int:
    if len(motor4) != 4:
        return 0
    # The high-amplitude field occupies the even bits of byte 1; bit 0 is control.
    idx = (motor4[1] & 0xFE) >> 1
    if idx <= 0:
        amp = 0.0
    elif idx < 16:
        amp = _LOW_AMPLITUDES[idx]
    elif idx < 32:
        amp = (2.0 ** (idx / 16.0)) / 17.0
    else:
        amp = (2.0 ** (idx / 32.0)) / 8.7
    return max(0, min(65535, round(min(1.0, amp) * 65535.0)))

def parse_rumble_packet(data: bytes, session: int, slot: int = 0):
    if len(data) != RUMBLE_PACKET_SIZE:
        return None
    magic, version, ptype, hsize, psize, flags, packet_session, seq, timestamp = struct.unpack_from('<IBBHHHIII', data, 0)
    if magic != 0x544E5753 or version != 3 or ptype != RUMBLE_TYPE or hsize != 24 or psize != 12:
        return None
    if packet_session != session:
        return None
    if (flags & 0x0100) != (0x0100 if int(slot)==1 else 0):
        return None
    expected = struct.unpack_from('<I', data, 36)[0]
    if (zlib.crc32(data[:36]) & 0xFFFFFFFF) != expected:
        return None
    raw = data[24:32]
    hold_ms, gain_field = struct.unpack_from('<HH', data, 32)
    # v1.7.11 uses the formerly-reserved field as 0..100% gain.
    # A zero field from older firmware means legacy/full intensity.
    gain_percent = gain_field if 0 < gain_field <= 100 else 100
    left = round(_decode_hd_amp(raw[:4]) * gain_percent / 100.0)
    right = round(_decode_hd_amp(raw[4:]) * gain_percent / 100.0)
    return {
        'left': max(0, min(65535, left)),
        'right': max(0, min(65535, right)),
        'hold_ms': hold_ms,
        'gain_percent': gain_percent,
        'raw': raw.hex(' ').upper(),
        'sequence': seq,
    }

class Worker:
    def __init__(self, xi):
        self.xi = xi
        self.steam = SteamHidReader()
        self.switchpro = SwitchProReader()
        self.switch2pro = Switch2ProReader()
        self.dualsense = DualSenseReader()
        self.stadia = StadiaReader()
        self.kbm = WindowsKeyboardMouseReader()
        self.stop_evt = threading.Event()
        self.thread = None
        self.lock = threading.Lock()
        self.life_lock = threading.Lock()
        self.snap = {
            "running": False, "connected": False, "tx": 0, "errors": 0, "total": 0,
            "status": "Ready", "values": {}, "input_backend": "-", "input_detail": ""
        }

    def start(self, host, port, rate, index, dz, labels, backend, steam_mapping=None, steam_gyro_trim=False, switch2_rear_mapping=None, controller_mapping=None, slot=0, controller_path="", controller_paths=None, keyboard_mapping=None, keyboard_exclusive=True, keyboard_release_key=DEFAULT_RELEASE_KEY, mouse_sensitivity=6500):
        self.stop()
        with self.life_lock:
            self.stop_evt.clear()
            self.pub(
                running=True,
                connected=False,
                status=f"Starting {backend}…",
                input_backend="-",
                input_detail="initializing worker",
            )
            args=(
                host,port,rate,index,dz,labels,backend,steam_mapping,
                steam_gyro_trim,switch2_rear_mapping,controller_mapping,slot,controller_path,controller_paths,
                keyboard_mapping,keyboard_exclusive,keyboard_release_key,mouse_sensitivity
            )
            self.thread=threading.Thread(
                target=self._run_guarded,
                args=args,
                name=f"SwitchNet-Network-Worker-P{slot+1}",
                daemon=True,
            )
            self.thread.start()

    def stop(self):
        # Only the network worker owns the HID readers. The old implementation
        # stopped HID threads from the GUI while the network thread was still
        # polling them, which could race native ReadFile/CloseHandle and crash
        # the entire Python process.
        self.stop_evt.set()
        with self.life_lock:
            thread = self.thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(4.0)
        with self.life_lock:
            if self.thread is thread and (not thread or not thread.is_alive()):
                self.thread = None
        if thread and thread.is_alive():
            self.pub(status="Stopping service...")

    def get(self):
        with self.lock:
            return {**self.snap, "values": dict(self.snap.get("values", {}))}

    def pub(self, **kw):
        with self.lock:
            self.snap.update(kw)

    def _run_guarded(
        self,host,port,rate,index,dz,labels,backend,
        steam_mapping=None,steam_gyro_trim=False,switch2_rear_mapping=None,controller_mapping=None,slot=0,
        controller_path="",controller_paths=None,
        keyboard_mapping=None,keyboard_exclusive=True,
        keyboard_release_key=DEFAULT_RELEASE_KEY,
        mouse_sensitivity=6500
    ):
        try:
            self.run(
                host,port,rate,index,dz,labels,backend,
                steam_mapping,steam_gyro_trim,switch2_rear_mapping,controller_mapping,slot,
                controller_path,controller_paths,
                keyboard_mapping,keyboard_exclusive,keyboard_release_key,mouse_sensitivity
            )
        except Exception as exc:
            import traceback
            detail=traceback.format_exc()
            log_exception(f"worker P{slot+1}",exc)
            self.pub(
                running=False,
                connected=False,
                status=f"P{slot+1} worker failed: {exc}",
                input_backend=backend,
                input_detail=str(exc),
                worker_exception=detail,
            )

    def run(self, host, port, rate, index, dz, labels, backend, steam_mapping=None, steam_gyro_trim=False, switch2_rear_mapping=None, controller_mapping=None, slot=0, controller_path="", controller_paths=None, keyboard_mapping=None, keyboard_exclusive=True, keyboard_release_key=DEFAULT_RELEASE_KEY, mouse_sensitivity=6500):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        dst = (host, port)
        session = random.getrandbits(32) or 1
        seq = 0
        start_ns = time.perf_counter_ns()
        period = max(1_000_000, int(1e9 / max(1, rate)))
        nxt = time.perf_counter_ns()
        stat = nxt + 1_000_000_000
        tx = err = total = 0
        rumble_rx = 0
        rumble_left = rumble_right = 0
        rumble_backend = "-"
        last_rumble_at = 0.0
        steam_mode = backend in ("auto", "steam_passive", "steam_direct")
        switchpro_mode = backend in ("auto", "switchpro_hid")
        switch2pro_mode = backend in ("auto", "switch2pro_hid")
        dualsense_mode = backend in ("auto", "dualsense_hid")
        stadia_mode = backend in ("auto", "stadia_hid")
        keyboard_mode = backend == "keyboard_mouse"
        if steam_mode:
            self.steam.start(
                active_mode=(backend == "steam_direct"),
                preferred_path=controller_path,
                preferred_paths=controller_paths,
            )
        if switchpro_mode:
            self.switchpro.start(
                controller_path,
                preferred_paths=controller_paths,
            )
        if switch2pro_mode:
            self.switch2pro.start(
                controller_path,
                preferred_paths=controller_paths,
            )
        if dualsense_mode:
            self.dualsense.start(controller_path)
        if stadia_mode:
            self.stadia.start(controller_path)
        if keyboard_mode:
            self.kbm.start(keyboard_mapping,exclusive=keyboard_exclusive,release_key=keyboard_release_key)
        self.pub(running=True, status="Transmission active in background")
        try:
            while not self.stop_evt.is_set():
                rem = nxt - time.perf_counter_ns()
                if rem > 1_000_000:
                    time.sleep((rem - 500_000) / 1e9)
                    continue
                while time.perf_counter_ns() < nxt:
                    time.sleep(0)

                vals = None
                connected = False
                input_backend = "-"
                input_detail = ""

                if keyboard_mode:
                    keys,dx,dy,kstatus,kexclusive,kbm_enabled=self.kbm.consume()
                    vals=keyboard_mouse_values(
                        keys,dx,dy,keyboard_mapping,mouse_sensitivity,
                        BTN_A,BTN_B,BTN_X,BTN_Y,BTN_L,BTN_R,
                        BTN_BACK,BTN_START,BTN_LS,BTN_RS,BTN_GUIDE,BTN_CAPTURE,
                    )
                    connected=True
                    input_backend="Keyboard + Mouse"
                    input_detail=kstatus+(
                        " · enabled" if kbm_enabled else " · neutral"
                    )

                if vals is None and switchpro_mode:
                    nsp=self.switchpro.snapshot()
                    if nsp["state"] is not None:
                        vals=switchpro_values(
                            nsp["state"],dz,labels,controller_mapping
                        )
                        connected=True
                        input_backend="Nintendo Switch Pro HID"
                        input_detail="Native HID"
                    elif backend=="switchpro_hid":
                        input_backend="Nintendo Switch Pro HID"
                        input_detail=nsp["status"]

                if vals is None and switch2pro_mode:
                    ns2=self.switch2pro.snapshot()
                    if ns2["state"] is not None:
                        vals=switch2pro_values(
                            ns2["state"],dz,labels,
                            rear_mapping=switch2_rear_mapping,
                            mapping=controller_mapping,
                        )
                        connected=True
                        input_backend="Nintendo Switch 2 Pro USB"
                        input_detail="Native USB HID"
                    elif backend=="switch2pro_hid":
                        input_backend="Nintendo Switch 2 Pro USB"
                        input_detail=ns2["status"]

                if vals is None and steam_mode:
                    ss = self.steam.snapshot()
                    if ss["state"] is not None:
                        vals = steam_values(ss["state"], dz, labels, steam_mapping, steam_gyro_trim)
                        connected = True
                        input_backend = "Steam Controller 2026 HID"
                        cal = "gyro OK" if ss.get("gyro_calibrated") else "gyro calibration..."
                        input_detail = f"report 0x{ss['report_id']:02X}, {ss['reports']} raw, {cal}"
                    elif backend != "auto":
                        input_backend = "Steam Controller 2026 HID"
                        input_detail = ss["status"]

                if vals is None and dualsense_mode:
                    ds = self.dualsense.snapshot()
                    if ds["state"] is not None:
                        vals = dualsense_values(
                            ds["state"],dz,labels,controller_mapping
                        )
                        connected = True
                        input_backend = "DualSense HID"
                        input_detail = f"{ds['reports']} raw, {ds.get('calibration_status', 'cal?')}"
                    elif backend == "dualsense_hid":
                        input_backend = "DualSense HID"
                        input_detail = ds["status"]

                if vals is None and stadia_mode:
                    st = self.stadia.snapshot()
                    if st["state"] is not None:
                        vals = stadia_values(
                            st["state"],dz,labels,controller_mapping
                        )
                        connected = True
                        input_backend = "Google Stadia Controller HID"
                        input_detail = f"{st['reports']} raw"
                    elif backend == "stadia_hid":
                        input_backend = "Google Stadia Controller HID"
                        input_detail = st["status"]

                if vals is None and backend in ("auto", "xinput"):
                    state = self.xi.state(index)
                    if state is not None:
                        vals = xinput_values(
                            state,dz,labels,controller_mapping
                        )
                        connected = True
                        input_backend = f"XInput {index}"
                        input_detail = self.xi.dll_name

                if vals is None:
                    vals = neutral_values()

                payload = pack_payload(vals)
                us = (time.perf_counter_ns() - start_ns) // 1000
                data = make_packet(payload, session, seq, us, slot)
                seq = (seq + 1) & 0xFFFFFFFF
                try:
                    sock.sendto(data, dst)
                    tx += 1
                    total += 1
                except OSError:
                    err += 1

                # ESP32 sends haptic feedback back to the same UDP source port.
                while True:
                    try:
                        feedback, _ = sock.recvfrom(128)
                    except BlockingIOError:
                        break
                    except OSError:
                        break
                    r = parse_rumble_packet(feedback, session, slot)
                    if not r:
                        continue
                    rumble_rx += 1
                    rumble_left, rumble_right = r['left'], r['right']
                    last_rumble_at = time.monotonic()
                    if input_backend.startswith("XInput"):
                        if self.xi.rumble(index, rumble_left, rumble_right):
                            rumble_backend = "XInput"
                    elif input_backend.startswith("Nintendo Switch Pro"):
                        if self.switchpro.rumble(
                            rumble_left,rumble_right
                        ):
                            rumble_backend="Nintendo Switch Pro HID"
                    elif input_backend.startswith("Nintendo Switch 2 Pro"):
                        if self.switch2pro.rumble(rumble_left,rumble_right):
                            rumble_backend="Switch 2 Pro USB"
                    elif input_backend.startswith("Steam Controller"):
                        if self.steam.rumble(rumble_left, rumble_right):
                            rumble_backend = "Steam HID 2026"
                    elif input_backend.startswith("DualSense"):
                        if self.dualsense.rumble(rumble_left, rumble_right):
                            rumble_backend = "DualSense HID"
                    elif input_backend.startswith("Google Stadia"):
                        if self.stadia.rumble(rumble_left, rumble_right):
                            rumble_backend = "Stadia HID"

                # Safety stop if the reverse channel disappears mid-effect.
                if last_rumble_at and time.monotonic() - last_rumble_at > 0.12 and (rumble_left or rumble_right):
                    rumble_left = rumble_right = 0
                    if input_backend.startswith("XInput"):
                        self.xi.rumble(index, 0, 0)
                    elif input_backend.startswith("Nintendo Switch Pro"):
                        self.switchpro.rumble(0,0)
                    elif input_backend.startswith("Nintendo Switch 2 Pro"):
                        self.switch2pro.rumble(0,0)
                    elif input_backend.startswith("Steam Controller"):
                        self.steam.rumble(0, 0)
                    elif input_backend.startswith("DualSense"):
                        self.dualsense.rumble(0, 0)
                    elif input_backend.startswith("Google Stadia"):
                        self.stadia.rumble(0, 0)

                now = time.perf_counter_ns()
                nxt += period
                if now - nxt > 100_000_000:
                    nxt = now + period
                if now >= stat:
                    status = "Transmission active in background" if connected else "Controller unavailable: neutral state"
                    self.pub(running=True, connected=connected, tx=tx, errors=err, total=total,
                             status=status, values=vals, input_backend=input_backend,
                             input_detail=input_detail, rumble_rx=rumble_rx, rumble_left=rumble_left,
                             rumble_right=rumble_right, rumble_backend=rumble_backend)
                    tx = err = 0
                    stat = now + 1_000_000_000
        except Exception as exc:
            log_exception("network worker", exc)
            self.pub(status=f"Worker error: {exc}", errors=err + 1)
        finally:
            neutral = pack_payload(neutral_values())
            for _ in range(8):
                try:
                    sock.sendto(make_packet(neutral, session, seq, 0), dst)
                except OSError:
                    pass
                seq += 1
                time.sleep(0.002)
            self.xi.rumble(index, 0, 0)
            try:
                self.switch2pro.rumble(0,0)
            except Exception:
                pass
            try:
                self.steam.rumble(0, 0)
            except Exception:
                pass
            try:
                self.dualsense.rumble(0, 0)
            except Exception:
                pass
            try:
                self.stadia.rumble(0, 0)
            except Exception:
                pass
            sock.close()
            self.switchpro.stop()
            self.switch2pro.stop()
            self.steam.stop()
            self.dualsense.stop()
            self.stadia.stop()
            self.kbm.stop()
            self.pub(running=False, connected=False, tx=0, status="Transmission stopped")


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long,
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


class NativeTrayIcon:
    """Small native Windows tray icon with no third-party dependencies.

    The tray owns its Win32 message loop on a dedicated thread. All actions that
    touch Tk are marshalled back to Tk's main thread with ``root.after``.
    """

    WM_TRAY = 0x8001  # WM_APP + 1
    WM_LBUTTONDBLCLK = 0x0203
    WM_RBUTTONUP = 0x0205
    WM_CLOSE = 0x0010
    WM_DESTROY = 0x0002
    WM_NULL = 0x0000

    NIM_ADD = 0x00000000
    NIM_MODIFY = 0x00000001
    NIM_DELETE = 0x00000002
    NIM_SETVERSION = 0x00000004
    NIF_MESSAGE = 0x00000001
    NIF_ICON = 0x00000002
    NIF_TIP = 0x00000004
    NOTIFYICON_VERSION_4 = 4

    MF_STRING = 0x00000000
    MF_GRAYED = 0x00000001
    MF_DISABLED = 0x00000002
    MF_SEPARATOR = 0x00000800
    TPM_RIGHTBUTTON = 0x0002
    TPM_RETURNCMD = 0x0100

    CMD_OPEN = 1001
    CMD_TOGGLE = 1002
    CMD_EXIT = 1003
    CMD_WAKE = 1004
    CMD_DISCOVER = 1005

    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x0010
    LR_DEFAULTSIZE = 0x0040

    def __init__(self, root, on_open, on_start, on_stop, on_wake, on_exit):
        self.root = root
        self.on_open = on_open
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_wake = on_wake
        self.on_exit = on_exit
        self._lock = threading.Lock()
        self._service_running = False
        self._service_status = "Stopped"
        self._controller = "None"
        self._hwnd = None
        self._thread = None
        self._ready = threading.Event()
        self._wndproc = None
        self._class_name = f"SwitchNetTray_{os.getpid()}"
        self._icon_active = None
        self._icon_inactive = None
        self._last_icon_running = None

        self.user32 = ctypes.WinDLL("user32.dll", use_last_error=True)
        self.shell32 = ctypes.WinDLL("shell32.dll", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)
        self._configure_api()

    def _configure_api(self):
        self.kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        self.kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        self.user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
        self.user32.RegisterClassW.restype = wintypes.ATOM
        self.user32.CreateWindowExW.argtypes = [
            wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p
        ]
        self.user32.CreateWindowExW.restype = wintypes.HWND
        self.user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.user32.DefWindowProcW.restype = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
        self.user32.DestroyWindow.argtypes = [wintypes.HWND]
        self.user32.DestroyWindow.restype = wintypes.BOOL
        self.user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.user32.PostMessageW.restype = wintypes.BOOL
        self.user32.GetMessageW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.UINT]
        self.user32.GetMessageW.restype = wintypes.BOOL
        self.user32.TranslateMessage.argtypes = [ctypes.c_void_p]
        self.user32.DispatchMessageW.argtypes = [ctypes.c_void_p]
        self.user32.PostQuitMessage.argtypes = [ctypes.c_int]
        self.user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
        self.user32.LoadIconW.restype = wintypes.HICON
        self.user32.LoadImageW.argtypes = [
            wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
            ctypes.c_int, ctypes.c_int, wintypes.UINT
        ]
        self.user32.LoadImageW.restype = wintypes.HANDLE
        self.user32.DestroyIcon.argtypes = [wintypes.HICON]
        self.user32.DestroyIcon.restype = wintypes.BOOL
        self.user32.CreatePopupMenu.restype = wintypes.HMENU
        self.user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
        self.user32.TrackPopupMenu.argtypes = [
            wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, ctypes.c_void_p
        ]
        self.user32.TrackPopupMenu.restype = wintypes.UINT
        self.user32.DestroyMenu.argtypes = [wintypes.HMENU]
        self.user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
        self.user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
        self.shell32.Shell_NotifyIconW.restype = wintypes.BOOL

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="SwitchNet-Tray", daemon=True)
        self._thread.start()
        self._ready.wait(2.0)

    def stop(self):
        hwnd = self._hwnd
        if hwnd:
            self.user32.PostMessageW(hwnd, self.WM_CLOSE, 0, 0)
        if self._thread and self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(2.0)

    def update(self, running: bool, status: str, controller: str):
        with self._lock:
            self._service_running = bool(running)
            self._service_status = status or ("Running" if running else "Stopped")
            self._controller = controller or "None"
        hwnd = self._hwnd
        if hwnd:
            self._modify_tray()

    def _schedule(self, callback):
        try:
            self.root.after(0, callback)
        except Exception:
            pass

    def _snapshot(self):
        with self._lock:
            return self._service_running, self._service_status, self._controller

    def _load_icons(self):
        if self._icon_active and self._icon_inactive:
            return
        flags = self.LR_LOADFROMFILE | self.LR_DEFAULTSIZE
        active_path = resource_path(os.path.join("assets", "tray_active.ico"))
        inactive_path = resource_path(os.path.join("assets", "tray_inactive.ico"))
        self._icon_active = self.user32.LoadImageW(
            None, active_path, self.IMAGE_ICON, 0, 0, flags
        )
        self._icon_inactive = self.user32.LoadImageW(
            None, inactive_path, self.IMAGE_ICON, 0, 0, flags
        )
        # Defensive fallback for development copies with missing assets.
        if not self._icon_active or not self._icon_inactive:
            resource = ctypes.cast(ctypes.c_void_p(32512), wintypes.LPCWSTR)
            fallback = self.user32.LoadIconW(None, resource)
            self._icon_active = self._icon_active or fallback
            self._icon_inactive = self._icon_inactive or fallback

    def _current_icon(self):
        self._load_icons()
        running, _, _ = self._snapshot()
        return self._icon_active if running else self._icon_inactive

    def _make_nid(self, include_icon=False):
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uCallbackMessage = self.WM_TRAY
        nid.uFlags = self.NIF_MESSAGE | self.NIF_TIP
        if include_icon:
            nid.uFlags |= self.NIF_ICON
            nid.hIcon = self._current_icon()
        running, _, controller = self._snapshot()
        tip = f"SwitchNet - {'Running' if running else 'Stopped'} - {controller}"[:127]
        nid.szTip = tip
        return nid

    def _modify_tray(self):
        if not self._hwnd:
            return
        running, _, _ = self._snapshot()
        include_icon = running != self._last_icon_running
        nid = self._make_nid(include_icon)
        if self.shell32.Shell_NotifyIconW(self.NIM_MODIFY, ctypes.byref(nid)):
            if include_icon:
                self._last_icon_running = running

    def _show_menu(self, hwnd):
        running, status, controller = self._snapshot()
        menu = self.user32.CreatePopupMenu()
        if not menu:
            return
        try:
            disabled = self.MF_STRING | self.MF_GRAYED | self.MF_DISABLED
            self.user32.AppendMenuW(menu, disabled, 0, f"Service: {status}")
            self.user32.AppendMenuW(menu, disabled, 0, f"Controller: {controller}")
            self.user32.AppendMenuW(menu, self.MF_SEPARATOR, 0, None)
            self.user32.AppendMenuW(menu, self.MF_STRING, self.CMD_OPEN, "Open SwitchNet")
            self.user32.AppendMenuW(
                menu, self.MF_STRING, self.CMD_TOGGLE,
                "Stop service" if running else "Start service"
            )
            self.user32.AppendMenuW(
                menu, self.MF_STRING, self.CMD_WAKE, "Wake Switch 2"
            )
            self.user32.AppendMenuW(
                menu, self.MF_STRING, self.CMD_DISCOVER, "Discover SwitchNet"
            )
            self.user32.AppendMenuW(menu, self.MF_SEPARATOR, 0, None)
            self.user32.AppendMenuW(menu, self.MF_STRING, self.CMD_EXIT, "Exit")

            pos = POINT()
            self.user32.GetCursorPos(ctypes.byref(pos))
            self.user32.SetForegroundWindow(hwnd)
            cmd = self.user32.TrackPopupMenu(
                menu, self.TPM_RIGHTBUTTON | self.TPM_RETURNCMD, pos.x, pos.y, 0, hwnd, None
            )
            self.user32.PostMessageW(hwnd, self.WM_NULL, 0, 0)
            if cmd == self.CMD_OPEN:
                self._schedule(self.on_open)
            elif cmd == self.CMD_TOGGLE:
                self._schedule(self.on_stop if running else self.on_start)
            elif cmd == self.CMD_WAKE:
                self._schedule(self.on_wake)
            elif cmd == self.CMD_DISCOVER:
                self._schedule(self.root.discover_device)
            elif cmd == self.CMD_EXIT:
                self._schedule(self.on_exit)
        finally:
            self.user32.DestroyMenu(menu)

    def _run(self):
        hinst = self.kernel32.GetModuleHandleW(None)

        @WNDPROC
        def wndproc(hwnd, msg, wparam, lparam):
            if msg == self.WM_TRAY:
                event = int(lparam) & 0xFFFF
                if event == self.WM_LBUTTONDBLCLK:
                    self._schedule(self.on_open)
                    return 0
                if event == self.WM_RBUTTONUP:
                    self._show_menu(hwnd)
                    return 0
            elif msg == self.WM_CLOSE:
                self.user32.DestroyWindow(hwnd)
                return 0
            elif msg == self.WM_DESTROY:
                self.user32.PostQuitMessage(0)
                return 0
            return self.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc = wndproc
        wc = WNDCLASSW()
        wc.lpfnWndProc = wndproc
        wc.hInstance = hinst
        wc.lpszClassName = self._class_name
        self.user32.RegisterClassW(ctypes.byref(wc))
        hwnd = self.user32.CreateWindowExW(
            0, self._class_name, "SwitchNet Tray", 0,
            0, 0, 0, 0, None, None, hinst, None
        )
        if not hwnd:
            self._ready.set()
            return
        self._hwnd = hwnd
        nid = self._make_nid(True)
        if self.shell32.Shell_NotifyIconW(self.NIM_ADD, ctypes.byref(nid)):
            self._last_icon_running = self._snapshot()[0]
            ver = self._make_nid(False)
            ver.uTimeoutOrVersion = self.NOTIFYICON_VERSION_4
            self.shell32.Shell_NotifyIconW(self.NIM_SETVERSION, ctypes.byref(ver))
        self._ready.set()

        # MSG is pointer-sized; a byte buffer is sufficient because the API owns
        # its exact native layout. 64 bytes comfortably covers Win32/Win64 MSG.
        msg = ctypes.create_string_buffer(64)
        while self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            self.user32.TranslateMessage(ctypes.byref(msg))
            self.user32.DispatchMessageW(ctypes.byref(msg))

        try:
            nid = self._make_nid(False)
            self.shell32.Shell_NotifyIconW(self.NIM_DELETE, ctypes.byref(nid))
        finally:
            self._hwnd = None
            # LoadImageW icons are process resources; release them on exit.
            for icon in (self._icon_active, self._icon_inactive):
                if icon:
                    try:
                        self.user32.DestroyIcon(icon)
                    except Exception:
                        pass
            self._icon_active = None
            self._icon_inactive = None




class ClientApiServer:
    """Local HTTP control API for the Windows client.

    Bound to loopback by default so no unauthenticated control endpoint is
    exposed to the LAN. GUI operations are marshalled onto Tk's main thread.
    """

    def __init__(self, app, host=CLIENT_API_HOST, port=CLIENT_API_PORT):
        self.app = app
        self.host = host
        self.port = int(port)
        self.httpd = None
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        api = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "SwitchNetClientAPI/1.0"

            def log_message(self, fmt, *args):
                return

            def _json(self, code, payload):
                data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def _text(self, code, value):
                data = str(value).encode("ascii")
                self.send_response(code)
                self.send_header("Content-Type", "text/plain; charset=us-ascii")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def do_GET(self):
                path = self.path.split("?", 1)[0]
                if path == "/status":
                    self._text(200, "ON" if api.app.api_service_running() else "OFF")
                    return
                if path == "/status/details":
                    self._json(200, api.app.api_status())
                    return
                if path == "/health":
                    self._json(200, {"ok": True, "service": "SwitchNetClient", "version": APP_VERSION})
                    return
                self._json(404, {"ok": False, "error": "not_found"})

            def do_POST(self):
                path = self.path.split("?", 1)[0]
                if path == "/start":
                    ok, message = api.app.api_command("start")
                    self._json(200 if ok else 409, {"ok": ok, "action": "start", "message": message})
                    return
                if path == "/stop":
                    ok, message = api.app.api_command("stop")
                    self._json(200 if ok else 409, {"ok": ok, "action": "stop", "message": message})
                    return
                self._json(404, {"ok": False, "error": "not_found"})

        class ReusableServer(ThreadingHTTPServer):
            allow_reuse_address = True
            daemon_threads = True

        self.httpd = ReusableServer((self.host, self.port), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="SwitchNet-HTTP-API", daemon=True)
        self.thread.start()

    def stop(self):
        httpd = self.httpd
        self.httpd = None
        if httpd is not None:
            try:
                httpd.shutdown()
            except Exception:
                pass
            try:
                httpd.server_close()
            except Exception:
                pass
        thread = self.thread
        self.thread = None
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(1.5)



def roster_move(slots,source,target,minimum_slots=4):
    out=list(slots)
    while len(out)<minimum_slots:
        out.append("")
    source=int(source);target=int(target)
    if source<0 or target<0 or source>=len(out) or target>=len(out):
        return out
    if source==target:
        return out
    value=out.pop(source)
    out.insert(target,value)
    while len(out)<minimum_slots:
        out.append("")
    return out


class App(tk.Tk):
    def __init__(self, startup_launch=False):
        super().__init__()
        # Keep the native Tk top-level unmapped from its very first usable
        # frame.  Calling withdraw() only later via after() lets Windows paint
        # the window for a frame, which causes the startup flash seen when
        # launching directly to the tray.
        self.withdraw()
        self.startup_launch = bool(startup_launch)
        self.title(f"SwitchNet Client {APP_VERSION}")
        try:
            self.iconbitmap(resource_path(os.path.join("assets", "tray_active.ico")))
        except Exception:
            pass
        self.geometry("920x660")
        self.minsize(760,540)
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.bind("<Unmap>", self._on_unmap)
        self.xi = XInput()
        self.worker = Worker(self.xi)
        self.worker2 = Worker(self.xi)
        self.closing = False
        self.refresh_job = None
        self._hide_job = None
        self._controller_missing_counts={}
        self._controller_seen_counts={}
        self._last_roster_signature=None
        self._restart_events=[]
        self._service_restart_after_id=None
        self._service_restart_reason=""
        self._roster_drag_source=None
        self.load()
        self.ui()
        self.refresh_controller_roster()
        self.tray = NativeTrayIcon(
            self, self.show_window, self.start, self.stop_service,
            self.wake_switch2, self.exit_from_tray
        )
        self.tray.start()
        self.after(700, self._auto_discover_if_needed)
        self.api = ClientApiServer(self)
        try:
            self.api.start()
        except Exception as exc:
            log_exception("HTTP API", exc)
            self.api = None
        self.refresh_job = self.after(200, self.refresh)
        if self.auto_start.get():
            self.after(300, self.start)

        # The window starts withdrawn.  For tray/startup launches we simply
        # leave it that way, so Windows never maps it and there is no flash.
        # For an ordinary launch, reveal it only once initialization and tray
        # registration are complete.
        if not (self.startup_launch or self.minimized.get()):
            self.after_idle(self.show_window)

    def load(self):
        c = configparser.ConfigParser()
        c.read(cfg_path())
        q = c["client"] if c.has_section("client") else {}
        self.host = tk.StringVar(value=q.get("host", "192.168.0.53"))
        self.port = tk.IntVar(value=int(q.get("port", 5454)))
        self.rate = tk.IntVar(value=int(q.get("rate", 250)))
        self.index = tk.IntVar(value=int(q.get("controller", 0)))
        self.player2_enabled = tk.BooleanVar(value=q.get("player2_enabled", "0") == "1")
        self.backend2 = tk.StringVar(value=q.get("input_backend2", "xinput"))
        self.index2 = tk.IntVar(value=int(q.get("controller2", 1)))
        try:
            legacy_deadzone=int(q.get("deadzone",6000))
        except Exception:
            legacy_deadzone=6000
        legacy_deadzone=max(0,min(16000,legacy_deadzone))

        self.controller_deadzones={}
        for deadzone_id in CONTROLLER_DEADZONE_SPECS:
            try:
                value=int(
                    q.get(
                        f"deadzone_{deadzone_id}",
                        str(legacy_deadzone),
                    )
                )
            except Exception:
                value=legacy_deadzone
            self.controller_deadzones[deadzone_id]=tk.IntVar(
                value=max(0,min(16000,value))
            )

        # Read only for backward-compatible migration; current releases do not
        # use the historical global Button layout setting.
        self.legacy_layout=q.get("layout","position")
        self.keyboard_enabled = tk.BooleanVar(value=q.get("keyboard_enabled","0")=="1")
        self.keyboard_exclusive = tk.BooleanVar(value=q.get("keyboard_exclusive","1")!="0")
        self.keyboard_release_key = tk.StringVar(value=normalized_release_key(q.get("keyboard_release_key",DEFAULT_RELEASE_KEY)))
        self.mouse_sensitivity = tk.IntVar(value=int(q.get("mouse_sensitivity","6500")))
        # Keyboard + Mouse uses the same Default + Custom 1/2/3 profile
        # model as physical controllers. The old single keyboard_mapping value
        # is imported into Custom 1 when present, preserving upgrades.
        self.keyboard_profile=tk.StringVar(
            value=q.get("keyboard_profile","Default")
        )
        if self.keyboard_profile.get() not in CONTROLLER_PROFILE_SLOTS:
            self.keyboard_profile.set("Default")

        self.keyboard_profile_names={
            slot:(
                q.get(
                    f"keyboard_profile_name_{index}",
                    slot,
                ).strip() or slot
            )
            for index,slot in enumerate(CONTROLLER_PROFILE_SLOTS[1:],1)
        }

        legacy_keyboard_mapping=None
        try:
            raw_legacy=json.loads(q.get("keyboard_mapping","{}"))
            if raw_legacy:
                legacy_keyboard_mapping=mapping_without_release_conflict(
                    raw_legacy,self.keyboard_release_key.get()
                )
        except Exception:
            legacy_keyboard_mapping=None

        self.keyboard_profiles={}
        for slot in CONTROLLER_PROFILE_SLOTS[1:]:
            mapping=normalized_keyboard_mapping(None)
            section=f"keyboard_profile:{slot}"
            if c.has_section(section):
                sec=c[section]
                candidate={
                    action:sec.get(action,mapping[action])
                    for action,_label in KEYBOARD_ACTIONS
                }
                mapping=mapping_without_release_conflict(
                    candidate,self.keyboard_release_key.get()
                )
            elif slot=="Custom 1" and legacy_keyboard_mapping is not None:
                mapping=dict(legacy_keyboard_mapping)
            self.keyboard_profiles[slot]=mapping

        self.keyboard_profile_display=tk.StringVar(
            value=(
                "Default"
                if self.keyboard_profile.get()=="Default"
                else self.keyboard_profile_names.get(
                    self.keyboard_profile.get(),
                    self.keyboard_profile.get(),
                )
            )
        )
        self.keyboard_mapping=self._active_keyboard_mapping()
        self.backend = tk.StringVar(value=q.get("input_backend", "auto"))
        self.steam_gyro_trim = tk.BooleanVar(value=q.get("steam_gyro_trim","0")=="1")
        self.switch2_gl_mapping=tk.StringVar(
            value=q.get("switch2_gl_mapping","None")
        )
        if self.switch2_gl_mapping.get() not in SWITCH2_PRO_REAR_TARGETS:
            self.switch2_gl_mapping.set("None")

        self.switch2_gr_mapping=tk.StringVar(
            value=q.get("switch2_gr_mapping","None")
        )
        if self.switch2_gr_mapping.get() not in SWITCH2_PRO_REAR_TARGETS:
            self.switch2_gr_mapping.set("None")

        self.steam_profile = tk.StringVar(value=q.get("steam_profile", "Default"))
        if self.steam_profile.get() not in STEAM_PROFILE_NAMES:
            self.steam_profile.set("Default")
        self.steam_profile_names = {
            "Custom 1": q.get("steam_profile_name_1", "Custom 1").strip() or "Custom 1",
            "Custom 2": q.get("steam_profile_name_2", "Custom 2").strip() or "Custom 2",
            "Custom 3": q.get("steam_profile_name_3", "Custom 3").strip() or "Custom 3",
        }
        self.steam_profiles = {}
        for profile_name in STEAM_PROFILE_NAMES[1:]:
            section_name = "steam_profile:" + profile_name
            mapping = default_steam_mapping(False)
            if c.has_section(section_name):
                sec = c[section_name]
                for source, _label in STEAM_MAPPING_SOURCES:
                    target = sec.get(source, mapping[source])
                    if target in STEAM_TARGETS:
                        mapping[source] = target
            self.steam_profiles[profile_name] = mapping
        self.steam_profile_display = tk.StringVar(value=self._steam_profile_label(self.steam_profile.get()))

        self.controller_profile_slots={}
        self.controller_profile_names={}
        self.controller_profiles={}
        self.controller_profile_display={}

        for controller_id,spec in CONTROLLER_MAPPING_SPECS.items():
            selected=q.get(
                f"{controller_id}_profile","Default"
            )
            if selected not in CONTROLLER_PROFILE_SLOTS:
                selected="Default"

            self.controller_profile_slots[controller_id]=tk.StringVar(
                value=selected
            )
            self.controller_profile_names[controller_id]={
                slot:(
                    q.get(
                        f"{controller_id}_profile_name_{index}",
                        slot,
                    ).strip() or slot
                )
                for index,slot in enumerate(
                    CONTROLLER_PROFILE_SLOTS[1:],1
                )
            }

            profiles={}
            for slot in CONTROLLER_PROFILE_SLOTS[1:]:
                mapping=default_controller_mapping(
                    controller_id,False,
                    self._switch2_rear_mapping()
                    if controller_id=="switch2pro" else None,
                )
                section=f"controller_profile:{controller_id}:{slot}"
                if c.has_section(section):
                    sec=c[section]
                    for source,_label in spec["sources"]:
                        target=sec.get(source,mapping.get(source,"None"))
                        if target in STEAM_TARGETS:
                            mapping[source]=target
                profiles[slot]=mapping
            self.controller_profiles[controller_id]=profiles

            display=(
                "Default" if selected=="Default" else
                self.controller_profile_names[controller_id].get(
                    selected,selected
                )
            )
            self.controller_profile_display[controller_id]=tk.StringVar(
                value=display
            )

        self.auto_start = tk.BooleanVar(value=q.get("auto_start", "0") == "1")
        self.minimized = tk.BooleanVar(value=q.get("start_minimized", "0") == "1")
        self.windows_startup = tk.BooleanVar(value=windows_startup_enabled())
        try:self.controller_slots=list(json.loads(q.get("controller_slots","[]")))
        except Exception:self.controller_slots=[]
        try:self.controller_blacklist=set(json.loads(q.get("controller_blacklist","[]")))
        except Exception:self.controller_blacklist=set()
        self.controller_slots=[str(x or "") for x in self.controller_slots][:16]
        while len(self.controller_slots)<4:self.controller_slots.append("")
        self.controller_catalog={}

    def save(self):
        c = configparser.ConfigParser()
        c["client"] = {
            "host": self.host.get(), "port": str(self.port.get()), "rate": str(self.rate.get()),
            "controller": str(self.index.get()), "player2_enabled": "1" if self.player2_enabled.get() else "0",
            "controller2": str(self.index2.get()), "input_backend2": self.backend2.get(),
            # Legacy keys remain only for downgrade compatibility.
            "deadzone": str(self.controller_deadzones["xinput"].get()),
            "layout": "position",
            **{
                f"deadzone_{deadzone_id}":str(variable.get())
                for deadzone_id,variable in self.controller_deadzones.items()
            },
            "input_backend": self.backend.get(),
            "switch2_gl_mapping": self.switch2_gl_mapping.get(),
            "switch2_gr_mapping": self.switch2_gr_mapping.get(),
            "steam_profile": self.steam_profile.get(),
            "steam_gyro_trim": "1" if self.steam_gyro_trim.get() else "0",
            "steam_profile_name_1": self.steam_profile_names.get("Custom 1", "Custom 1"),
            "steam_profile_name_2": self.steam_profile_names.get("Custom 2", "Custom 2"),
            "steam_profile_name_3": self.steam_profile_names.get("Custom 3", "Custom 3"),
            **{
                f"{controller_id}_profile":
                    self.controller_profile_slots[controller_id].get()
                for controller_id in CONTROLLER_MAPPING_SPECS
            },
            **{
                f"{controller_id}_profile_name_{index}":
                    self.controller_profile_names[controller_id].get(slot,slot)
                for controller_id in CONTROLLER_MAPPING_SPECS
                for index,slot in enumerate(CONTROLLER_PROFILE_SLOTS[1:],1)
            },
            "auto_start": "1" if self.auto_start.get() else "0",
            "start_minimized": "1" if self.minimized.get() else "0",
            "windows_startup": "1" if self.windows_startup.get() else "0",
            # Kept for backward compatibility with old INI files. Tray-first is
            # mandatory from v1.5 and close/minimize always hides the window.
            "close_to_background": "1",
            "controller_slots": json.dumps(self.controller_slots, separators=(",", ":")),
            "controller_blacklist": json.dumps(sorted(self.controller_blacklist), separators=(",", ":")),
            "keyboard_enabled": "1" if self.keyboard_enabled.get() else "0",
            "keyboard_exclusive": "1" if self.keyboard_exclusive.get() else "0",
            "keyboard_release_key": normalized_release_key(self.keyboard_release_key.get()),
            "mouse_sensitivity": str(int(self.mouse_sensitivity.get())),
            "keyboard_profile": self.keyboard_profile.get(),
            "keyboard_profile_name_1": self.keyboard_profile_names.get("Custom 1","Custom 1"),
            "keyboard_profile_name_2": self.keyboard_profile_names.get("Custom 2","Custom 2"),
            "keyboard_profile_name_3": self.keyboard_profile_names.get("Custom 3","Custom 3"),
            # Legacy single-map key mirrors the active mapping for downgrade
            # compatibility with pre-profile releases.
            "keyboard_mapping": json.dumps(
                self._active_keyboard_mapping(),
                separators=(",",":"),
            ),
        }
        for profile_name, mapping in self.steam_profiles.items():
            section_name = "steam_profile:" + profile_name
            c[section_name] = {source: mapping.get(source, "None") for source, _label in STEAM_MAPPING_SOURCES}

        for controller_id,spec in CONTROLLER_MAPPING_SPECS.items():
            for slot,mapping in self.controller_profiles.get(
                controller_id,{}
            ).items():
                section=f"controller_profile:{controller_id}:{slot}"
                c[section]={
                    source:mapping.get(source,"None")
                    for source,_label in spec["sources"]
                }

        for slot,mapping in self.keyboard_profiles.items():
            section=f"keyboard_profile:{slot}"
            c[section]={
                action:mapping.get(action,DEFAULT_KEYBOARD_MAPPING[action])
                for action,_label in KEYBOARD_ACTIONS
            }

        with open(cfg_path(), "w", encoding="utf-8") as f:
            c.write(f)

    def ui(self):
        root=ttk.Frame(self,padding=(10,10,10,8))
        root.pack(fill="both",expand=True)

        style=ttk.Style(self)
        try:
            style.configure("SwitchNet.TNotebook.Tab",padding=(14,7))
        except Exception:
            pass

        notebook=ttk.Notebook(root,style="SwitchNet.TNotebook")
        notebook.pack(fill="both",expand=True)

        controllers_tab=ttk.Frame(notebook,padding=12)
        mappings_tab=ttk.Frame(notebook,padding=0)
        network_tab=ttk.Frame(notebook,padding=12)
        extra_tab=ttk.Frame(notebook,padding=12)
        diagnostics_tab=ttk.Frame(notebook,padding=12)

        notebook.add(controllers_tab,text="Controllers")
        notebook.add(mappings_tab,text="Mappings")
        notebook.add(network_tab,text="Network")
        notebook.add(extra_tab,text="Extra")
        notebook.add(diagnostics_tab,text="Diagnostics")

        # ---------------- Controllers ----------------
        controller_box=ttk.LabelFrame(
            controllers_tab,text="Controller priority",padding=12
        )
        controller_box.pack(fill="both",expand=True)

        ttk.Label(
            controller_box,
            text=(
                "Slots 1 and 2 are active P1/P2. Reorder controllers by drag "
                "and drop or with the Up / Down buttons. Slots 3 and 4 are inactive."
            ),
            wraplength=780,
        ).pack(anchor="w",pady=(0,8))

        list_frame=ttk.Frame(controller_box)
        list_frame.pack(fill="both",expand=True)

        self.controller_list=tk.Listbox(
            list_frame,
            height=10,
            exportselection=False,
            activestyle="dotbox",
            font=("Segoe UI",10),
        )
        controller_scroll=ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.controller_list.yview,
        )
        self.controller_list.configure(
            yscrollcommand=controller_scroll.set
        )
        self.controller_list.pack(
            side="left",fill="both",expand=True
        )
        controller_scroll.pack(side="right",fill="y")

        self.controller_list.bind(
            "<ButtonPress-1>",self._roster_drag_start
        )
        self.controller_list.bind(
            "<B1-Motion>",self._roster_drag_motion
        )
        self.controller_list.bind(
            "<ButtonRelease-1>",self._roster_drag_end
        )

        controller_actions=ttk.Frame(controller_box)
        controller_actions.pack(fill="x",pady=(8,0))

        ttk.Button(
            controller_actions,
            text="↑ Up",
            command=lambda:self.move_controller(-1),
        ).pack(side="left")
        ttk.Button(
            controller_actions,
            text="↓ Down",
            command=lambda:self.move_controller(1),
        ).pack(side="left",padx=(5,0))
        ttk.Button(
            controller_actions,
            text="Manage blacklist…",
            command=self.open_blacklist_dialog,
        ).pack(side="left",padx=(12,0))
        ttk.Button(
            controller_actions,
            text="Refresh",
            command=lambda:self.refresh_controller_roster(force=True),
        ).pack(side="right")

        # ---------------- Mappings ----------------
        mappings_host=ttk.Frame(mappings_tab)
        mappings_host.pack(fill="both",expand=True)

        mappings_canvas=tk.Canvas(
            mappings_host,highlightthickness=0,borderwidth=0
        )
        mappings_scroll=ttk.Scrollbar(
            mappings_host,
            orient="vertical",
            command=mappings_canvas.yview,
        )
        mappings_body=ttk.Frame(
            mappings_canvas,padding=(12,12,8,12)
        )
        mappings_window=mappings_canvas.create_window(
            (0,0),window=mappings_body,anchor="nw"
        )
        mappings_canvas.configure(
            yscrollcommand=mappings_scroll.set
        )

        def _mapping_scrollregion(_event=None):
            mappings_canvas.configure(
                scrollregion=mappings_canvas.bbox("all")
            )

        def _mapping_width(event):
            mappings_canvas.itemconfigure(
                mappings_window,width=event.width
            )

        def _mapping_mousewheel(event):
            if event.delta:
                mappings_canvas.yview_scroll(
                    int(-event.delta/120),"units"
                )

        mappings_body.bind(
            "<Configure>",_mapping_scrollregion
        )
        mappings_canvas.bind(
            "<Configure>",_mapping_width
        )
        mappings_canvas.bind(
            "<Enter>",
            lambda _e:mappings_canvas.bind_all(
                "<MouseWheel>",_mapping_mousewheel
            ),
        )
        mappings_canvas.bind(
            "<Leave>",
            lambda _e:mappings_canvas.unbind_all("<MouseWheel>"),
        )

        mappings_canvas.pack(
            side="left",fill="both",expand=True
        )
        mappings_scroll.pack(side="right",fill="y")

        steam_box=ttk.LabelFrame(
            mappings_body,text="Steam Controller 2026",padding=10
        )
        steam_box.pack(fill="x",pady=(0,8))
        ttk.Label(
            steam_box,text="Mapping profile"
        ).grid(row=0,column=0,sticky="w",padx=(0,10))
        self.steam_profile_combo=ttk.Combobox(
            steam_box,
            textvariable=self.steam_profile_display,
            values=self._steam_profile_display_values(),
            state="readonly",
            width=24,
        )
        self.steam_profile_combo.grid(
            row=0,column=1,sticky="w"
        )
        self.steam_profile_combo.bind(
            "<<ComboboxSelected>>",
            self._on_steam_profile_selected,
        )
        ttk.Button(
            steam_box,
            text="Edit profiles…",
            command=self.open_steam_mapping_editor,
        ).grid(row=0,column=2,sticky="w",padx=(10,0))
        ttk.Checkbutton(
            steam_box,
            text=(
                "Gyro trim (80% roll / 90% pitch-yaw)"
            ),
            variable=self.steam_gyro_trim,
        ).grid(
            row=1,column=0,columnspan=3,
            sticky="w",pady=(6,0)
        )
        steam_box.columnconfigure(1,weight=1)

        for controller_id in (
            "dualsense","stadia","switchpro","switch2pro","xinput"
        ):
            self._build_mapping_profile_box(
                mappings_body,controller_id
            )

        keyboard_box=ttk.LabelFrame(
            mappings_body,
            text="Keyboard + Mouse Controller (experimental)",
            padding=10,
        )
        keyboard_box.pack(fill="x")
        ttk.Checkbutton(
            keyboard_box,
            text="Show Keyboard + Mouse in controller roster",
            variable=self.keyboard_enabled,
            command=self._keyboard_controller_option_changed,
        ).grid(
            row=0,column=0,columnspan=3,sticky="w"
        )
        ttk.Checkbutton(
            keyboard_box,
            text="Exclusive capture while active",
            variable=self.keyboard_exclusive,
        ).grid(
            row=1,column=0,columnspan=3,sticky="w",pady=(3,0)
        )
        ttk.Label(
            keyboard_box,text="Emergency release"
        ).grid(row=2,column=0,sticky="w",pady=4)
        release_combo=ttk.Combobox(
            keyboard_box,
            textvariable=self.keyboard_release_key,
            values=RELEASE_KEY_CHOICES,
            state="readonly",
            width=10,
        )
        release_combo.grid(row=2,column=1,sticky="w",pady=4)
        release_combo.bind(
            "<<ComboboxSelected>>",
            self._keyboard_release_key_changed,
        )
        ttk.Label(
            keyboard_box,text="Mouse sensitivity"
        ).grid(row=3,column=0,sticky="w",pady=4)
        ttk.Spinbox(
            keyboard_box,
            from_=100,to=20000,
            textvariable=self.mouse_sensitivity,
            width=10,
        ).grid(row=3,column=1,sticky="w",pady=4)

        ttk.Label(
            keyboard_box,text="Mapping profile"
        ).grid(row=4,column=0,sticky="w",pady=4)
        self.keyboard_profile_combo=ttk.Combobox(
            keyboard_box,
            textvariable=self.keyboard_profile_display,
            values=self._keyboard_profile_display_values(),
            state="readonly",
            width=24,
        )
        self.keyboard_profile_combo.grid(
            row=4,column=1,sticky="w",pady=4
        )
        self.keyboard_profile_combo.bind(
            "<<ComboboxSelected>>",
            self._on_keyboard_profile_selected,
        )
        ttk.Button(
            keyboard_box,
            text="Edit profiles…",
            command=self.open_keyboard_mapping_editor,
        ).grid(row=4,column=2,sticky="w",padx=(10,0))

        deadzone_box=ttk.LabelFrame(
            mappings_body,text="Stick deadzones",padding=10
        )
        deadzone_box.pack(fill="x",pady=(0,8))

        ttk.Label(
            deadzone_box,
            text=(
                "Independent deadzone for each controller family. "
                "Use the slider or enter the exact value."
            ),
            foreground="#606060",
            wraplength=760,
        ).grid(
            row=0,column=0,columnspan=3,
            sticky="w",pady=(0,6)
        )

        for row,deadzone_id in enumerate(
            (
                "steam","dualsense","stadia",
                "switchpro","switch2pro","xinput",
            ),
            start=1,
        ):
            self._build_deadzone_row(
                deadzone_box,deadzone_id,row
            )

        deadzone_box.columnconfigure(1,weight=1)

        # ---------------- Network ----------------
        network_box=ttk.LabelFrame(
            network_tab,text="SwitchNet connection",padding=12
        )
        network_box.pack(fill="x")

        ttk.Label(
            network_box,text="SwitchNet IP / hostname"
        ).grid(row=0,column=0,sticky="w",padx=(0,12),pady=5)
        ttk.Entry(
            network_box,textvariable=self.host
        ).grid(row=0,column=1,sticky="ew",pady=5)

        ttk.Label(
            network_box,text="UDP port"
        ).grid(row=1,column=0,sticky="w",padx=(0,12),pady=5)
        ttk.Spinbox(
            network_box,
            from_=1,to=65535,
            textvariable=self.port,
            width=12,
        ).grid(row=1,column=1,sticky="w",pady=5)

        ttk.Label(
            network_box,text="UDP rate"
        ).grid(row=2,column=0,sticky="w",padx=(0,12),pady=5)
        ttk.Spinbox(
            network_box,
            from_=60,to=500,
            textvariable=self.rate,
            width=12,
        ).grid(row=2,column=1,sticky="w",pady=5)

        self.discover_button=ttk.Button(
            network_box,
            text="Discover SwitchNet",
            command=self.discover_device,
        )
        self.discover_button.grid(
            row=3,column=1,sticky="w",pady=(10,2)
        )
        network_box.columnconfigure(1,weight=1)

        ttk.Label(
            network_tab,
            text=(
                "Discovery searches the local network automatically. "
                "You can also use switchnet.local when mDNS is available."
            ),
            foreground="#606060",
            wraplength=760,
        ).pack(anchor="w",pady=(8,0))

        # ---------------- Extra ----------------
        startup_box=ttk.LabelFrame(
            extra_tab,text="Startup",padding=12
        )
        startup_box.pack(fill="x")
        ttk.Checkbutton(
            startup_box,
            text="Start service automatically",
            variable=self.auto_start,
        ).pack(anchor="w",pady=2)
        ttk.Checkbutton(
            startup_box,
            text="Start in tray",
            variable=self.minimized,
        ).pack(anchor="w",pady=2)
        ttk.Checkbutton(
            startup_box,
            text="Start SwitchNet with Windows",
            variable=self.windows_startup,
            command=self.toggle_windows_startup,
        ).pack(anchor="w",pady=2)

        # ---------------- Diagnostics ----------------
        summary=ttk.Frame(diagnostics_tab)
        summary.pack(fill="x")
        self.stats=ttk.Label(summary,text="TX 0/s")
        self.stats.pack(anchor="w")
        self.conn=ttk.Label(
            summary,text="Controller: not connected"
        )
        self.conn.pack(anchor="w",pady=(2,0))
        self.source=ttk.Label(
            summary,text="Input: -"
        )
        self.source.pack(anchor="w",pady=(2,8))

        text_frame=ttk.Frame(diagnostics_tab)
        text_frame.pack(fill="both",expand=True)
        self.text=tk.Text(
            text_frame,
            state="disabled",
            font=("Consolas",9),
            wrap="none",
        )
        diag_y=ttk.Scrollbar(
            text_frame,
            orient="vertical",
            command=self.text.yview,
        )
        diag_x=ttk.Scrollbar(
            diagnostics_tab,
            orient="horizontal",
            command=self.text.xview,
        )
        self.text.configure(
            yscrollcommand=diag_y.set,
            xscrollcommand=diag_x.set,
        )
        self.text.pack(
            side="left",fill="both",expand=True
        )
        diag_y.pack(side="right",fill="y")
        diag_x.pack(fill="x")

        # ---------------- Fixed status bar ----------------
        separator=ttk.Separator(root,orient="horizontal")
        separator.pack(fill="x",pady=(8,7))

        status_bar=ttk.Frame(root)
        status_bar.pack(fill="x")

        self.service_indicator=tk.Canvas(
            status_bar,
            width=16,height=16,
            highlightthickness=0,
            borderwidth=0,
        )
        self.service_indicator.pack(
            side="left",padx=(0,5)
        )
        self.service_indicator_dot=self.service_indicator.create_oval(
            3,3,13,13,
            fill="#c62828",
            outline="",
        )

        self.status=ttk.Label(
            status_bar,text="Service stopped"
        )
        self.status.pack(side="left",fill="x",expand=True)

        self.service_toggle_button=ttk.Button(
            status_bar,
            text="Start",
            command=self.toggle_service,
            width=9,
        )
        self.service_toggle_button.pack(
            side="left",padx=(8,5)
        )

        self.wake_button=ttk.Button(
            status_bar,
            text="Wake Switch 2",
            command=self.wake_switch2,
        )
        self.wake_button.pack(side="left",padx=(0,5))

        ttk.Button(
            status_bar,
            text="Hide to tray",
            command=self.hide_to_tray,
        ).pack(side="left",padx=(0,5))

        ttk.Button(
            status_bar,
            text="Close",
            command=self.exit_from_tray,
        ).pack(side="left")

        self._update_service_controls()

    def discover_device(self):
        if hasattr(self, "discover_button"):
            self.discover_button.configure(state="disabled")
        self.status.config(text="Discovering SwitchNet...")
        threading.Thread(
            target=self._discover_device_thread,
            name="SwitchNet-Discovery",
            daemon=True,
        ).start()

    def _discover_device_thread(self):
        result = discover_switchnet()
        self.after(0, self._finish_discovery, result)

    def _finish_discovery(self, result):
        if hasattr(self, "discover_button"):
            self.discover_button.configure(state="normal")
        if result:
            self.host.set(result["ip"])
            self.status.config(
                text=f'Discovered SwitchNet {result["version"] or ""} at {result["ip"]}'
            )
            try:
                self.save_config()
            except Exception:
                pass
        else:
            self.status.config(
                text="SwitchNet discovery failed; enter the IP or use switchnet.local"
            )

    def _auto_discover_if_needed(self):
        self.discover_device()

    def _switch2_rear_mapping(self):
        return {
            "GL":self.switch2_gl_mapping.get(),
            "GR":self.switch2_gr_mapping.get(),
        }

    def _switch2_rear_mapping_changed(self,_event=None):
        self.save()
        if self.api_service_running():
            active=self.active_controller_descriptors()
            if any(
                d and d.get("backend")=="switch2pro_hid"
                for d in active
            ):
                self.schedule_service_restart(
                    "Switch 2 Pro rear-button mapping changed"
                )

    def wake_switch2(self):
        host = self.host.get().strip()
        if not host:
            self.status.config(text="Wake error: SwitchNet host is empty")
            return
        if hasattr(self, "wake_button"):
            self.wake_button.configure(state="disabled")
        self.status.config(text="Sending Switch 2 wake beacon...")
        threading.Thread(
            target=self._wake_request_thread,
            args=(host,),
            name="SwitchNet-Wake",
            daemon=True,
        ).start()

    def _wake_request_thread(self, host):
        try:
            base = host.rstrip("/")
            if not base.startswith(("http://", "https://")):
                base = "http://" + base
            req = urllib.request.Request(
                base + "/api/wake",
                data=b"",
                method="POST",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=4.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not payload.get("ok"):
                raise RuntimeError(payload.get("error", "wake request rejected"))
            self.after(0, self._finish_wake_request, True, "Switch 2 wake beacon started")
        except Exception as exc:
            self.after(0, self._finish_wake_request, False, f"Wake error: {exc}")

    def _finish_wake_request(self, ok, message):
        if hasattr(self, "wake_button"):
            self.wake_button.configure(state="normal")
        self.status.config(text=message)

    def _deadzone_for_backend(self,backend):
        key=controller_deadzone_key_for_backend(backend)
        variable=self.controller_deadzones.get(key)
        if variable is None:
            return 6000
        try:
            return max(0,min(16000,int(variable.get())))
        except Exception:
            return 6000

    def _normalize_deadzone_var(self,deadzone_id):
        variable=self.controller_deadzones[deadzone_id]
        try:
            value=int(variable.get())
        except Exception:
            value=6000
        variable.set(max(0,min(16000,value)))

    def _commit_deadzone(self,deadzone_id,_event=None):
        self._normalize_deadzone_var(deadzone_id)
        self.save()
        if self.api_service_running():
            self.schedule_service_restart(
                f"{CONTROLLER_DEADZONE_SPECS[deadzone_id]['title']} deadzone changed"
            )

    def _build_deadzone_row(self,parent,deadzone_id,row):
        spec=CONTROLLER_DEADZONE_SPECS[deadzone_id]
        variable=self.controller_deadzones[deadzone_id]

        ttk.Label(parent,text=spec["title"]).grid(
            row=row,column=0,sticky="w",padx=(0,12),pady=4
        )

        slider=ttk.Scale(
            parent,from_=0,to=16000,variable=variable,orient="horizontal"
        )
        slider.grid(row=row,column=1,sticky="ew",pady=4)
        slider.bind(
            "<ButtonRelease-1>",
            lambda event,key=deadzone_id:self._commit_deadzone(key,event),
        )

        value=ttk.Spinbox(
            parent,from_=0,to=16000,increment=100,
            textvariable=variable,width=7,
            command=lambda key=deadzone_id:self._commit_deadzone(key),
        )
        value.grid(row=row,column=2,sticky="e",padx=(10,0),pady=4)
        value.bind(
            "<Return>",
            lambda event,key=deadzone_id:self._commit_deadzone(key,event),
        )
        value.bind(
            "<FocusOut>",
            lambda event,key=deadzone_id:self._commit_deadzone(key,event),
        )

    def _controller_profile_label(self,controller_id,slot):
        if slot=="Default":
            return "Default"
        return self.controller_profile_names.get(
            controller_id,{}
        ).get(slot,slot)

    def _controller_profile_display_values(self,controller_id):
        return tuple(
            self._controller_profile_label(controller_id,slot)
            for slot in CONTROLLER_PROFILE_SLOTS
        )

    def _controller_profile_slot_from_label(self,controller_id,label):
        if label=="Default":
            return "Default"
        for slot in CONTROLLER_PROFILE_SLOTS[1:]:
            if self._controller_profile_label(
                controller_id,slot
            )==label:
                return slot
        return "Default"

    def _controller_mapping_for_backend(self,backend):
        controller_id=None
        for candidate,spec in CONTROLLER_MAPPING_SPECS.items():
            if backend in spec["backends"]:
                controller_id=candidate
                break
        if controller_id is None:
            return None

        slot=self.controller_profile_slots[controller_id].get()
        if slot=="Default":
            return None
        return dict(
            self.controller_profiles.get(
                controller_id,{}
            ).get(
                slot,
                default_controller_mapping(
                    controller_id,
                    False,
                    self._switch2_rear_mapping()
                    if controller_id=="switch2pro" else None,
                ),
            )
        )

    def _refresh_controller_profile_combo(self,controller_id):
        combo=getattr(
            self,
            f"{controller_id}_profile_combo",
            None,
        )
        if combo is not None:
            combo.configure(
                values=self._controller_profile_display_values(
                    controller_id
                )
            )
        slot=self.controller_profile_slots[controller_id].get()
        self.controller_profile_display[controller_id].set(
            self._controller_profile_label(controller_id,slot)
        )

    def _controller_profile_selected(self,controller_id,_event=None):
        label=self.controller_profile_display[controller_id].get()
        slot=self._controller_profile_slot_from_label(
            controller_id,label
        )
        if slot==self.controller_profile_slots[controller_id].get():
            return
        self.controller_profile_slots[controller_id].set(slot)
        self.save()
        if self.api_service_running():
            self.schedule_service_restart(
                f"{CONTROLLER_MAPPING_SPECS[controller_id]['title']} profile changed"
            )

    def _build_mapping_profile_box(self,parent,controller_id):
        spec=CONTROLLER_MAPPING_SPECS[controller_id]
        box=ttk.LabelFrame(
            parent,text=spec["title"],padding=10
        )
        box.pack(fill="x",pady=(0,8))

        ttk.Label(
            box,text="Mapping profile"
        ).grid(row=0,column=0,sticky="w",padx=(0,10))

        combo=ttk.Combobox(
            box,
            textvariable=self.controller_profile_display[controller_id],
            values=self._controller_profile_display_values(controller_id),
            state="readonly",
            width=24,
        )
        combo.grid(row=0,column=1,sticky="w")
        combo.bind(
            "<<ComboboxSelected>>",
            lambda event,cid=controller_id:
                self._controller_profile_selected(cid,event),
        )
        setattr(
            self,
            f"{controller_id}_profile_combo",
            combo,
        )

        ttk.Button(
            box,
            text="Edit profiles…",
            command=lambda cid=controller_id:
                self.open_controller_mapping_editor(cid),
        ).grid(row=0,column=2,sticky="w",padx=(10,0))
        box.columnconfigure(1,weight=1)
        return box

    def open_controller_mapping_editor(self,controller_id):
        spec=CONTROLLER_MAPPING_SPECS[controller_id]
        win=tk.Toplevel(self)
        win.title(f"SwitchNet - {spec['title']} Profiles")
        win.transient(self)
        win.geometry("600x740")
        win.minsize(540,600)

        top=ttk.Frame(win,padding=12)
        top.pack(fill="both",expand=True)

        ttk.Label(
            top,
            text=f"{spec['title']} Profiles",
            font=("Segoe UI",15,"bold"),
        ).pack(anchor="w")
        ttk.Label(
            top,
            text=(
                "Custom profiles remap every physical button to a Switch "
                "command. The Default profile always preserves SwitchNet's "
                "standard behavior."
            ),
            wraplength=550,
        ).pack(anchor="w",pady=(2,10))

        current=self.controller_profile_slots[controller_id].get()
        if current=="Default":
            current="Custom 1"

        profile_var=tk.StringVar(
            value=self._controller_profile_label(
                controller_id,current
            )
        )

        selector=ttk.Frame(top)
        selector.pack(fill="x",pady=(0,6))
        ttk.Label(
            selector,text="Preset to edit"
        ).pack(side="left")
        profile_combo=ttk.Combobox(
            selector,
            textvariable=profile_var,
            values=tuple(
                self._controller_profile_label(controller_id,slot)
                for slot in CONTROLLER_PROFILE_SLOTS[1:]
            ),
            state="readonly",
            width=24,
        )
        profile_combo.pack(side="left",padx=8)

        name_row=ttk.Frame(top)
        name_row.pack(fill="x",pady=(0,8))
        ttk.Label(
            name_row,text="Preset name",width=18
        ).pack(side="left")
        name_var=tk.StringVar()
        ttk.Entry(
            name_row,textvariable=name_var,width=30
        ).pack(side="left",fill="x",expand=True)

        canvas=tk.Canvas(top,highlightthickness=0)
        scroll=ttk.Scrollbar(
            top,orient="vertical",command=canvas.yview
        )
        body=ttk.Frame(canvas)
        body.bind(
            "<Configure>",
            lambda _e:canvas.configure(
                scrollregion=canvas.bbox("all")
            ),
        )
        canvas.create_window(
            (0,0),window=body,anchor="nw"
        )
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left",fill="both",expand=True)
        scroll.pack(side="right",fill="y")

        variables={
            source:tk.StringVar()
            for source,_label in spec["sources"]
        }

        def current_slot():
            return self._controller_profile_slot_from_label(
                controller_id,profile_var.get()
            )

        def load_profile(*_args):
            slot=current_slot()
            if slot=="Default":
                slot="Custom 1"
            mapping=self.controller_profiles[
                controller_id
            ].get(
                slot,
                default_controller_mapping(
                    controller_id,False,
                    self._switch2_rear_mapping()
                    if controller_id=="switch2pro" else None,
                ),
            )
            name_var.set(
                self._controller_profile_label(
                    controller_id,slot
                )
            )
            for source,_label in spec["sources"]:
                variables[source].set(
                    mapping.get(source,"None")
                )

        for row,(source,label) in enumerate(spec["sources"]):
            ttk.Label(
                body,text=label,width=20
            ).grid(
                row=row,column=0,sticky="w",
                padx=(2,10),pady=3
            )
            ttk.Combobox(
                body,
                textvariable=variables[source],
                values=STEAM_TARGETS,
                state="readonly",
                width=22,
            ).grid(
                row=row,column=1,sticky="ew",pady=3
            )
        body.columnconfigure(1,weight=1)

        footer=ttk.Frame(
            win,padding=(12,4,12,12)
        )
        footer.pack(fill="x")

        def reset_profile():
            mapping=default_controller_mapping(
                controller_id,
                False,
                self._switch2_rear_mapping()
                if controller_id=="switch2pro" else None,
            )
            for source,_label in spec["sources"]:
                variables[source].set(
                    mapping.get(source,"None")
                )

        def save_profile():
            slot=current_slot()
            if slot=="Default":
                slot="Custom 1"

            new_name=name_var.get().strip()
            if not new_name:
                messagebox.showerror(
                    "SwitchNet",
                    "The preset name cannot be empty.",
                    parent=win,
                )
                return
            if len(new_name)>32:
                messagebox.showerror(
                    "SwitchNet",
                    "The preset name can contain at most 32 characters.",
                    parent=win,
                )
                return
            if new_name.casefold()=="default":
                messagebox.showerror(
                    "SwitchNet",
                    "'Default' is a reserved name.",
                    parent=win,
                )
                return

            for other in CONTROLLER_PROFILE_SLOTS[1:]:
                if (
                    other!=slot and
                    self._controller_profile_label(
                        controller_id,other
                    ).casefold()==new_name.casefold()
                ):
                    messagebox.showerror(
                        "SwitchNet",
                        "A preset with this name already exists.",
                        parent=win,
                    )
                    return

            self.controller_profile_names[
                controller_id
            ][slot]=new_name
            self.controller_profiles[
                controller_id
            ][slot]={
                source:(
                    variables[source].get()
                    if variables[source].get() in STEAM_TARGETS
                    else "None"
                )
                for source,_label in spec["sources"]
            }
            self.controller_profile_slots[
                controller_id
            ].set(slot)
            self._refresh_controller_profile_combo(
                controller_id
            )
            profile_combo.configure(
                values=tuple(
                    self._controller_profile_label(
                        controller_id,item
                    )
                    for item in CONTROLLER_PROFILE_SLOTS[1:]
                )
            )
            profile_var.set(new_name)
            self.save()

            if self.api_service_running():
                self.schedule_service_restart(
                    f"{spec['title']} profile saved"
                )

        ttk.Button(
            footer,text="Restore default",
            command=reset_profile,
        ).pack(side="left")
        ttk.Button(
            footer,text="Save and use preset",
            command=save_profile,
        ).pack(side="right")
        ttk.Button(
            footer,text="Close",
            command=win.destroy,
        ).pack(side="right",padx=8)

        profile_var.trace_add("write",load_profile)
        load_profile()
        win.grab_set()

    def _steam_profile_label(self, slot):
        if slot == "Default":
            return "Default"
        return self.steam_profile_names.get(slot, slot)

    def _steam_profile_display_values(self):
        return tuple(self._steam_profile_label(slot) for slot in STEAM_PROFILE_NAMES)

    def _steam_profile_slot_from_label(self, label):
        if label == "Default":
            return "Default"
        for slot in STEAM_PROFILE_NAMES[1:]:
            if self._steam_profile_label(slot) == label:
                return slot
        return "Default"

    def _refresh_steam_profile_combo(self):
        if hasattr(self, "steam_profile_combo"):
            self.steam_profile_combo.configure(values=self._steam_profile_display_values())
        self.steam_profile_display.set(self._steam_profile_label(self.steam_profile.get()))

    def _on_steam_profile_selected(self, _event=None):
        slot = self._steam_profile_slot_from_label(self.steam_profile_display.get())
        if slot == self.steam_profile.get():
            return
        was_running = bool(self.worker.get().get("running"))
        self.steam_profile.set(slot)
        self.save()
        if was_running:
            self.status.config(text="Preset changed: restarting service...")
            self.after(10, self._restart_service_after_profile_change)

    def _restart_service_after_profile_change(self):
        try:
            self._stop_service()
            self._start_service()
        except Exception as exc:
            log_exception("restart after Steam profile change", exc)
            messagebox.showerror("SwitchNet", f"Unable to restart the service after changing preset:\n{exc}")

    def open_steam_mapping_editor(self):
        win = tk.Toplevel(self)
        win.title("SwitchNet - Steam Controller Profiles")
        win.transient(self)
        win.geometry("600x780")
        win.minsize(560, 660)

        top = ttk.Frame(win, padding=12)
        top.pack(fill="both", expand=True)
        ttk.Label(top, text="Steam Controller Profiles", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(
            top,
            text="The three Custom presets can have a custom name. Every physical source, including the L5+R5 combo, can be assigned to a Switch command.",
            wraplength=550,
        ).pack(anchor="w", pady=(2, 10))

        selected_slot = self.steam_profile.get() if self.steam_profile.get() != "Default" else "Custom 1"
        profile_var = tk.StringVar(value=self._steam_profile_label(selected_slot))
        selector = ttk.Frame(top)
        selector.pack(fill="x", pady=(0, 6))
        ttk.Label(selector, text="Preset to edit").pack(side="left")
        profile_combo = ttk.Combobox(
            selector, textvariable=profile_var,
            values=tuple(self._steam_profile_label(slot) for slot in STEAM_PROFILE_NAMES[1:]),
            state="readonly", width=24
        )
        profile_combo.pack(side="left", padx=8)

        name_row = ttk.Frame(top)
        name_row.pack(fill="x", pady=(0, 8))
        ttk.Label(name_row, text="Preset name", width=18).pack(side="left")
        name_var = tk.StringVar()
        ttk.Entry(name_row, textvariable=name_var, width=30).pack(side="left", fill="x", expand=True)

        canvas = tk.Canvas(top, highlightthickness=0)
        scroll = ttk.Scrollbar(top, orient="vertical", command=canvas.yview)
        body = ttk.Frame(canvas)
        body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        vars_by_source = {source: tk.StringVar() for source, _label in STEAM_MAPPING_SOURCES}

        def current_slot():
            return self._steam_profile_slot_from_label(profile_var.get())

        def load_profile(*_args):
            slot = current_slot()
            if slot == "Default":
                slot = "Custom 1"
            mapping = self.steam_profiles.get(slot, default_steam_mapping(False))
            name_var.set(self._steam_profile_label(slot))
            for source, _label in STEAM_MAPPING_SOURCES:
                vars_by_source[source].set(mapping.get(source, "None"))

        for row, (source, label) in enumerate(STEAM_MAPPING_SOURCES):
            ttk.Label(body, text=label, width=20).grid(row=row, column=0, sticky="w", padx=(2, 10), pady=3)
            ttk.Combobox(
                body, textvariable=vars_by_source[source], values=STEAM_TARGETS,
                state="readonly", width=22
            ).grid(row=row, column=1, sticky="ew", pady=3)
        body.columnconfigure(1, weight=1)

        footer = ttk.Frame(win, padding=(12, 4, 12, 12))
        footer.pack(fill="x")

        def reset_profile():
            mapping = default_steam_mapping(False)
            for source, _label in STEAM_MAPPING_SOURCES:
                vars_by_source[source].set(mapping[source])

        def save_profile():
            slot = current_slot()
            if slot == "Default":
                slot = "Custom 1"
            new_name = name_var.get().strip()
            if not new_name:
                messagebox.showerror("SwitchNet", "The preset name cannot be empty.", parent=win)
                return
            if len(new_name) > 32:
                messagebox.showerror("SwitchNet", "The preset name can contain at most 32 characters.", parent=win)
                return
            if new_name.casefold() == "default":
                messagebox.showerror("SwitchNet", "'Default' is a reserved name.", parent=win)
                return
            for other in STEAM_PROFILE_NAMES[1:]:
                if other != slot and self._steam_profile_label(other).casefold() == new_name.casefold():
                    messagebox.showerror("SwitchNet", "A preset with this name already exists.", parent=win)
                    return

            was_running = bool(self.worker.get().get("running"))
            self.steam_profile_names[slot] = new_name
            self.steam_profiles[slot] = {
                source: vars_by_source[source].get() if vars_by_source[source].get() in STEAM_TARGETS else "None"
                for source, _label in STEAM_MAPPING_SOURCES
            }
            self.steam_profile.set(slot)
            self._refresh_steam_profile_combo()
            profile_combo.configure(values=tuple(self._steam_profile_label(x) for x in STEAM_PROFILE_NAMES[1:]))
            profile_var.set(new_name)
            self.save()
            if was_running:
                self.status.config(text="Profile saved: restarting service...")
                self.after(10, self._restart_service_after_profile_change)

        ttk.Button(footer, text="Restore default", command=reset_profile).pack(side="left")
        ttk.Button(footer, text="Save and use preset", command=save_profile).pack(side="right")
        ttk.Button(footer, text="Close", command=win.destroy).pack(side="right", padx=8)

        profile_var.trace_add("write", load_profile)
        load_profile()
        win.grab_set()

    def _keyboard_profile_label(self,slot):
        if slot=="Default":
            return "Default"
        return self.keyboard_profile_names.get(slot,slot)

    def _keyboard_profile_display_values(self):
        return tuple(
            self._keyboard_profile_label(slot)
            for slot in CONTROLLER_PROFILE_SLOTS
        )

    def _keyboard_profile_slot_from_label(self,label):
        if label=="Default":
            return "Default"
        for slot in CONTROLLER_PROFILE_SLOTS[1:]:
            if self._keyboard_profile_label(slot)==label:
                return slot
        return "Default"

    def _active_keyboard_mapping(self):
        slot=self.keyboard_profile.get()
        if slot=="Default":
            mapping=normalized_keyboard_mapping(None)
        else:
            mapping=dict(
                self.keyboard_profiles.get(
                    slot,normalized_keyboard_mapping(None)
                )
            )
        return mapping_without_release_conflict(
            mapping,self.keyboard_release_key.get()
        )

    def _refresh_keyboard_profile_combo(self):
        if hasattr(self,"keyboard_profile_combo"):
            self.keyboard_profile_combo.configure(
                values=self._keyboard_profile_display_values()
            )
        self.keyboard_profile_display.set(
            self._keyboard_profile_label(self.keyboard_profile.get())
        )

    def _on_keyboard_profile_selected(self,_event=None):
        slot=self._keyboard_profile_slot_from_label(
            self.keyboard_profile_display.get()
        )
        if slot==self.keyboard_profile.get():
            return
        self.keyboard_profile.set(slot)
        self.keyboard_mapping=self._active_keyboard_mapping()
        self.save()
        if self.api_service_running():
            for index,descriptor in enumerate(
                self.active_controller_descriptors()
            ):
                if descriptor and descriptor.get("backend")=="keyboard_mouse":
                    self.restart_slot(
                        index,"keyboard mapping profile changed"
                    )

    def _keyboard_controller_option_changed(self):
        self.save()
        self._last_roster_signature=None
        self.refresh_controller_roster(force=True)
        self.schedule_service_restart("Keyboard+Mouse roster changed")

    def _keyboard_release_key_changed(self,_event=None):
        self.keyboard_release_key.set(
            normalized_release_key(self.keyboard_release_key.get())
        )
        for slot,mapping in list(self.keyboard_profiles.items()):
            self.keyboard_profiles[slot]=mapping_without_release_conflict(
                mapping,self.keyboard_release_key.get()
            )
        self.keyboard_mapping=self._active_keyboard_mapping()
        self.save()
        if self.api_service_running():
            for slot,d in enumerate(self.active_controller_descriptors()):
                if d and d.get("backend")=="keyboard_mouse":
                    self.restart_slot(slot,"keyboard release key change")

    def open_keyboard_mapping_editor(self):
        win=tk.Toplevel(self)
        win.title("SwitchNet - Keyboard + Mouse Profiles")
        win.geometry("520x720")
        win.minsize(480,600)
        win.transient(self)

        top=ttk.Frame(win,padding=12)
        top.pack(fill="x")

        ttk.Label(top,text="Profile").grid(
            row=0,column=0,sticky="w",padx=(0,8)
        )
        profile_var=tk.StringVar(
            value=self._keyboard_profile_label(
                self.keyboard_profile.get()
            )
        )
        profile_combo=ttk.Combobox(
            top,
            textvariable=profile_var,
            values=self._keyboard_profile_display_values(),
            state="readonly",
            width=22,
        )
        profile_combo.grid(row=0,column=1,sticky="w")

        ttk.Label(
            top,
            text=(
                "Mouse movement is always the right stick. "
                f"{self.keyboard_release_key.get()} is reserved for "
                "emergency release."
            ),
            wraplength=470,
        ).grid(
            row=1,column=0,columnspan=2,
            sticky="w",pady=(8,0)
        )
        top.columnconfigure(1,weight=1)

        frame=ttk.Frame(win,padding=(12,0,12,0))
        frame.pack(fill="both",expand=True)
        canvas=tk.Canvas(frame,highlightthickness=0)
        bar=ttk.Scrollbar(
            frame,orient="vertical",command=canvas.yview
        )
        body=ttk.Frame(canvas)
        body.bind(
            "<Configure>",
            lambda _e:canvas.configure(
                scrollregion=canvas.bbox("all")
            ),
        )
        canvas.create_window((0,0),window=body,anchor="nw")
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left",fill="both",expand=True)
        bar.pack(side="right",fill="y")

        variables={}
        for row,(action,label) in enumerate(KEYBOARD_ACTIONS):
            ttk.Label(
                body,text=label,width=18
            ).grid(
                row=row,column=0,sticky="w",pady=2
            )
            variable=tk.StringVar()
            variables[action]=variable
            ttk.Combobox(
                body,
                textvariable=variable,
                values=[
                    key for key in KEYBOARD_KEY_CHOICES
                    if key!=self.keyboard_release_key.get()
                ],
                state="readonly",
                width=20,
            ).grid(
                row=row,column=1,sticky="ew",pady=2
            )
        body.columnconfigure(1,weight=1)

        name_frame=ttk.Frame(win,padding=(12,8,12,0))
        name_frame.pack(fill="x")
        ttk.Label(
            name_frame,text="Preset name"
        ).pack(side="left")
        name_var=tk.StringVar()
        name_entry=ttk.Entry(
            name_frame,textvariable=name_var,width=24
        )
        name_entry.pack(side="left",padx=(8,0))

        def current_slot():
            return self._keyboard_profile_slot_from_label(
                profile_var.get()
            )

        def load_profile(_event=None):
            slot=current_slot()
            if slot=="Default":
                mapping=normalized_keyboard_mapping(None)
                name_var.set("Default")
                name_entry.configure(state="disabled")
            else:
                mapping=self.keyboard_profiles.get(
                    slot,normalized_keyboard_mapping(None)
                )
                name_var.set(
                    self.keyboard_profile_names.get(slot,slot)
                )
                name_entry.configure(state="normal")
            mapping=mapping_without_release_conflict(
                mapping,self.keyboard_release_key.get()
            )
            for action,_label in KEYBOARD_ACTIONS:
                variables[action].set(
                    mapping.get(
                        action,DEFAULT_KEYBOARD_MAPPING[action]
                    )
                )

        def reset_profile():
            mapping=normalized_keyboard_mapping(None)
            for action,_label in KEYBOARD_ACTIONS:
                variables[action].set(mapping[action])

        def save_profile():
            slot=current_slot()
            if slot=="Default":
                slot="Custom 1"

            new_name=name_var.get().strip()
            if current_slot()=="Default":
                new_name=self.keyboard_profile_names.get(
                    slot,slot
                )
            if not new_name:
                messagebox.showerror(
                    "SwitchNet",
                    "The preset name cannot be empty.",
                    parent=win,
                )
                return
            if len(new_name)>32:
                messagebox.showerror(
                    "SwitchNet",
                    "The preset name can contain at most 32 characters.",
                    parent=win,
                )
                return
            if new_name.casefold()=="default":
                messagebox.showerror(
                    "SwitchNet",
                    "'Default' is a reserved name.",
                    parent=win,
                )
                return
            for other in CONTROLLER_PROFILE_SLOTS[1:]:
                if (
                    other!=slot
                    and self._keyboard_profile_label(other).casefold()
                    ==new_name.casefold()
                ):
                    messagebox.showerror(
                        "SwitchNet",
                        "Preset names must be unique.",
                        parent=win,
                    )
                    return

            mapping=mapping_without_release_conflict(
                {
                    action:variable.get()
                    for action,variable in variables.items()
                },
                self.keyboard_release_key.get(),
            )
            self.keyboard_profiles[slot]=mapping
            self.keyboard_profile_names[slot]=new_name
            self.keyboard_profile.set(slot)
            self.keyboard_mapping=self._active_keyboard_mapping()
            self._refresh_keyboard_profile_combo()
            self.save()

            if self.api_service_running():
                for index,descriptor in enumerate(
                    self.active_controller_descriptors()
                ):
                    if (
                        descriptor
                        and descriptor.get("backend")=="keyboard_mouse"
                    ):
                        self.restart_slot(
                            index,"keyboard mapping profile saved"
                        )
            win.destroy()

        profile_combo.bind("<<ComboboxSelected>>",load_profile)

        footer=ttk.Frame(win,padding=(12,8,12,12))
        footer.pack(fill="x")
        ttk.Button(
            footer,text="Defaults",command=reset_profile
        ).pack(side="left")
        ttk.Button(
            footer,text="Save and use preset",command=save_profile
        ).pack(side="right")
        ttk.Button(
            footer,text="Close",command=win.destroy
        ).pack(side="right",padx=8)

        load_profile()
        win.grab_set()

    def open_blacklist_dialog(self):
        existing=getattr(self,"_blacklist_window",None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.deiconify()
                    existing.lift()
                    existing.focus_force()
                    return
            except Exception:
                pass

        win=tk.Toplevel(self)
        self._blacklist_window=win
        win.title("SwitchNet - Controller Blacklist")
        win.transient(self)
        win.geometry("480x360")
        win.minsize(420,300)

        frame=ttk.Frame(win,padding=12)
        frame.pack(fill="both",expand=True)

        ttk.Label(
            frame,
            text="Blacklisted controllers",
            font=("Segoe UI",12,"bold"),
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "Blacklisted devices remain ignored until they are restored. "
                "Select a controller in the main Controllers tab before using "
                "Blacklist selected."
            ),
            wraplength=440,
        ).pack(anchor="w",pady=(2,8))

        list_host=ttk.Frame(frame)
        list_host.pack(fill="both",expand=True)

        self.blacklisted_list=tk.Listbox(
            list_host,
            exportselection=False,
        )
        bar=ttk.Scrollbar(
            list_host,
            orient="vertical",
            command=self.blacklisted_list.yview,
        )
        self.blacklisted_list.configure(
            yscrollcommand=bar.set
        )
        self.blacklisted_list.pack(
            side="left",fill="both",expand=True
        )
        bar.pack(side="right",fill="y")

        actions=ttk.Frame(frame)
        actions.pack(fill="x",pady=(8,0))

        ttk.Button(
            actions,
            text="Blacklist selected",
            command=self.blacklist_selected,
        ).pack(side="left")
        ttk.Button(
            actions,
            text="Restore selected",
            command=self.unblacklist_selected,
        ).pack(side="left",padx=(5,0))
        ttk.Button(
            actions,
            text="Close",
            command=win.destroy,
        ).pack(side="right")

        def _closed():
            try:
                win.destroy()
            finally:
                self.blacklisted_list=None
                self._blacklist_window=None

        win.protocol("WM_DELETE_WINDOW",_closed)
        self.refresh_controller_roster(force=True)

    def _roster_drag_start(self,event):
        if not hasattr(self,"controller_list"):
            return
        try:
            row=self.controller_list.nearest(event.y)
        except Exception:
            row=-1
        if row<0 or row>=len(self.controller_slots):
            self._roster_drag_source=None
            return
        self._roster_drag_source=row
        self.controller_list.selection_clear(0,"end")
        self.controller_list.selection_set(row)
        self.controller_list.activate(row)

    def _roster_drag_motion(self,event):
        if self._roster_drag_source is None:
            return
        try:
            row=self.controller_list.nearest(event.y)
        except Exception:
            return
        if row<0 or row>=self.controller_list.size():
            return
        self.controller_list.selection_clear(0,"end")
        self.controller_list.selection_set(row)
        self.controller_list.activate(row)
        self.controller_list.see(row)

    def _roster_drag_end(self,event):
        source=self._roster_drag_source
        self._roster_drag_source=None
        if source is None:
            return
        try:
            target=self.controller_list.nearest(event.y)
        except Exception:
            target=source
        target=max(0,min(int(target),len(self.controller_slots)-1))
        self.move_controller_to(source,target)

    def move_controller_to(self,source,target):
        source=int(source);target=int(target)
        if source<0 or target<0:
            return
        if source>=len(self.controller_slots) or target>=len(self.controller_slots):
            return
        if source==target:
            self.controller_list.selection_clear(0,"end")
            self.controller_list.selection_set(source)
            return

        before=tuple((self.controller_slots+["",""])[:2])
        selected_key=self.controller_slots[source]
        self.controller_slots=roster_move(self.controller_slots,source,target,4)
        after=tuple((self.controller_slots+["",""])[:2])

        self._last_roster_signature=None
        self.refresh_controller_roster(force=True)
        self.save()

        restore=target
        if selected_key:
            try:
                restore=self.controller_slots.index(selected_key)
            except ValueError:
                pass
        self.controller_list.selection_clear(0,"end")
        self.controller_list.selection_set(restore)
        self.controller_list.activate(restore)
        self.controller_list.see(restore)

        if self.api_service_running() and before!=after:
            self.schedule_service_restart("controller roster reordered")

    def schedule_service_restart(self,reason="controller roster changed"):
        if not self.api_service_running():
            return
        self._service_restart_reason=str(reason or "controller roster changed")
        if self._service_restart_after_id is not None:
            try:
                self.after_cancel(self._service_restart_after_id)
            except Exception:
                pass
        self._service_restart_after_id=self.after(
            350,self._perform_scheduled_service_restart
        )

    def _perform_scheduled_service_restart(self):
        self._service_restart_after_id=None
        reason=self._service_restart_reason or "controller roster changed"
        self._service_restart_reason=""
        if not self.api_service_running():
            return
        self._stop_service()
        self.after(
            120,
            lambda:self._finish_scheduled_service_restart(reason)
        )

    def _finish_scheduled_service_restart(self,reason):
        try:
            self._start_service()
            self.status.config(text=f"Service restarted: {reason}")
        except Exception as exc:
            log_exception("scheduled service restart",exc)
            self.status.config(text=f"Service restart failed: {exc}")

    def refresh_controller_roster(self,force=False):
        if not hasattr(self,"controller_list"):return
        selected=self.controller_list.curselection()
        selected_key=(self.controller_slots[selected[0]] if selected and selected[0]<len(self.controller_slots) else "")
        old_catalog=dict(self.controller_catalog)
        old_catalog_keys=set(old_catalog.keys())
        old_slots=tuple(self.controller_slots)
        old_active=tuple((self.controller_slots+["",""])[:2])

        discovered=discover_supported_controllers_windows(self.xi,self.keyboard_enabled.get())
        current={d["key"]:d for d in discovered}

        # Migrate old v1.22.1 per-collection Steam keys to the single physical
        # controller key produced by the new discovery model.
        steam_keys=[k for k in current if k.startswith("steam:")]
        if steam_keys:
            canonical=steam_keys[0]
            migrated=[]
            steam_written=False
            for key in self.controller_slots:
                if key.startswith("steam:"):
                    if not steam_written:
                        migrated.append(canonical)
                        steam_written=True
                    else:
                        migrated.append("")
                else:
                    migrated.append(key)

            # Also remove any accidental duplicate canonical entries left by
            # earlier refreshes/config migrations.
            seen_steam=False
            for i,key in enumerate(migrated):
                if key.startswith("steam:"):
                    if seen_steam:
                        migrated[i]=""
                    else:
                        migrated[i]=canonical
                        seen_steam=True

            self.controller_slots=migrated

        for key in current:
            self._controller_seen_counts[key]=self._controller_seen_counts.get(key,0)+1
            self._controller_missing_counts[key]=0

        protected={k for k in self.controller_slots if k}
        merged=dict(current)
        for key,d in old_catalog.items():
            if key in current:continue
            misses=self._controller_missing_counts.get(key,0)+1
            self._controller_missing_counts[key]=misses
            keep_limit=2 if key.startswith("steam:") else 3
            if key in protected and misses<keep_limit:merged[key]=d
        self.controller_catalog=merged

        slots=list(self.controller_slots)
        while len(slots)<4:slots.append("")
        if not self.keyboard_enabled.get():
            slots=["" if k=="virtual:keyboard_mouse" else k for k in slots]
        running=self.api_service_running()
        for i,key in enumerate(list(slots)):
            if not key:continue
            if key in self.controller_blacklist:slots[i]="";continue
            if key in current:continue
            misses=self._controller_missing_counts.get(key,0)
            active_running=(i==0 and self.worker.get().get("running")) or (i==1 and self.worker2.get().get("running"))
            if key.startswith("steam:"):
                remove_after=2
            else:
                remove_after=5 if active_running else 3
            if misses>=remove_after:slots[i]=""

        assigned={k for k in slots if k}
        for d in discovered:
            key=d["key"]
            if key in self.controller_blacklist or key in assigned:continue
            seen=self._controller_seen_counts.get(key,0)
            indices=list(range(2,len(slots))) if d.get("virtual") else list(range(len(slots)))
            if d.get("virtual") and len(slots)<4:indices+=list(range(len(slots),4))
            placed=False
            for i in indices:
                while i>=len(slots):slots.append("")
                if slots[i]:continue
                if running and i<2 and seen<2:continue
                slots[i]=key;assigned.add(key);placed=True;break
            if not placed:slots.append(key);assigned.add(key)
        while len(slots)<4:slots.append("")
        self.controller_slots=slots

        signature=(tuple(slots),
                   tuple((k,self.controller_catalog.get(k,{}).get("detail","")) for k in slots if k),
                   tuple(sorted(self.controller_blacklist)))
        if force or signature!=self._last_roster_signature:
            self.controller_list.delete(0,"end");restore=None
            for i,key in enumerate(slots):
                d=self.controller_catalog.get(key);state="P1" if i==0 else "P2" if i==1 else "inactive"
                self.controller_list.insert("end",f"{i+1} — {d['name']} [{state}] {d.get('detail','')}" if d else f"{i+1} — None")
                if key and key==selected_key:restore=i
            if restore is not None:self.controller_list.selection_set(restore)
            self._blacklisted_keys=sorted(self.controller_blacklist)
            blacklist_widget=getattr(self,"blacklisted_list",None)
            if blacklist_widget is not None:
                try:
                    if blacklist_widget.winfo_exists():
                        blacklist_widget.delete(0,"end")
                        for key in self._blacklisted_keys:
                            blacklist_widget.insert(
                                "end",
                                self.controller_catalog.get(
                                    key,{}
                                ).get("name",key),
                            )
                except Exception:
                    pass
            self._last_roster_signature=signature

        new_active=tuple((slots+["",""])[:2])
        # Only LOGICAL roster keys may trigger service topology restarts.
        # Descriptor path/caps changes for the same controller are metadata and
        # must never restart the UDP service.
        topology_changed=set(current.keys())!=old_catalog_keys
        roster_changed=tuple(self.controller_slots)!=old_slots
        if running and not force and (topology_changed or roster_changed):
            self.schedule_service_restart(
                "controller connected/removed"
                if topology_changed else
                "controller roster changed"
            )

    def _restart_after_roster_change(self):
        self._roster_restart_pending=False
        if self.api_service_running():
            try:self._stop_service();self._start_service()
            except Exception as exc:log_exception("restart after controller roster change",exc)

    def _worker_start_for_slot(self,slot,d):
        selected_profile=self.steam_profile.get()
        steam_mapping=None if selected_profile=="Default" else dict(
            self.steam_profiles.get(selected_profile,default_steam_mapping(False))
        )
        worker=self.worker if slot==0 else self.worker2
        worker.stop()
        if d is None:return
        worker.start(
            self.host.get().strip(),int(self.port.get()),int(self.rate.get()),
            int(d.get("index",slot) if d.get("index",-1)>=0 else slot),
            self._deadzone_for_backend(
                d.get("backend","xinput")
            ),
            False,
            d.get("backend","xinput"),steam_mapping,self.steam_gyro_trim.get(),
            self._switch2_rear_mapping(),
            self._controller_mapping_for_backend(
                d.get("backend","xinput")
            ),
            slot,d.get("path",""),
            list(d.get("paths") or ([d.get("path")] if d.get("path") else [])),
            self._active_keyboard_mapping(),self.keyboard_exclusive.get(),
            self.keyboard_release_key.get(),int(self.mouse_sensitivity.get())
        )

    def restart_slot(self,slot,reason="configuration change"):
        active=self.active_controller_descriptors()
        self._restart_events.append((time.monotonic(),int(slot),reason));self._restart_events=self._restart_events[-20:]
        self._worker_start_for_slot(int(slot),active[int(slot)])

    def active_controller_descriptors(self):
        slots=list(self.controller_slots)+["",""]
        return [self.controller_catalog.get(slots[0]),self.controller_catalog.get(slots[1])]

    def move_controller(self,delta):
        sel=self.controller_list.curselection()
        if not sel:
            return
        source=int(sel[0])
        target=source+int(delta)
        if target<0 or target>=len(self.controller_slots):
            return
        self.move_controller_to(source,target)


    def blacklist_selected(self):
        sel=self.controller_list.curselection()
        if not sel:return
        i=sel[0];key=self.controller_slots[i]
        if not key:return
        before=tuple((self.controller_slots+["",""])[:2])
        self.controller_blacklist.add(key)
        self.controller_slots[i]=""
        self._last_roster_signature=None
        self.refresh_controller_roster(force=True)
        self.save()
        after=tuple((self.controller_slots+["",""])[:2])
        if self.api_service_running():
            self.schedule_service_restart("controller blacklisted")

    def unblacklist_selected(self):
        widget=getattr(self,"blacklisted_list",None)
        if widget is None:
            return
        try:
            sel=widget.curselection()
        except Exception:
            return
        if not sel:
            return
        key=self._blacklisted_keys[sel[0]]
        self.controller_blacklist.discard(key)
        self.save()
        self.refresh_controller_roster(force=True)
        self.schedule_service_restart("controller restored")

    def toggle_windows_startup(self):
        desired = bool(self.windows_startup.get())
        try:
            set_windows_startup(desired)
            self.save()
        except Exception as exc:
            log_exception("windows startup", exc)
            self.windows_startup.set(not desired)
            messagebox.showerror(
                "SwitchNet",
                f"Unable to update Windows automatic startup:\n{exc}"
            )

    def _start_service(self):
        socket.inet_aton(self.host.get().strip())
        self.refresh_controller_roster()
        selected_profile=self.steam_profile.get()
        steam_mapping=None if selected_profile=="Default" else dict(
            self.steam_profiles.get(selected_profile,default_steam_mapping(False))
        )
        active=self.active_controller_descriptors()
        self.worker.stop()
        self.worker2.stop()

        started=0
        for slot,d in enumerate(active):
            if d is None:
                continue
            self._worker_start_for_slot(slot,d)
            started+=1

        if started==0:
            raise RuntimeError(
                "No active controller in slot 1 or slot 2."
            )

        self.save()
        self._update_service_controls()
    def start(self):
        try:
            self._start_service()
        except Exception as exc:
            log_exception("start service", exc)
            messagebox.showerror("SwitchNet", str(exc))

    def _stop_service(self):
        self.worker.stop()
        self.worker2.stop()
        self._update_service_controls()

    def stop_service(self):
        try:
            self._stop_service()
        except Exception as exc:
            log_exception("stop service", exc)
            messagebox.showerror("SwitchNet", f"Error while stopping: {exc}")

    def toggle_service(self):
        if self.api_service_running():
            self.stop_service()
        else:
            self.start()
        self.after(20,self._update_service_controls)

    def _update_service_controls(self):
        running=self.api_service_running()

        button=getattr(self,"service_toggle_button",None)
        if button is not None:
            try:
                button.configure(
                    text="Stop" if running else "Start"
                )
            except Exception:
                pass

        canvas=getattr(self,"service_indicator",None)
        dot=getattr(self,"service_indicator_dot",None)
        if canvas is not None and dot is not None:
            try:
                canvas.itemconfigure(
                    dot,
                    fill="#2e7d32" if running else "#c62828",
                )
            except Exception:
                pass

    def api_service_running(self):
        return bool(self.worker.get().get("running") or self.worker2.get().get("running"))

    def api_status(self):
        snap = self.worker.get()
        return {
            "service": "SwitchNetClient",
            "version": APP_VERSION,
            "running": bool(snap.get("running")),
            "controller_connected": bool(snap.get("connected")),
            "controller": snap.get("input_backend", "-"),
            "controller_detail": snap.get("input_detail", ""),
            "status": snap.get("status", ""),
            "tx_per_second": int(snap.get("tx", 0)),
            "errors_per_second": int(snap.get("errors", 0)),
            "packets_total": int(snap.get("total", 0)),
            "rumble_packets_received": int(snap.get("rumble_rx", 0)),
            "api": f"http://{CLIENT_API_HOST}:{CLIENT_API_PORT}",
        }

    def api_command(self, action):
        if self.closing:
            return False, "client_closing"
        done = threading.Event()
        result = {"ok": False, "message": "timeout"}

        def execute():
            try:
                if action == "start":
                    self._start_service()
                    result.update(ok=True, message="started")
                elif action == "stop":
                    self._stop_service()
                    result.update(ok=True, message="stopped")
                else:
                    result.update(ok=False, message="invalid_action")
            except Exception as exc:
                log_exception(f"API {action}", exc)
                result.update(ok=False, message=str(exc))
            finally:
                done.set()

        try:
            self.after(0, execute)
        except Exception as exc:
            return False, str(exc)
        if not done.wait(5.0):
            return False, "main_thread_timeout"
        return bool(result["ok"]), str(result["message"])

    def _on_unmap(self, _event=None):
        # A normal minimize first moves Tk to the iconic state. Turn that into a
        # true withdraw so SwitchNet disappears from the taskbar and lives only
        # in the notification area.
        if self.closing:
            return
        if self.state() == "iconic":
            if self._hide_job is not None:
                try:
                    self.after_cancel(self._hide_job)
                except Exception:
                    pass
            self._hide_job = self.after(40, self._withdraw_if_iconic)

    def _withdraw_if_iconic(self):
        self._hide_job = None
        if not self.closing and self.state() == "iconic":
            self.withdraw()

    def hide_to_tray(self):
        if self.closing:
            return
        try:
            self.save()
        except Exception:
            pass
        self.withdraw()

    def show_window(self):
        if self.closing:
            return
        self.deiconify()
        self.state("normal")
        self.lift()
        try:
            self.focus_force()
        except Exception:
            pass

    def exit_from_tray(self):
        # There is deliberately no normal-window exit action. This is the only
        # user-facing quit path, as requested by the tray-first UX.
        self.exit()

    def exit(self):
        if self.closing:
            return
        self.closing = True
        if self.refresh_job is not None:
            try:
                self.after_cancel(self.refresh_job)
            except Exception:
                pass
            self.refresh_job = None
        if self._hide_job is not None:
            try:
                self.after_cancel(self._hide_job)
            except Exception:
                pass
            self._hide_job = None
        try:
            self.worker.stop()
            self.worker2.stop()
            self.save()
        finally:
            try:
                if getattr(self, "api", None) is not None:
                    self.api.stop()
            finally:
                try:
                    self.tray.stop()
                finally:
                    self.destroy()

    def refresh(self):
        now=time.monotonic()
        if now-getattr(self,"_last_roster_scan",0.0)>=3.0:
            self._last_roster_scan=now;self.refresh_controller_roster()
        if self.closing:
            return
        snap = self.worker.get()
        snap2 = self.worker2.get()
        self._update_service_controls()
        self.status.config(text=snap["status"] if not snap2.get("running") else f"P1 {snap['status']} · P2 {snap2['status']}")
        self.stats.config(text=f"TX {snap['tx']}/s   Errors {snap['errors']}/s   Total {snap['total']}   Rumble RX {snap.get('rumble_rx', 0)}")
        self.conn.config(text=f"P1: {'connected' if snap['connected'] else 'not connected'} · P2: {'connected' if snap2.get('connected') else ('waiting' if snap2.get('running') else 'off')}")
        self.source.config(text=f"P1 input: {snap.get('input_backend', '-')} · P2 input: {snap2.get('input_backend', '-') if snap2.get('running') else 'Off'}")

        if snap["running"]:
            tray_status = "Running" if snap["connected"] else "Running - neutral state"
        else:
            tray_status = "Stopped"
        tray_controller = f"P1 {snap.get('input_backend','-') if snap['connected'] else 'None'} · P2 {snap2.get('input_backend','-') if snap2.get('connected') else ('Waiting' if snap2.get('running') else 'Off')}"
        self.tray.update(bool(snap["running"] or snap2.get("running")), tray_status, tray_controller)

        v = snap.get("values", {})
        text = (
            f"LX {v.get('lx', 0):6d}  LY {v.get('ly', 0):6d}\n"
            f"RX {v.get('rx', 0):6d}  RY {v.get('ry', 0):6d}\n"
            f"LT {v.get('lt', 0):5d}  RT {v.get('rt', 0):5d}\n"
            f"Hat {v.get('hat', 8)}\n"
            f"Buttons 0x{v.get('buttons', 0):08X}\n"
            f"Accel {v.get('ax', 0):6d} {v.get('ay', 0):6d} {v.get('az', 4096):6d}\n"
            f"Gyro  {v.get('gx', 0):6d} {v.get('gy', 0):6d} {v.get('gz', 0):6d}\n"
            f"Rumble L {snap.get('rumble_left', 0):5d}  R {snap.get('rumble_right', 0):5d}  via {snap.get('rumble_backend', '-')}\n"
            f"Roster: slot 1=P1, slot 2=P2\n"
            f"Steam profile: {self._steam_profile_label(self.steam_profile.get())}\n"
            f"Other profiles: "
            + ", ".join(
                f"{CONTROLLER_MAPPING_SPECS[cid]['title']}="
                f"{self._controller_profile_label(cid,self.controller_profile_slots[cid].get())}"
                for cid in CONTROLLER_MAPPING_SPECS
            )
            + "\n"
            f"XInput DLL: {self.xi.dll_name}\n"
            f"P1 worker error: {snap.get('input_detail','') if snap.get('worker_exception') else '-'}\n"
            f"P2 worker error: {snap2.get('input_detail','') if snap2.get('worker_exception') else '-'}\n"
            f"Config: {cfg_path()}"
        )
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.config(state="disabled")
        self.refresh_job = self.after(200, self.refresh)


def main():
    if sys.platform != "win32":
        print("This client is intended for Windows", file=sys.stderr)
        return 2
    def _thread_exception(args):
        log_exception(f"thread {args.thread.name if args.thread else '?'}", args.exc_value)
    threading.excepthook = _thread_exception
    try:
        startup_launch = "--startup" in sys.argv[1:]
        App(startup_launch=startup_launch).mainloop()
        return 0
    except Exception as exc:
        ctypes.windll.user32.MessageBoxW(None, str(exc), "SwitchNet Client", 0x10)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())