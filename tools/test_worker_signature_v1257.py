#!/usr/bin/env python3
import ast
from pathlib import Path

root=Path(__file__).resolve().parents[1]
path=root/"client-python-windows"/"switchnet_client.py"
text=path.read_text()
tree=ast.parse(text)

worker=None
for node in tree.body:
    if isinstance(node,ast.ClassDef) and node.name=="Worker":
        worker=node
        break
assert worker is not None

methods={
    node.name:node
    for node in worker.body
    if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))
}

for name in ("start","_run_guarded","run"):
    assert name in methods

def positional_names(fn):
    return [a.arg for a in fn.args.posonlyargs+fn.args.args][1:]  # drop self

start_names=positional_names(methods["start"])
guard_names=positional_names(methods["_run_guarded"])
run_names=positional_names(methods["run"])

expected=[
    "host","port","rate","index","dz","labels","backend",
    "steam_mapping","steam_gyro_trim","switch2_rear_mapping",
    "controller_mapping","slot","controller_path","controller_paths",
    "keyboard_mapping","keyboard_exclusive","keyboard_release_key",
    "mouse_sensitivity",
]

assert start_names==expected, start_names
assert guard_names==expected, guard_names
assert run_names==expected, run_names

# Validate the explicit forwarding call from _run_guarded() to self.run().
run_call=None
for node in ast.walk(methods["_run_guarded"]):
    if (
        isinstance(node,ast.Call)
        and isinstance(node.func,ast.Attribute)
        and isinstance(node.func.value,ast.Name)
        and node.func.value.id=="self"
        and node.func.attr=="run"
    ):
        run_call=node
        break

assert run_call is not None
forwarded=[
    arg.id
    for arg in run_call.args
    if isinstance(arg,ast.Name)
]
assert forwarded==expected, forwarded

assert 'APP_VERSION = "1.25.7"' in text
print("OK: Worker.start/_run_guarded/run signatures are synchronized")
