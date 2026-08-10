#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
linux=(root/"client-python-linux"/"switchnet_client.py").read_text()
windows=(root/"client-python-windows"/"switchnet_client.py").read_text()

for text in (linux,windows):
    assert "schedule_service_restart" in text
    assert "_perform_scheduled_service_restart" in text
    assert "controller connected/removed" in text
    assert "controller roster reordered" in text
    assert "controller blacklisted" in text
    assert "controller restored" in text

assert "self._service_restart_timer.start(350)" in linux
assert "350,self._perform_scheduled_service_restart" in windows
print("OK: roster changes trigger debounced full service restart on both clients")
