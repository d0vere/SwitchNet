#!/usr/bin/env python3
import ast
from pathlib import Path

root=Path(__file__).resolve().parents[1]
src=root/"client-python-windows"/"switchnet_client.py"
text=src.read_text(encoding="utf-8")
tree=ast.parse(text)

fn=next(
    node for node in tree.body
    if isinstance(node,ast.FunctionDef) and node.name=="steam_values"
)
args=[a.arg for a in fn.args.args]
assert args[:5]==["raw","dz","labels","steam_mapping","gyro_trim"], args

expected='steam_values(ss["state"], dz, labels, steam_mapping, steam_gyro_trim)'
assert expected in text, "worker call does not match steam_values signature"

print("OK: Windows steam_values worker contract is aligned")
