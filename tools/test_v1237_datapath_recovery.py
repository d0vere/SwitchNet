#!/usr/bin/env python3
import ast
from pathlib import Path

root=Path(__file__).resolve().parents[1]
client=(root/"client-python-windows"/"switchnet_client.py").read_text()
backend=(root/"client-python-windows"/"switch2_pro_windows.py").read_text()
bat=(root/"client-python-windows"/"build-exe.bat").read_text()

# One canonical Switch 2 Pro roster key regardless of collection count.
assert '"switch2pro:057e:2069"' in client
assert "stable identity" in client
assert "switch2_candidates" in client

# Network datapath essentials remain.
assert "sock.sendto(data, dst)" in client
assert "data = make_packet(payload, session, seq, us, slot)" in client
assert "payload = pack_payload(vals)" in client

# Switch2 worker gets all candidate paths.
assert "preferred_paths=controller_paths" in client
assert "def start(self,preferred_path=\"\",preferred_paths=None)" in backend

# Clean build.
assert 'rmdir /s /q "%~dp0build"' in bat
assert 'rmdir /s /q "%~dp0dist"' in bat
assert 'del /f /q "%~dp0SwitchNetClient.spec"' in bat

print("OK: stable Switch2 identity and recovered common UDP datapath")
