# 🎮 SwitchNet

### Network controller bridge for Nintendo Switch and Nintendo Switch 2 game streaming

> **Stream the console, network the controllers, play anywhere in your home.**

SwitchNet is a network controller bridge designed primarily for **Nintendo Switch and Nintendo Switch 2 game streaming setups**.

The project was created to solve a very practical problem: video from a Nintendo Switch can be captured and streamed to another device over the network, but the physical controller still needs to communicate directly with the console.

That becomes a problem as soon as you move far enough away from the Switch.

**SwitchNet solves the other half of the streaming equation:**

> **The video travels over the network, so why shouldn't the controller?**

With SwitchNet, controllers can be connected to a **Windows or Linux computer near the player**. Their inputs are sent over the local network to an **ESP32-S3 running SwitchNet**, which is connected via USB to the Nintendo Switch.

This allows the console to be controlled even when the player is outside the normal wireless range of the controller.

The result is a setup where you can leave your Switch connected to its dock, capture setup or TV and play it from another room — or potentially anywhere your home network reaches.

---

> [!IMPORTANT]
> ## SwitchNet does not capture or stream video/audio
>
> SwitchNet handles the **controller side** of the remote-play setup.
>
> To stream the Nintendo Switch or Nintendo Switch 2 video output, you need a
> **video capture card connected to the server PC**.
>
> A typical setup uses the console's HDMI output connected to a capture card,
> which allows the server PC to capture the game video and audio. That video
> stream can then be delivered to the remote client using your preferred
> streaming solution.
>
> SwitchNet handles the opposite direction: **controller input from the player
> back to the console**.

---

## ✨ Features

SwitchNet currently provides:

- 🌐 Low-latency controller input over the local network
- 🎮 Multiple controller support
- 🪟 Windows client
- 🐧 Linux client
- 🕹️ Configurable controller mappings
- 💾 Multiple mapping profiles
- 🎯 Per-controller analog stick deadzones
- 🌀 Gyroscope and accelerometer support for compatible controllers
- 📳 Rumble feedback for compatible controllers
- 🖱️ Experimental keyboard and mouse controller emulation
- 🔎 Automatic network discovery
- 📡 Configurable UDP update rate
- 🔄 Controller roster and player-slot management
- ⚙️ Controller-specific native backends where required
- 🛠️ Integrated diagnostics
- 🌙 Switch wake functionality

---

# 🔌 How It Works

SwitchNet consists of two main components:

1. **SwitchNet Client**
2. **SwitchNet ESP32-S3 firmware**

The complete setup looks approximately like this:

```text
Nintendo Switch / Switch 2
            │
            │ HDMI
            ▼
      Video Capture Card
            │
            ▼
        Server PC
            │
            │ Video / Audio Streaming
            ▼
        Local Network
            │
            ▼
         Client PC
            │
            ▼
          Player
```

Video and audio travel **from the console toward the player** using your preferred capture/streaming solution.

Controller input travels in the **opposite direction through SwitchNet**:

```text
Player
  │
  ▼
Controller
  │
  ▼
SwitchNet Client
  │
  │ LAN / Wi-Fi
  ▼
ESP32-S3 running SwitchNet
  │
  │ Native USB
  ▼
Nintendo Switch / Switch 2
```

This means that the physical controller stays next to the player instead of needing to remain within wireless range of the console.

---

# 💻 SwitchNet Client

The SwitchNet Client runs on the computer near the player.

Windows and Linux are supported.

The client is responsible for:

- Detecting connected controllers
- Reading buttons and analog sticks
- Reading triggers
- Reading motion sensors where supported
- Processing controller-specific inputs
- Applying mappings
- Applying analog stick deadzones
- Managing player slots
- Transmitting controller states over the network
- Receiving and reproducing supported rumble feedback

Depending on the controller, SwitchNet may use standard operating-system APIs or dedicated low-level implementations.

These include technologies such as:

- HID
- HIDRaw
- USB
- evdev
- XInput
- Controller-specific protocols

This allows SwitchNet to preserve functionality that might otherwise be lost through a generic gamepad abstraction.

---

# 🔧 Hardware Requirements

SwitchNet requires a dedicated **ESP32-S3 development board with native USB support** connected to the Nintendo Switch or Nintendo Switch 2.

## Tested Hardware

SwitchNet has been developed and tested using an:

### **ESP32-S3 SuperMini**

The board must provide:

- ESP32-S3 microcontroller
- Native **USB OTG / USB Device** support
- Wi-Fi connectivity
- Sufficient flash memory for the SwitchNet firmware and web interface
- A USB connection wired to the ESP32-S3 native USB peripheral

> [!WARNING]
> A regular ESP32 board is **not sufficient**.
>
> SwitchNet relies on the ESP32-S3 native USB peripheral to emulate the controller interface presented to the Nintendo Switch.

Other ESP32-S3 development boards may also work if they expose the native USB peripheral correctly, but unless explicitly documented they should currently be considered **untested**.

Some ESP32-S3 boards contain a USB connector connected only to a USB-to-serial interface.

That alone is **not sufficient for SwitchNet**.

Make sure the board exposes the ESP32-S3 native USB functionality.

## What You Need

A complete setup requires:

- 1× **ESP32-S3 SuperMini**
- 1× suitable USB cable
- 1× Nintendo Switch or Nintendo Switch 2
- A Windows or Linux computer near the player
- A supported controller
- A local network accessible by both the ESP32-S3 and the client computer
- A separate video capture/streaming solution

---

# 🚀 Getting Started

A typical SwitchNet setup works as follows:

### 1. Flash the ESP32-S3

Flash the SwitchNet firmware onto a compatible **ESP32-S3 SuperMini**.

### 2. Configure the network

Configure the SwitchNet device so that it can connect to the same local network used by the computer running the client.

### 3. Connect the ESP32-S3 to the console

Connect the ESP32-S3 native USB interface to the Nintendo Switch or Nintendo Switch 2.

### 4. Start the SwitchNet Client

Run the appropriate client for your operating system:

- Windows
- Linux

### 5. Find the SwitchNet device

Use automatic discovery when available, or manually enter the IP address of the SwitchNet device.

### 6. Connect your controllers

Connect one or more supported controllers to the Windows/Linux computer.

### 7. Configure the controller roster

Assign and reorder controllers according to the desired player slots.

### 8. Start the service

Start the SwitchNet service from the client.

### 9. Start your video stream

Open your preferred Nintendo Switch video capture/streaming solution.

You should now be able to see the console remotely while controller input travels back to the Switch through SwitchNet.

---

# 🎮 Supported Controllers

SwitchNet has been developed and tested with multiple controller families, including:

- **Nintendo Switch 2 Pro Controller**
- **Nintendo Switch Pro Controller**
- **Sony DualSense**
- **Steam Controller**
- **Google Stadia Controller**
- **XInput-compatible controllers**
- **Generic compatible gamepads**
- **Keyboard and mouse emulation**

Some controllers have dedicated implementations to expose features that would otherwise be unavailable through generic controller APIs.

For example, the Nintendo Switch 2 Pro Controller uses dedicated implementations for functionality such as:

- Native input reports
- Motion sensors
- Additional buttons
- Rumble
- Controller-specific HID communication

## Compatibility Overview

Controller capabilities depend on the operating system, connection method and available backend.

| Controller | Windows | Linux | Motion | Rumble | Mapping Profiles |
|---|:---:|:---:|:---:|:---:|:---:|
| Nintendo Switch 2 Pro Controller | ✅ | ✅ | ✅ | ✅ | ✅ |
| Nintendo Switch Pro Controller | ✅ | ✅ | Supported | Supported | ✅ |
| Sony DualSense | ✅ | ✅ | ✅ | Supported | ✅ |
| Steam Controller | ✅ | ✅ | Supported | Supported | ✅ |
| Google Stadia Controller | ✅ | ✅ | Controller dependent | Supported where available | ✅ |
| XInput-compatible controllers | ✅ | Platform dependent | Controller dependent | Platform dependent | ✅ |
| Generic gamepads | Platform dependent | Platform dependent | Controller dependent | Controller dependent | ✅ |
| Keyboard / Mouse | Experimental | Experimental | — | — | ✅ |

> [!NOTE]
> Compatibility can vary depending on controller firmware, connection type, operating system, drivers and other software accessing the controller.
>
> The table above is intended as a general overview rather than a guarantee for every hardware configuration.

---

# 🕹️ Controller Mapping

SwitchNet provides configurable controller mappings rather than requiring every physical controller to follow the same layout.

Multiple mapping profiles can be created for supported controller families.

Mappings can cover standard Nintendo controls such as:

```text
A / B / X / Y

L / R
ZL / ZR

D-Pad

L3 / R3

+ / -

Home
Capture
```

Controller-specific inputs can also be mapped where supported.

This includes additional inputs exposed by controllers such as the **Nintendo Switch 2 Pro Controller**.

SwitchNet therefore allows controllers from Nintendo, Sony, Valve, Google and XInput-compatible devices to be adapted to the layout expected by the console.

---

# 🎯 Per-Controller Deadzones

Analog stick deadzones can be configured independently for different controller families.

This is useful because different controllers can have significantly different stick behavior, calibration and wear characteristics.

Rather than applying one global deadzone to every device, SwitchNet can maintain appropriate settings for each controller type.

---

# 🌀 Gyroscope and Motion Controls

Motion controls are particularly important on Nintendo platforms.

SwitchNet forwards **gyroscope and accelerometer data** for supported controllers instead of limiting communication to conventional buttons and analog sticks.

Controller-specific processing and calibration are used where required to convert the physical controller's coordinate system into the motion representation expected by SwitchNet and the console.

This allows motion-controlled games to remain playable even though the controller is physically connected to the remote client rather than directly to the Nintendo Switch.

---

# 📳 Rumble and Feedback

SwitchNet supports bidirectional communication for compatible controllers.

Controller input travels toward the console:

```text
Controller
    │
    ▼
Client
    │
    ▼
Network
    │
    ▼
ESP32-S3
    │
    ▼
Nintendo Switch
```

Feedback can travel in the opposite direction:

```text
Nintendo Switch
    │
    ▼
ESP32-S3
    │
    ▼
Network
    │
    ▼
SwitchNet Client
    │
    ▼
Physical Controller
```

This allows supported rumble feedback generated by the console to be reproduced on the physical controller near the player.

Because different controllers implement feedback differently, SwitchNet uses controller-specific rumble implementations where necessary.

---

# 👥 Multiple Controllers

SwitchNet is not limited to a single player.

The client maintains an ordered **controller roster** so that connected devices can be assigned to player slots.

Controllers can be reordered from the graphical interface.

This allows multiple players located near the streaming client to send their controllers through the network to the same Nintendo Switch.

SwitchNet can therefore be used both for single-player remote play and local multiplayer away from the physical console.

---

# ⌨️ Keyboard and Mouse

SwitchNet also includes **experimental keyboard and mouse controller emulation**.

Keyboard keys can be mapped to Nintendo Switch controller inputs, while mouse movement can be used as an analog input.

Keyboard and mouse mappings support configurable profiles in the same general way as physical controllers.

This feature should currently be considered **experimental**.

---

# 🪟 Windows and 🐧 Linux

SwitchNet provides clients for both **Windows and Linux**.

Although the user-facing functionality is intended to remain consistent, controller access differs significantly between the two operating systems.

For that reason, SwitchNet uses platform-specific implementations where required rather than forcing every controller through a single abstraction layer.

## Client Interface

The graphical client is divided into several sections.

### Controllers

Contains:

- Connected controller list
- Player-slot ordering
- Controller blacklist management

### Mappings

Contains:

- Controller mapping profiles
- Controller-specific mappings
- Keyboard/mouse mappings
- Analog stick deadzones
- Motion-related configuration

### Network

Contains:

- SwitchNet IP address
- UDP configuration
- Update rate
- Automatic discovery

### Extra

Contains application and startup-related settings.

### Diagnostics

Provides information useful for:

- Controller troubleshooting
- Input backend diagnostics
- Network diagnostics
- Rumble diagnostics
- Configuration verification

A persistent status bar provides access to:

- Service status
- Start/Stop toggle
- Switch wake functionality
- Hide to tray
- Close

---

# 🌐 Network Discovery

SwitchNet is designed primarily for use on a **local network**.

The client can automatically discover the SwitchNet endpoint using local network discovery mechanisms such as **mDNS**.

Manual IP configuration remains available when automatic discovery is not appropriate or does not work in a particular network environment.

Controller state is transmitted at a configurable update rate with the goal of keeping input latency low enough for real gameplay.

---

# 🎯 The Goal

The simplest way to describe SwitchNet is:

> **SwitchNet makes the controller follow the player instead of forcing the player to stay within wireless range of the Nintendo Switch.**

The Nintendo Switch can remain permanently connected to:

- Its dock
- A television
- A capture card
- A streaming setup

The player can then move to another room, open the game stream, connect a controller to the nearby computer and continue playing.

```text
Console ───── video/audio ─────► Player

Console ◄──── controller ─────── Player
              via SwitchNet
```

Together, these two paths make remote play inside the home practical without physically moving the Nintendo Switch.

---

# 💡 Inspiration: OpenPuck

The idea behind SwitchNet started thanks to [OpenPuck](https://github.com/safijari/openpuck).

OpenPuck provided the original inspiration for approaching Nintendo Switch controller communication in a way that could be separated from the player's physical proximity to the console.

SwitchNet grew from that inspiration into a larger experiment involving:

- Network controller transport
- Multiple controller families
- Windows and Linux clients
- Motion controls
- Rumble
- Configurable mappings
- Multiple mapping profiles
- Multiple players
- Keyboard and mouse emulation
- Automatic network discovery
- A graphical configuration interface

The OpenPuck project and its contributors therefore deserve credit for inspiring the idea that eventually became SwitchNet.

---

# 🤖 About the Development of SwitchNet

There is one important detail about this project that I want to make completely transparent:

> **I did not personally develop or write the source code of SwitchNet.**

The entire project has been created through **AI-assisted code generation**.

My contribution has instead been:

- Defining the original idea and its goals
- Deciding how the system should behave
- Requesting and designing features
- Testing the software on real hardware
- Testing different controllers
- Identifying bugs and regressions
- Comparing different implementations
- Validating fixes
- Testing networking behavior
- Testing motion controls
- Testing rumble
- Testing mappings
- Testing Windows and Linux behavior
- Repeatedly iterating on the project

So while the source code itself was generated by AI, the project has been driven by **human ideas, requirements, experimentation, hardware testing and iteration**.

This is intentionally disclosed because anyone using or contributing to the project should know how the codebase was produced.

AI-generated code can contain:

- Bugs
- Incorrect assumptions
- Unexpected behavior
- Inefficient implementations
- Platform-specific problems
- Security issues

Code review and contributions from experienced developers are therefore especially welcome.

---

# 🧪 Experimental Project

SwitchNet should be considered an **experimental project**.

Controller hardware is complicated.

Different operating systems can expose the same controller in completely different ways. Firmware revisions can change behavior, USB and Bluetooth paths may behave differently, and some advanced functionality requires communicating directly with controller-specific HID protocols.

Real hardware testing has therefore been a fundamental part of SwitchNet's development.

If something does not work correctly, please consider opening an issue.

## Useful Bug Reports

A useful controller-related bug report should ideally include:

- Operating system
- SwitchNet version
- Controller manufacturer and model
- USB or Bluetooth connection
- Vendor ID and Product ID, when available
- Which buttons work
- Which buttons do not work
- Analog stick behavior
- Gyroscope/accelerometer behavior
- Rumble behavior
- Relevant SwitchNet diagnostics
- Relevant error messages
- Steps required to reproduce the problem

Hardware testing is particularly valuable because many controller-specific behaviors cannot be reliably validated without the physical device.

---

# 📚 Documentation

Additional technical documentation is included in the repository.

Relevant documents include:

- `HTTP_API.md`
- `KEYBOARD_CONTROLLER.md`
- `PARTITIONS.md`
- `USB_HID_TEST_HISTORY.md`

Platform-specific documentation is also available inside:

```text
client-python-linux/
client-python-windows/
```

The repository additionally contains diagnostic and regression-testing utilities under:

```text
tools/
```

These tests document many of the controller and platform-specific regressions encountered during development.

---

# 🤝 Contributing

Contributions are welcome.

Because much of the existing codebase was AI-generated, review from experienced developers is particularly valuable.

Useful contributions include:

- Code review
- Bug fixes
- Controller compatibility improvements
- Testing additional hardware
- Linux compatibility improvements
- Windows compatibility improvements
- Motion-control improvements
- Rumble improvements
- Documentation
- Regression tests
- Network improvements

If you modify controller-specific behavior, please test the change on real hardware whenever possible.

---

# ☕ Support SwitchNet

SwitchNet has required a considerable amount of time for:

- The original idea
- Feature planning
- Hardware testing
- Controller testing
- Troubleshooting
- Regression testing
- Testing AI-generated implementations
- Validating fixes
- Designing and integrating new features

If you enjoy the project and would like to support me for the **idea, time, testing and features that went into making SwitchNet possible**, you can make a donation here:

### ☕ [Support me on Buy Me a Coffee](https://buymeacoffee.com/dovere)

Donations are completely optional and are simply a way to support the time and effort behind the project.

---

# 📄 License

Please refer to the `LICENSE` file included with the repository for the terms under which SwitchNet is distributed.

> [!NOTE]
> Third-party projects, libraries or components used by or referenced by SwitchNet remain subject to their respective licenses.

---

# ⚠️ Disclaimer

SwitchNet is an **independent, unofficial and experimental project**.

It is not affiliated with, authorized by, sponsored by or endorsed by Nintendo, Sony, Valve, Google, Microsoft or any other hardware/software manufacturer mentioned in this project.

Nintendo Switch, Nintendo Switch 2 and other product names and trademarks belong to their respective owners.

SwitchNet is provided without any guarantee of compatibility with every:

- Controller
- Controller firmware revision
- Nintendo Switch firmware revision
- Operating system
- Driver
- USB implementation
- Bluetooth implementation
- Network configuration

Use the project at your own risk.

---

<div align="center">

### 🎮 SwitchNet

**Stream the console. Network the controllers. Play anywhere in your home.**

</div>
