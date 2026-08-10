# SwitchNet HTTP API

All firmware HTTP endpoints use port 80.

## Read endpoints

- `GET /` — dashboard or setup page.
- `GET /network` — Wi-Fi configuration page.
- `GET /api/status` — complete runtime diagnostics.
- `GET /api/config` — current runtime configuration.
- `GET /api/routes` — machine-readable endpoint inventory.
- `GET /api/wifi/scan` — starts or polls Wi-Fi scanning.

## Write endpoints

- `POST /wifi` — save Wi-Fi credentials and restart validation.
- `POST /api/config` — save hostname, UDP port and emulated-controller mode.
- `POST /api/rumble` — form fields `enabled` and/or `intensity` (0-100).
- `POST /api/auto-wake` — form field `enabled=true|false`.
- `POST /api/wake` — transmit the live Switch 2 BLE wake beacon.
- `POST /api/wake/capture` — schedule 60-second Joy-Con 2 identity capture.
- `POST /api/wake/clear` — clear the stored wake identity.
- `POST /api/ota` — multipart firmware upload.

## Auto wake

Auto wake is enabled by default. When a controller client establishes a new UDP
session, SwitchNet gives the Nintendo USB backend time to prove that the console
is already active. If there is no recent successful USB traffic, one BLE wake
request is sent. The same client session cannot trigger another automatic wake.
