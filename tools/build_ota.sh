#!/usr/bin/env bash
# Build an ESP32-S3 application image for SwitchNet's dual-OTA layout.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${1:-$ROOT/build-ota}"
FQBN="${SWITCHNET_FQBN:-esp32:esp32:esp32s3:USBMode=default,CDCOnBoot=default,FlashSize=4M,PartitionScheme=default}"
MAX_APP_SIZE=1769472 # app0/app1, 0x1B0000 bytes each, in partitions.csv.

[[ -f "$ROOT/partitions.csv" && -f "$ROOT/SwitchNet.ino" ]] || {
  echo "ERROR: run this script inside the SwitchNet repository." >&2
  exit 1
}
command -v arduino-cli >/dev/null || {
  echo "ERROR: arduino-cli is required." >&2
  exit 1
}

mkdir -p "$OUTPUT_DIR"
arduino-cli compile \
  --clean \
  --fqbn "$FQBN" \
  --build-property "upload.maximum_size=$MAX_APP_SIZE" \
  --output-dir "$OUTPUT_DIR" \
  "$ROOT"

FIRMWARE="$OUTPUT_DIR/SwitchNet.ino.bin"
PARTITIONS="$OUTPUT_DIR/SwitchNet.ino.partitions.bin"
[[ -s "$FIRMWARE" && -s "$PARTITIONS" ]] || {
  echo "ERROR: firmware or generated partitions binary missing." >&2
  exit 1
}

# A size override alone is unsafe if the Arduino core silently uses a
# different partition table. Verify the compiled binary against the
# repository's authoritative partitions.csv before offering OTA output.
CORE_PART_TOOL="${HOME}/.arduino15/packages/esp32/hardware/esp32/3.3.11/tools/gen_esp32part.py"
if [[ ! -f "$CORE_PART_TOOL" ]]; then
  CORE_PART_TOOL="$(find "${HOME}/.arduino15/packages/esp32" -name gen_esp32part.py -print -quit 2>/dev/null || true)"
fi
if [[ -z "$CORE_PART_TOOL" || ! -f "$CORE_PART_TOOL" ]]; then
  echo "ERROR: gen_esp32part.py not found; cannot verify the OTA partition layout." >&2
  exit 1
fi
TMP_PARTITIONS="$(mktemp)"
trap 'rm -f "$TMP_PARTITIONS"' EXIT
python3 "$CORE_PART_TOOL" "$ROOT/partitions.csv" "$TMP_PARTITIONS"
if ! cmp -s "$TMP_PARTITIONS" "$PARTITIONS"; then
  echo "ERROR: built partition table does not match partitions.csv. Do NOT upload via OTA." >&2
  exit 1
fi

SIZE="$(stat -c%s "$FIRMWARE")"
if (( SIZE > MAX_APP_SIZE )); then
  echo "ERROR: firmware ($SIZE bytes) exceeds OTA slot ($MAX_APP_SIZE bytes)." >&2
  exit 1
fi

echo "OTA firmware: $FIRMWARE"
echo "Size: $SIZE / $MAX_APP_SIZE bytes"
echo "Partition table verified; OTA image is ready (if the ESP32 already has this layout)."
