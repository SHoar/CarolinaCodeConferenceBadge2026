# Social Radar — CCC 2026 Badge Design

Date: 2026-08-13
Status: approved

## Goal

A launcher sample that is a walking nameplate first and a BLE “who am I walking near” radar second. Worn 9am–4pm on conference days. Personalized hallway greetings for anyone running the same sample, with extra-special treatment for a local VIP list (array of names).

Stock badges are invisible. “Every attendee” is an adoption goal: the protocol is name-only and documented so copying one folder plus two `settings.toml` lines is enough to join.

## Out of scope

- Detecting attendees still running the stock launcher
- Broadcasting affiliation, hometown, URL, or attendance count
- Persisting a met log to the filesystem or NVM (RAM only; reset or power loss clears it)
- WiFi, CTF tooling, or a cloud check-in server
- Attacking or scraping [ctf.dc864.org](https://ctf.dc864.org/)
- Mutual handshake / button-to-log meetings

## Hardware

Existing CCC 2026 badge: ESP32-S3, ST7735 128×160 portrait LCD (`adafruit_st7735r`, `rotation=0`), 5 WS2812 NeoPixels on GPIO4, three active-low switches (SW1 GPIO1, SW2 GPIO2, SW3 GPIO43). Powered by CR123A for a full conference day — no WiFi in this sample.

## Architecture

One new sample: `samples/SocialRadar/`. The existing launcher auto-discovers any folder under `/samples/` that contains `code.py`, so no launcher change is required.

Two jobs share one main loop:

1. **Foreground nameplate** — local identity on the LCD (not broadcast).
2. **Background BLE mesh** — advertise `RADAR_NAME`, scan for other CCC radar advertisements, drive the NeoPixels in both screen modes.

SW3 toggles the LCD between nameplate and radar. LEDs always reflect radar state unless the wearer is in an LED demo pattern, which Found/Met interrupts.

```
Nameplate LCD  --SW3-->  Radar LCD
       ^                    |
       +--------SW3---------+
BLE advertise+scan --> nearby table --> LEDs + radar view
```

Follow the existing sample pattern: a single `code.py` plus a README. Do not split into extra modules unless `code.py` becomes unmaintainable.

## Air protocol

- BLE advertise + scan using `adafruit_ble` (must be copied into `lib/` from the CircuitPython library bundle; it is not on the drive today).
- Custom 128-bit service UUID `ccc20260-0001-4000-8000-000000000001` (constant in `code.py` and the README) so headphones and phones are ignored.
- Payload: advertised name only, ASCII, truncated to 16 characters.
- Tracking key: BLE address. Display label: advertised name. Two people named Sean appear as two rows that both say “Sean”.
- No WiFi. Conference WiFi is unused by this sample.

Strangers join by copying `samples/SocialRadar/` onto their CIRCUITPY drive (or picking it from the launcher after dropping the folder under `/samples/`) and setting `RADAR_NAME`.

## Configuration

`settings.toml` (string values only; no arrays):

```toml
RADAR_NAME = "Sean"
RADAR_VIPS = "Alex,Pat"
```

- `RADAR_NAME`: what this badge broadcasts. If missing or empty, advertise the first word of the nameplate display name (`Sean` from `Sean Hoar`).
- `RADAR_VIPS`: comma-separated names, case-insensitive match against advertised names. These people get VIP LED color and VIP greeting copy. The list lives only on this badge; VIPs do not broadcast a special flag.

Nameplate lines are constants at the top of `samples/SocialRadar/code.py` (same style as the stock Nameplate sample), defaulted for this wearer:

- Display name: FIRSTNAME LASTNAME
- Role: Role
- Hometown: HOMETOWN
- URL: URL
- Note: NOTE

Anyone who copies the sample edits those constants for themselves. They are never placed in BLE packets.

## Screens

Portrait 128×160, `auto_refresh=False`, explicit `display.refresh()`, backlight GPIO5 on after init (dark during slow imports, matching the launcher).

### Nameplate (boot default)

Identity card, not giant two-line name:

- Note line (NOTE)
- FIRSTNAME LASTNAME
- Role
- HOMETOWN
- URL
- Button hint: `S1 LED  S3 radar`

### Radar

Greeting-hero layout:

- Status chip: `VIP NEARBY` / `FOUND` / `MET` / `SCANNING`
- Big hello: `Hello,` + the focus name (VIP gold, stranger cyan)
- Footer of other people: `+ Jordan found` / `+ Sam met`
- Empty: `scanning…` (no fabricated name)
- Button hint: `S2 next  S3 back`

Focus priority: VIP in range, else newest Found, else Met still nearby, else scanning. SW2 cycles focus among people currently in range when more than one is present.

## Buttons

| Switch | Nameplate | Radar |
|--------|-----------|--------|
| SW1 | Cycle LED mode: radar-status, then SOLID / BREATHE / CHASE / SPARKLE / WAVE | Same — LEDs are global |
| SW2 | Cycle demo palette: RAINBOW / WHITE / RED / ORANGE / YELLOW / GREEN / CYAN / BLUE / PURPLE / PINK (ignored while LED mode is radar-status) | Cycle radar focus among nearby names |
| SW3 | Toggle to radar | Toggle to nameplate |

Edge-triggered, debounced, same pattern as existing samples. SW3 is never “LEDs off”.

Found or Met while a demo pattern is active forces LED mode back to radar-status so a hallway moment is visible.

## LED states

Brightness 0.2 (battery and 3.3 V rail, consistent with other samples).

| Condition | Strip |
|-----------|--------|
| Scanning, nobody nearby | Slow dim cyan chase |
| Stranger Found (dwell counting) | Cyan pulse |
| VIP Found or VIP is focus | All five gold |
| Met (the instant dwell completes) | Brief green sparkle, then the appropriate still-nearby state |
| BLE init failed | Slow red blink |
| Demo pattern | Selected pattern × palette, until Found/Met interrupts |

## Found and Met

- **Found:** advertisement with our service UUID and RSSI ≥ −70 dBm. Dwell timer starts. Drop below the threshold (or disappear from scans) and the timer resets; they leave the nearby table after 2.0 seconds without a packet.
- **Met:** still Found for 6 seconds continuously. No button press. Stored in RAM for the rest of this process lifetime only. Reset, `code.py` reload, or power loss clears Met.
- Once Met, returning to range does not sparkle again; they show as Met in the list and may take focus only if nothing higher-priority is present.

## Data flow

1. Advertise `RADAR_NAME` continuously.
2. Scan; keep a dict keyed by BLE address: name, rssi, last_seen, in_range_since, met (bool).
3. Each loop: expire stale entries, promote Found → Met, choose focus, update LEDs, refresh LCD at ~10 Hz (LEDs every iteration).
4. Screen mode is independent of the table; toggling SW3 does not pause scanning.

## Error handling

- BLE init failure: nameplate still runs; LEDs red blink; radar screen shows `BLE unavailable`. Do not crash into REPL.
- Name longer than 16 characters: truncate for the advertisement only.
- Empty VIP list: legal; nobody is VIP.
- VIP match is on advertised name, not BLE address (so a VIP who changes `RADAR_NAME` stops matching until the list is updated).
- Font-chip CS held high so it does not fight the LCD on SPI (existing badge rule).

## Testing

Before the conference, with at least two badges (or one badge plus nRF Connect):

- Advertisement visible to nRF Connect with the documented UUID and name.
- Walk-toward / walk-away crosses the −70 dBm gate; Found appears and disappears.
- Six-second dwell promotes Found → Met; Met sparkle happens once.
- VIP name paints gold and wins focus over a stranger.
- SW3 toggles screens; scanning continues on the nameplate.
- SW1 demo pattern is interrupted by a Found event.
- Unplug BLE by using a build without the library (or a forced init failure) and confirm nameplate still works.
- Cold boot: backlight stays dark during imports, then nameplate appears.

## Files to add or change

- Add `samples/SocialRadar/code.py`
- Add `samples/SocialRadar/README.md` (what it does, controls, steal-this protocol, `settings.toml` keys, how others join)
- Add `adafruit_ble` (and its bundle dependencies) under `lib/`
- Document `RADAR_NAME` / `RADAR_VIPS` in `settings.toml.example`
- No launcher edit unless discovery fails in practice

## Success criteria

Sean can wear the badge as a nameplate all day, flip to radar with SW3, see `Hello, {name}` for people running this sample, get a gold salute when another VIP (friend or colleague) is in walking range, and last a 9am–4pm day on CR123A without WiFi. A stranger can join from the README in a few minutes.
