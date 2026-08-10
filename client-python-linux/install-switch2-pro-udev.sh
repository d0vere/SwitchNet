#!/usr/bin/env bash
set -euo pipefail

RULE=/etc/udev/rules.d/50-switchnet-switch2-pro.rules

sudo tee "$RULE" >/dev/null <<'EOF'
# SwitchNet - Nintendo Switch 2 Pro Controller USB access
SUBSYSTEM=="usb", ATTR{idVendor}=="057e", ATTR{idProduct}=="2069", MODE="0666", TAG+="uaccess"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="057e", ATTRS{idProduct}=="2069", MODE="0666", TAG+="uaccess"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger

echo "Installed $RULE"
echo "Unplug and reconnect the Switch 2 Pro Controller."
