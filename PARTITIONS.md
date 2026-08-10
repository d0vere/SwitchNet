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
