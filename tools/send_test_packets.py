#!/usr/bin/env python3
"""Send SwitchNet Protocol v3 packets at a configurable rate."""

from __future__ import annotations

import argparse
import random
import socket
import struct
import time
import zlib

MAGIC = 0x544E5753
VERSION = 3
PACKET_TYPE_CONTROLLER = 1
HEADER_SIZE = 24
PAYLOAD_SIZE = 36
FLAGS = 0

HEADER = struct.Struct("<IBBHHHIII")
STATE = struct.Struct("<IhhhhHHB3xhhhhhhI")
CRC = struct.Struct("<I")
PACKET_SIZE = HEADER.size + STATE.size + CRC.size


def make_packet(
    session_id: int,
    sequence: int,
    timestamp_us: int,
    left_x: int,
) -> bytes:
    header = HEADER.pack(
        MAGIC,
        VERSION,
        PACKET_TYPE_CONTROLLER,
        HEADER_SIZE,
        PAYLOAD_SIZE,
        FLAGS,
        session_id,
        sequence,
        timestamp_us,
    )

    state = STATE.pack(
        0,       # buttons
        left_x,
        0,       # leftY
        0,       # rightX
        0,       # rightY
        0,       # left trigger
        0,       # right trigger
        8,       # hat neutral
        0, 0, 4096,  # accelerometer: stationary, +1g Z
        0, 0, 0,     # gyroscope
        timestamp_us,
    )

    body = header + state
    checksum = zlib.crc32(body) & 0xFFFFFFFF
    return body + CRC.pack(checksum)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("host", help="SwitchNet's IP, ex.192.168.0.53")
    parser.add_argument("--port", type=int, default=5454)
    parser.add_argument("--rate", type=float, default=250.0)
    parser.add_argument(
        "--corrupt-every",
        type=int,
        default=0,
        help="corrompe ogni N pacchetti per verificare il CRC",
    )
    args = parser.parse_args()

    if args.rate <= 0:
        raise SystemExit("--rate deve essere maggiore di zero")

    period = 1.0 / args.rate
    sequence = 0
    session_id = random.getrandbits(32)
    started = time.perf_counter()
    next_send = started

    print(
        f"SwitchNet Protocol v{VERSION}, packet={PACKET_SIZE} byte, "
        f"session=0x{session_id:08x}"
    )

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        print(f"Sending to {args.host}:{args.port} at {args.rate:g} Hz. Ctrl+C to stop.")

        try:
            while True:
                now = time.perf_counter()
                phase = int((now - started) * 2.0) & 1
                left_x = 16000 if phase else -16000
                timestamp_us = int((now - started) * 1_000_000) & 0xFFFFFFFF

                packet = bytearray(
                    make_packet(session_id, sequence, timestamp_us, left_x)
                )

                if args.corrupt_every > 0 and sequence > 0:
                    if sequence % args.corrupt_every == 0:
                        packet[HEADER_SIZE] ^= 0x01

                sock.sendto(packet, (args.host, args.port))
                sequence = (sequence + 1) & 0xFFFFFFFF
                next_send += period

                delay = next_send - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
                else:
                    next_send = time.perf_counter()
        except KeyboardInterrupt:
            print("\nTest terminato.")


if __name__ == "__main__":
    main()
