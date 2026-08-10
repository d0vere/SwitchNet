# Moonlight coexistence — SwitchNet v1.19.9

Moonlight and SwitchNet must coexist. The correct ownership model is not to pause
or kill Moonlight: Moonlight's SDL layer must ignore the physical Nintendo
Switch 2 Pro Controller (`057e:2069`) while continuing video streaming.

Run once:

```bash
./install-moonlight-coexistence.sh
```

Then fully exit and reopen Moonlight once. From that point Moonlight can remain
running while SwitchNet initializes and reads the controller.

The installer sets both:

- `SDL_GAMECONTROLLER_IGNORE_DEVICES=0x057e/0x2069`
- `SDL_HIDAPI_IGNORE_DEVICES=0x057e/0x2069`

For Flatpak Moonlight it uses a persistent per-app Flatpak override. For native
packages it creates a user-level desktop launcher override. A
`~/.local/bin/moonlight-switchnet` wrapper is also installed.

Only `057e:2069` is excluded from Moonlight. Other controllers are unaffected.
