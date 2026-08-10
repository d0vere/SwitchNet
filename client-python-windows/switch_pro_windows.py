from __future__ import annotations

import ctypes
import math
import os
import re
import struct
import threading
import time
from ctypes import wintypes

NINTENDO_VID = 0x057E
SWITCH_PRO_PID = 0x2009

REPORT_SUBCOMMAND_REPLY = 0x21
REPORT_FULL_STATE = 0x30
REPORT_COMMAND_ACK = 0x81

OUTPUT_SUBCOMMAND = 0x01
OUTPUT_RUMBLE = 0x10
OUTPUT_PROPRIETARY = 0x80

SUBCMD_SET_INPUT_MODE = 0x03
SUBCMD_SET_PLAYER_LIGHTS = 0x30
SUBCMD_ENABLE_IMU = 0x40
SUBCMD_ENABLE_VIBRATION = 0x48

PROP_HANDSHAKE = 0x02
PROP_HIGH_SPEED = 0x03
PROP_FORCE_USB = 0x04

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
FILE_FLAG_OVERLAPPED = 0x40000000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
DIGCF_PRESENT = 0x00000002
DIGCF_DEVICEINTERFACE = 0x00000010
ERROR_IO_PENDING = 997
WAIT_OBJECT_0 = 0
HIDP_STATUS_SUCCESS = 0x00110000

RUMBLE_WRITE_INTERVAL_S = 0.030
RUMBLE_REFRESH_S = 0.050
RUMBLE_HIGH_FREQ = 0x0074
RUMBLE_LOW_FREQ = 0x3D

RUMBLE_THRESHOLDS = (
    0,514,775,921,1096,1303,1550,1843,2192,2606,3100,3686,4383,5213,6199,
    7372,7698,8039,8395,8767,9155,9560,9984,10426,10887,11369,11873,12398,
    12947,13520,14119,14744,15067,15397,15734,16079,16431,16790,17158,17534,
    17918,18310,18711,19121,19540,19967,20405,20851,21308,21775,22251,22739,
    23236,23745,24265,24797,25340,25894,26462,27041,27633,28238,28856,29488,
    30134,30794,31468,32157,32861,33581,34316,35068,35836,36620,37422,38242,
    39079,39935,40809,41703,42616,43549,44503,45477,46473,47491,48531,49593,
    50679,51789,52923,54082,55266,56476,57713,58977,60268,61588,62936,64315,
    65535,
)

NEUTRAL_RUMBLE = bytes((0x00, 0x01, 0x40, 0x40))


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.c_size_t),
    ]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", ctypes.c_ushort),
        ("UsagePage", ctypes.c_ushort),
        ("InputReportByteLength", ctypes.c_ushort),
        ("OutputReportByteLength", ctypes.c_ushort),
        ("FeatureReportByteLength", ctypes.c_ushort),
        ("Reserved", ctypes.c_ushort * 17),
        ("NumberLinkCollectionNodes", ctypes.c_ushort),
        ("NumberInputButtonCaps", ctypes.c_ushort),
        ("NumberInputValueCaps", ctypes.c_ushort),
        ("NumberInputDataIndices", ctypes.c_ushort),
        ("NumberOutputButtonCaps", ctypes.c_ushort),
        ("NumberOutputValueCaps", ctypes.c_ushort),
        ("NumberOutputDataIndices", ctypes.c_ushort),
        ("NumberFeatureButtonCaps", ctypes.c_ushort),
        ("NumberFeatureValueCaps", ctypes.c_ushort),
        ("NumberFeatureDataIndices", ctypes.c_ushort),
    ]


class OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_size_t),
        ("InternalHigh", ctypes.c_size_t),
        ("Offset", wintypes.DWORD),
        ("OffsetHigh", wintypes.DWORD),
        ("hEvent", wintypes.HANDLE),
    ]


def _physical_key(path):
    low = str(path or "").casefold()
    return re.sub(r"&col[0-9a-f]+", "", low)


def _is_bluetooth_path(path):
    low = str(path or "").casefold()
    return (
        "bthenum" in low
        or "00001124-0000-1000-8000-00805f9b34fb" in low
        or "vid&0002057e_pid&2009" in low
    )


class NativeHid:
    def __init__(self):
        if os.name != "nt":
            raise RuntimeError("Nintendo Switch Pro backend is Windows-only")

        self.hid = ctypes.WinDLL("hid.dll", use_last_error=True)
        self.setupapi = ctypes.WinDLL("setupapi.dll", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)

        self.hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
        self.hid.HidD_GetPreparsedData.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)
        ]
        self.hid.HidD_GetPreparsedData.restype = wintypes.BOOLEAN
        self.hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
        self.hid.HidP_GetCaps.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)
        ]
        self.hid.HidP_GetCaps.restype = ctypes.c_long

        self.setupapi.SetupDiGetClassDevsW.argtypes = [
            ctypes.POINTER(GUID), wintypes.LPCWSTR, ctypes.c_void_p, wintypes.DWORD
        ]
        self.setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
        self.setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID),
            wintypes.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)
        ]
        self.setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
        self.setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
            ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p
        ]
        self.setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
        self.setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

        self.kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
        ]
        self.kernel32.CreateFileW.restype = wintypes.HANDLE
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel32.ReadFile.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(OVERLAPPED)
        ]
        self.kernel32.ReadFile.restype = wintypes.BOOL
        self.kernel32.WriteFile.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(OVERLAPPED)
        ]
        self.kernel32.WriteFile.restype = wintypes.BOOL
        self.kernel32.CreateEventW.argtypes = [
            ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR
        ]
        self.kernel32.CreateEventW.restype = wintypes.HANDLE
        self.kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel32.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel32.GetOverlappedResult.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(OVERLAPPED),
            ctypes.POINTER(wintypes.DWORD), wintypes.BOOL
        ]
        self.kernel32.GetOverlappedResult.restype = wintypes.BOOL
        self.kernel32.CancelIoEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p]

    def _all_paths(self):
        guid = GUID()
        self.hid.HidD_GetHidGuid(ctypes.byref(guid))
        info = self.setupapi.SetupDiGetClassDevsW(
            ctypes.byref(guid), None, None,
            DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
        )
        if info in (None, INVALID_HANDLE_VALUE):
            return []

        result = []
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
                    info, ctypes.byref(data), None, 0,
                    ctypes.byref(needed), None
                )
                if needed.value < 8 or needed.value > 65536:
                    continue

                buf = ctypes.create_string_buffer(needed.value)
                ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = (
                    8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
                )
                if not self.setupapi.SetupDiGetDeviceInterfaceDetailW(
                    info, ctypes.byref(data), buf, needed.value,
                    ctypes.byref(needed), None
                ):
                    continue

                try:
                    path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
                except Exception:
                    continue
                result.append(path)
        finally:
            self.setupapi.SetupDiDestroyDeviceInfoList(info)

        return result

    def caps(self, path):
        h = self.kernel32.CreateFileW(
            path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, None,
            OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None
        )
        if h in (None, INVALID_HANDLE_VALUE):
            return None
        try:
            pp = ctypes.c_void_p()
            if not self.hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
                return None
            try:
                caps = HIDP_CAPS()
                if self.hid.HidP_GetCaps(
                    pp, ctypes.byref(caps)
                ) != HIDP_STATUS_SUCCESS:
                    return None
                return caps
            finally:
                self.hid.HidD_FreePreparsedData(pp)
        finally:
            self.kernel32.CloseHandle(h)

    def enumerate(self):
        result = []
        for path in self._all_paths():
            low = path.casefold()
            if (
                ("vid_057e" not in low or "pid_2009" not in low)
                and "vid&0002057e_pid&2009" not in low
            ):
                continue

            try:
                caps = self.caps(path)
            except Exception:
                caps = None

            bluetooth = _is_bluetooth_path(path)
            result.append({
                "path": path,
                "input_len": int(caps.InputReportByteLength) if caps else 64,
                "output_len": int(caps.OutputReportByteLength) if caps else (
                    49 if bluetooth else 64
                ),
                "bluetooth": bluetooth,
                "physical_key": _physical_key(path),
            })
        return result

    def open(self, path):
        h = self.kernel32.CreateFileW(
            path, GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE, None,
            OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None
        )
        return None if h in (None, INVALID_HANDLE_VALUE) else h

    def close(self, h):
        if h not in (None, INVALID_HANDLE_VALUE):
            self.kernel32.CloseHandle(h)

    def cancel(self, h):
        if h not in (None, INVALID_HANDLE_VALUE):
            try:
                self.kernel32.CancelIoEx(h, None)
            except Exception:
                pass

    def read(self, h, size=64, timeout_ms=100):
        event = self.kernel32.CreateEventW(None, True, False, None)
        if not event:
            return b""
        ov = OVERLAPPED()
        ov.hEvent = event
        buf = (ctypes.c_ubyte * max(64, int(size)))()
        got = wintypes.DWORD(0)
        try:
            ok = self.kernel32.ReadFile(
                h, buf, len(buf), ctypes.byref(got), ctypes.byref(ov)
            )
            if ok:
                return bytes(buf[:got.value])
            if ctypes.get_last_error() != ERROR_IO_PENDING:
                return b""
            if self.kernel32.WaitForSingleObject(
                event, timeout_ms
            ) != WAIT_OBJECT_0:
                try:
                    self.kernel32.CancelIoEx(h, ctypes.byref(ov))
                except Exception:
                    pass
                self.kernel32.WaitForSingleObject(event, 20)
                return b""
            if not self.kernel32.GetOverlappedResult(
                h, ctypes.byref(ov), ctypes.byref(got), False
            ):
                return b""
            return bytes(buf[:got.value])
        finally:
            self.kernel32.CloseHandle(event)

    def write(self, h, data, output_len=64, timeout_ms=150):
        size = max(len(data), int(output_len or len(data)))
        payload = bytes(data) + bytes(max(0, size - len(data)))

        event = self.kernel32.CreateEventW(None, True, False, None)
        if not event:
            return False
        ov = OVERLAPPED()
        ov.hEvent = event
        buf = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
        got = wintypes.DWORD(0)
        try:
            ok = self.kernel32.WriteFile(
                h, buf, len(payload), ctypes.byref(got), ctypes.byref(ov)
            )
            if ok:
                return got.value == len(payload)
            if ctypes.get_last_error() != ERROR_IO_PENDING:
                return False
            if self.kernel32.WaitForSingleObject(
                event, timeout_ms
            ) != WAIT_OBJECT_0:
                try:
                    self.kernel32.CancelIoEx(h, ctypes.byref(ov))
                except Exception:
                    pass
                self.kernel32.WaitForSingleObject(event, 20)
                return False
            if not self.kernel32.GetOverlappedResult(
                h, ctypes.byref(ov), ctypes.byref(got), False
            ):
                return False
            return got.value == len(payload)
        finally:
            self.kernel32.CloseHandle(event)


def enumerate_switch_pro_hid():
    if os.name != "nt":
        return []
    try:
        return NativeHid().enumerate()
    except Exception:
        return []


def _unpack_stick(data, offset):
    return (
        data[offset] | ((data[offset + 1] & 0x0F) << 8),
        (data[offset + 1] >> 4) | (data[offset + 2] << 4),
    )


def _axis12(value):
    center = 2048.0
    if value >= center:
        normalized = (float(value) - center) / (4095.0 - center)
    else:
        normalized = (float(value) - center) / center
    return max(-32768, min(32767, round(normalized * 32767.0)))


class GyroZero:
    def __init__(self):
        self.reset()

    def reset(self):
        self.ready = False
        self.count = 0
        self.target = 120
        self.total = [0.0, 0.0, 0.0]
        self.bias = [0.0, 0.0, 0.0]

    def apply(self, accel, gyro):
        ax, ay, az = accel
        gx, gy, gz = gyro

        if not self.ready:
            accel_mag = math.sqrt(float(ax * ax + ay * ay + az * az))
            gyro_mag = math.sqrt(float(gx * gx + gy * gy + gz * gz))
            if 3000.0 <= accel_mag <= 5200.0 and gyro_mag <= 1000.0:
                self.total[0] += gx
                self.total[1] += gy
                self.total[2] += gz
                self.count += 1
                if self.count >= self.target:
                    self.bias = [
                        self.total[0] / self.count,
                        self.total[1] / self.count,
                        self.total[2] / self.count,
                    ]
                    self.ready = True

        return (
            round(gx - self.bias[0]),
            round(gy - self.bias[1]),
            round(gz - self.bias[2]),
        )


def parse_full_report(report, gyro_zero=None):
    if not report or len(report) < 49 or report[0] != REPORT_FULL_STATE:
        return None

    right_buttons = report[3]
    shared_buttons = report[4]
    left_buttons = report[5]

    buttons = set()

    for name, mask in (
        ("Y", 0x01), ("X", 0x02), ("B", 0x04), ("A", 0x08),
        ("R", 0x40), ("ZR", 0x80),
    ):
        if right_buttons & mask:
            buttons.add(name)

    for name, mask in (
        ("MINUS", 0x01), ("PLUS", 0x02), ("R3", 0x04), ("L3", 0x08),
        ("HOME", 0x10), ("CAPTURE", 0x20),
    ):
        if shared_buttons & mask:
            buttons.add(name)

    for name, mask in (
        ("DOWN", 0x01), ("UP", 0x02), ("RIGHT", 0x04), ("LEFT", 0x08),
        ("L", 0x40), ("ZL", 0x80),
    ):
        if left_buttons & mask:
            buttons.add(name)

    lx_raw, ly_raw = _unpack_stick(report, 6)
    rx_raw, ry_raw = _unpack_stick(report, 9)

    # imuState[0] begins at byte 13. SDL processes it as the newest sample.
    ax, ay, az, gx, gy, gz = struct.unpack_from("<hhhhhh", report, 13)

    if gyro_zero is not None:
        gx, gy, gz = gyro_zero.apply((ax, ay, az), (gx, gy, gz))

    return {
        "buttons": buttons,
        "lx": _axis12(lx_raw),
        "ly": -_axis12(ly_raw),
        "rx": _axis12(rx_raw),
        "ry": -_axis12(ry_raw),
        # The source is already a Nintendo controller. Keep its native
        # Nintendo IMU frame when forwarding it back to the console.
        "ax": max(-32768, min(32767, int(ax))),
        "ay": max(-32768, min(32767, int(ay))),
        "az": max(-32768, min(32767, int(az))),
        "gx": max(-32768, min(32767, int(gx))),
        "gy": max(-32768, min(32767, int(gy))),
        "gz": max(-32768, min(32767, int(gz))),
        "imu_timestamp": (time.perf_counter_ns() // 1000) & 0xFFFFFFFF,
        "report_id": REPORT_FULL_STATE,
    }


def _amplitude_index(amplitude):
    value = max(0, min(65535, int(amplitude or 0)))
    for index, threshold in enumerate(RUMBLE_THRESHOLDS):
        if value <= threshold:
            return index
    return len(RUMBLE_THRESHOLDS) - 1


def encode_motor_rumble(amplitude):
    amplitude = max(0, min(65535, int(amplitude or 0)))
    if amplitude <= 0:
        return NEUTRAL_RUMBLE

    index = _amplitude_index(amplitude)
    high_amp = (index * 2) & 0xFF
    low_amp = (
        (0x8000 if (index & 1) else 0)
        | (0x40 + (index // 2))
    )

    return bytes((
        RUMBLE_HIGH_FREQ & 0xFF,
        high_amp | ((RUMBLE_HIGH_FREQ >> 8) & 0x01),
        RUMBLE_LOW_FREQ | ((low_amp >> 8) & 0x80),
        low_amp & 0xFF,
    ))


def build_rumble_report(counter, left, right):
    packet = bytearray(10)
    packet[0] = OUTPUT_RUMBLE
    packet[1] = int(counter) & 0x0F
    packet[2:6] = encode_motor_rumble(left)
    packet[6:10] = encode_motor_rumble(right)
    return bytes(packet)


class SwitchProReader:
    def __init__(self):
        self.api = None
        self.handle = None
        self.thread = None
        self.stop_evt = threading.Event()
        self.lock = threading.Lock()

        self.preferred_path = ""
        self.preferred_paths = []
        self.path = ""
        self.input_len = 64
        self.output_len = 64
        self.bluetooth = False

        self.latest = None
        self.status = "Nintendo Switch Pro inactive"
        self.reports = 0
        self.errors = 0

        self.command_counter = 0
        self.gyro_zero = GyroZero()

        self.rumble_left = 0
        self.rumble_right = 0
        self.rumble_counter = 0
        self.rumble_due = 0.0
        self.rumble_refresh_due = 0.0

    def start(self, preferred_path="", preferred_paths=None):
        self.stop()
        self.stop_evt.clear()
        self.preferred_path = str(preferred_path or "")
        self.preferred_paths = [
            str(path) for path in (preferred_paths or []) if path
        ]
        self.gyro_zero.reset()

        self.thread = threading.Thread(
            target=self._run,
            name="SwitchNet-SwitchPro",
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.stop_evt.set()

        if self.api and self.handle:
            self.api.cancel(self.handle)

        thread = self.thread
        if (
            thread and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(2.5)

        if not thread or not thread.is_alive():
            if self.api and self.handle:
                self.api.close(self.handle)
            self.handle = None
            self.thread = None

        with self.lock:
            self.latest = None
            if not thread or not thread.is_alive():
                self.status = "Nintendo Switch Pro inactive"

    def snapshot(self):
        with self.lock:
            return {
                "state": dict(self.latest) if self.latest else None,
                "status": self.status,
                "reports": self.reports,
                "errors": self.errors,
            }

    def rumble(self, left, right):
        with self.lock:
            self.rumble_left = max(0, min(65535, int(left or 0)))
            self.rumble_right = max(0, min(65535, int(right or 0)))
        return bool(self.handle)

    def _candidates(self):
        devices = self.api.enumerate()
        preferred = {
            path.casefold() for path in self.preferred_paths
        }
        if self.preferred_path:
            preferred.add(self.preferred_path.casefold())

        def rank(device):
            return (
                1 if device["path"].casefold() in preferred else 0,
                1 if not device["bluetooth"] else 0,
                int(device["input_len"]),
            )

        return sorted(devices, key=rank, reverse=True)

    def _read_until(self, predicate, timeout_s=0.16):
        deadline = time.monotonic() + timeout_s
        while (
            time.monotonic() < deadline
            and not self.stop_evt.is_set()
        ):
            report = self.api.read(
                self.handle, self.input_len, 25
            )
            if report and predicate(report):
                return report
        return None

    def _write(self, data):
        return self.api.write(
            self.handle, data, self.output_len, 150
        )

    def _proprietary(self, command, wait=True):
        if not self._write(bytes((OUTPUT_PROPRIETARY, command))):
            return False
        if not wait:
            return True

        return self._read_until(
            lambda report: (
                len(report) >= 2
                and report[0] == REPORT_COMMAND_ACK
                and report[1] == command
            ),
            0.16,
        ) is not None

    def _subcommand(self, command, data=b"", wait=True):
        packet = bytearray(49)
        packet[0] = OUTPUT_SUBCOMMAND
        packet[1] = self.command_counter & 0x0F
        packet[2:6] = NEUTRAL_RUMBLE
        packet[6:10] = NEUTRAL_RUMBLE
        packet[10] = command
        packet[11:11 + len(data)] = data
        self.command_counter = (self.command_counter + 1) & 0x0F

        if not self._write(packet):
            return False
        if not wait:
            return True

        return self._read_until(
            lambda report: (
                len(report) >= 15
                and report[0] == REPORT_SUBCOMMAND_REPLY
                and report[14] == command
                and (report[13] & 0x80) != 0
            ),
            0.18,
        ) is not None

    def _initialize(self):
        # SDL uses the proprietary handshake only on USB.
        if not self.bluetooth:
            if not self._proprietary(PROP_HANDSHAKE, True):
                return False
            # High-speed acknowledgement is expected from the official
            # controller but is not required for continuing the sequence.
            self._proprietary(PROP_HIGH_SPEED, True)
            self._proprietary(PROP_HANDSHAKE, True)
            if not self._proprietary(PROP_FORCE_USB, False):
                return False

        if not self._subcommand(
            SUBCMD_ENABLE_VIBRATION, b"\x01", True
        ):
            return False

        if not self._subcommand(
            SUBCMD_ENABLE_IMU, b"\x01", True
        ):
            return False

        if not self._subcommand(
            SUBCMD_SET_INPUT_MODE,
            bytes((REPORT_FULL_STATE,)),
            True,
        ):
            return False

        # Player LED is useful but not required for gameplay.
        self._subcommand(
            SUBCMD_SET_PLAYER_LIGHTS, b"\x01", False
        )

        if not self.bluetooth:
            # Start USB reports after all subcommands are configured.
            self._proprietary(PROP_FORCE_USB, False)

        return True

    def _send_rumble_if_due(self, force=False):
        now = time.monotonic()

        with self.lock:
            left = self.rumble_left
            right = self.rumble_right

        active = bool(left or right)
        if not (
            force
            or now >= self.rumble_due
            or (active and now >= self.rumble_refresh_due)
        ):
            return

        packet = build_rumble_report(
            self.rumble_counter, left, right
        )
        if self._write(packet):
            self.rumble_counter = (
                self.rumble_counter + 1
            ) & 0x0F
        else:
            self.errors += 1

        self.rumble_due = now + RUMBLE_WRITE_INTERVAL_S
        self.rumble_refresh_due = now + RUMBLE_REFRESH_S

    def _run(self):
        try:
            self.api = NativeHid()
        except Exception as exc:
            with self.lock:
                self.status = (
                    f"Nintendo Switch Pro backend unavailable: {exc}"
                )
            return

        while not self.stop_evt.is_set():
            devices = self._candidates()
            if not devices:
                with self.lock:
                    self.latest = None
                    self.status = (
                        "Nintendo Switch Pro not connected"
                    )
                self.stop_evt.wait(0.5)
                continue

            device = devices[0]
            self.path = device["path"]
            self.input_len = max(
                49, int(device["input_len"] or 64)
            )
            self.bluetooth = bool(device["bluetooth"])
            self.output_len = max(
                49 if self.bluetooth else 64,
                int(device["output_len"] or 0),
            )

            handle = self.api.open(self.path)
            if not handle:
                self.errors += 1
                with self.lock:
                    self.latest = None
                    self.status = (
                        "Nintendo Switch Pro HID unavailable"
                    )
                self.stop_evt.wait(0.35)
                continue

            self.handle = handle
            self.command_counter = 0
            self.gyro_zero.reset()

            try:
                with self.lock:
                    self.status = (
                        "Initializing Nintendo Switch Pro"
                    )

                if not self._initialize():
                    self.errors += 1
                    with self.lock:
                        self.latest = None
                        self.status = (
                            "Nintendo Switch Pro initialization failed"
                        )
                    self.stop_evt.wait(0.3)
                    continue

                with self.lock:
                    self.status = "Nintendo Switch Pro active"

                last_valid = time.monotonic()

                while not self.stop_evt.is_set():
                    self._send_rumble_if_due()

                    report = self.api.read(
                        handle, self.input_len, 80
                    )
                    if not report:
                        if time.monotonic() - last_valid > 1.0:
                            # Another HID application can change reporting
                            # mode. Re-open and initialize again.
                            break
                        continue

                    parsed = parse_full_report(
                        report, self.gyro_zero
                    )
                    if parsed is None:
                        continue

                    last_valid = time.monotonic()
                    with self.lock:
                        self.latest = parsed
                        self.reports += 1

            except Exception as exc:
                self.errors += 1
                with self.lock:
                    self.latest = None
                    self.status = (
                        f"Nintendo Switch Pro read error: {exc}"
                    )
            finally:
                if handle:
                    with self.lock:
                        old_left = self.rumble_left
                        old_right = self.rumble_right
                        self.rumble_left = 0
                        self.rumble_right = 0

                    for _ in range(2):
                        self._send_rumble_if_due(force=True)
                        time.sleep(0.03)

                    with self.lock:
                        self.rumble_left = old_left
                        self.rumble_right = old_right

                self.api.cancel(handle)
                self.api.close(handle)
                self.handle = None
                self.rumble_due = 0.0
                self.rumble_refresh_due = 0.0

            if not self.stop_evt.is_set():
                self.stop_evt.wait(0.2)
