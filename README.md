# 🎮 SwitchNet

The project allows you to control your Nintendo Switch/OLED/2 over your local network using almost any controller (or keyboard and mouse) connected to your PC. 

By routing controller inputs over Wi-Fi/LAN, SwitchNet enables low-latency PC-to-Switch streaming, letting you play anywhere in your house at maximum resolution and refresh rate without being tethered to the console.

> [!IMPORTANT]
> SwitchNet handles **controller input only**.
>
> Video and audio require a separate capture card and streaming solution.

---


> [!WARNING]
> Every part of this project _HEAVILY_ used LLMs*

---

## 🛠️ How It Works

The project consists of two main components working together:

1. **Client Software (Windows & Linux)**  
   A desktop application running on your PC. It reads inputs from whatever controllers or peripherals you have connected to your computer and sends them across your network to the ESP32 hardware in real-time.

2. **Hardware (ESP32-S3 SuperMini)**  
   A compact USB device plugged directly into your Nintendo Switch (Switch / OLED / Switch 2). To the console, it pretends to be a standard **Nintendo Switch Pro Controller**. Under the hood, it listens to your local network and instantly converts incoming data packets into console inputs.

```text
Controller
    │
    ▼
Client PC ─── LAN / Wi-Fi ───► ESP32-S3 ─── USB ───► Nintendo Switch
```

---

## 💡 Use Cases

* 📡 **Remote Play & High-FPS Streaming:** Play your Switch anywhere on your home network with high resolution and smooth frame rates.
* ⌨️ **Keyboard & Mouse Support:** Control Switch games using standard PC peripherals.
* 🕹️ **Custom Controllers & Remapping:** Use Xbox, PlayStation, Stadia, Steam controller with fully tailored button layouts.
* 👥 **Easy Multiplayer:** Play local multiplayer games with friends without buying additional official Switch controllers.


[![SwitchNet Intro](https://img.youtube.com/vi/f59DOEypre0/maxresdefault.jpg)](https://youtu.be/f59DOEypre0?si=1AS3WwvE7aTBhF1q)

## 🔧 What You Need

- **Nintendo Switch or Nintendo Switch 2**
- **ESP32-S3 Supermini board with native USB support** (like 15$ on Amazon) (Other ESP32-S3 boards may work but should currently be considered **untested** )
- Windows or Linux PC near the player
- Supported controller
- Local network accessible by both the PC and ESP32-S3
- USB cable
- Separate video capture (Elgato 4kS/X) and streaming setup (Apollo/Moonlight)

## 🚀 Getting Started

### 1. Flash the ESP32-S3

Compile and Flash the SwitchNet firmware onto a compatible ESP32-S3 board with arduino-cli.

### 2. Configure Wi-Fi

Connect the SwitchNet device to the same local network as the client PC.

### 3. Connect it to the Switch

Connect the ESP32-S3 native USB interface to the Nintendo Switch/2 or Nintendo Switch/2 Dock.
You'll need to enable the pro controller wired communication option

### 4. Start the client

Run the SwitchNet client on:

- Windows
- Linux

The client can automatically discover the SwitchNet device on the network. You can also enter its IP address manually.

### 5. Connect your controller

Connect one or more controllers to the client PC, configure mappings/player slots if needed, and start the SwitchNet service.

### 6. Start your video stream

Start your preferred capture/streaming solution.
Your video stream travels from the console to you, while SwitchNet sends controller input back to the console.

```text
Nintendo Switch ───── video/audio ─────► Player
Nintendo Switch ◄──── controller ─────── Player
                         SwitchNet
```

## 🧪 Experimental Project

SwitchNet is experimental software.
Controller behavior can vary depending on:
- Operating system
- Controller firmware
- USB vs Bluetooth
- Drivers
- Hardware revisions
- Other software accessing the controller
Real-hardware testing is therefore especially valuable.

If you encounter a problem, please open an issue and include, when relevant:
- Operating system and SwitchNet version
- Controller manufacturer/model
- USB or Bluetooth connection
- What works and what doesn't
- Motion/rumble behavior
- Relevant diagnostics or error messages
- Steps to reproduce the problem

---

## 📚 Documentation

Additional technical documentation is available in the repository:

- `HTTP_API.md`
- `KEYBOARD_CONTROLLER.md`
- `PARTITIONS.md`
- `USB_HID_TEST_HISTORY.md`

Platform-specific documentation is also available under:

```text
client-python-linux/
client-python-windows/
```

Diagnostic and regression-testing utilities can be found in:

```text
tools/
```

---

## 🤖 AI-Assisted Development

SwitchNet was created using **AI-assisted code generation**.
The project has been driven through human-defined requirements, feature design, hardware testing, debugging, validation and repeated iteration, while the source code itself was generated with AI assistance.
This is disclosed for transparency. AI-generated code may contain bugs, incorrect assumptions, security issues or platform-specific problems, so **code review and contributions from experienced developers are especially welcome**.

---

# 💡 Inspiration and Acknowledgements: OpenPuck

The idea behind SwitchNet started thanks to
[OpenPuck](https://github.com/safijari/openpuck).

OpenPuck was the original inspiration for the project and also served as
an important technical reference during SwitchNet's development.

OpenPuck is distributed under the **GNU Affero General Public License
v3.0 (AGPL-3.0)**. SwitchNet is also distributed under the AGPL-3.0.

Many thanks to the OpenPuck project and its contributors for making
their work available to the community.

---

# 🚀 Possible Future Expansion

SwitchNet is currently focused on **Nintendo Switch and Nintendo Switch 2**.

That remains the primary goal of the project.
However, the architecture behind SwitchNet — separating controller
transport from video/audio streaming — could potentially be adapted to
other consoles/PCs.

If the project receives significant community interest, feature requests,
contributions and financial support, I would be interested in exploring
whether SwitchNet could be expanded to platforms such as:
### 🎮 PlayStation 5
A future implementation could investigate providing a similar network
controller bridge for capture-based PlayStation 5 remote gaming setups.

### 🎮 Xbox
The same concept could potentially be investigated for Xbox consoles,
with controller input transported independently from the video/audio
stream.

> [!IMPORTANT]
> **PlayStation 5 and Xbox are not currently supported.**
>
> These are possible future research directions, not promised features or
> announced release plans.
>
> Their feasibility would depend on console protocols, hardware
> requirements, technical research, development time and access to the
> necessary testing hardware.

If SwitchNet receives enough interest and support, donations may also
help fund the additional consoles, controllers, adapters and development
hardware required to investigate these platforms.

## ☕ Support

If you find SwitchNet useful and would like to support the time, hardware testing and experimentation behind the project:

### ☕ [Buy Me a Coffee](https://buymeacoffee.com/dovere)

---

# 📄 License

SwitchNet is licensed under the **GNU Affero General Public License v3.0
(AGPL-3.0)**.

You are free to use, study, modify and redistribute SwitchNet under the
terms of the AGPL-3.0.

If you modify and distribute the software, or operate a modified version
in circumstances covered by the AGPL network-use provisions, you must
make the corresponding source code available as required by the license.

See the [`LICENSE`](LICENSE) file for the complete license terms.

Third-party projects, libraries and components remain subject to their
respective licenses.

---

## ⚠️ Disclaimer

SwitchNet is an **independent, unofficial and experimental project**.
It is not affiliated with, authorized by, sponsored by or endorsed by Nintendo, Sony, Valve, Google, Microsoft or any other manufacturer mentioned in this project.
Nintendo Switch, Nintendo Switch 2 and other product names and trademarks belong to their respective owners.
Compatibility with every controller, firmware revision, operating system or network configuration is not guaranteed.
Use the project at your own risk.

---

<div align="center">

### 🎮 SwitchNet

**Stream the console. Network the controllers. Play anywhere in your home.**

</div>
