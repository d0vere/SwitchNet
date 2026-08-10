#!/usr/bin/env python3
import ast
from pathlib import Path
h=(Path(__file__).resolve().parents[1]/"client-python-linux"/"switch2_pro_usb_init.py").read_text()
assert "EXTENDED_COMMANDS" in h
assert '"report-05"' in h
assert '"--extended" in sys.argv' in h
assert "for name, command in commands:" in h
ast.parse(h)
print("OK: Linux USB helper extended 0x05 mode")
