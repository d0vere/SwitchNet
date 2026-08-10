#!/usr/bin/env python3
"""Protocol regression test for SwitchNet controller slot flags."""
import struct
import zlib

MAGIC = 0x544E5753
SLOT2 = 0x0100

def packet(slot):
    flags = SLOT2 if slot == 1 else 0
    payload = bytes(36)
    header = struct.pack("<IBBHHHIII", MAGIC, 3, 1, 24, 36, flags, 1, 2, 3)
    body = header + payload
    return body + struct.pack("<I", zlib.crc32(body) & 0xffffffff)

def flags(pkt):
    return struct.unpack_from("<H", pkt, 10)[0]

p1 = packet(0)
p2 = packet(1)
assert flags(p1) == 0x0000, hex(flags(p1))
assert flags(p2) == 0x0100, hex(flags(p2))
assert (zlib.crc32(p1[:-4]) & 0xffffffff) == struct.unpack_from("<I",p1,len(p1)-4)[0]
assert (zlib.crc32(p2[:-4]) & 0xffffffff) == struct.unpack_from("<I",p2,len(p2)-4)[0]
print("OK: P1 flags=0x0000, P2 flags=0x0100, CRC valid")
