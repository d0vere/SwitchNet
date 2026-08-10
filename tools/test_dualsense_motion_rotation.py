#!/usr/bin/env python3

def linux_transform(ax,ay,az,gx,gy,gz):
    # Values are already normalized to their source physical units here.
    return (+ay,-ax,+az,+gy,-gx,+gz)

def windows_reference(ax,ay,az,gx,gy,gz):
    # Existing Windows DualSense mapping:
    # Switch X <- +Sony Y; Switch Y <- -Sony X; Switch Z <- +Sony Z.
    return (+ay,-ax,+az,+gy,-gx,+gz)

samples = [
    (0,0,8192, 0,0,0),
    (8192,0,0, 1024,0,0),
    (0,8192,0, 0,1024,0),
    (-4096,2048,7000, -512,256,128),
]
for sample in samples:
    assert linux_transform(*sample) == windows_reference(*sample)

# Neutral physical pose must not introduce a lateral component merely because
# Sony X/Y were left unrotated.
assert linux_transform(0,0,8192,0,0,0) == (0,0,8192,0,0,0)

print("OK: Linux DualSense rotation matches Windows reference")
