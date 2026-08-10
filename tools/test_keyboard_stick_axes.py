#!/usr/bin/env python3

def axis(keys, neg_key, pos_key):
    return (32767 if pos_key in keys else 0) - (32767 if neg_key in keys else 0)

def left_stick(keys):
    lx = axis(keys, "A", "D")
    ly = axis(keys, "W", "S")
    return lx, ly

assert left_stick({"W"}) == (0, -32767)
assert left_stick({"S"}) == (0, 32767)
assert left_stick({"A"}) == (-32767, 0)
assert left_stick({"D"}) == (32767, 0)
assert left_stick({"W","D"}) == (32767, -32767)

print("OK: W=left-stick up, S=left-stick down")
