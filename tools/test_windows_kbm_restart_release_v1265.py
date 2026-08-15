#!/usr/bin/env python3
"""Regression guards for Windows KBM Stop/Start and UDP slot release."""
from pathlib import Path
import struct
import zlib

root=Path(__file__).resolve().parents[1]
client=(root/'client-python-windows'/'switchnet_client.py').read_text()
kbm=(root/'client-python-windows'/'keyboard_mouse_backend.py').read_text()
proto=(root/'src'/'SwitchNetProtocol.h').read_text()
udp=(root/'src'/'UdpServer.cpp').read_text()
decoder_h=(root/'src'/'PacketDecoder.h').read_text()
decoder_cpp=(root/'src'/'PacketDecoder.cpp').read_text()

# Correct slot must be preserved for shutdown neutral packets.
assert 'make_packet(neutral, session, seq, 0, slot)' in client
assert 'PACKET_FLAG_CONTROLLER_DISCONNECT = 0x0002' in client
assert 'PACKET_FLAG_CONTROLLER_DISCONNECT,' in client

# Worker lifecycle must refuse an overlapping replacement worker.
assert 'if not self.stop():' in client
assert 'Previous controller worker did not stop cleanly' in client
assert 'return False' in client[client.index('class Worker:'):client.index('class POINT')]

# KBM lifecycle must retain a live native-hook thread instead of forgetting it.
assert 'self.lifecycle_lock=threading.RLock()' in kbm
assert 'if self.thread is thread and not alive:' in kbm
assert 'Keyboard+Mouse cleanup still in progress' in kbm

# Keyboard+Mouse follows the same P1/P2 roster priority as physical devices.
assert 'indices=list(range(len(slots)))' in client
assert 'list(range(2,len(slots))) if d.get("virtual")' not in client

# Protocol release is explicit and exact-owner only.
assert 'ControllerDisconnect = 1U << 1' in proto
assert 'std::uint16_t& packetFlags' in decoder_h
assert 'packetFlags = packet.header.flags;' in decoder_cpp
assert 'decodedFlags & SwitchNetProtocol::ControllerDisconnect' in udp
assert 'remoteIp == client.ip' in udp
assert 'remotePort == client.port' in udp
assert 'decodedSessionId == client.sessionId' in udp
assert 'disconnectClient(controllerSlot);' in udp

# Wire compatibility: release only occupies a previously unused low flag bit.
def packet(slot, release=False):
    flags=(0x0100 if slot == 1 else 0) | (0x0002 if release else 0)
    payload=bytes(36)
    header=struct.pack('<IBBHHHIII',0x544E5753,3,1,24,36,flags,7,8,9)
    body=header+payload
    return body+struct.pack('<I',zlib.crc32(body)&0xffffffff)

for slot in (0,1):
    pkt=packet(slot,True)
    flags=struct.unpack_from('<H',pkt,10)[0]
    assert flags & 0x0002
    assert bool(flags & 0x0100) == bool(slot)
    assert len(pkt)==64
    assert (zlib.crc32(pkt[:-4])&0xffffffff)==struct.unpack_from('<I',pkt,60)[0]

print('OK: Windows KBM lifecycle, roster priority, shutdown slot and explicit UDP release guarded')
