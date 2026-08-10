#!/usr/bin/env python3

STATE_IDS={0x01,0x09,0x0A,0x0B,0x0C}

def probe_sequence(collections):
    """Model collection failover after 12 invalid reports."""
    chosen=None
    for name,reports in collections:
        invalid=0
        for rid in reports:
            if rid in STATE_IDS:
                chosen=name
                break
            invalid+=1
            if invalid>=12:
                break
        if chosen:
            break
    return chosen

bad=[0x02]*12
good=[0x01,0x01]
assert probe_sequence([
    ("collection0",bad),
    ("collection1",bad),
    ("collection2",good),
    ("collection3",bad),
])=="collection2"

assert probe_sequence([
    ("collection0",[0x09]),
])=="collection0"

print("OK: Steam collection probe rejects non-state HID collections")
