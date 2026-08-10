from __future__ import annotations
import threading
import math
import time
try:
    from evdev import InputDevice, ecodes, list_devices
except ImportError:
    InputDevice=None; ecodes=None; list_devices=None

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


_LINUX_KEYS={}
if ecodes:
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        _LINUX_KEYS[c]=getattr(ecodes,f"KEY_{c}")
    for c in "0123456789":
        _LINUX_KEYS[c]=getattr(ecodes,f"KEY_{c}")
    _LINUX_KEYS.update({
        "UP":ecodes.KEY_UP,"DOWN":ecodes.KEY_DOWN,"LEFT":ecodes.KEY_LEFT,"RIGHT":ecodes.KEY_RIGHT,
        "SPACE":ecodes.KEY_SPACE,"ENTER":ecodes.KEY_ENTER,"TAB":ecodes.KEY_TAB,
        "BACKSPACE":ecodes.KEY_BACKSPACE,"ESC":ecodes.KEY_ESC,
        "LEFT_SHIFT":ecodes.KEY_LEFTSHIFT,"RIGHT_SHIFT":ecodes.KEY_RIGHTSHIFT,
        "LEFT_CTRL":ecodes.KEY_LEFTCTRL,"RIGHT_CTRL":ecodes.KEY_RIGHTCTRL,
        "LEFT_ALT":ecodes.KEY_LEFTALT,"RIGHT_ALT":ecodes.KEY_RIGHTALT,
        **{f"F{i}":getattr(ecodes,f"KEY_F{i}") for i in range(1,13)},
        "COMMA":ecodes.KEY_COMMA,"PERIOD":ecodes.KEY_DOT,"SEMICOLON":ecodes.KEY_SEMICOLON,
        "APOSTROPHE":ecodes.KEY_APOSTROPHE,"MINUS_KEY":ecodes.KEY_MINUS,"EQUAL":ecodes.KEY_EQUAL,
    })
_CODE_TO_KEY={v:k for k,v in _LINUX_KEYS.items()}

class LinuxKeyboardMouseReader:
    def __init__(self):
        self.devices=[]; self.keys_down=set(); self.mouse_dx=0; self.mouse_dy=0
        self.exclusive_active=False; self.status="inactive"; self.lock=threading.Lock(); self.reports=0
        self.release_key=DEFAULT_RELEASE_KEY
        self.mouse_filter=MouseStickFilter()
        self.controller_enabled=True
        self.exclusive_requested=True

    @staticmethod
    def _is_keyboard(dev):
        try:
            keys=set(dev.capabilities(absinfo=False).get(ecodes.EV_KEY,[]))
            return {ecodes.KEY_W,ecodes.KEY_A,ecodes.KEY_S,ecodes.KEY_D}.issubset(keys)
        except Exception:return False

    @staticmethod
    def _is_mouse(dev):
        try:
            rel=set(dev.capabilities(absinfo=False).get(ecodes.EV_REL,[]))
            return ecodes.REL_X in rel and ecodes.REL_Y in rel
        except Exception:return False

    def start(self,exclusive=True,release_key=DEFAULT_RELEASE_KEY):
        self.close()
        self.release_key=normalized_release_key(release_key)
        self.exclusive_requested=bool(exclusive)
        self.controller_enabled=True
        self.mouse_filter.reset()
        if InputDevice is None:
            self.status="python-evdev unavailable"; return False
        opened=[]
        for path in sorted(list_devices() or []):
            dev=None
            try:
                dev=InputDevice(path)
                kind="keyboard" if self._is_keyboard(dev) else "mouse" if self._is_mouse(dev) else ""
                if not kind:
                    dev.close(); continue
                opened.append((dev,kind))
            except Exception:
                if dev is not None:
                    try:dev.close()
                    except Exception:pass
        if not opened:
            self.status="No keyboard/mouse evdev devices accessible"; return False

        grabbed=[]
        if exclusive:
            try:
                for dev,_kind in opened:
                    dev.grab(); grabbed.append(dev)
            except Exception as exc:
                for dev in grabbed:
                    try:dev.ungrab()
                    except Exception:pass
                grabbed=[]
                self.status=f"Exclusive capture unavailable: {exc}"

        self.devices=opened
        self.exclusive_active=bool(grabbed) and len(grabbed)==len(opened)
        self.keys_down=set()
        for dev,kind in opened:
            if kind!="keyboard":continue
            try:
                for code in dev.active_keys():
                    key=_CODE_TO_KEY.get(code)
                    if key:self.keys_down.add(key)
            except Exception:pass
        if self.exclusive_active:self.status=f"exclusive capture · {len(opened)} devices · {self.release_key} releases"
        elif not self.status.startswith("Exclusive"):self.status=f"background capture · {len(opened)} devices"
        return True

    def _set_toggle_state(self,enabled):
        enabled=bool(enabled)

        if not enabled:
            for dev,_kind in list(self.devices):
                try:
                    dev.ungrab()
                except Exception:
                    pass

            self.controller_enabled=False
            self.exclusive_active=False
            self.keys_down.clear()
            self.mouse_dx=self.mouse_dy=0
            self.mouse_filter.reset()
            self.status=(
                f"Keyboard+Mouse OFF · "
                f"{self.release_key} toggles ON"
            )
            return

        grabbed=[]
        if self.exclusive_requested:
            try:
                for dev,_kind in self.devices:
                    dev.grab()
                    grabbed.append(dev)
            except Exception as exc:
                for dev in grabbed:
                    try:
                        dev.ungrab()
                    except Exception:
                        pass
                grabbed=[]
                self.status=(
                    f"Keyboard+Mouse ON · background · "
                    f"grab failed: {exc}"
                )

        self.controller_enabled=True
        self.exclusive_active=(
            bool(grabbed) and
            len(grabbed)==len(self.devices)
        )

        if self.exclusive_active:
            self.status=(
                f"Keyboard+Mouse ON · exclusive · "
                f"{self.release_key} toggles OFF"
            )
        elif not self.status.startswith("Keyboard+Mouse ON"):
            self.status=(
                f"Keyboard+Mouse ON · background · "
                f"{self.release_key} toggles OFF"
            )


    def poll(self):
        count=0
        toggle=False
        for dev,kind in list(self.devices):
            try:
                while True:
                    try:events=dev.read()
                    except BlockingIOError:break
                    for ev in events:
                        if ev.type==ecodes.EV_KEY and kind=="keyboard":
                            key=_CODE_TO_KEY.get(ev.code)
                            if key:
                                if key==self.release_key and ev.value==1:
                                    toggle=True
                                elif self.controller_enabled:
                                    if ev.value:
                                        self.keys_down.add(key)
                                    else:
                                        self.keys_down.discard(key)
                            count+=1
                        elif (
                            ev.type==ecodes.EV_REL and
                            kind=="mouse" and
                            self.controller_enabled
                        ):
                            if ev.code==ecodes.REL_X:
                                self.mouse_dx+=int(ev.value)
                            elif ev.code==ecodes.REL_Y:
                                self.mouse_dy+=int(ev.value)
                            count+=1
            except OSError:pass
        if toggle:
            self._set_toggle_state(
                not self.controller_enabled
            )
        self.reports+=count
        return count

    def consume(self):
        enabled=bool(self.controller_enabled)
        if enabled:
            keys=set(self.keys_down)
            dx=self.mouse_dx
            dy=self.mouse_dy
        else:
            keys=set()
            dx=dy=0
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

    def close(self):
        devices=list(self.devices); self.devices=[]; self.keys_down=set()
        self.mouse_dx=self.mouse_dy=0; self.exclusive_active=False
        self.mouse_filter.reset()
        for dev,_kind in devices:
            try:dev.ungrab()
            except Exception:pass
            try:dev.close()
            except Exception:pass
        self.status="inactive"
