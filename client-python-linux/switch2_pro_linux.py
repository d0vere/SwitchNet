from __future__ import annotations
import json, math, os, re, select, struct, subprocess, sys, threading, time
from pathlib import Path

NINTENDO_VID=0x057E
SWITCH2_PRO_PID=0x2069
REPORT_ID=0x09
REPORT_ID_EXTENDED=0x05
RUMBLE_MAX=29000
RUMBLE_HI_FREQ=0x187
RUMBLE_LO_FREQ=0x112

BUTTON_BITS={
"A":(3,1),"B":(3,0),"X":(3,3),"Y":(3,2),"UP":(4,3),"DOWN":(4,0),
"LEFT":(4,2),"RIGHT":(4,1),"L":(4,4),"R":(3,4),"ZL":(4,5),"ZR":(3,5),
"MINUS":(4,6),"PLUS":(3,6),"L3":(4,7),"R3":(3,7),"HOME":(5,0),
"CAPTURE":(5,1),"GR":(5,2),"GL":(5,3),"C":(5,4),
}
EXT_BUTTON_BITS={
"Y":(5,0),"X":(5,1),"B":(5,2),"A":(5,3),"R":(5,6),"ZR":(5,7),
"MINUS":(6,0),"PLUS":(6,1),"R3":(6,2),"L3":(6,3),"HOME":(6,4),
"CAPTURE":(6,5),"C":(6,6),"DOWN":(7,0),"UP":(7,1),"RIGHT":(7,2),
"LEFT":(7,3),"L":(7,6),"ZL":(7,7),"GR":(8,0),"GL":(8,1),
}
STICK_CAL={"LX":(437,3582),"LY":(661,3670),"RX":(628,3656),"RY":(471,3626)}

def _props(entry):
    try:text=(entry/"device"/"uevent").read_text(errors="ignore")
    except Exception:return {}
    return dict(line.split("=",1) for line in text.splitlines() if "=" in line)

def _anchor(props,path):
    uniq=(props.get("HID_UNIQ","") or "").strip()
    phys=(props.get("HID_PHYS","") or "").strip()
    if uniq:return "uniq:"+uniq
    if phys:return "phys:"+re.sub(r"/input\d+$","",phys)
    return "path:"+str(Path(path).parent)

def enumerate_switch2_pro_hidraw():
    groups={}
    for entry in sorted(Path("/sys/class/hidraw").glob("hidraw*")):
        props=_props(entry);parts=(props.get("HID_ID","") or "").split(":")
        if len(parts)!=3:continue
        try:vid=int(parts[1],16);pid=int(parts[2],16)
        except Exception:continue
        if (vid,pid)!=(NINTENDO_VID,SWITCH2_PRO_PID):continue
        path=f"/dev/{entry.name}";anchor=_anchor(props,path)
        groups.setdefault(anchor,[]).append(path)
    return [
        {"key":f"switch2pro:057e:2069:{a}","name":"Nintendo Switch 2 Pro Controller",
         "anchor":a,"paths":sorted(set(paths))}
        for a,paths in sorted(groups.items())
    ]

def _norm(raw,endpoints):
    lo,hi=endpoints;span=(hi-lo) or 1
    return max(-1.0,min(1.0,(2.0*(float(raw)-lo)/span)-1.0))
def _pair(r,o):return r[o]|((r[o+1]&15)<<8),(r[o+1]>>4)|(r[o+2]<<4)
def _s16(d,o):return struct.unpack_from("<h",d,o)[0]
def _u32(d,o):return struct.unpack_from("<I",d,o)[0]

class SensorClock:
    def __init__(self):self.reset()
    def reset(self):
        self.sample_count=0;self.first_timestamp=0;self.ready=False
        self.sensor_ts_coeff=10000;self.gyro_coeff=34.8
        self.bias_ready=False;self.bias_count=0
        self.bias_sum=[0.0,0.0,0.0];self.bias=[0.0,0.0,0.0];self.bias_target=120
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

def _bias(clock,ax,ay,az,gx,gy,gz):
    if clock.bias_ready:return
    amag=math.sqrt(float(ax*ax+ay*ay+az*az));gmag=math.sqrt(float(gx*gx+gy*gy+gz*gz))
    if not (3300<=amag<=4900 and gmag<=900):return
    for i,v in enumerate((gx,gy,gz)):clock.bias_sum[i]+=v
    clock.bias_count+=1
    if clock.bias_count>=clock.bias_target:
        clock.bias=[x/clock.bias_count for x in clock.bias_sum];clock.bias_ready=True

def parse_report09(r):
    if not r or len(r)<12 or r[0]!=REPORT_ID:return None
    buttons={n for n,(bi,bit) in BUTTON_BITS.items() if bi<len(r) and ((r[bi]>>bit)&1)}
    lx0,ly0=_pair(r,6);rx0,ry0=_pair(r,9);cl=lambda v:max(-32768,min(32767,int(v)))
    return dict(buttons=buttons,lx=cl(round(_norm(lx0,STICK_CAL["LX"])*32767)),
        ly=cl(round(-_norm(ly0,STICK_CAL["LY"])*32767)),
        rx=cl(round(_norm(rx0,STICK_CAL["RX"])*32767)),
        ry=cl(round(-_norm(ry0,STICK_CAL["RY"])*32767)),
        lt=65535 if "ZL" in buttons else 0,rt=65535 if "ZR" in buttons else 0,
        ax=0,ay=0,az=4096,gx=0,gy=0,gz=0,imu_timestamp=0,imu_ready=False,report_id=9)

def parse_report05(r,clock):
    if not r or len(r)<64 or r[0]!=REPORT_ID_EXTENDED:return None
    buttons={n for n,(bi,bit) in EXT_BUTTON_BITS.items() if ((r[bi]>>bit)&1)}
    lx0,ly0=_pair(r,11);rx0,ry0=_pair(r,14)
    lx=round(_norm(lx0,STICK_CAL["LX"])*32767);ly=round(-_norm(ly0,STICK_CAL["LY"])*32767)
    rx=round(_norm(rx0,STICK_CAL["RX"])*32767);ry=round(-_norm(ry0,STICK_CAL["RY"])*32767)
    ts=_u32(r,0x2b);clock.update(ts)
    axr,ayr,azr=_s16(r,0x31),_s16(r,0x33),_s16(r,0x35)
    gxr,gyr,gzr=_s16(r,0x37),_s16(r,0x39),_s16(r,0x3b)
    ax,ay,az=ayr,-axr,azr;raw_gx,raw_gy,raw_gz=float(gyr),float(-gxr),float(gzr)
    _bias(clock,ax,ay,az,raw_gx,raw_gy,raw_gz)
    scale=(clock.gyro_coeff/32767.0)*(180.0/math.pi)*16.384
    gx=round((raw_gx-clock.bias[0])*scale);gy=round((raw_gy-clock.bias[1])*scale);gz=round((raw_gz-clock.bias[2])*scale)
    if abs(gx)<10:gx=0
    if abs(gy)<10:gy=0
    if abs(gz)<10:gz=0
    cl=lambda v:max(-32768,min(32767,int(v)))
    return dict(buttons=buttons,lx=cl(lx),ly=cl(ly),rx=cl(rx),ry=cl(ry),
        lt=65535 if "ZL" in buttons else 0,rt=65535 if "ZR" in buttons else 0,
        ax=cl(ax),ay=cl(ay),az=cl(az),gx=cl(gx),gy=cl(gy),gz=cl(gz),
        imu_timestamp=((ts*clock.sensor_ts_coeff//10)&0xffffffff if ts else 0),
        imu_ready=clock.ready,gyro_bias_ready=clock.bias_ready,
        gyro_bias_samples=clock.bias_count,report_id=5)

def encode_hd_rumble(hf,ha,lf,la):
    return bytes([hf&255,((ha>>4)&0xfc)|((hf>>8)&3),((ha>>12)&15)|((lf<<4)&0xf0),
                  (la&0xc0)|((lf>>4)&0x3f),(la>>8)&255])
def build_pro_rumble_frame(counter,low_amp,high_amp):
    low=(max(0,min(65535,int(low_amp or 0)))*RUMBLE_MAX)//65535
    high=(max(0,min(65535,int(high_amp or 0)))*RUMBLE_MAX)//65535
    wave=encode_hd_rumble(RUMBLE_HI_FREQ,high,RUMBLE_LO_FREQ,low)
    f=bytearray(64);f[0]=2;f[1]=0x50|(counter&15);f[2:7]=wave;f[0x11:0x17]=f[1:7]
    return bytes(f)

class Switch2ProHidraw:
    def __init__(self):
        self.fd=None;self.path="";self.status="Switch 2 Pro HIDRaw inactive"
        self.latest=None;self.reports=0;self.errors=0;self.last_report_at=0.0
        self.clock=SensorClock();self.rumble_counter=0;self.lock=threading.Lock()
        self.extended_seen=False;self.last_init=""
        self.helper=Path(__file__).resolve().with_name("switch2_pro_usb_init.py")
    def close(self):
        if self.fd is not None:
            try:self.rumble(0,0)
            except Exception:pass
            try:os.close(self.fd)
            except Exception:pass
        self.fd=None;self.path="";self.latest=None;self.last_report_at=0.0;self.extended_seen=False
    def _init(self):
        try:
            r=subprocess.run([sys.executable,str(self.helper),"--extended"],capture_output=True,text=True,timeout=8,check=False)
            out=(r.stdout or "").strip();payload={}
            if out:
                try:payload=json.loads(out.splitlines()[-1])
                except Exception:pass
            self.last_init=payload.get("message") or payload.get("error") or (r.stderr or out).strip()
            return r.returncode==0 and bool(payload.get("ok"))
        except Exception as exc:self.last_init=str(exc);return False
    @staticmethod
    def _packet(r):
        return r[1:] if len(r)>=2 and r[0]==0 and r[1] in (5,9) else r
    def _parse(self,r):
        p=self._packet(r)
        if not p:return None
        if p[0]==5:
            x=parse_report05(p,self.clock);self.extended_seen=self.extended_seen or x is not None;return x
        if p[0]==9:return parse_report09(p)
        return None
    def _paths(self,preferred):
        out=[]
        for x in preferred or []:
            if x and x not in out:out.append(str(x))
        for d in enumerate_switch2_pro_hidraw():
            for x in d["paths"]:
                if x not in out:out.append(x)
        return out
    def connect(self,preferred=None):
        self.close();self.status="Initializing Switch 2 Pro native USB";self._init();time.sleep(.30)
        for path in self._paths(preferred):
            fd=None
            try:
                try:fd=os.open(path,os.O_RDWR|os.O_NONBLOCK)
                except OSError:fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK)
                started=time.monotonic();self.clock=SensorClock()
                while time.monotonic()-started<1.0:
                    ready,_,_=select.select([fd],[],[],0.12)
                    if not ready:continue
                    try:r=os.read(fd,128)
                    except BlockingIOError:continue
                    st=self._parse(r)
                    if st is None:continue
                    self.fd=fd;self.path=path;self.latest=st;self.reports+=1;self.last_report_at=time.monotonic()
                    self.status="Switch 2 Pro HIDRaw active · "+("0x05 motion" if st.get("report_id")==5 else "0x09 basic")
                    return True
                os.close(fd)
            except Exception as exc:
                self.errors+=1;self.status=f"HIDRaw probe failed: {exc}"
                if fd is not None:
                    try:os.close(fd)
                    except Exception:pass
        self.status="Switch 2 Pro initialized but no native HID state stream";return False
    def poll(self,max_batches=8):
        if self.fd is None:return 0
        count=0
        try:
            for _ in range(max_batches):
                try:r=os.read(self.fd,128)
                except BlockingIOError:break
                if not r:break
                st=self._parse(r)
                if st is None:continue
                self.latest=st;self.reports+=1;count+=1;self.last_report_at=time.monotonic()
                self.status="Switch 2 Pro HIDRaw active · "+("0x05 motion" if st.get("report_id")==5 else "0x09 basic")
            return count
        except OSError as exc:self.errors+=1;self.status=f"HIDRaw read error: {exc}";self.close();return 0
    def snapshot(self):
        age=-1 if not self.last_report_at else max(0,int((time.monotonic()-self.last_report_at)*1000))
        return dict(state=dict(self.latest) if self.latest else None,status=self.status,reports=self.reports,
                    errors=self.errors,path=self.path,input_age_ms=age,extended_seen=self.extended_seen,last_init=self.last_init)
    def rumble(self,left,right):
        if self.fd is None:return False
        frame=build_pro_rumble_frame(self.rumble_counter,left,right)
        try:
            with self.lock:n=os.write(self.fd,frame)
            if n!=64:return False
            self.rumble_counter=(self.rumble_counter+1)&15;return True
        except OSError:return False
