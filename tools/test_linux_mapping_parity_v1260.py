#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
linux=(root/"client-python-linux"/"switchnet_client.py").read_text()

assert '("c","C"),("gl","GL"),("gr","GR")' in linux
assert "default_linux_mapping" in linux
assert "apply_switch_mapping" in linux
assert "mapping=controller_mapping" in linux
assert "family=controller_family" in linux
assert '"controller_mapping":controller_mapping' in linux
assert '"controller_family":family' in linux

# Roster/hot-plug Linux stability logic retained.
assert "SYN_DROPPED" in linux
assert "_controller_missing_counts" in linux
assert "_controller_seen_counts" in linux
assert "roster_target_from_boundary" in linux
assert "EVDEV_HOLD_GRACE_S" in linux

print("OK: Linux mapping profiles integrate with existing evdev stability path")
