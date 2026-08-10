# SwitchNet

Network controller bridge for Nintendo Switch and Nintendo Switch 2 game streaming.

> Stream the console, network the controllers, play anywhere in your home.

SwitchNet is a network controller bridge designed primarily for Nintendo Switch and Nintendo Switch 2 game streaming setups.

The project was created to solve a very practical problem: video from a Nintendo Switch can be captured and streamed to another device over the network, but the physical controller still needs to communicate directly with the console.

That becomes a problem as soon as you move far enough away from the Switch.

SwitchNet solves the other half of the streaming equation:

The video travels over the network, so why shouldn't the controller?

With SwitchNet, controllers can be connected to a Windows or Linux computer near the player. Their inputs are sent over the local network to a SwitchNet device connected to the Nintendo Switch, allowing the console to be controlled even when the player is outside normal controller range.

The result is a setup where you can leave your Switch connected in one place and play it from another room — or potentially anywhere your home network reaches.

Why SwitchNet Exists

Imagine this setup:

ROOM A                              ROOM B

Nintendo Switch                    PC / Laptop / Mini PC
      │                                      │
      │ HDMI                                 │
      ▼                                      │
Capture / Streaming ─── Network ────────► Video
                                             │
                                             ▼
                                           Player
                                             │
                                         Controller
                                             │
                                             ▼
                                      SwitchNet Client
                                             │
                                             │ Network
                                             ▼
Nintendo Switch ◄──── SwitchNet Hardware / Server

Streaming the picture is relatively easy.

The controller is the difficult part.

Nintendo controllers communicate directly with the console, and their usable wireless range is limited. Walls, distance and interference can make playing from another part of the house unreliable or impossible.

SwitchNet moves that controller connection onto the network.

The controller stays next to the player, while SwitchNet transports its state back to the Nintendo Switch.

How It Works

SwitchNet consists of two sides.

SwitchNet Client

The client runs on the computer near the player.

It supports Windows and Linux and is responsible for detecting connected controllers, reading their state and transmitting that information over the network.

Depending on the controller, SwitchNet can handle much more than buttons and analog sticks, including:

Gyroscope
Accelerometer
Rumble
Touchpad input
Additional controller-specific buttons
Custom mappings
Multiple mapping profiles
Per-controller deadzones

SwitchNet also includes experimental keyboard and mouse controller emulation, allowing a computer keyboard and mouse to be mapped to Nintendo Switch controls.

SwitchNet Hardware / Console Side

The other side of SwitchNet is connected to the Nintendo Switch.

It receives controller states from the network and translates them into controller input that the console can understand.

This effectively moves the physical controller connection from:

Controller ───────────────► Nintendo Switch
        Bluetooth / USB

to:

Controller
    │
    ▼
SwitchNet Client
    │
    │ LAN / Wi-Fi
    ▼
SwitchNet
    │
    ▼
Nintendo Switch

The controller can therefore remain with the player even when the Nintendo Switch is located somewhere else in the house.

More Than Basic Button Forwarding

A major goal of SwitchNet is to avoid reducing every controller to just a few buttons and analog sticks.

Modern controllers contain much more functionality, and some games depend heavily on it.

SwitchNet therefore contains controller-specific implementations where necessary.

Depending on the controller and platform, this includes support for functionality such as:

Native button layouts
Analog sticks and triggers
Gyroscope
Accelerometer
Rumble / haptic feedback
Touchpad input
Capture
Home
Additional rear buttons
Controller-specific HID reports

For some devices, generic operating-system controller APIs are sufficient.

For others, SwitchNet communicates with the hardware at a lower level using HID, HIDRaw, USB, evdev or dedicated controller-specific protocols.

Supported Controllers

SwitchNet has been developed and tested with multiple controller families, including:

Nintendo Switch 2 Pro Controller
Nintendo Switch Pro Controller
Sony DualSense
Steam Controller
Google Stadia Controller
XInput-compatible controllers
Generic compatible gamepads
Keyboard and mouse emulation

Support varies depending on the controller and operating system.

Some controllers have dedicated implementations to expose features that would otherwise be unavailable through generic controller APIs.

For example, the Nintendo Switch 2 Pro Controller uses dedicated implementations for functionality such as native input reports, motion sensors, additional buttons and rumble.

Controller Mapping

SwitchNet provides configurable controller mappings rather than requiring every physical controller to follow the same layout.

Multiple profiles can be created for supported controller families.

Mappings can cover standard controls such as:

A / B / X / Y
L / R
ZL / ZR
D-Pad
L3 / R3
+ / -
Home
Capture

as well as controller-specific inputs where supported.

Deadzone configuration is also available independently for different controller families.

This allows SwitchNet to accommodate the different physical layouts and behaviors of Nintendo, Sony, Valve, Google and XInput controllers while presenting the correct controls to the console.

Gyroscope and Motion Controls

Motion controls are particularly important on Nintendo platforms.

SwitchNet therefore forwards gyroscope and accelerometer information for supported controllers rather than limiting communication to conventional gamepad state.

Controller-specific processing and calibration are used where required to convert the physical controller's coordinate system into the motion representation expected by SwitchNet and the console.

This makes motion-controlled games usable even though the controller itself is connected to the remote client rather than directly to the Nintendo Switch.

Rumble

Controller feedback can travel in the opposite direction.

Instead of communication being limited to:

Controller → Network → Switch

SwitchNet can also transport supported feedback back toward the player:

Switch → Network → Client → Controller

This allows rumble to remain functional on supported controllers despite the controller being physically located on the remote side of the network.

Different controllers use different feedback mechanisms, so SwitchNet contains controller-specific implementations where necessary.

Multiple Controllers

SwitchNet is not limited to a single player.

The client maintains an ordered controller roster so that connected devices can be assigned to player slots.

Controllers can be reordered from the graphical interface, allowing multiple players near the streaming client to send their controllers back to the same Nintendo Switch.

This makes the project useful not only for playing alone from another room, but also for local multiplayer away from the physical console.

Windows and Linux Clients

SwitchNet provides clients for both Windows and Linux.

Although the user-facing functionality is intended to remain consistent, controller access differs significantly between the two operating systems.

For that reason, SwitchNet uses platform-specific implementations when required rather than forcing every controller through a single abstraction layer.

The GUI provides dedicated sections for:

Controllers — connected controllers, player order and blacklist management.

Mappings — controller profiles, keyboard/mouse configuration and deadzones.

Network — SwitchNet address, UDP configuration, update rate and discovery.

Extra — startup and application behavior.

Diagnostics — information useful for testing controllers and troubleshooting communication.

The persistent status bar provides service control, Switch wake functionality, tray controls and application status.

Network Discovery

SwitchNet is designed for a local-network environment.

The client can discover the SwitchNet endpoint automatically, including local network discovery mechanisms such as mDNS, while manual addressing remains available when required.

Controller state is transmitted at a configurable update rate with the goal of keeping input latency low enough for real gameplay.

The Goal

The simplest way to describe the project is:

SwitchNet makes the controller follow the player instead of forcing the player to stay within wireless range of the Nintendo Switch.

A Switch can remain permanently connected to a dock, capture setup or streaming system.

The player can then move to another room, open the game stream, connect a controller to the nearby computer and continue playing.

Video travels from the console to the player.

Controller input travels from the player back to the console.

Together, the two paths make remote play inside the home practical without physically moving the Nintendo Switch.

Inspiration: OpenPuck

The idea behind SwitchNet started thanks to OpenPuck.

OpenPuck provided the original inspiration for approaching Nintendo Switch controller communication in a way that could be separated from the player's physical proximity to the console.

SwitchNet grew from that inspiration into a larger experiment involving network controller transport, multiple controller families, Windows and Linux clients, motion controls, rumble, configurable mappings, multiple players and a graphical configuration interface.

The OpenPuck project and its contributors therefore deserve credit for inspiring the idea that eventually became SwitchNet.

About the Development of SwitchNet

There is one important detail about this project that I want to make completely transparent:

I did not personally develop or write the source code of SwitchNet.

The entire project has been created through AI-assisted code generation.

My contribution has instead been defining the original idea and its goals, deciding how the system should behave, requesting and designing features, testing the software on real hardware, identifying bugs and regressions, comparing different implementations, validating fixes and repeatedly iterating on the project.

This included extensive real-world testing of controllers, motion controls, rumble, networking, mappings, Windows and Linux behavior and the interaction between the client and the Nintendo Switch.

So while the source code itself was generated by AI, the project has been driven by human ideas, requirements, experimentation and extensive hardware testing.

This is intentionally disclosed because anyone using or contributing to the project should know how the codebase was produced.

AI-generated code can contain bugs, incorrect assumptions and unexpected behavior. Code review and contributions from experienced developers are therefore especially welcome.

Experimental Project

SwitchNet should be considered an experimental project.

Controller hardware is complicated.

Different operating systems expose the same controller differently, firmware revisions can change behavior, USB and Bluetooth paths may behave differently, and some advanced functionality requires communicating directly with proprietary HID protocols.

Real hardware testing has therefore been a fundamental part of SwitchNet's development.

Bug reports are welcome, particularly when they contain information about:

Operating system
Controller model
Connection method
Vendor ID / Product ID
Button or stick problems
Gyroscope behavior
Rumble behavior
Relevant diagnostics
Reproduction steps
Support SwitchNet

SwitchNet has required a considerable amount of time for the original idea, feature planning, hardware testing, troubleshooting, regression testing and repeatedly validating new implementations.

If you enjoy the project and would like to support me for the idea, time, testing and features that went into making SwitchNet possible, you can make a donation here:

☕ Support me on Buy Me a Coffee

Donations are completely optional and are simply a way to support the time and effort behind the project.

Disclaimer

SwitchNet is an independent, unofficial project.

It is not affiliated with, authorized by, sponsored by or endorsed by Nintendo, Sony, Valve, Google, Microsoft or any other hardware/software manufacturer mentioned in this project.

Nintendo Switch, Nintendo Switch 2 and other product names and trademarks belong to their respective owners.

SwitchNet is provided as experimental software without any guarantee of compatibility with every controller, firmware version, operating system or network configuration.

SwitchNet — stream the console, network the controllers, play anywhere in your home.
