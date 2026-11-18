# SwitchNet 4 MB Partition Layout

SwitchNet v1.17.0 includes `partitions.csv` in the sketch directory.

| Partition | Offset | Size |
|---|---:|---:|
| NVS | 0x9000 | 20 KiB |
| OTA metadata | 0xE000 | 8 KiB |
| OTA app 0 | 0x10000 | 1,769,472 bytes |
| OTA app 1 | 0x1C0000 | 1,769,472 bytes |
| SPIFFS | 0x370000 | 512 KiB |
| Coredump | 0x3F0000 | 64 KiB |

Arduino-ESP32 3.3.11 copies a `partitions.csv` from the sketch source directory
after the selected board partition scheme, so this file overrides
`PartitionScheme=default` during compilation.

## First migration

A firmware-only OTA upload cannot rewrite the flash partition table. Therefore
the first v1.17.0 installation must use a normal USB upload so the generated
`partitions.bin` is flashed too.

After that one-time migration, SwitchNet's HTTP OTA continues to use the two
larger OTA application partitions normally.

## Reliable Arduino CLI build for HTTP OTA

On ESP32 Arduino Core 3.3.11, the generic board profile may enforce
`upload.maximum_size=1310720` (1.25 MiB) even when the sketch directory's
custom `partitions.csv` is selected. SwitchNet's two application slots
are **0x1B0000 bytes (1,769,472)** each.

From the repository root on Linux:

```bash
bash tools/build_ota.sh
```

The script sets `upload.maximum_size=1769472`, verifies the generated
partition binary matches this repository's `partitions.csv`, checks the
application image size and produces `build-ota/SwitchNet.ino.bin`.

**Important:** This build-time size override does not modify flash partitions.
Never OTA-update a device still using a smaller/different partition layout;
install the two-slot layout with a full USB flash first. The HTTP OTA form
requires the ESP32 to be connected to the router, not in setup-AP mode.
