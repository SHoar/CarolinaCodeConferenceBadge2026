# Social Radar

Walking nameplate plus BLE hallway radar. The screen is your identity card (name, RV.NUG, hometown, website). In the background the badge advertises a short name and scans for other badges running this sample. Flip to radar with SW3 for a `Hello, {name}` greeting. A local VIP list paints the five NeoPixels gold when those people walk near you.

Stock badges are invisible until they copy this sample. The air protocol is **name only** — affiliation and URL stay on your screen.

## How to run it

Pick **SocialRadar** from the launcher, or copy this folder's `code.py` over the top-level `code.py` (back up the launcher first).

You also need `adafruit_ble` in `/lib/` (already bundled in this repo).

## How to join the mesh (steal this)

1. Copy `samples/SocialRadar/` onto the CIRCUITPY drive (the launcher picks up any folder under `/samples/` that contains `code.py`).
2. In `settings.toml`:

```toml
RADAR_NAME = "Sean"
RADAR_VIPS = "Alex,Pat"
```

3. Edit the `DISPLAY_*` constants at the top of `code.py` for the on-screen nameplate. Those strings are never broadcast.

`RADAR_NAME` is truncated to 16 ASCII characters on the air. If it is missing, the badge advertises the first word of `DISPLAY_NAME`. `RADAR_VIPS` is a comma-separated list of advertised names (case-insensitive) that *this* badge treats as VIP. Other people do not need to know they are on your list.

## Protocol

| Field | Value |
|-------|--------|
| BLE service UUID | `ccc20260-0001-4000-8000-000000000001` |
| Payload | advertised name only |
| Tracking | BLE address (two people named Sean stay two rows) |
| Found | RSSI ≥ −70 dBm |
| Met | still Found for 6 seconds (RAM only — reset forgets) |
| Drop | 2 seconds without a packet |

The 128-bit UUID is in the primary advertisement; the name rides in the scan response so both fit the 31-byte legacy packet. nRF Connect should show the UUID plus the complete local name.

No WiFi. This sample is meant to last a 9am–4pm CR123A day.

## Controls

| Switch | Nameplate | Radar |
|--------|-----------|--------|
| SW1 (IO1) | Cycle LED mode: radar-status, then SOLID / BREATHE / CHASE / SPARKLE / WAVE | Same (LEDs are global) |
| SW2 (IO2) | Cycle demo palette (ignored in radar-status) | Cycle focus among nearby names |
| SW3 (IO43) | Open radar | Back to nameplate |

A Found or Met event forces the LEDs back to radar-status so a demo pattern cannot hide a hallway moment.

## What you should see

**Nameplate (boot default)** — note line, name, role, hometown, website, `S1 LED  S3 radar`.

**Radar** — `VIP NEARBY` / `FOUND` / `MET` / `SCANNING`, then `Hello,` and a big name. Other people are `+ Jordan found` under that. Empty radar shows `scanning...`. If BLE failed to start, the nameplate still works and radar says `BLE UNAVAILABLE`.

**LEDs**

| Condition | Strip |
|-----------|--------|
| Scanning | Slow dim cyan chase |
| Stranger Found | Cyan pulse |
| VIP in range | All five gold |
| The instant someone Mets | Brief green sparkle |
| BLE failed | Slow red blink |
| Demo pattern | Selected pattern × palette |

## Code design

- **Two `displayio.Group` scenes** — nameplate and radar. SW3 only reassigns `display.root_group`. Scanning never stops.
- **Advertise + short scans** — `ProvideServicesAdvertisement` for the CCC UUID; `start_scan(..., timeout=0.05)` so the LED/button loop stays alive.
- **Address key, name label** — nearby dict keyed by BLE address bytes; a separate `met_addrs` set survives walking away for this process only.
- **VIP is local** — `RADAR_VIPS` is matched against advertised names on this badge. Nothing special goes over the air.
- **Demo LEDs are a mode, not a screen** — SW1 walks radar-status → Nameplate patterns. Presence events set `led_mode` back to 0.

## Configuration

`settings.toml` (copy from `settings.toml.example` if you do not have one yet):

```toml
RADAR_NAME = "Sean"
RADAR_VIPS = "Alex,Pat"
```

Nameplate strings live at the top of `code.py` so they match the other samples' "edit these two lines" workflow.
