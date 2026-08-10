#!/usr/bin/env python3

def roster_move(slots, source, target, minimum_slots=4):
    out=list(slots)
    while len(out)<minimum_slots:
        out.append("")
    source=int(source); target=int(target)
    if source<0 or target<0 or source>=len(out) or target>=len(out):
        return out
    if source==target:
        return out
    value=out.pop(source)
    out.insert(target,value)
    while len(out)<minimum_slots:
        out.append("")
    return out

# User's examples / required semantics.
assert roster_move(["steam","dualsense","",""],1,2) == [
    "steam","","dualsense",""
]
assert roster_move(["steam","dualsense","",""],1,0) == [
    "dualsense","steam","",""
]
assert roster_move(["steam","dualsense","stadia",""],2,0) == [
    "stadia","steam","dualsense",""
]

# Up then Down round-trip.
a=["steam","dualsense","stadia",""]
b=roster_move(a,1,0)
c=roster_move(b,0,1)
assert c==a

# None slots are real positions.
assert roster_move(["steam","","dualsense",""],2,1) == [
    "steam","dualsense","",""
]

print("OK: controller roster move semantics")
