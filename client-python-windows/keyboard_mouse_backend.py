from __future__ import annotations
import ctypes, threading, math, time
from ctypes import wintypes

# Portable Win32 handle aliases.
# Some Python/PyInstaller runtimes do not expose all HANDLE typedefs through
# ctypes.wintypes (notably HCURSOR/HICON/HBRUSH/HRAWINPUT).
HANDLE_T = ctypes.c_void_p
HWND_T = ctypes.c_void_p
HINSTANCE_T = ctypes.c_void_p
HICON_T = ctypes.c_void_p
HCURSOR_T = ctypes.c_void_p
HBRUSH_T = ctypes.c_void_p
HRAWINPUT_T = ctypes.c_void_p

KEYBOARD_ACTIONS = (
    ("LS_UP", "Left Stick Up"), ("LS_DOWN", "Left Stick Down"),
    ("LS_LEFT", "Left Stick Left"), ("LS_RIGHT", "Left Stick Right"),
    ("ZL", "ZL"), ("ZR", "ZR"),
    ("DPAD_UP", "D-Pad Up"), ("DPAD_DOWN", "D-Pad Down"),
    ("DPAD_LEFT", "D-Pad Left"), ("DPAD_RIGHT", "D-Pad Right"),
    ("L", "L"), ("R", "R"), ("X", "X"), ("Y", "Y"), ("B", "B"), ("A", "A"),
    ("L3", "L3"), ("R3", "R3"), ("PLUS", "+"), ("MINUS", "-"),
    ("CAPTURE", "Capture"), ("HOME", "Home"),
)
DEFAULT_KEYBOARD_MAPPING = {
    "LS_UP":"W","LS_DOWN":"S","LS_LEFT":"A","LS_RIGHT":"D",
    "ZL":"Q","ZR":"O",
    "DPAD_UP":"UP","DPAD_DOWN":"DOWN","DPAD_LEFT":"LEFT","DPAD_RIGHT":"RIGHT",
    "L":"E","R":"U","X":"I","Y":"J","B":"K","A":"L",
    "L3":"X","R3":"M","PLUS":"Y","MINUS":"T","CAPTURE":"G","HOME":"B",
}
KEYBOARD_KEY_CHOICES = tuple(
    [chr(ord("A")+i) for i in range(26)] +
    [str(i) for i in range(10)] +
    ["UP","DOWN","LEFT","RIGHT","SPACE","ENTER","TAB","BACKSPACE","ESC",
     "LEFT_SHIFT","RIGHT_SHIFT","LEFT_CTRL","RIGHT_CTRL","LEFT_ALT","RIGHT_ALT"] +
    [f"F{i}" for i in range(1,13)] +
    ["COMMA","PERIOD","SEMICOLON","APOSTROPHE","MINUS_KEY","EQUAL"]
)


RELEASE_KEY_CHOICES = tuple(f"F{i}" for i in range(1,13))
DEFAULT_RELEASE_KEY = "F10"

def normalized_release_key(value):
    value=str(value or DEFAULT_RELEASE_KEY).upper()
    return value if value in RELEASE_KEY_CHOICES else DEFAULT_RELEASE_KEY

def mapping_without_release_conflict(mapping, release_key):
    out=normalized_keyboard_mapping(mapping)
    release_key=normalized_release_key(release_key)
    for action,_label in KEYBOARD_ACTIONS:
        if out.get(action)==release_key:
            out[action]=DEFAULT_KEYBOARD_MAPPING[action]
    return out

class MouseStickFilter:
    """Short velocity memory for converting sparse REL mouse events to a stick."""
    def __init__(self):
        self.x=0.0
        self.y=0.0
        self.last_update=time.monotonic()

    def reset(self):
        self.x=0.0
        self.y=0.0
        self.last_update=time.monotonic()

    def update(self,dx,dy):
        now=time.monotonic()
        dt=max(0.0,min(0.100,now-self.last_update))
        self.last_update=now

        decay=math.exp(-dt/0.055)
        self.x*=decay
        self.y*=decay

        dx=float(dx or 0.0)
        dy=float(dy or 0.0)
        if dx or dy:
            self.x=self.x*0.30+dx
            self.y=self.y*0.30+dy

        if abs(self.x)<0.015:self.x=0.0
        if abs(self.y)<0.015:self.y=0.0
        return self.x,self.y

def normalized_keyboard_mapping(mapping):
    out=dict(DEFAULT_KEYBOARD_MAPPING)
    if isinstance(mapping,dict):
        for action,_label in KEYBOARD_ACTIONS:
            value=str(mapping.get(action,out[action]) or out[action]).upper()
            if value in KEYBOARD_KEY_CHOICES:
                out[action]=value
    return out

def keyboard_mouse_values(keys_down, mouse_dx, mouse_dy, mapping, mouse_sensitivity,
                          BTN_A, BTN_B, BTN_X, BTN_Y, BTN_L, BTN_R,
                          BTN_BACK, BTN_START, BTN_LS, BTN_RS, BTN_GUIDE, BTN_CAPTURE):
    mapping=normalized_keyboard_mapping(mapping)
    keys=set(keys_down or ())
    def pressed(action): return mapping[action] in keys
    def axis(neg,pos): return (32767 if pressed(pos) else 0) - (32767 if pressed(neg) else 0)
    out=0
    for action,bit in (
        ("A",BTN_A),("B",BTN_B),("X",BTN_X),("Y",BTN_Y),
        ("L",BTN_L),("R",BTN_R),("MINUS",BTN_BACK),("PLUS",BTN_START),
        ("L3",BTN_LS),("R3",BTN_RS),("HOME",BTN_GUIDE),("CAPTURE",BTN_CAPTURE),
    ):
        if pressed(action): out|=bit
    u,d,l,r=(pressed("DPAD_UP"),pressed("DPAD_DOWN"),pressed("DPAD_LEFT"),pressed("DPAD_RIGHT"))
    if u and r:hat=1
    elif r and d:hat=3
    elif d and l:hat=5
    elif l and u:hat=7
    elif u:hat=0
    elif r:hat=2
    elif d:hat=4
    elif l:hat=6
    else:hat=8
    sens=max(100,min(20000,int(mouse_sensitivity)))
    return dict(
        buttons=out,lx=axis("LS_LEFT","LS_RIGHT"),ly=axis("LS_UP","LS_DOWN"),
        rx=max(-32768,min(32767,round(float(mouse_dx)*sens))),
        ry=max(-32768,min(32767,round(float(mouse_dy)*sens))),
        lt=65535 if pressed("ZL") else 0,rt=65535 if pressed("ZR") else 0,hat=hat,
        ax=0,ay=0,az=4096,gx=0,gy=0,gz=0,imu_ts=0,
    )


VK={**{chr(ord("A")+i):ord("A")+i for i in range(26)},
    **{str(i):ord("0")+i for i in range(10)},
    "UP":0x26,"DOWN":0x28,"LEFT":0x25,"RIGHT":0x27,"SPACE":0x20,"ENTER":0x0D,
    "TAB":0x09,"BACKSPACE":0x08,"ESC":0x1B,"LEFT_SHIFT":0xA0,"RIGHT_SHIFT":0xA1,
    "LEFT_CTRL":0xA2,"RIGHT_CTRL":0xA3,"LEFT_ALT":0xA4,"RIGHT_ALT":0xA5,
    **{f"F{i}":0x6F+i for i in range(1,13)},
    "COMMA":0xBC,"PERIOD":0xBE,"SEMICOLON":0xBA,"APOSTROPHE":0xDE,
    "MINUS_KEY":0xBD,"EQUAL":0xBB}
VK_TO_KEY={v:k for k,v in VK.items()}
WH_KEYBOARD_LL=13; WH_MOUSE_LL=14; HC_ACTION=0
WM_KEYDOWN=0x100; WM_KEYUP=0x101; WM_SYSKEYDOWN=0x104; WM_SYSKEYUP=0x105
WM_MOUSEMOVE=0x200; WM_QUIT=0x12
_MOUSE_MESSAGES={0x200,0x201,0x202,0x204,0x205,0x207,0x208,0x20A,0x20B,0x20C,0x20E}
LRESULT=ctypes.c_ssize_t
HOOKPROC=ctypes.WINFUNCTYPE(LRESULT,ctypes.c_int,wintypes.WPARAM,wintypes.LPARAM)

class POINT(ctypes.Structure):_fields_=[("x",wintypes.LONG),("y",wintypes.LONG)]
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_=[("vkCode",wintypes.DWORD),("scanCode",wintypes.DWORD),("flags",wintypes.DWORD),
              ("time",wintypes.DWORD),("dwExtraInfo",ctypes.c_void_p)]
class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_=[("pt",POINT),("mouseData",wintypes.DWORD),("flags",wintypes.DWORD),
              ("time",wintypes.DWORD),("dwExtraInfo",ctypes.c_void_p)]


WM_INPUT=0x00FF
WM_CREATE=0x0001
WM_DESTROY=0x0002
RIM_TYPEMOUSE=0
RID_INPUT=0x10000003
RIDEV_INPUTSINK=0x00000100
RIDEV_NOLEGACY=0x00000030
HID_USAGE_PAGE_GENERIC=0x01
HID_USAGE_GENERIC_MOUSE=0x02

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_=[
        ("usUsagePage",wintypes.USHORT),
        ("usUsage",wintypes.USHORT),
        ("dwFlags",wintypes.DWORD),
        ("hwndTarget",HWND_T),
    ]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_=[
        ("dwType",wintypes.DWORD),
        ("dwSize",wintypes.DWORD),
        ("hDevice",wintypes.HANDLE),
        ("wParam",wintypes.WPARAM),
    ]

class RAWMOUSEBUTTONS(ctypes.Structure):
    _fields_=[
        ("usButtonFlags",wintypes.USHORT),
        ("usButtonData",wintypes.USHORT),
    ]

class RAWMOUSEUNION(ctypes.Union):
    _fields_=[
        ("ulButtons",wintypes.ULONG),
        ("buttons",RAWMOUSEBUTTONS),
    ]

class RAWMOUSE(ctypes.Structure):
    _anonymous_=("u",)
    _fields_=[
        ("usFlags",wintypes.USHORT),
        ("u",RAWMOUSEUNION),
        ("ulRawButtons",wintypes.ULONG),
        ("lLastX",wintypes.LONG),
        ("lLastY",wintypes.LONG),
        ("ulExtraInformation",wintypes.ULONG),
    ]

class RAWINPUTUNION(ctypes.Union):
    _fields_=[("mouse",RAWMOUSE)]

class RAWINPUT(ctypes.Structure):
    _anonymous_=("data",)
    _fields_=[("header",RAWINPUTHEADER),("data",RAWINPUTUNION)]

WNDPROC=ctypes.WINFUNCTYPE(
    LRESULT,HWND_T,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM
)

class WNDCLASSW(ctypes.Structure):
    _fields_=[
        ("style",wintypes.UINT),
        ("lpfnWndProc",WNDPROC),
        ("cbClsExtra",ctypes.c_int),
        ("cbWndExtra",ctypes.c_int),
        ("hInstance",HINSTANCE_T),
        ("hIcon",HICON_T),
        ("hCursor",HCURSOR_T),
        ("hbrBackground",HBRUSH_T),
        ("lpszMenuName",wintypes.LPCWSTR),
        ("lpszClassName",wintypes.LPCWSTR),
    ]


class WindowsKeyboardMouseReader:
    def __init__(self):
        self.user32=ctypes.windll.user32; self.kernel32=ctypes.windll.kernel32
        self.user32.SetWindowsHookExW.argtypes=[ctypes.c_int,HOOKPROC,ctypes.c_void_p,wintypes.DWORD]
        self.user32.SetWindowsHookExW.restype=ctypes.c_void_p
        self.user32.CallNextHookEx.argtypes=[ctypes.c_void_p,ctypes.c_int,wintypes.WPARAM,wintypes.LPARAM]
        self.user32.CallNextHookEx.restype=LRESULT
        self.user32.UnhookWindowsHookEx.argtypes=[ctypes.c_void_p]
        self.user32.PostThreadMessageW.argtypes=[wintypes.DWORD,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
        self.kernel32.GetModuleHandleW.restype=ctypes.c_void_p
        self.user32.RegisterClassW.argtypes=[ctypes.POINTER(WNDCLASSW)]
        self.user32.RegisterClassW.restype=wintypes.WORD
        self.user32.CreateWindowExW.argtypes=[
            wintypes.DWORD,wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.DWORD,
            ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,
            HWND_T,HANDLE_T,HINSTANCE_T,ctypes.c_void_p
        ]
        self.user32.CreateWindowExW.restype=HWND_T
        self.user32.DestroyWindow.argtypes=[HWND_T]
        self.user32.DestroyWindow.restype=wintypes.BOOL
        self.user32.DefWindowProcW.argtypes=[
            HWND_T,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM
        ]
        self.user32.DefWindowProcW.restype=LRESULT
        self.user32.RegisterRawInputDevices.argtypes=[
            ctypes.POINTER(RAWINPUTDEVICE),wintypes.UINT,wintypes.UINT
        ]
        self.user32.RegisterRawInputDevices.restype=wintypes.BOOL
        self.user32.GetRawInputData.argtypes=[
            HRAWINPUT_T,wintypes.UINT,ctypes.c_void_p,
            ctypes.POINTER(wintypes.UINT),wintypes.UINT
        ]
        self.user32.GetRawInputData.restype=wintypes.UINT
        self.user32.DefWindowProcW.restype=LRESULT
        self.thread=None; self.thread_id=0; self.ready=threading.Event(); self.stop_evt=threading.Event()
        self.lock=threading.Lock(); self.keys_down=set(); self.mouse_dx=0; self.mouse_dy=0
        self.last_mouse=None; self.exclusive_active=False; self.status="inactive"
        self.keyboard_hook=None; self.mouse_hook=None; self._kbd_cb=None; self._mouse_cb=None
        self.release_key=DEFAULT_RELEASE_KEY
        self.mouse_filter=MouseStickFilter()
        self.controller_enabled=True
        self.exclusive_requested=True
        self.raw_hwnd=None
        self._wndproc=None
        self._window_class_name=f"SwitchNetRawMouse_{id(self):x}"

    def start(self,mapping=None,exclusive=True,release_key=DEFAULT_RELEASE_KEY):
        self.stop(); self.release_key=normalized_release_key(release_key)
        self.mapping=mapping_without_release_conflict(mapping,self.release_key)
        self.requested=bool(exclusive)
        self.exclusive_requested=bool(exclusive)
        self.controller_enabled=True
        self.mouse_filter.reset()
        self.stop_evt.clear(); self.ready.clear()
        self.thread=threading.Thread(target=self._run,name="SwitchNet-KBM-Hooks",daemon=True)
        self.thread.start(); self.ready.wait(2.0)
        return bool(self.keyboard_hook and self.mouse_hook)

    def _set_toggle_state(self,enabled):
        self.controller_enabled=bool(enabled)
        if not self.controller_enabled:
            with self.lock:
                self.keys_down.clear()
                self.mouse_dx=0
                self.mouse_dy=0
                self.mouse_filter.reset()
            self.exclusive_active=False
            self.status=f"Keyboard+Mouse OFF · {self.release_key} toggles ON"
        else:
            self.exclusive_active=bool(
                self.exclusive_requested and
                self.keyboard_hook and self.mouse_hook
            )
            self.status=(
                f"Keyboard+Mouse ON · exclusive · {self.release_key} toggles OFF"
                if self.exclusive_active else
                f"Keyboard+Mouse ON · background · {self.release_key} toggles OFF"
            )

    def _run(self):
        self.thread_id=self.kernel32.GetCurrentThreadId()
        mapped={VK.get(v) for v in self.mapping.values()}
        mapped.discard(None)

        @HOOKPROC
        def kbd(nCode,wParam,lParam):
            if nCode==HC_ACTION:
                info=ctypes.cast(
                    lParam,ctypes.POINTER(KBDLLHOOKSTRUCT)
                ).contents
                vk=int(info.vkCode)
                key=VK_TO_KEY.get(vk)
                down=int(wParam) in (WM_KEYDOWN,WM_SYSKEYDOWN)
                up=int(wParam) in (WM_KEYUP,WM_SYSKEYUP)

                if key and (down or up):
                    # Release key is observed even while the controller is OFF.
                    if key==self.release_key and down:
                        self._set_toggle_state(not self.controller_enabled)
                        return 1

                    if self.controller_enabled:
                        with self.lock:
                            if down:
                                self.keys_down.add(key)
                            else:
                                self.keys_down.discard(key)
                        if self.exclusive_active and vk in mapped:
                            return 1

            return self.user32.CallNextHookEx(
                None,nCode,wParam,lParam
            )

        @HOOKPROC
        def mouse_hook(nCode,wParam,lParam):
            # Mouse motion is read from WM_INPUT, not screen coordinates.
            # The low-level hook exists only to suppress legacy mouse messages
            # while exclusive Keyboard+Mouse mode is ON.
            if (
                nCode==HC_ACTION and
                self.controller_enabled and
                self.exclusive_active and
                int(wParam) in _MOUSE_MESSAGES
            ):
                return 1

            return self.user32.CallNextHookEx(
                None,nCode,wParam,lParam
            )

        @WNDPROC
        def wndproc(hwnd,msg,wParam,lParam):
            if msg==WM_INPUT:
                size=wintypes.UINT(0)
                header_size=ctypes.sizeof(RAWINPUTHEADER)
                self.user32.GetRawInputData(
                    lParam,RID_INPUT,None,
                    ctypes.byref(size),header_size
                )
                if size.value:
                    buf=ctypes.create_string_buffer(size.value)
                    got=self.user32.GetRawInputData(
                        lParam,RID_INPUT,buf,
                        ctypes.byref(size),header_size
                    )
                    if got!=0xFFFFFFFF:
                        raw=ctypes.cast(
                            buf,ctypes.POINTER(RAWINPUT)
                        ).contents
                        if (
                            raw.header.dwType==RIM_TYPEMOUSE and
                            self.controller_enabled
                        ):
                            with self.lock:
                                self.mouse_dx+=int(raw.mouse.lLastX)
                                self.mouse_dy+=int(raw.mouse.lLastY)
                return 0

            return self.user32.DefWindowProcW(
                hwnd,msg,wParam,lParam
            )

        self._kbd_cb=kbd
        self._mouse_cb=mouse_hook
        self._wndproc=wndproc

        hmod=self.kernel32.GetModuleHandleW(None)

        wc=WNDCLASSW()
        wc.lpfnWndProc=self._wndproc
        wc.hInstance=hmod
        wc.lpszClassName=self._window_class_name
        self.user32.RegisterClassW(ctypes.byref(wc))

        # Message-only/raw-input target. A tiny hidden top-level window works
        # across Python/Win32 versions more reliably than HWND_MESSAGE here.
        hwnd=self.user32.CreateWindowExW(
            0,self._window_class_name,"SwitchNet Raw Mouse",
            0,0,0,0,0,None,None,hmod,None
        )
        self.raw_hwnd=hwnd

        if hwnd:
            rid=RAWINPUTDEVICE(
                HID_USAGE_PAGE_GENERIC,
                HID_USAGE_GENERIC_MOUSE,
                RIDEV_INPUTSINK,
                hwnd,
            )
            self.user32.RegisterRawInputDevices(
                ctypes.byref(rid),1,ctypes.sizeof(rid)
            )

        self.keyboard_hook=self.user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,self._kbd_cb,hmod,0
        )
        self.mouse_hook=self.user32.SetWindowsHookExW(
            WH_MOUSE_LL,self._mouse_cb,hmod,0
        )

        self.controller_enabled=True
        self.exclusive_active=bool(
            self.requested and
            self.keyboard_hook and
            self.mouse_hook
        )
        self.status=(
            f"Keyboard+Mouse ON · exclusive · raw mouse · "
            f"{self.release_key} toggles OFF"
            if self.exclusive_active else
            f"Keyboard+Mouse ON · background · raw mouse · "
            f"{self.release_key} toggles OFF"
        )
        self.ready.set()

        msg=ctypes.create_string_buffer(64)
        while (
            not self.stop_evt.is_set() and
            self.user32.GetMessageW(
                ctypes.byref(msg),None,0,0
            )>0
        ):
            self.user32.TranslateMessage(ctypes.byref(msg))
            self.user32.DispatchMessageW(ctypes.byref(msg))

        for hook in (self.keyboard_hook,self.mouse_hook):
            if hook:
                try:
                    self.user32.UnhookWindowsHookEx(hook)
                except Exception:
                    pass

        if self.raw_hwnd:
            try:
                self.user32.DestroyWindow(self.raw_hwnd)
            except Exception:
                pass

        self.keyboard_hook=None
        self.mouse_hook=None
        self.raw_hwnd=None
        self.controller_enabled=False
        self.exclusive_active=False
        self.status="inactive"

    def consume(self):
        with self.lock:
            enabled=bool(self.controller_enabled)
            if enabled:
                keys=set(self.keys_down)
                dx=self.mouse_dx
                dy=self.mouse_dy
            else:
                keys=set()
                dx=0
                dy=0
            self.mouse_dx=self.mouse_dy=0

        if enabled:
            fx,fy=self.mouse_filter.update(dx,dy)
        else:
            self.mouse_filter.reset()
            fx=fy=0.0

        return (
            keys,fx,fy,
            self.status,self.exclusive_active,enabled
        )

    def stop(self):
        self.stop_evt.set()
        if self.thread_id:
            try:self.user32.PostThreadMessageW(self.thread_id,WM_QUIT,0,0)
            except Exception:pass
        if self.thread and self.thread.is_alive() and self.thread is not threading.current_thread():
            self.thread.join(2.0)
        self.thread=None; self.thread_id=0
