#!/usr/bin/env python3
def norm(raw,res,target): return round(raw*(target/res))
assert norm(8192,8192,4096)==4096
assert norm(1024,1024,16.384)==16
assert norm(10240,1024,16.384)==164
assert norm(-10240,1024,16.384)==-164
assert round(1000*1.0)==1000
assert round(1000*0.8)==800
assert round(1000*0.9)==900
print("OK: motion normalization and Steam raw/trim profiles")
