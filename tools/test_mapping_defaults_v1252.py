#!/usr/bin/env python3
from pathlib import Path

root=Path(__file__).resolve().parents[1]
text=(root/"client-python-windows"/"switchnet_client.py").read_text()

# Default behavior preservation checks.
assert '"cross":"B","circle":"A","square":"Y","triangle":"X"' in text
assert 'face=label_face if labels else positional_face' in text
assert '"a":"A","b":"B","x":"X","y":"Y"' in text
assert '"assistant":"None","capture":"CAPTURE"' in text
assert '"c":"None"' in text
assert '"lt":"ZL","rt":"ZR"' in text

# Analog trigger strength is retained when mapped to ZL/ZR.
assert '{"l2":lt_strength,"r2":rt_strength}' in text
assert '{"lt":lt_strength,"rt":rt_strength}' in text

print("OK: default mappings preserve current behavior and trigger strength")
