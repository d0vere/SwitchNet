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
SWITCH2_PRO_PID = 0x2069
REPORT_ID = 0x09
REPORT_ID_EXTENDED = 0x05

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
USBD_PIPE_TYPE_BULK = 2

# The controller's WinUSB vendor interface (MI_01). This is the interface used
# by public Switch 2 tools and SDL's Switch 2 backend to arm USB streaming.
WINUSB_IFACE_GUID = "{6F13725E-EF0E-4FD3-AE5F-B2DE989EC825}"

# Minimal proven sequence that arms report 0x09 at ~4 ms intervals.
BASIC_WAKE_SEQUENCE = (
    bytes([0x03,0x91,0x00,0x0d,0x00,0x08,0x00,0x00,0x01,0x00,
           0xff,0xff,0xff,0xff,0xff,0xff]),
    bytes([0x07,0x91,0x00,0x01,0x00,0x00,0x00,0x00]),
    bytes([0x16,0x91,0x00,0x01,0x00,0x00,0x00,0x00]),
    bytes([0x03,0x91,0x00,0x0a,0x00,0x04,0x00,0x00,0x09,0x00,0x00,0x00]),
    bytes([0x09,0x91,0x00,0x07,0x00,0x08,0x00,0x00,0x01,0x00,
           0x00,0x00,0x00,0x00,0x00,0x00]),
)

EXTENDED_INIT_SEQUENCE = (
    bytes([0x07,0x91,0x00,0x01,0x00,0x00,0x00,0x00]),
    bytes([0x0c,0x91,0x00,0x02,0x00,0x04,0x00,0x00,0x27,0x00,0x00,0x00]),
    bytes([0x11,0x91,0x00,0x01,0x00,0x00,0x00,0x00]),
    bytes([0x0a,0x91,0x00,0x08,0x00,0x14,0x00,0x00,
           0x01,0xff,0xff,0xff,0xff,0xff,0xff,0xff,
           0xff,0x35,0x00,0x46,0x00,0x00,0x00,0x00,
           0x00,0x00,0x00,0x00]),
    bytes([0x0c,0x91,0x00,0x04,0x00,0x04,0x00,0x00,0x27,0x00,0x00,0x00]),
    bytes([0x01,0x91,0x00,0x0c,0x00,0x00,0x00,0x00]),
    bytes([0x01,0x91,0x00,0x01,0x00,0x00,0x00,0x00]),
    bytes([0x08,0x91,0x00,0x02,0x00,0x04,0x00,0x00,0x01,0x00,0x00,0x00]),
    bytes([0x03,0x91,0x00,0x0a,0x00,0x04,0x00,0x00,0x05,0x00,0x00,0x00]),
    bytes([0x03,0x91,0x00,0x0d,0x00,0x08,0x00,0x00,
           0x01,0x00,0xff,0xff,0xff,0xff,0xff,0xff]),
)

RUMBLE_INTERVAL_S=0.012
RUMBLE_MAX=29000
RUMBLE_HI_FREQ=0x187
RUMBLE_LO_FREQ=0x112


# Verified public report-0x09 button layout.
BUTTON_BITS = {
    "A":(3,1),"B":(3,0),"X":(3,3),"Y":(3,2),
    "UP":(4,3),"DOWN":(4,0),"LEFT":(4,2),"RIGHT":(4,1),
    "L":(4,4),"R":(3,4),"ZL":(4,5),"ZR":(3,5),
    "MINUS":(4,6),"PLUS":(3,6),"L3":(4,7),"R3":(3,7),
    "HOME":(5,0),"CAPTURE":(5,1),
    "GR":(5,2),"GL":(5,3),"C":(5,4),
}

# Publicly verified calibration sample. We use these only as axis endpoints for
# the first SwitchNet implementation; the configurable SwitchNet deadzone is
# still applied downstream. A later release can read factory calibration.
STICK_CAL = {
    "LX":(437,3582),
    "LY":(661,3670),
    "RX":(628,3656),
    "RY":(471,3626),
}


class GUID(ctypes.Structure):
    _fields_=[
        ("Data1",ctypes.c_ulong),
        ("Data2",ctypes.c_ushort),
        ("Data3",ctypes.c_ushort),
        ("Data4",ctypes.c_ubyte*8),
    ]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_=[
        ("cbSize",wintypes.DWORD),
        ("InterfaceClassGuid",GUID),
        ("Flags",wintypes.DWORD),
        ("Reserved",ctypes.c_size_t),
    ]


class HIDP_CAPS(ctypes.Structure):
    _fields_=[
        ("Usage",ctypes.c_ushort),("UsagePage",ctypes.c_ushort),
        ("InputReportByteLength",ctypes.c_ushort),
        ("OutputReportByteLength",ctypes.c_ushort),
        ("FeatureReportByteLength",ctypes.c_ushort),
        ("Reserved",ctypes.c_ushort*17),
        ("NumberLinkCollectionNodes",ctypes.c_ushort),
        ("NumberInputButtonCaps",ctypes.c_ushort),
        ("NumberInputValueCaps",ctypes.c_ushort),
        ("NumberInputDataIndices",ctypes.c_ushort),
        ("NumberOutputButtonCaps",ctypes.c_ushort),
        ("NumberOutputValueCaps",ctypes.c_ushort),
        ("NumberOutputDataIndices",ctypes.c_ushort),
        ("NumberFeatureButtonCaps",ctypes.c_ushort),
        ("NumberFeatureValueCaps",ctypes.c_ushort),
        ("NumberFeatureDataIndices",ctypes.c_ushort),
    ]


class OVERLAPPED(ctypes.Structure):
    _fields_=[
        ("Internal",ctypes.c_size_t),
        ("InternalHigh",ctypes.c_size_t),
        ("Offset",wintypes.DWORD),
        ("OffsetHigh",wintypes.DWORD),
        ("hEvent",wintypes.HANDLE),
    ]


class USB_INTERFACE_DESCRIPTOR(ctypes.Structure):
    _fields_=[
        ("bLength",ctypes.c_ubyte),("bDescriptorType",ctypes.c_ubyte),
        ("bInterfaceNumber",ctypes.c_ubyte),("bAlternateSetting",ctypes.c_ubyte),
        ("bNumEndpoints",ctypes.c_ubyte),("bInterfaceClass",ctypes.c_ubyte),
        ("bInterfaceSubClass",ctypes.c_ubyte),("bInterfaceProtocol",ctypes.c_ubyte),
        ("iInterface",ctypes.c_ubyte),
    ]


class WINUSB_PIPE_INFORMATION(ctypes.Structure):
    _fields_=[
        ("PipeType",ctypes.c_int),
        ("PipeId",ctypes.c_ubyte),
        ("MaximumPacketSize",ctypes.c_ushort),
        ("Interval",ctypes.c_ubyte),
    ]


def _guid(text):
    text=text.strip("{}")
    p=text.split("-")
    g=GUID()
    g.Data1=int(p[0],16)
    g.Data2=int(p[1],16)
    g.Data3=int(p[2],16)
    raw=bytes.fromhex(p[3]+p[4])
    for i,b in enumerate(raw):
        g.Data4[i]=b
    return g


def _physical_key(path):
    low=str(path or "").casefold()
    # Keep the HID instance but discard collection decorations.
    low=re.sub(r"&col[0-9a-f]+","",low)
    return low


class NativeApi:
    def __init__(self):
        if os.name!="nt":
            raise RuntimeError("Switch 2 Pro Windows backend is Windows-only")

        self.hid=ctypes.WinDLL("hid.dll",use_last_error=True)
        self.setupapi=ctypes.WinDLL("setupapi.dll",use_last_error=True)
        self.kernel32=ctypes.WinDLL("kernel32.dll",use_last_error=True)
        self.winusb=ctypes.WinDLL("winusb.dll",use_last_error=True)

        self.hid.HidD_GetHidGuid.argtypes=[ctypes.POINTER(GUID)]
        self.hid.HidD_GetPreparsedData.argtypes=[
            wintypes.HANDLE,ctypes.POINTER(ctypes.c_void_p)
        ]
        self.hid.HidD_GetPreparsedData.restype=wintypes.BOOLEAN
        self.hid.HidD_FreePreparsedData.argtypes=[ctypes.c_void_p]
        self.hid.HidP_GetCaps.argtypes=[
            ctypes.c_void_p,ctypes.POINTER(HIDP_CAPS)
        ]
        self.hid.HidP_GetCaps.restype=ctypes.c_long

        self.setupapi.SetupDiGetClassDevsW.argtypes=[
            ctypes.POINTER(GUID),wintypes.LPCWSTR,
            ctypes.c_void_p,wintypes.DWORD
        ]
        self.setupapi.SetupDiGetClassDevsW.restype=ctypes.c_void_p
        self.setupapi.SetupDiEnumDeviceInterfaces.argtypes=[
            ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(GUID),
            wintypes.DWORD,ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)
        ]
        self.setupapi.SetupDiEnumDeviceInterfaces.restype=wintypes.BOOL
        self.setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes=[
            ctypes.c_void_p,ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
            ctypes.c_void_p,wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p
        ]
        self.setupapi.SetupDiGetDeviceInterfaceDetailW.restype=wintypes.BOOL
        self.setupapi.SetupDiDestroyDeviceInfoList.argtypes=[ctypes.c_void_p]

        self.kernel32.CreateFileW.argtypes=[
            wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,
            wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE
        ]
        self.kernel32.CreateFileW.restype=wintypes.HANDLE
        self.kernel32.CloseHandle.argtypes=[wintypes.HANDLE]
        self.kernel32.ReadFile.argtypes=[
            wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),ctypes.POINTER(OVERLAPPED)
        ]
        self.kernel32.ReadFile.restype=wintypes.BOOL
        self.kernel32.WriteFile.argtypes=[
            wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),ctypes.POINTER(OVERLAPPED)
        ]
        self.kernel32.WriteFile.restype=wintypes.BOOL
        self.kernel32.CreateEventW.argtypes=[
            ctypes.c_void_p,wintypes.BOOL,wintypes.BOOL,wintypes.LPCWSTR
        ]
        self.kernel32.CreateEventW.restype=wintypes.HANDLE
        self.kernel32.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
        self.kernel32.WaitForSingleObject.restype=wintypes.DWORD
        self.kernel32.GetOverlappedResult.argtypes=[
            wintypes.HANDLE,ctypes.POINTER(OVERLAPPED),
            ctypes.POINTER(wintypes.DWORD),wintypes.BOOL
        ]
        self.kernel32.GetOverlappedResult.restype=wintypes.BOOL
        self.kernel32.CancelIoEx.argtypes=[wintypes.HANDLE,ctypes.c_void_p]

        self.winusb.WinUsb_Initialize.argtypes=[
            wintypes.HANDLE,ctypes.POINTER(ctypes.c_void_p)
        ]
        self.winusb.WinUsb_Initialize.restype=wintypes.BOOL
        self.winusb.WinUsb_Free.argtypes=[ctypes.c_void_p]
        self.winusb.WinUsb_QueryInterfaceSettings.argtypes=[
            ctypes.c_void_p,ctypes.c_ubyte,
            ctypes.POINTER(USB_INTERFACE_DESCRIPTOR)
        ]
        self.winusb.WinUsb_QueryInterfaceSettings.restype=wintypes.BOOL
        self.winusb.WinUsb_QueryPipe.argtypes=[
            ctypes.c_void_p,ctypes.c_ubyte,ctypes.c_ubyte,
            ctypes.POINTER(WINUSB_PIPE_INFORMATION)
        ]
        self.winusb.WinUsb_QueryPipe.restype=wintypes.BOOL
        self.winusb.WinUsb_WritePipe.argtypes=[
            ctypes.c_void_p,ctypes.c_ubyte,ctypes.c_void_p,wintypes.ULONG,
            ctypes.POINTER(wintypes.ULONG),ctypes.POINTER(OVERLAPPED)
        ]
        self.winusb.WinUsb_WritePipe.restype=wintypes.BOOL
        self.winusb.WinUsb_ReadPipe.argtypes=[
            ctypes.c_void_p,ctypes.c_ubyte,ctypes.c_void_p,wintypes.ULONG,
            ctypes.POINTER(wintypes.ULONG),ctypes.POINTER(OVERLAPPED)
        ]
        self.winusb.WinUsb_ReadPipe.restype=wintypes.BOOL
        self.winusb.WinUsb_GetOverlappedResult.argtypes=[
            ctypes.c_void_p,ctypes.POINTER(OVERLAPPED),
            ctypes.POINTER(wintypes.ULONG),wintypes.BOOL
        ]
        self.winusb.WinUsb_GetOverlappedResult.restype=wintypes.BOOL
        self.winusb.WinUsb_AbortPipe.argtypes=[ctypes.c_void_p,ctypes.c_ubyte]

    def _enumerate_guid_paths(self,guid):
        info=self.setupapi.SetupDiGetClassDevsW(
            ctypes.byref(guid),None,None,
            DIGCF_PRESENT|DIGCF_DEVICEINTERFACE
        )
        if info in (None,INVALID_HANDLE_VALUE):
            return []
        out=[]
        try:
            idx=0
            while True:
                data=SP_DEVICE_INTERFACE_DATA()
                data.cbSize=ctypes.sizeof(data)
                if not self.setupapi.SetupDiEnumDeviceInterfaces(
                    info,None,ctypes.byref(guid),idx,ctypes.byref(data)
                ):
                    break
                idx+=1
                need=wintypes.DWORD(0)
                self.setupapi.SetupDiGetDeviceInterfaceDetailW(
                    info,ctypes.byref(data),None,0,ctypes.byref(need),None
                )
                if need.value<8 or need.value>65536:
                    continue
                buf=ctypes.create_string_buffer(need.value)
                ctypes.cast(buf,ctypes.POINTER(wintypes.DWORD))[0]=(
                    8 if ctypes.sizeof(ctypes.c_void_p)==8 else 6
                )
                if not self.setupapi.SetupDiGetDeviceInterfaceDetailW(
                    info,ctypes.byref(data),buf,need.value,
                    ctypes.byref(need),None
                ):
                    continue
                try:
                    path=ctypes.wstring_at(ctypes.addressof(buf)+4)
                except Exception:
                    continue
                out.append(path)
        finally:
            self.setupapi.SetupDiDestroyDeviceInfoList(info)
        return out

    def hid_paths(self):
        guid=GUID()
        self.hid.HidD_GetHidGuid(ctypes.byref(guid))
        out=[]
        for path in self._enumerate_guid_paths(guid):
            low=path.casefold()
            if "vid_057e" not in low or "pid_2069" not in low:
                continue
            caps=self.caps(path)
            in_len=int(caps.InputReportByteLength) if caps else 64
            out.append({
                "path":path,
                "in_len":in_len,
                "physical_key":_physical_key(path),
            })
        return out

    def caps(self,path):
        h=self.kernel32.CreateFileW(
            path,0,FILE_SHARE_READ|FILE_SHARE_WRITE,None,
            OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,None
        )
        if h in (None,INVALID_HANDLE_VALUE):
            return None
        try:
            pp=ctypes.c_void_p()
            if not self.hid.HidD_GetPreparsedData(h,ctypes.byref(pp)):
                return None
            try:
                caps=HIDP_CAPS()
                if self.hid.HidP_GetCaps(pp,ctypes.byref(caps))!=HIDP_STATUS_SUCCESS:
                    return None
                return caps
            finally:
                self.hid.HidD_FreePreparsedData(pp)
        finally:
            self.kernel32.CloseHandle(h)

    def open_hid(self,path):
        h=self.kernel32.CreateFileW(
            path,GENERIC_READ|GENERIC_WRITE,
            FILE_SHARE_READ|FILE_SHARE_WRITE,None,
            OPEN_EXISTING,FILE_FLAG_OVERLAPPED,None
        )
        if h in (None,INVALID_HANDLE_VALUE):
            h=self.kernel32.CreateFileW(
                path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,None,
                OPEN_EXISTING,FILE_FLAG_OVERLAPPED,None
            )
        return None if h in (None,INVALID_HANDLE_VALUE) else h

    def close(self,h):
        if h not in (None,INVALID_HANDLE_VALUE):
            self.kernel32.CloseHandle(h)

    def cancel(self,h):
        if h not in (None,INVALID_HANDLE_VALUE):
            try:
                self.kernel32.CancelIoEx(h,None)
            except Exception:
                pass

    def read_hid(self,h,size=64,timeout_ms=300):
        event=self.kernel32.CreateEventW(None,True,False,None)
        if not event:
            return None
        ov=OVERLAPPED()
        ov.hEvent=event
        buf=(ctypes.c_ubyte*max(64,int(size)))()
        got=wintypes.DWORD(0)
        try:
            ok=self.kernel32.ReadFile(
                h,buf,len(buf),ctypes.byref(got),ctypes.byref(ov)
            )
            if ok:
                return bytes(buf[:got.value])
            if ctypes.get_last_error()!=ERROR_IO_PENDING:
                return None
            if self.kernel32.WaitForSingleObject(event,timeout_ms)!=WAIT_OBJECT_0:
                self.kernel32.CancelIoEx(h,ctypes.byref(ov))
                self.kernel32.GetOverlappedResult(
                    h,ctypes.byref(ov),ctypes.byref(got),True
                )
                return None
            if not self.kernel32.GetOverlappedResult(
                h,ctypes.byref(ov),ctypes.byref(got),False
            ):
                return None
            return bytes(buf[:got.value])
        finally:
            self.kernel32.CloseHandle(event)

    def write_hid(self,h,data,timeout_ms=250):
        if not h or not data:return False
        event=self.kernel32.CreateEventW(None,True,False,None)
        if not event:return False
        ov=OVERLAPPED();ov.hEvent=event
        buf=(ctypes.c_ubyte*len(data)).from_buffer_copy(data)
        got=wintypes.DWORD(0)
        try:
            ok=self.kernel32.WriteFile(
                h,buf,len(data),ctypes.byref(got),ctypes.byref(ov)
            )
            if ok:return got.value==len(data)
            if ctypes.get_last_error()!=ERROR_IO_PENDING:return False
            if self.kernel32.WaitForSingleObject(event,timeout_ms)!=WAIT_OBJECT_0:
                try:self.kernel32.CancelIoEx(h,ctypes.byref(ov))
                except Exception:pass
                self.kernel32.WaitForSingleObject(event,50)
                return False
            if not self.kernel32.GetOverlappedResult(
                h,ctypes.byref(ov),ctypes.byref(got),False
            ):return False
            return got.value==len(data)
        finally:self.kernel32.CloseHandle(event)

    def vendor_path(self):
        guid=_guid(WINUSB_IFACE_GUID)
        for path in self._enumerate_guid_paths(guid):
            low=path.casefold()
            if "vid_057e" in low and "pid_2069" in low:
                return path
        return None

    def _bulk_pipes(self,usb):
        desc=USB_INTERFACE_DESCRIPTOR()
        if not self.winusb.WinUsb_QueryInterfaceSettings(usb,0,ctypes.byref(desc)):
            return None,None
        out_pipe=in_pipe=None
        for idx in range(desc.bNumEndpoints):
            pipe=WINUSB_PIPE_INFORMATION()
            if not self.winusb.WinUsb_QueryPipe(usb,0,idx,ctypes.byref(pipe)):
                continue
            if pipe.PipeType!=USBD_PIPE_TYPE_BULK:continue
            if pipe.PipeId&0x80:in_pipe=int(pipe.PipeId)
            else:out_pipe=int(pipe.PipeId)
        return out_pipe,in_pipe


    def _write_bulk(self,usb,pipe,data,timeout_ms=800):
        event=self.kernel32.CreateEventW(None,True,False,None)
        if not event:
            return False
        ov=OVERLAPPED()
        ov.hEvent=event
        buf=(ctypes.c_ubyte*len(data)).from_buffer_copy(data)
        written=wintypes.ULONG(0)
        try:
            ok=self.winusb.WinUsb_WritePipe(
                usb,pipe,buf,len(data),ctypes.byref(written),ctypes.byref(ov)
            )
            if not ok:
                if ctypes.get_last_error()!=ERROR_IO_PENDING:
                    return False
                if self.kernel32.WaitForSingleObject(
                    event,timeout_ms
                )!=WAIT_OBJECT_0:
                    self.winusb.WinUsb_AbortPipe(usb,pipe)
                    self.winusb.WinUsb_GetOverlappedResult(
                        usb,ctypes.byref(ov),ctypes.byref(written),True
                    )
                    return False
                if not self.winusb.WinUsb_GetOverlappedResult(
                    usb,ctypes.byref(ov),ctypes.byref(written),False
                ):
                    return False
            return written.value==len(data)
        finally:
            self.kernel32.CloseHandle(event)

    def _read_bulk(self,usb,pipe,size=64,timeout_ms=120):
        if pipe is None:return b""
        event=self.kernel32.CreateEventW(None,True,False,None)
        if not event:return b""
        ov=OVERLAPPED();ov.hEvent=event
        buf=(ctypes.c_ubyte*max(1,int(size)))();got=wintypes.ULONG(0)
        try:
            ok=self.winusb.WinUsb_ReadPipe(
                usb,pipe,buf,len(buf),ctypes.byref(got),ctypes.byref(ov)
            )
            if not ok:
                if ctypes.get_last_error()!=ERROR_IO_PENDING:return b""
                if self.kernel32.WaitForSingleObject(event,timeout_ms)!=WAIT_OBJECT_0:
                    self.winusb.WinUsb_AbortPipe(usb,pipe)
                    self.winusb.WinUsb_GetOverlappedResult(
                        usb,ctypes.byref(ov),ctypes.byref(got),True
                    );return b""
                if not self.winusb.WinUsb_GetOverlappedResult(
                    usb,ctypes.byref(ov),ctypes.byref(got),False
                ):return b""
            return bytes(buf[:got.value])
        finally:self.kernel32.CloseHandle(event)

    def _run_vendor_sequence(self,usb,out_pipe,in_pipe,sequence):
        replies=0
        for command in sequence:
            if not self._write_bulk(usb,out_pipe,command):return False,replies
            if self._read_bulk(usb,in_pipe,64,120):replies+=1
            time.sleep(0.010)
        return True,replies

    def wake(self,extended=True):
        path=self.vendor_path()
        if not path:return False,"WinUSB MI_01 interface not found"
        h=self.kernel32.CreateFileW(
            path,GENERIC_READ|GENERIC_WRITE,
            FILE_SHARE_READ|FILE_SHARE_WRITE,None,
            OPEN_EXISTING,FILE_FLAG_OVERLAPPED,None
        )
        if h in (None,INVALID_HANDLE_VALUE):
            return False,f"WinUSB CreateFile failed ({ctypes.get_last_error()})"
        usb=ctypes.c_void_p()
        try:
            if not self.winusb.WinUsb_Initialize(h,ctypes.byref(usb)):
                return False,f"WinUsb_Initialize failed ({ctypes.get_last_error()})"
            out_pipe,in_pipe=self._bulk_pipes(usb)
            if out_pipe is None:return False,"WinUSB bulk OUT endpoint not found"
            seq=EXTENDED_INIT_SEQUENCE if extended else BASIC_WAKE_SEQUENCE
            ok,replies=self._run_vendor_sequence(usb,out_pipe,in_pipe,seq)
            if not ok:return False,f"init bulk write failed ({ctypes.get_last_error()})"
            return True,(("0x05 motion+rumble" if extended else "0x09 basic")+f" · OUT 0x{out_pipe:02X} · replies {replies}")
        finally:
            if usb:
                try:self.winusb.WinUsb_Free(usb)
                except Exception:pass
            self.kernel32.CloseHandle(h)



def enumerate_switch2_pro_hid():
    if os.name!="nt":
        return []
    try:
        return NativeApi().hid_paths()
    except Exception:
        return []


def _unpack_pair(report,offset):
    lo=report[offset]
    mid=report[offset+1]
    hi=report[offset+2]
    x=lo|((mid&0x0F)<<8)
    y=(mid>>4)|(hi<<4)
    return x,y


def _norm_axis(raw,endpoints):
    neg,pos=endpoints
    span=(pos-neg) or 1
    v=(2.0*(float(raw)-neg)/span)-1.0
    return max(-1.0,min(1.0,v))


def parse_report09(report):
    if not report or len(report)<12 or report[0]!=REPORT_ID:
        return None

    buttons=set()
    for name,(byte_index,bit) in BUTTON_BITS.items():
        if byte_index<len(report) and ((report[byte_index]>>bit)&1):
            buttons.add(name)

    lx_raw,ly_raw=_unpack_pair(report,6)
    rx_raw,ry_raw=_unpack_pair(report,9)

    # Public mapping normalizes Y as positive-up. SwitchNet's internal axis
    # convention is negative-up / positive-down, hence the sign inversion.
    lx=round(_norm_axis(lx_raw,STICK_CAL["LX"])*32767)
    ly=round(-_norm_axis(ly_raw,STICK_CAL["LY"])*32767)
    rx=round(_norm_axis(rx_raw,STICK_CAL["RX"])*32767)
    ry=round(-_norm_axis(ry_raw,STICK_CAL["RY"])*32767)

    return {
        "buttons":buttons,
        "lx":max(-32768,min(32767,lx)),
        "ly":max(-32768,min(32767,ly)),
        "rx":max(-32768,min(32767,rx)),
        "ry":max(-32768,min(32767,ry)),
        "counter":report[1] if len(report)>1 else 0,
        "marker":report[2] if len(report)>2 else 0,
        "report_id":report[0],
        "extra_buttons":tuple(sorted(
            b for b in buttons if b in ("C","GL","GR")
        )),
    }



EXT_BUTTON_BITS={
    "Y":(5,0),"X":(5,1),"B":(5,2),"A":(5,3),"R":(5,6),"ZR":(5,7),
    "MINUS":(6,0),"PLUS":(6,1),"R3":(6,2),"L3":(6,3),"HOME":(6,4),
    "CAPTURE":(6,5),"C":(6,6),"DOWN":(7,0),"UP":(7,1),
    "RIGHT":(7,2),"LEFT":(7,3),"L":(7,6),"ZL":(7,7),"GR":(8,0),"GL":(8,1),
}
def _s16(d,o):return struct.unpack_from("<h",d,o)[0]
def _u32(d,o):return struct.unpack_from("<I",d,o)[0]
def _unpack_pair_ext(r,o):return r[o]|((r[o+1]&15)<<8),(r[o+1]>>4)|(r[o+2]<<4)

class SensorClock:
    def __init__(self):
        self.sample_count=0;self.first_timestamp=0;self.ready=False
        self.sensor_ts_coeff=10000;self.gyro_coeff=34.8
        self.bias_ready=False
        self.bias_count=0
        self.bias_sum=[0.0,0.0,0.0]
        self.bias=[0.0,0.0,0.0]
        self.bias_target=120
    def reset(self):self.__init__()
    def update(self,ts):
        ts=int(ts)&0xffffffff
        if not ts or self.ready:return
        self.sample_count+=1
        if self.sample_count>=5 and not self.first_timestamp:
            self.first_timestamp=ts;self.sample_count=0;return
        if self.sample_count==100:
            delta=(ts-self.first_timestamp)&0xffffffff
            coeff=(1000*delta)//(self.sample_count*4) if delta else 0
            if coeff and ((coeff+100000)//200000)==5:
                self.sensor_ts_coeff=10000;self.gyro_coeff=34.8;self.ready=True
            elif coeff:
                self.sensor_ts_coeff=10000000000//coeff;self.gyro_coeff=40.0;self.ready=True
            else:self.first_timestamp=0;self.sample_count=0

def _update_gyro_bias(clock,ax,ay,az,gx,gy,gz):
    if clock.bias_ready:
        return

    amag=math.sqrt(float(ax*ax+ay*ay+az*az))
    gmag=math.sqrt(float(gx*gx+gy*gy+gz*gz))

    # Learn only while the pad is genuinely stationary.
    if not (3300.0<=amag<=4900.0 and gmag<=900.0):
        return

    clock.bias_sum[0]+=gx
    clock.bias_sum[1]+=gy
    clock.bias_sum[2]+=gz
    clock.bias_count+=1

    if clock.bias_count>=clock.bias_target:
        clock.bias=[
            clock.bias_sum[0]/clock.bias_count,
            clock.bias_sum[1]/clock.bias_count,
            clock.bias_sum[2]/clock.bias_count,
        ]
        clock.bias_ready=True


def parse_report05(r,clock):
    if not r or len(r)<64 or r[0]!=REPORT_ID_EXTENDED:
        return None

    buttons={n for n,(bi,bit) in EXT_BUTTON_BITS.items() if (r[bi]>>bit)&1}

    lx0,ly0=_unpack_pair_ext(r,11)
    rx0,ry0=_unpack_pair_ext(r,14)

    lx=round(_norm_axis(lx0,STICK_CAL["LX"])*32767)
    ly=round(-_norm_axis(ly0,STICK_CAL["LY"])*32767)
    rx=round(_norm_axis(rx0,STICK_CAL["RX"])*32767)
    ry=round(-_norm_axis(ry0,STICK_CAL["RY"])*32767)

    ts=_u32(r,0x2b)
    clock.update(ts)

    axr,ayr,azr=_s16(r,0x31),_s16(r,0x33),_s16(r,0x35)
    gxr,gyr,gzr=_s16(r,0x37),_s16(r,0x39),_s16(r,0x3b)

    # SwitchNet's console-facing Nintendo motion frame is the same proper
    # controller rotation already validated with Steam Controller and DualSense:
    #
    #   Nintendo X <- source Y
    #   Nintendo Y <- -source X
    #   Nintendo Z <- source Z
    #
    # v1.24.2 intentionally left accel in raw/native coordinates while we
    # isolated the gravity-axis bug. v1.24.3 then rotated only gyro. That left
    # accel and gyro in DIFFERENT frames, so Mario Kart's orientation fusion
    # could still interpret physical pitch as steering.
    #
    # With the user's real stationary raw sample ~= (32,-720,4136), this becomes
    # ~= (-720,-32,4136): gravity remains correctly on Z while X/Y now match
    # every other validated SwitchNet motion backend.
    ax,ay,az=ayr,-axr,azr

    # Gyro uses the exact same proper rotation so accel and gyro describe one
    # coherent rigid-body coordinate frame.
    #
    #   Nintendo X <- source Y
    #   Nintendo Y <- -source X
    #   Nintendo Z <- source Z
    #
    # On real Switch 2 Pro hardware the previous SDL-derived mapping put pitch
    # (front edge up/down) onto Nintendo X, so Mario Kart treated pitch like
    # steering. This rotation moves pitch onto Nintendo Y and puts the physical
    # wheel/roll motion onto Nintendo X as expected.
    raw_gx=float(gyr)
    raw_gy=float(-gxr)
    raw_gz=float(gzr)

    _update_gyro_bias(
        clock,ax,ay,az,
        raw_gx,raw_gy,raw_gz
    )

    corr_gx=raw_gx-clock.bias[0]
    corr_gy=raw_gy-clock.bias[1]
    corr_gz=raw_gz-clock.bias[2]

    scale=(clock.gyro_coeff/32767.0)*(180.0/math.pi)*16.384

    gx=round(corr_gx*scale)
    gy=round(corr_gy*scale)
    gz=round(corr_gz*scale)

    # Remove tiny residual stationary noise without smoothing actual motion.
    if abs(gx)<10:gx=0
    if abs(gy)<10:gy=0
    if abs(gz)<10:gz=0

    clamp=lambda v:max(-32768,min(32767,int(v)))

    return dict(
        buttons=buttons,
        lx=clamp(lx),ly=clamp(ly),
        rx=clamp(rx),ry=clamp(ry),
        lt=65535 if "ZL" in buttons else 0,
        rt=65535 if "ZR" in buttons else 0,
        ax=clamp(ax),ay=clamp(ay),az=clamp(az),
        gx=clamp(gx),gy=clamp(gy),gz=clamp(gz),
        imu_timestamp=((ts*clock.sensor_ts_coeff//10)&0xffffffff if ts else 0),
        imu_ready=clock.ready,
        gyro_bias_ready=clock.bias_ready,
        gyro_bias_samples=clock.bias_count,
        gyro_bias=tuple(round(v,2) for v in clock.bias),
        report_id=5,
        extra_buttons=tuple(sorted(b for b in buttons if b in ("C","GL","GR")))
    )

def encode_hd_rumble(hf,ha,lf,la):
    return bytes([hf&255,((ha>>4)&0xfc)|((hf>>8)&3),((ha>>12)&15)|((lf<<4)&0xf0),(la&0xc0)|((lf>>4)&0x3f),(la>>8)&255])

def build_pro_rumble_frame(counter,low_amp,high_amp):
    low=(max(0,min(65535,int(low_amp or 0)))*RUMBLE_MAX)//65535
    high=(max(0,min(65535,int(high_amp or 0)))*RUMBLE_MAX)//65535
    wave=encode_hd_rumble(RUMBLE_HI_FREQ,high,RUMBLE_LO_FREQ,low)
    f=bytearray(64);f[0]=2;f[1]=0x50|(counter&15);f[2:7]=wave;f[0x11:0x17]=f[1:7]
    return bytes(f)

class Switch2ProReader:
    """Native USB reader for Nintendo Switch 2 Pro Controller 057E:2069."""

    def __init__(self):
        self.api=None
        self.stop_evt=threading.Event()
        self.thread=None
        self.handle=None
        self.lock=threading.Lock()
        self.latest=None
        self.status="Switch 2 Pro USB inactive"
        self.reports=0
        self.errors=0
        self.path=""
        self.wake_attempts=0
        self.last_wake=""
        self.preferred_path=""
        self.preferred_paths=[]
        self.candidate_paths=[]
        self.candidate_index=0
        self.last_report_id=-1
        self.last_report_len=0
        self.last_error=""
        self.extended_mode=True;self.sensor_clock=SensorClock()
        self.rumble_low=0;self.rumble_high=0;self.rumble_counter=0;self.rumble_due=0.0
        self.rumble_writes=0;self.rumble_errors=0;self.last_imu_ready=False

    def start(self,preferred_path="",preferred_paths=None):
        self.stop()
        self.stop_evt.clear()
        self.preferred_path=str(preferred_path or "")
        self.extended_mode=True;self.sensor_clock.reset();self.rumble_due=0.0;self.last_imu_ready=False
        self.preferred_paths=[
            str(p) for p in (preferred_paths or []) if p
        ]
        self.thread=threading.Thread(
            target=self._run,
            name="SwitchNet-Switch2ProUSB",
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.stop_evt.set()
        if self.api and self.handle:
            self.api.cancel(self.handle)
        thread=self.thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(2.5)
        if not thread or not thread.is_alive():
            if self.api and self.handle:
                self.api.close(self.handle)
            self.handle=None
            self.thread=None
        with self.lock:
            self.latest=None
            if not thread or not thread.is_alive():
                self.status="Switch 2 Pro USB inactive"

    def snapshot(self):
        with self.lock:
            return {
                "state":dict(self.latest) if self.latest else None,
                "status":self.status,
                "reports":self.reports,
                "errors":self.errors,
                "path":self.path,
                "wake_attempts":self.wake_attempts,
                "last_wake":self.last_wake,
                "extended_mode":self.extended_mode,"imu_ready":self.last_imu_ready,
                "gyro_bias_ready":self.sensor_clock.bias_ready,
                "gyro_bias_samples":self.sensor_clock.bias_count,
                "gyro_bias":tuple(round(v,2) for v in self.sensor_clock.bias),
                "rumble_writes":self.rumble_writes,"rumble_errors":self.rumble_errors,
                "rumble_low":self.rumble_low,"rumble_high":self.rumble_high,
            }

    def rumble(self,left,right):
        with self.lock:
            self.rumble_low=max(0,min(65535,int(left or 0)));self.rumble_high=max(0,min(65535,int(right or 0)))
        return bool(self.handle)

    def _send_rumble_if_due(self,handle,force=False):
        now=time.monotonic()
        if not force and now<self.rumble_due:return
        with self.lock:low,high=self.rumble_low,self.rumble_high
        if not force and not low and not high and self.rumble_due==0:return
        if self.api.write_hid(handle,build_pro_rumble_frame(self.rumble_counter,low,high),120):
            self.rumble_writes+=1;self.rumble_counter=(self.rumble_counter+1)&15
        else:self.rumble_errors+=1
        self.rumble_due=now+RUMBLE_INTERVAL_S


    def _refresh_candidates(self):
        devices=self.api.hid_paths()
        if not devices:
            self.candidate_paths=[]
            self.candidate_index=0
            return []

        preferred_set={
            p.casefold() for p in self.preferred_paths
        }
        if self.preferred_path:
            preferred_set.add(self.preferred_path.casefold())

        def rank(d):
            preferred=(
                1 if d["path"].casefold() in preferred_set
                else 0
            )
            return (preferred,int(d.get("in_len",0) or 0))

        self.candidate_paths=sorted(
            devices,key=rank,reverse=True
        )
        self.candidate_index=0
        return self.candidate_paths

    def _next_candidate(self):
        if not self.candidate_paths:
            self._refresh_candidates()
        if not self.candidate_paths:
            return None
        d=self.candidate_paths[
            self.candidate_index % len(self.candidate_paths)
        ]
        self.candidate_index=(
            self.candidate_index+1
        ) % len(self.candidate_paths)
        return d


    def _run(self):
        try:
            self.api=NativeApi()
        except Exception as exc:
            self.last_error=str(exc)
            with self.lock:
                self.status=f"Switch 2 Pro backend unavailable: {exc}"
            return

        while not self.stop_evt.is_set():
            candidates=self._refresh_candidates()
            if not candidates:
                with self.lock:
                    self.latest=None
                    self.status="Switch 2 Pro USB not connected"
                self.stop_evt.wait(0.5)
                continue

            self.wake_attempts+=1
            ok,detail=self.api.wake(extended=self.extended_mode)
            self.last_wake=detail

            if not ok:
                self.last_error=detail
                with self.lock:
                    self.latest=None
                    self.status=f"Switch 2 Pro WinUSB init failed: {detail}"
                self.stop_evt.wait(0.5)
                continue

            with self.lock:
                self.status=(
                    f"Switch 2 Pro WinUSB init OK · "
                    f"probing {len(candidates)} HID collection(s)"
                )

            self.stop_evt.wait(0.22)
            if self.stop_evt.is_set():
                break

            found_state=False

            for idx in range(len(candidates)):
                if self.stop_evt.is_set():
                    break

                device=self._next_candidate()
                if not device:
                    break

                self.path=device["path"]
                in_len=max(64,int(device.get("in_len",64) or 64))
                handle=self.api.open_hid(self.path)

                if not handle:
                    self.errors+=1
                    self.last_error=(
                        f"HID open failed "
                        f"{idx+1}/{len(candidates)}"
                    )
                    continue

                self.handle=handle
                invalid_count=0
                started=time.monotonic()

                try:
                    with self.lock:
                        self.status="Initializing Switch 2 Pro USB"

                    while (
                        not self.stop_evt.is_set() and
                        time.monotonic()-started<1.0
                    ):
                        report=self.api.read_hid(
                            handle,in_len,180
                        )
                        if not report:
                            continue

                        self.last_report_id=report[0]
                        self.last_report_len=len(report)

                        packet=(report[1:] if len(report)>=2 and report[0]==0 and report[1] in (REPORT_ID_EXTENDED,REPORT_ID) else report)
                        parsed=(parse_report05(packet,self.sensor_clock) if packet and packet[0]==REPORT_ID_EXTENDED else parse_report09(packet))

                        if parsed is None:
                            invalid_count+=1
                            continue

                        found_state=True
                        last_valid=time.monotonic()

                        with self.lock:
                            self.latest=parsed
                            self.last_imu_ready=bool(parsed.get("imu_ready",False))
                            self.reports+=1
                            self.status="Switch 2 Pro USB active"

                        # Lock onto the real state interface.
                        while not self.stop_evt.is_set():
                            self._send_rumble_if_due(handle)
                            report=self.api.read_hid(
                                handle,in_len,350
                            )
                            if not report:
                                if time.monotonic()-last_valid>0.9:
                                    break
                                continue

                            self.last_report_id=report[0]
                            self.last_report_len=len(report)

                            packet=(report[1:] if len(report)>=2 and report[0]==0 and report[1] in (REPORT_ID_EXTENDED,REPORT_ID) else report)
                            parsed=(parse_report05(packet,self.sensor_clock) if packet and packet[0]==REPORT_ID_EXTENDED else parse_report09(packet))

                            if parsed is None:
                                continue

                            last_valid=time.monotonic()
                            with self.lock:
                                self.latest=parsed
                                self.reports+=1

                        break

                except Exception as exc:
                    self.errors+=1
                    self.last_error=str(exc)
                    with self.lock:
                        self.status=(
                            f"Switch 2 Pro HID "
                            f"{idx+1}/{len(candidates)} error: {exc}"
                        )
                finally:
                    if handle:
                        with self.lock:ol,oh=self.rumble_low,self.rumble_high;self.rumble_low=self.rumble_high=0
                        for _ in range(3):
                            self._send_rumble_if_due(handle,force=True);time.sleep(0.010)
                        with self.lock:self.rumble_low,self.rumble_high=ol,oh
                    self.api.cancel(handle);self.api.close(handle);self.handle=None;self.rumble_due=0.0

                if found_state:
                    break

                with self.lock:
                    rid=(
                        f"0x{self.last_report_id:02X}"
                        if self.last_report_id>=0 else "none"
                    )
                    self.status="Initializing Switch 2 Pro USB"

            if not found_state:
                rid=(f"0x{self.last_report_id:02X}" if self.last_report_id>=0 else "none")
                mode="extended 0x05" if self.extended_mode else "basic 0x09"
                self.last_error=f"no state in {mode} · last {rid} · len {self.last_report_len}"
                with self.lock:
                    self.latest=None;self.status="Switch 2 Pro initialized but no state stream · "+self.last_error
                self.extended_mode=not self.extended_mode;self.sensor_clock.reset()

            if not self.stop_evt.is_set():
                self.stop_evt.wait(0.35)
