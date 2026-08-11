# SwitchNet — Complete Build and Flash Guide

This guide explains how to set up the toolchain, compile, and flash **SwitchNet** on an **ESP32-S3 board with native USB support**, using either **Windows** or **Linux**.

Project repository:

```text
https://github.com/d0vere/SwitchNet
```

> [!IMPORTANT]
> SwitchNet requires an **ESP32-S3 with native USB support**.
>
> The firmware must be compiled with the USB configuration required by the project, using **USB-OTG / TinyUSB**.
>
> SwitchNet also uses a custom `partitions.csv`. The first installation of that partition layout should be performed through a **full USB flash**, not by flashing only the application binary and not by relying on OTA.

---

## Table of Contents

1. [Requirements](#1-requirements)
2. [How SwitchNet Works](#2-how-switchnet-works)
3. [Supported Hardware](#3-supported-hardware)
4. [Clone the Repository](#4-clone-the-repository)
5. [Install Arduino CLI](#5-install-arduino-cli)
6. [Configure Arduino CLI](#6-configure-arduino-cli)
7. [Install the ESP32 Arduino Core](#7-install-the-esp32-arduino-core)
8. [Connect and Detect the Board](#8-connect-and-detect-the-board)
9. [Linux Serial Port Permissions](#9-linux-serial-port-permissions)
10. [Select the ESP32-S3 Target](#10-select-the-esp32-s3-target)
11. [Find the Correct USB Mode](#11-find-the-correct-usb-mode)
12. [Build SwitchNet](#12-build-switchnet)
13. [Flash SwitchNet on Windows](#13-flash-switchnet-on-windows)
14. [Flash SwitchNet on Linux](#14-flash-switchnet-on-linux)
15. [Enter the ESP32-S3 Bootloader Manually](#15-enter-the-esp32-s3-bootloader-manually)
16. [Verify the Partition Table Is Flashed](#16-verify-the-partition-table-is-flashed)
17. [Open the Serial Monitor](#17-open-the-serial-monitor)
18. [First Boot](#18-first-boot)
19. [Connect the Board to Nintendo Switch](#19-connect-the-board-to-nintendo-switch)
20. [Troubleshooting](#20-troubleshooting)
21. [Erase the Entire Flash](#21-erase-the-entire-flash)
22. [Quick Windows Procedure](#22-quick-windows-procedure)
23. [Quick Linux Procedure](#23-quick-linux-procedure)
24. [Final Checklist](#24-final-checklist)
25. [Notes for Waveshare ESP32-S3FH4R2](#25-notes-for-waveshare-esp32-s3fh4r2)

---

# 1. Requirements

You will need:

- an **ESP32-S3 development board with native USB support**;
- preferably a board with **4 MB flash** if you are using the partition layout currently supplied with SwitchNet;
- a proper **USB data cable**;
- a Windows or Linux PC;
- Git;
- Arduino CLI;
- a Nintendo Switch / Switch OLED / Switch 2 setup compatible with the project;
- a network connection between the PC running the SwitchNet client and the ESP32-S3.

A USB charging-only cable will not work for flashing.

---

# 2. How SwitchNet Works

SwitchNet uses the ESP32-S3 as a network-connected USB controller device.

The general data path is:

```text
Controller / Keyboard / Mouse
              |
              v
             PC
              |
         LAN / Wi-Fi
              |
              v
          ESP32-S3
              |
         Native USB
              |
              v
       Nintendo Switch
```

The PC reads your input devices and sends controller state over the network.

The ESP32-S3 receives that state and presents itself to the Nintendo Switch as a USB HID controller.

This is why **native USB support is mandatory**.

A board that only exposes a USB-to-UART bridge such as CH340 or CP210x is not enough unless the board also gives access to the ESP32-S3 native USB interface.

---

# 3. Supported Hardware

The safest choice is an ESP32-S3 board with:

```text
SoC:        ESP32-S3
Flash:      4 MB
Native USB: Yes
Wi-Fi:      Yes
```

Native USB is the most important requirement.

SwitchNet must be able to control the ESP32-S3 USB device peripheral directly.

For generic boards, the Arduino target used in this guide is:

```text
ESP32S3 Dev Module
```

with FQBN:

```text
esp32:esp32:esp32s3
```

Other ESP32-S3 variants may work, but the actual USB wiring of the board must expose the SoC's native USB interface.

---

# 4. Clone the Repository

## Windows

Open PowerShell:

```powershell
cd $HOME
git clone https://github.com/d0vere/SwitchNet.git
cd SwitchNet
```

Check the directory:

```powershell
dir
```

You should see at least:

```text
SwitchNet.ino
partitions.csv
src
```

## Linux

Open a terminal:

```bash
cd ~
git clone https://github.com/d0vere/SwitchNet.git
cd SwitchNet
```

Check the directory:

```bash
ls
```

You should see at least:

```text
SwitchNet.ino
partitions.csv
src/
```

> [!WARNING]
> Do not copy only `SwitchNet.ino` into another folder.
>
> SwitchNet depends on the rest of the repository, including the source files under `src/` and the custom `partitions.csv`.

---

# 5. Install Arduino CLI

Arduino CLI is used to:

- install the ESP32 Arduino core;
- inspect board options;
- compile SwitchNet;
- upload the firmware;
- open the serial monitor.

---

## 5.1 Windows

Install Arduino CLI from the official Arduino distribution.

After installation, open a new PowerShell window and run:

```powershell
arduino-cli version
```

You should get output similar to:

```text
arduino-cli Version: 1.x.x
```

If PowerShell returns:

```text
arduino-cli : The term 'arduino-cli' is not recognized
```

then the folder containing `arduino-cli.exe` is not in your `PATH`.

Add that folder to your Windows `PATH`, then reopen PowerShell.

### Alternative: Git Bash

If Git Bash is installed, Arduino CLI can also be installed with:

```bash
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh
```

The executable is usually placed under a local `bin` directory.

---

## 5.2 Linux

On Debian or Ubuntu:

```bash
sudo apt update
sudo apt install -y git curl
```

Install Arduino CLI:

```bash
cd ~
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh
```

The installer commonly creates:

```text
~/bin/arduino-cli
```

Add it to your shell PATH:

```bash
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Verify:

```bash
arduino-cli version
```

---

# 6. Configure Arduino CLI

Initialize the Arduino CLI configuration:

```bash
arduino-cli config init
```

If Arduino CLI reports that the config file already exists, that is fine.

Display the current configuration:

```bash
arduino-cli config dump
```

Add the official Espressif board index:

```bash
arduino-cli config add board_manager.additional_urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
```

Update indexes:

```bash
arduino-cli core update-index
```

Verify the configuration:

```bash
arduino-cli config dump
```

You should see an entry similar to:

```yaml
board_manager:
  additional_urls:
    - https://espressif.github.io/arduino-esp32/package_esp32_index.json
```

---

# 7. Install the ESP32 Arduino Core

This guide uses:

```text
Arduino-ESP32 3.3.11
```

Install that exact version:

```bash
arduino-cli core install esp32:esp32@3.3.11
```

Verify:

```bash
arduino-cli core list
```

Expected output:

```text
ID           Installed
esp32:esp32  3.3.11
```

Using the exact core version expected by the project is recommended because board options, USB behavior, TinyUSB support, and partition handling can change between versions.

---

# 8. Connect and Detect the Board

Connect the ESP32-S3 to your computer using a USB data cable.

Run:

```bash
arduino-cli board list
```

## Windows example

```text
Port  Protocol Type
COM5  serial   Serial Port (USB)
```

In this example, the board is available on:

```text
COM5
```

## Linux example

Common device names are:

```text
/dev/ttyACM0
```

or:

```text
/dev/ttyUSB0
```

For ESP32-S3 native USB, `/dev/ttyACM*` is common.

A useful test is:

1. run `arduino-cli board list`;
2. unplug the board;
3. run it again;
4. reconnect the board;
5. run it again.

The new port is usually the board you want.

---

# 9. Linux Serial Port Permissions

If Linux detects the board but upload fails with permission errors, inspect the device:

```bash
ls -l /dev/ttyACM0
```

On Debian/Ubuntu systems, serial devices are commonly assigned to the `dialout` group.

Add your user to that group:

```bash
sudo usermod -aG dialout $USER
```

Then log out and log back in.

Verify:

```bash
groups
```

You should see:

```text
dialout
```

For the current shell only, you can sometimes use:

```bash
newgrp dialout
```

> [!WARNING]
> Do not use this as a permanent fix:
>
> ```bash
> sudo chmod 777 /dev/ttyACM0
> ```
>
> It is insecure and the permission change usually disappears when the USB device reconnects.

---

# 10. Select the ESP32-S3 Target

List available ESP32-S3 boards.

## Linux

```bash
arduino-cli board listall | grep -i "ESP32-S3"
```

## Windows PowerShell

```powershell
arduino-cli board listall | Select-String "ESP32-S3"
```

For a generic ESP32-S3 board, use:

```text
ESP32S3 Dev Module
```

FQBN:

```text
esp32:esp32:esp32s3
```

This is the base FQBN used throughout the rest of this guide.

---

# 11. Find the Correct USB Mode

SwitchNet requires the ESP32-S3 native USB peripheral to operate in the mode expected by the firmware.

The project requires a configuration corresponding to:

```text
USB-OTG / TinyUSB
```

Inspect the available board options:

```bash
arduino-cli board details --fqbn esp32:esp32:esp32s3
```

## Linux filtering

```bash
arduino-cli board details --fqbn esp32:esp32:esp32s3 | grep -i -A12 usb
```

## Windows PowerShell filtering

```powershell
arduino-cli board details --fqbn esp32:esp32:esp32s3 | Select-String -Pattern "USB" -Context 0,12
```

Look for the menu corresponding to:

```text
USB Mode
```

and identify the internal value that maps to:

```text
USB-OTG (TinyUSB)
```

Arduino CLI board options are appended to the FQBN.

The general format is:

```text
esp32:esp32:esp32s3:OPTION=VALUE
```

For example:

```text
esp32:esp32:esp32s3:USBMode=<USB_OTG_VALUE>
```

> [!IMPORTANT]
> Replace `<USB_OTG_VALUE>` with the exact value shown by your installed ESP32 core.
>
> Do not blindly copy an internal `USBMode` value from a tutorial written for another ESP32 Arduino core version.

---

# 12. Build SwitchNet

Enter the SwitchNet repository.

## Windows

```powershell
cd $HOME\SwitchNet
```

## Linux

```bash
cd ~/SwitchNet
```

Verify that the following exist:

```text
SwitchNet.ino
partitions.csv
src/
```

---

## 12.1 Basic Build Test

You can first try:

```bash
arduino-cli compile --fqbn esp32:esp32:esp32s3 .
```

If the firmware reports that the USB configuration is invalid, that is expected until the USB mode is explicitly selected.

---

## 12.2 Build with the Correct USB Mode

After identifying the correct USB-OTG/TinyUSB value:

## Windows

```powershell
arduino-cli compile --fqbn "esp32:esp32:esp32s3:USBMode=<USB_OTG_VALUE>" .
```

## Linux

```bash
arduino-cli compile \
  --fqbn "esp32:esp32:esp32s3:USBMode=<USB_OTG_VALUE>" \
  .
```

A successful build should end with output similar to:

```text
Sketch uses XXXXX bytes (...) of program storage space.
Global variables use XXXXX bytes (...) of dynamic memory.
```

---

## 12.3 Use a Separate Build Directory

Using a dedicated build directory makes it easier to inspect the generated binaries.

### Windows

```powershell
mkdir build
```

Then:

```powershell
arduino-cli compile --fqbn "esp32:esp32:esp32s3:USBMode=<USB_OTG_VALUE>" --output-dir build .
```

### Linux

```bash
mkdir -p build
```

Then:

```bash
arduino-cli compile \
  --fqbn "esp32:esp32:esp32s3:USBMode=<USB_OTG_VALUE>" \
  --output-dir build \
  .
```

Typical generated files include:

```text
SwitchNet.ino.bin
SwitchNet.ino.bootloader.bin
SwitchNet.ino.partitions.bin
```

Exact filenames may vary.

---

# 13. Flash SwitchNet on Windows

Detect the board:

```powershell
arduino-cli board list
```

Assume the board appears as:

```text
COM5
```

Compile:

```powershell
arduino-cli compile --fqbn "esp32:esp32:esp32s3:USBMode=<USB_OTG_VALUE>" .
```

Upload:

```powershell
arduino-cli upload -v -p COM5 --fqbn "esp32:esp32:esp32s3:USBMode=<USB_OTG_VALUE>" .
```

You can also compile and upload in one command:

```powershell
arduino-cli compile --upload -p COM5 --fqbn "esp32:esp32:esp32s3:USBMode=<USB_OTG_VALUE>" .
```

For first-time setup, keeping compile and upload as separate commands is recommended because it makes troubleshooting easier.

---

# 14. Flash SwitchNet on Linux

Detect the board:

```bash
arduino-cli board list
```

Assume the device is:

```text
/dev/ttyACM0
```

Compile:

```bash
arduino-cli compile \
  --fqbn "esp32:esp32:esp32s3:USBMode=<USB_OTG_VALUE>" \
  .
```

Upload:

```bash
arduino-cli upload \
  -v \
  -p /dev/ttyACM0 \
  --fqbn "esp32:esp32:esp32s3:USBMode=<USB_OTG_VALUE>" \
  .
```

Or compile and upload in one command:

```bash
arduino-cli compile \
  --upload \
  -p /dev/ttyACM0 \
  --fqbn "esp32:esp32:esp32s3:USBMode=<USB_OTG_VALUE>" \
  .
```

---

# 15. Enter the ESP32-S3 Bootloader Manually

If upload fails with errors such as:

```text
Failed to connect to ESP32-S3
```

or:

```text
No serial data received
```

put the board into download mode manually.

A common ESP32-S3 sequence is:

1. press and hold **BOOT**;
2. press and release **RESET** or **RST**;
3. wait briefly;
4. release **BOOT**.

Then run:

```bash
arduino-cli board list
```

The serial port can change.

Example on Windows:

```text
COM5 -> COM6
```

Example on Linux:

```text
/dev/ttyACM0 -> /dev/ttyACM1
```

Use the new port for the upload command.

---

## Alternative Bootloader Method

On some boards:

1. unplug USB;
2. hold BOOT;
3. reconnect USB;
4. wait about one second;
5. release BOOT.

Then run:

```bash
arduino-cli board list
```

again.

---

# 16. Verify the Partition Table Is Flashed

SwitchNet includes a custom:

```text
partitions.csv
```

The first installation of this partition layout should be done through a normal USB upload.

Use verbose mode.

## Windows

```powershell
arduino-cli upload -v -p COM5 --fqbn "esp32:esp32:esp32s3:USBMode=<USB_OTG_VALUE>" .
```

## Linux

```bash
arduino-cli upload \
  -v \
  -p /dev/ttyACM0 \
  --fqbn "esp32:esp32:esp32s3:USBMode=<USB_OTG_VALUE>" \
  .
```

Watch the output for the partition table binary being included in the flash process.

The project file:

```text
partitions.csv
```

must remain in the root of the Arduino sketch.

> [!IMPORTANT]
> Do not flash only `SwitchNet.ino.bin` during the first installation.
>
> The normal Arduino upload process is preferred because it handles the application, bootloader, and partition table according to the selected build configuration.

---

# 17. Open the Serial Monitor

After flashing, inspect the firmware output.

First determine the current port:

```bash
arduino-cli board list
```

## Windows

```powershell
arduino-cli monitor -p COM5 -c baudrate=115200
```

## Linux

```bash
arduino-cli monitor -p /dev/ttyACM0 -c baudrate=115200
```

If the USB device re-enumerates after reset, the port may change.

Run:

```bash
arduino-cli board list
```

again and use the new port.

---

# 18. First Boot

After flashing:

1. press RESET, or unplug and reconnect the board;
2. open the serial monitor;
3. verify that SwitchNet starts correctly;
4. inspect the logs for configuration or networking errors;
5. complete the network setup required by SwitchNet;
6. start the PC-side SwitchNet client.

If the board was previously used for another firmware, stale NVS configuration may still exist.

If behavior is inconsistent, see the flash erase section later in this guide.

---

# 19. Connect the Board to Nintendo Switch

Once:

- SwitchNet has been flashed successfully;
- network configuration is complete;
- the PC-side SwitchNet client is running;

connect the ESP32-S3 native USB interface to the Nintendo Switch or dock as required by your hardware setup.

On Nintendo Switch, enable wired Pro Controller communication:

```text
System Settings
  -> Controllers and Sensors
  -> Pro Controller Wired Communication
```

SwitchNet relies on the ESP32-S3 native USB interface to present the controller device to the console.

---

# 20. Troubleshooting

## 20.1 `arduino-cli` Command Not Found

### Windows

Error:

```text
arduino-cli : The term 'arduino-cli' is not recognized
```

Fix:

- locate `arduino-cli.exe`;
- add its directory to Windows `PATH`;
- close and reopen PowerShell.

Verify:

```powershell
arduino-cli version
```

### Linux

Error:

```text
arduino-cli: command not found
```

Try:

```bash
export PATH="$HOME/bin:$PATH"
```

Then:

```bash
arduino-cli version
```

---

## 20.2 Board Is Not Detected

Run:

```bash
arduino-cli board list
```

If nothing appears:

- use another USB cable;
- make sure the cable supports data;
- try another USB port;
- avoid USB hubs while troubleshooting;
- manually enter bootloader mode;
- check Device Manager on Windows;
- inspect kernel messages on Linux.

Linux:

```bash
sudo dmesg | tail -n 50
```

Also check:

```bash
ls /dev/ttyACM*
ls /dev/ttyUSB*
```

---

## 20.3 Linux `Permission denied`

Example:

```text
Permission denied: /dev/ttyACM0
```

Fix:

```bash
sudo usermod -aG dialout $USER
```

Log out and log back in.

Verify:

```bash
groups
```

---

## 20.4 Windows COM Port Is Busy

Typical errors:

```text
Access is denied
```

or:

```text
could not open port COM5
```

Close programs that may already have the port open:

- Arduino Serial Monitor;
- PuTTY;
- VS Code serial extensions;
- PlatformIO Monitor;
- another terminal application.

Then retry the upload.

---

## 20.5 `Failed to connect to ESP32-S3`

Enter download mode manually:

```text
Hold BOOT
-> press RESET
-> release RESET
-> release BOOT
```

Then:

```bash
arduino-cli board list
```

Use the detected port.

---

## 20.6 `No serial data received`

Possible causes:

- board is not in bootloader mode;
- wrong COM/TTY port;
- USB charging-only cable;
- unstable USB connection;
- another process is using the serial port.

Try manual bootloader mode and detect the port again.

---

## 20.7 Native USB Build Error

If SwitchNet reports that native USB support is required, make sure you are compiling for:

```text
esp32:esp32:esp32s3
```

Do not use a classic ESP32 target.

---

## 20.8 USB-OTG / TinyUSB Build Error

If SwitchNet reports that the USB mode is wrong:

```bash
arduino-cli board details --fqbn esp32:esp32:esp32s3
```

Find the value corresponding to:

```text
USB-OTG (TinyUSB)
```

Then rebuild with:

```text
esp32:esp32:esp32s3:USBMode=<USB_OTG_VALUE>
```

---

## 20.9 `Sketch too big`

If compilation reports:

```text
Sketch too big
```

verify the installed core:

```bash
arduino-cli core list
```

Confirm that the expected core version is installed.

Also confirm that:

```text
partitions.csv
```

exists in the SwitchNet repository root.

Build the complete repository:

```bash
arduino-cli compile ... .
```

Do not compile a copied standalone `.ino` file.

---

## 20.10 USB Device Disappears After Flashing

Firmware that takes control of the ESP32-S3 native USB peripheral can change USB enumeration after boot.

If the board disappears:

1. unplug the board;
2. enter bootloader mode manually;
3. reconnect it;
4. run `arduino-cli board list`;
5. flash again if necessary.

---

## 20.11 Nintendo Switch Does Not Detect the Controller

Check all of the following:

- the firmware was built using USB-OTG/TinyUSB;
- the USB connector being used is actually wired to native ESP32-S3 USB;
- the USB cable carries data;
- Pro Controller Wired Communication is enabled on the Switch;
- the SwitchNet PC client is running;
- the PC and ESP32-S3 can reach each other over the network;
- SwitchNet has booted successfully;
- the serial log does not show initialization errors.

---

# 21. Erase the Entire Flash

A full erase is not normally required.

It can be useful if:

- the board previously ran unrelated firmware;
- stored NVS settings are causing issues;
- the partition table has changed several times;
- the board behaves inconsistently after multiple experiments.

Install `esptool`.

## Windows

```powershell
python -m pip install esptool
```

Erase:

```powershell
python -m esptool --chip esp32s3 --port COM5 erase-flash
```

## Linux

```bash
python3 -m pip install esptool
```

Erase:

```bash
python3 -m esptool --chip esp32s3 --port /dev/ttyACM0 erase-flash
```

After erasing, perform a full SwitchNet USB upload again.

> [!WARNING]
> `erase-flash` removes the firmware, partition data, and saved configuration.

---

# 22. Quick Windows Procedure

Open PowerShell:

```powershell
cd $HOME

git clone https://github.com/d0vere/SwitchNet.git
cd SwitchNet

arduino-cli config init

arduino-cli config add board_manager.additional_urls https://espressif.github.io/arduino-esp32/package_esp32_index.json

arduino-cli core update-index

arduino-cli core install esp32:esp32@3.3.11

arduino-cli core list

arduino-cli board list

arduino-cli board details --fqbn esp32:esp32:esp32s3
```

Find the board option corresponding to:

```text
USB Mode -> USB-OTG (TinyUSB)
```

Compile:

```powershell
arduino-cli compile --fqbn "esp32:esp32:esp32s3:USBMode=<USB_OTG_VALUE>" .
```

Assuming the board is on `COM5`, upload:

```powershell
arduino-cli upload -v -p COM5 --fqbn "esp32:esp32:esp32s3:USBMode=<USB_OTG_VALUE>" .
```

Open the serial monitor:

```powershell
arduino-cli monitor -p COM5 -c baudrate=115200
```

---

# 23. Quick Linux Procedure

On Debian/Ubuntu:

```bash
sudo apt update
sudo apt install -y git curl
```

Install Arduino CLI:

```bash
cd ~
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh
export PATH="$HOME/bin:$PATH"
```

Verify:

```bash
arduino-cli version
```

Clone SwitchNet:

```bash
git clone https://github.com/d0vere/SwitchNet.git
cd SwitchNet
```

Configure Arduino CLI:

```bash
arduino-cli config init

arduino-cli config add board_manager.additional_urls \
https://espressif.github.io/arduino-esp32/package_esp32_index.json

arduino-cli core update-index

arduino-cli core install esp32:esp32@3.3.11

arduino-cli core list
```

Detect the board:

```bash
arduino-cli board list
```

Inspect USB options:

```bash
arduino-cli board details --fqbn esp32:esp32:esp32s3
```

Find:

```text
USB Mode -> USB-OTG (TinyUSB)
```

Compile:

```bash
arduino-cli compile \
  --fqbn "esp32:esp32:esp32s3:USBMode=<USB_OTG_VALUE>" \
  .
```

Assuming the board is `/dev/ttyACM0`, upload:

```bash
arduino-cli upload \
  -v \
  -p /dev/ttyACM0 \
  --fqbn "esp32:esp32:esp32s3:USBMode=<USB_OTG_VALUE>" \
  .
```

Open the serial monitor:

```bash
arduino-cli monitor -p /dev/ttyACM0 -c baudrate=115200
```

---

# 24. Final Checklist

Before considering the installation complete, verify:

- [ ] ESP32-S3 board with native USB;
- [ ] USB data cable;
- [ ] full SwitchNet repository cloned;
- [ ] `SwitchNet.ino` exists;
- [ ] `src/` exists;
- [ ] `partitions.csv` exists;
- [ ] Arduino CLI works;
- [ ] Espressif package index is configured;
- [ ] `esp32:esp32@3.3.11` is installed;
- [ ] target is `esp32:esp32:esp32s3`;
- [ ] USB mode is configured for USB-OTG/TinyUSB;
- [ ] compilation completes without errors;
- [ ] correct COM/TTY port is detected;
- [ ] first installation is flashed over USB;
- [ ] partition table is included in the flash;
- [ ] firmware boots correctly;
- [ ] networking is configured;
- [ ] SwitchNet PC client is running;
- [ ] Pro Controller Wired Communication is enabled on Nintendo Switch.

---

# 25. Notes for Waveshare ESP32-S3FH4R2

For a Waveshare board based on **ESP32-S3FH4R2**, the important hardware characteristics are:

```text
SoC:        ESP32-S3
Flash:      4 MB
PSRAM:      2 MB
Wi-Fi:      2.4 GHz
Native USB: supported by ESP32-S3
```

Use the generic Arduino target as a starting point:

```text
ESP32S3 Dev Module
```

FQBN:

```text
esp32:esp32:esp32s3
```

The flash size should remain consistent with the physical device:

```text
4 MB
```

Do not configure 8 MB or 16 MB flash on a 4 MB board.

For SwitchNet, the critical USB setting is:

```text
USB-OTG / TinyUSB
```

The physical USB connector used with the Nintendo Switch must be connected to the ESP32-S3 native USB signals.

If a board has both native USB and a USB-to-UART interface, make sure you are using the native USB path for the controller connection.

---

# Updating SwitchNet Later

To update your local repository:

```bash
cd SwitchNet
git pull
```

Before rebuilding a newer revision, check whether the project has changed:

- the recommended ESP32 Arduino core version;
- `partitions.csv`;
- USB mode requirements;
- build flags;
- OTA behavior;
- board support.

If the partition table changes, perform another full USB flash rather than assuming that an application-only update is sufficient.

---

# Recommended Recovery Procedure

If the board becomes difficult to flash:

1. disconnect it from the Nintendo Switch;
2. connect it directly to the PC;
3. enter bootloader mode manually;
4. run `arduino-cli board list`;
5. verify the current serial port;
6. if necessary, erase the flash with `esptool`;
7. compile SwitchNet again;
8. perform a full USB upload;
9. reboot the board;
10. check the serial monitor before reconnecting it to the Switch.

This is the cleanest way to recover from a broken build, incorrect USB mode, stale partition table, or invalid stored configuration.
