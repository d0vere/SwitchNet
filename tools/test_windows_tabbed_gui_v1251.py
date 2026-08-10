#!/usr/bin/env python3
from pathlib import Path

root=Path(__file__).resolve().parents[1]
client=(root/"client-python-windows"/"switchnet_client.py").read_text()

assert 'ttk.Notebook(root' in client
for name in ("Controllers","Mappings","Network","Extra","Diagnostics"):
    assert f'text="{name}"' in client

assert 'text="SwitchNet Client",font=("Segoe UI",18,"bold")' not in client
assert 'text="Manage blacklist…"' in client
assert "def open_blacklist_dialog" in client

assert "def toggle_service" in client
assert 'text="Start"' in client
assert 'text="Stop" if running else "Start"' in client
assert 'fill="#2e7d32" if running else "#c62828"' in client

assert 'text="Wake Switch 2"' in client
assert 'text="Hide to tray"' in client
assert 'text="Close"' in client

# Discovery belongs to Network, not the persistent action bar.
assert 'text="Discover SwitchNet"' in client

# Confirm requested clean build policy is retained.
bat=(root/"client-python-windows"/"build-exe.bat").read_text()
assert 'rmdir /s /q "%~dp0build"' in bat
assert 'rmdir /s /q "%~dp0dist"' in bat
assert 'del /f /q "%~dp0SwitchNetClient.spec"' in bat

print("OK: v1.25.1 tabbed GUI structure and fixed status bar")
