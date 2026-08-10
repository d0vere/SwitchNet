#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

OLD_OUTPUT = '''static bool tinyusb_on_set_output(uint8_t report_id, const uint8_t *buffer, uint16_t reqlen) {
  USBHIDDevice *device = tinyusb_get_device_by_report_id(report_id);
  if (device) {
    device->_onOutput(report_id, buffer, reqlen);
    return true;
  }
  return false;
}'''

NEW_OUTPUT = '''static bool tinyusb_on_set_output(uint8_t report_id, const uint8_t *buffer, uint16_t reqlen) {
  USBHIDDevice *device = tinyusb_get_device_by_report_id(report_id);
  // SwitchNet compatibility: esp_hid_parse_report_map() in ESP32 Arduino Core
  // 3.3.x can omit vendor-defined OUTPUT-only report IDs from the routing map.
  // When exactly one HID device is registered, safely route unmatched reports
  // to that device. This preserves normal multi-device routing semantics.
  if (!device && tinyusb_loaded_hid_devices_num == 1) {
    device = tinyusb_hid_devices[0].device;
  }
  if (device) {
    device->_onOutput(report_id, buffer, reqlen);
    return true;
  }
  return false;
}'''

OLD_FEATURE = '''static bool tinyusb_on_set_feature(uint8_t report_id, const uint8_t *buffer, uint16_t reqlen) {
  USBHIDDevice *device = tinyusb_get_device_by_report_id(report_id);
  if (device) {
    device->_onSetFeature(report_id, buffer, reqlen);
    return true;
  }
  return false;
}'''

NEW_FEATURE = '''static bool tinyusb_on_set_feature(uint8_t report_id, const uint8_t *buffer, uint16_t reqlen) {
  USBHIDDevice *device = tinyusb_get_device_by_report_id(report_id);
  // Same single-device fallback used for OUTPUT reports. Linux hid-nintendo
  // may send initialization SET_REPORT requests through the control endpoint.
  if (!device && tinyusb_loaded_hid_devices_num == 1) {
    device = tinyusb_hid_devices[0].device;
  }
  if (device) {
    device->_onSetFeature(report_id, buffer, reqlen);
    return true;
  }
  return false;
}'''


def candidates() -> list[Path]:
    root = Path.home() / ".arduino15/packages/esp32/hardware/esp32"
    if not root.exists():
        return []
    return sorted(root.glob("*/libraries/USB/src/USBHID.cpp"), reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch ESP32 Arduino USBHID routing for SwitchNet")
    parser.add_argument("--restore", action="store_true", help="restore USBHID.cpp from the backup")
    parser.add_argument("--file", type=Path, help="explicit USBHID.cpp path")
    args = parser.parse_args()

    paths = [args.file] if args.file else candidates()
    paths = [p.expanduser().resolve() for p in paths if p and p.exists()]
    if not paths:
        raise SystemExit("USBHID.cpp not found under ~/.arduino15/packages/esp32/hardware/esp32")

    target = paths[0]
    backup = target.with_suffix(target.suffix + ".switchnet-backup")

    if args.restore:
        if not backup.exists():
            raise SystemExit(f"Backup not found: {backup}")
        shutil.copy2(backup, target)
        print(f"Restored: {target}")
        return 0

    text = target.read_text(encoding="utf-8")
    if "SwitchNet compatibility:" in text:
        print(f"Already patched: {target}")
        return 0

    if OLD_OUTPUT not in text or OLD_FEATURE not in text:
        raise SystemExit(
            "Expected ESP32 Arduino Core 3.3.x functions were not found. "
            "No changes were made."
        )

    if not backup.exists():
        shutil.copy2(target, backup)

    text = text.replace(OLD_OUTPUT, NEW_OUTPUT).replace(OLD_FEATURE, NEW_FEATURE)
    target.write_text(text, encoding="utf-8")
    print(f"Patched: {target}")
    print(f"Backup:  {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
