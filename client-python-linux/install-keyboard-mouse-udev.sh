#!/usr/bin/env bash
set -euo pipefail
RULE=/etc/udev/rules.d/72-switchnet-keyboard-mouse.rules

sudo tee "$RULE" >/dev/null <<'EOF'
# SwitchNet keyboard/mouse controller.
# Grant the active local desktop user access through systemd-logind/uaccess.
SUBSYSTEM=="input", KERNEL=="event*", ENV{ID_INPUT_KEYBOARD}=="1", TAG+="uaccess"
SUBSYSTEM=="input", KERNEL=="event*", ENV{ID_INPUT_MOUSE}=="1", TAG+="uaccess"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=input
echo "Installed $RULE"
echo "Log out/in or reconnect the keyboard/mouse if the current ACL does not refresh immediately."
