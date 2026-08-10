#!/usr/bin/env python3

def target(source,boundary,count):
    boundary=max(0,min(boundary,count))
    t=boundary-(1 if boundary>source else 0)
    return max(0,min(t,count-1))

# Upward drags.
assert target(3,0,4)==0
assert target(3,1,4)==1
assert target(2,0,4)==0
assert target(2,1,4)==1

# Downward drags.
assert target(0,2,4)==1
assert target(0,3,4)==2
assert target(0,4,4)==3
assert target(1,4,4)==3

# Dropping around own row is a no-op.
assert target(1,1,4)==1
assert target(1,2,4)==1

print("OK: symmetric drag target mapping")
