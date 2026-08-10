# Switch 2 Pro Controller USB — v1.19.6

"
For `057e:2069`, SwitchNet first attempts a minimal claim of vendor interface 1.
If libusb returns `EBUSY`, it automatically enters a compatibility fallback
matching the public NSW2 Linux enabler: detach all active kernel drivers on the
composite device, re-assert the active configuration, claim interface 1, send
the 17-command Nintendo initialization sequence, release, and reattach only the
interfaces SwitchNet detached.

If `Resource busy` remains after the fallback,
a userspace process is the likely owner. Close Steam/Steam Input and other
gamepad/HID tools and reconnect the controller. This is deliberately reported
as a distinct diagnostic rather than hidden behind retries.
