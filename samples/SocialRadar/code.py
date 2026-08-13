"""
code.py -- Social Radar for the Carolina Code Conference 2026 badge
===================================================================
Walking nameplate plus BLE hallway radar. Advertise a short name, scan
for other badges running this sample, greet people who walk near you.

The air protocol is name-only. Affiliation / hometown / URL stay on
YOUR screen. A local VIP list (the other RV.NUG officers, friends)
gets a gold salute when those advertised names are in range.

Controls
--------
  SW1 (IO1)   -- cycle LED mode: radar-status, then SOLID / BREATHE /
                 CHASE / SPARKLE / WAVE (global, both screens)
  SW2 (IO2)   -- nameplate: cycle demo palette
                 radar: cycle focus among nearby names
  SW3 (IO43)  -- toggle nameplate <-> radar

Found (RSSI >= -70 dBm) or Met (6 s dwell) steals the LEDs back from
a demo pattern so you don't miss a hallway moment.

Join the mesh: copy this folder onto CIRCUITPY (or pick SocialRadar
from the launcher) and set RADAR_NAME in settings.toml.
"""

# ==============================================================
#   >>>  YOUR NAMEPLATE  <<<
#   Local display only -- never broadcast. Edit these, save,
#   CircuitPython reloads.
# ==============================================================
DISPLAY_NAME = "FIRSTNAME LASTNAME"
DISPLAY_ROLE = "ROLE"
DISPLAY_HOME = "HOMETOWN"
DISPLAY_URL  = "URL"
DISPLAY_NOTE = "NOTE"
# ==============================================================

# --- backlight off FIRST, before slow imports -----------------
import board
import digitalio
bl = digitalio.DigitalInOut(board.IO5)
bl.direction = digitalio.Direction.OUTPUT
bl.value = False

import os
import time
import math
import random
import busio
import displayio
import fourwire
import neopixel
import terminalio
import adafruit_st7735r
from adafruit_display_text import label


# ------------------------------------------------------------------
# Config (settings.toml). Name-only on the air.
# ------------------------------------------------------------------
RADAR_UUID_STR = "ccc20260-0001-4000-8000-000000000001"
NAME_MAX = 16
RSSI_FOUND = -70
DWELL_MET_S = 6.0
MISS_TIMEOUT_S = 2.0
LED_BRIGHTNESS = 0.2
SCAN_TIMEOUT_S = 0.05
DISPLAY_PERIOD_S = 0.1
DEBOUNCE_S = 0.15

def _first_word(text):
    parts = text.strip().split(" ")
    return parts[0] if parts and parts[0] else "Badge"


def _parse_vips(raw):
    if not raw:
        return ()
    out = []
    for part in raw.split(","):
        name = part.strip().lower()
        if name:
            out.append(name)
    return tuple(out)


_env_name = os.getenv("RADAR_NAME")
if _env_name:
    _env_name = _env_name.strip()
RADAR_NAME = (_env_name or _first_word(DISPLAY_NAME))[:NAME_MAX]
VIPS = _parse_vips(os.getenv("RADAR_VIPS") or "")


# ------------------------------------------------------------------
# Hardware
# ------------------------------------------------------------------
pixels = neopixel.NeoPixel(board.IO4, 5, brightness=LED_BRIGHTNESS, auto_write=False)
pixels.fill((0, 0, 0))
pixels.show()

sw1 = digitalio.DigitalInOut(board.IO1)
sw1.switch_to_input(pull=digitalio.Pull.UP)
sw2 = digitalio.DigitalInOut(board.IO2)
sw2.switch_to_input(pull=digitalio.Pull.UP)
sw3 = digitalio.DigitalInOut(board.IO43)
sw3.switch_to_input(pull=digitalio.Pull.UP)

font_cs = digitalio.DigitalInOut(board.IO9)
font_cs.direction = digitalio.Direction.OUTPUT
font_cs.value = True

displayio.release_displays()
spi = busio.SPI(clock=board.IO12, MOSI=board.IO11)
display_bus = fourwire.FourWire(
    spi, command=board.IO6, chip_select=board.IO10, reset=board.IO7,
    baudrate=8_000_000,
)
display = adafruit_st7735r.ST7735R(
    display_bus, width=128, height=160, rotation=0, bgr=True, auto_refresh=False,
)


# ------------------------------------------------------------------
# Color helpers (same idea as Nameplate)
# ------------------------------------------------------------------
def hsv_to_rgb(h, s, v):
    if s == 0.0:
        c = int(v * 255)
        return (c, c, c)
    h6 = h * 6.0
    i = int(h6) % 6
    f = h6 - int(h6)
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    if i == 0:
        return (int(v * 255), int(t * 255), int(p * 255))
    if i == 1:
        return (int(q * 255), int(v * 255), int(p * 255))
    if i == 2:
        return (int(p * 255), int(v * 255), int(t * 255))
    if i == 3:
        return (int(p * 255), int(q * 255), int(v * 255))
    if i == 4:
        return (int(t * 255), int(p * 255), int(v * 255))
    return (int(v * 255), int(p * 255), int(q * 255))


def scale_rgb(rgb, b):
    if b < 0.0:
        b = 0.0
    elif b > 1.0:
        b = 1.0
    return (int(rgb[0] * b), int(rgb[1] * b), int(rgb[2] * b))


PALETTES = [
    ("RAINBOW", None),
    ("WHITE",   (255, 255, 255)),
    ("RED",     (255,   0,   0)),
    ("ORANGE",  (255, 120,   0)),
    ("YELLOW",  (255, 220,   0)),
    ("GREEN",   (  0, 255,   0)),
    ("CYAN",    (  0, 200, 255)),
    ("BLUE",    ( 30,  60, 255)),
    ("PURPLE",  (180,   0, 255)),
    ("PINK",    (255,  50, 150)),
]
PATTERNS = ("SOLID", "BREATHE", "CHASE", "SPARKLE", "WAVE")

CYAN = (0, 200, 255)
GOLD = (255, 204, 51)
GREEN = (0, 220, 80)
RED = (255, 0, 0)

COLOR_BG = 0x0A1628
COLOR_MUTED = 0x7AA0C8
COLOR_NAME = 0x7EC8FF
COLOR_GOLD = 0xFFCC33
COLOR_BODY = 0xC5D4E4
COLOR_DIM = 0x9BB3C9
COLOR_HINT = 0x5E7A94
COLOR_CYAN = 0x3EC6FF


def palette_color(pal_idx, pixel_i, t):
    if pal_idx == 0:
        hue = ((pixel_i / 5.0) + t * 0.15) % 1.0
        return hsv_to_rgb(hue, 1.0, 1.0)
    return PALETTES[pal_idx][1]


def render_pattern(pattern, pal_idx, t):
    out = [(0, 0, 0)] * 5
    if pattern == "SOLID":
        for i in range(5):
            out[i] = palette_color(pal_idx, i, t)
    elif pattern == "BREATHE":
        b = 0.15 + 0.85 * ((math.sin(t * 2.2) + 1) / 2)
        for i in range(5):
            out[i] = scale_rgb(palette_color(pal_idx, i, t), b)
    elif pattern == "CHASE":
        pos = (t * 3.0) % 5.0
        for i in range(5):
            d = min(abs(i - pos), abs(i - pos - 5), abs(i - pos + 5))
            b = max(0.0, 1.0 - d * 0.55)
            out[i] = scale_rgb(palette_color(pal_idx, i, t), b)
    elif pattern == "SPARKLE":
        for i in range(5):
            if random.random() < 0.25:
                out[i] = scale_rgb(palette_color(pal_idx, i, t), random.uniform(0.4, 1.0))
    elif pattern == "WAVE":
        for i in range(5):
            phase = t * 3.0 - i * 0.6
            b = 0.15 + 0.85 * ((math.sin(phase) + 1) / 2)
            out[i] = scale_rgb(palette_color(pal_idx, i, t), b)
    return out


def render_cyan_chase(t):
    pos = (t * 1.4) % 5.0
    out = [(0, 0, 0)] * 5
    for i in range(5):
        d = min(abs(i - pos), abs(i - pos - 5), abs(i - pos + 5))
        b = max(0.08, 0.55 - d * 0.35)
        out[i] = scale_rgb(CYAN, b)
    return out


def render_pulse(rgb, t, speed=3.0):
    b = 0.25 + 0.75 * ((math.sin(t * speed) + 1) / 2)
    c = scale_rgb(rgb, b)
    return [c, c, c, c, c]


def render_sparkle_green():
    out = [(0, 0, 0)] * 5
    for i in range(5):
        if random.random() < 0.55:
            out[i] = scale_rgb(GREEN, random.uniform(0.4, 1.0))
    return out


def render_red_blink(t):
    on = (int(t * 1.5) % 2) == 0
    c = RED if on else (40, 0, 0)
    return [c, c, c, c, c]


# ------------------------------------------------------------------
# BLE -- advertise name + service UUID; scan for the same UUID.
# 128-bit UUID lives in the primary packet; the name is in the
# scan response (31-byte adv limit). Merge both by address.
# ------------------------------------------------------------------
ble = None
ble_ok = False
own_addr = b""
RADAR_UUID = None

try:
    from adafruit_ble import BLERadio
    from adafruit_ble.advertising import Advertisement
    from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
    from adafruit_ble.services import Service
    from adafruit_ble.uuid import VendorUUID

    class CCCRadarService(Service):
        uuid = VendorUUID(RADAR_UUID_STR)

    RADAR_UUID = CCCRadarService.uuid
    ble = BLERadio()
    ble.name = RADAR_NAME
    own_addr = bytes(ble.address_bytes)
    adv = ProvideServicesAdvertisement(CCCRadarService())
    adv.connectable = False
    ble.start_advertising(adv)
    ble_ok = True
    print("SocialRadar advertising as %s" % RADAR_NAME)
except Exception as exc:
    ble_ok = False
    print("BLE unavailable:", exc)


# ------------------------------------------------------------------
# Nearby table. Keyed by BLE address bytes. Met is a separate set
# so walking away does not forget a meeting this process.
# ------------------------------------------------------------------
nearby = {}
met_addrs = set()
focus_key = None
sparkle_until = 0.0
led_mode = 0          # 0 = radar-status, then 1..len(PATTERNS)
palette_idx = 0
screen_radar = False
interrupt_demo = False


def _is_vip(name):
    if not name:
        return False
    return name.lower() in VIPS


def ingest(adv):
    try:
        addr = bytes(adv.address.address_bytes)
    except AttributeError:
        return
    if own_addr and addr == own_addr:
        return

    has_uuid = False
    services = getattr(adv, "services", None)
    if services:
        try:
            has_uuid = RADAR_UUID in services
        except (TypeError, AttributeError, ValueError):
            has_uuid = False

    name = getattr(adv, "complete_name", None) or getattr(adv, "short_name", None)
    if name:
        name = str(name).strip()[:NAME_MAX]
        if not name:
            name = None

    if addr not in nearby:
        if not has_uuid:
            return
        nearby[addr] = {
            "name": name,
            "rssi": adv.rssi,
            "last_seen": time.monotonic(),
            "in_range_since": None,
        }
        return

    peer = nearby[addr]
    peer["rssi"] = adv.rssi
    peer["last_seen"] = time.monotonic()
    if name:
        peer["name"] = name


def poll_ble():
    if not ble_ok:
        return
    try:
        for adv in ble.start_scan(
            ProvideServicesAdvertisement,
            Advertisement,
            timeout=SCAN_TIMEOUT_S,
            active=True,
            minimum_rssi=-85,
        ):
            ingest(adv)
    except Exception as exc:
        print("scan error:", exc)
    try:
        ble.stop_scan()
    except Exception:
        pass


def update_presence(now):
    global sparkle_until, interrupt_demo, focus_key
    stale = []
    newly_found = False
    newly_met = False
    for addr, peer in nearby.items():
        if now - peer["last_seen"] > MISS_TIMEOUT_S:
            stale.append(addr)
            continue
        in_range = peer["rssi"] >= RSSI_FOUND
        if in_range:
            if peer["in_range_since"] is None:
                peer["in_range_since"] = now
                newly_found = True
            elif (addr not in met_addrs) and (now - peer["in_range_since"] >= DWELL_MET_S):
                met_addrs.add(addr)
                newly_met = True
        else:
            peer["in_range_since"] = None
    for addr in stale:
        del nearby[addr]
        if focus_key == addr:
            focus_key = None
    if newly_found or newly_met:
        interrupt_demo = True
        if led_mode != 0:
            print("radar event -- LEDs back to status")
    if newly_met:
        sparkle_until = now + 0.45


def in_range_peers():
    """Named peers currently at Found-or-closer RSSI, VIP first."""
    rows = []
    for addr, peer in nearby.items():
        if peer["in_range_since"] is None:
            continue
        name = peer["name"]
        if not name:
            continue
        vip = _is_vip(name)
        met = addr in met_addrs
        rows.append((vip, not met, peer["last_seen"], addr, name, met))
    # VIP, then still-Found (not yet Met), then newest last_seen
    rows.sort(key=lambda r: (not r[0], not r[1], -r[2]))
    return rows


def choose_focus(rows):
    global focus_key
    if not rows:
        focus_key = None
        return None
    keys = [r[3] for r in rows]
    vip_keys = [r[3] for r in rows if r[0]]
    if focus_key not in keys:
        focus_key = vip_keys[0] if vip_keys else keys[0]
    elif vip_keys and focus_key not in vip_keys:
        focus_key = vip_keys[0]
    for r in rows:
        if r[3] == focus_key:
            return r
    return rows[0]


def cycle_focus(rows):
    global focus_key
    if not rows:
        focus_key = None
        return
    keys = [r[3] for r in rows]
    if focus_key not in keys:
        focus_key = keys[0]
        return
    i = keys.index(focus_key)
    focus_key = keys[(i + 1) % len(keys)]


# ------------------------------------------------------------------
# Display scenes
# ------------------------------------------------------------------
def _label(text, color, x, y, scale=1, anchor=None, pos=None):
    lbl = label.Label(terminalio.FONT, text=text, color=color, scale=scale)
    if anchor:
        lbl.anchor_point = anchor
        lbl.anchored_position = pos
    else:
        lbl.x = x
        lbl.y = y
    return lbl


def _bg_group(color):
    g = displayio.Group()
    bmp = displayio.Bitmap(128, 160, 1)
    pal = displayio.Palette(1)
    pal[0] = color
    g.append(displayio.TileGrid(bmp, pixel_shader=pal))
    return g


name_scene = _bg_group(COLOR_BG)
name_scene.append(_label(DISPLAY_NOTE, COLOR_MUTED, 0, 0, anchor=(0.5, 0.0), pos=(64, 8)))
name_scene.append(_label(DISPLAY_NAME, COLOR_NAME, 0, 0, scale=2, anchor=(0.5, 0.0), pos=(64, 28)))
name_scene.append(_label(DISPLAY_ROLE, COLOR_GOLD, 0, 0, anchor=(0.5, 0.0), pos=(64, 62)))
name_scene.append(_label(DISPLAY_HOME, COLOR_BODY, 0, 0, anchor=(0.5, 0.0), pos=(64, 80)))
name_scene.append(_label(DISPLAY_URL, COLOR_DIM, 0, 0, anchor=(0.5, 0.0), pos=(64, 98)))
name_hint = _label("S1 LED  S3 radar", COLOR_HINT, 0, 0, anchor=(0.5, 1.0), pos=(64, 156))
name_scene.append(name_hint)

radar_scene = _bg_group(COLOR_BG)
radar_status = _label("SCANNING", COLOR_MUTED, 0, 0, anchor=(0.5, 0.0), pos=(64, 8))
radar_hello = _label("Hello,", COLOR_DIM, 0, 0, anchor=(0.5, 0.0), pos=(64, 36))
radar_focus = _label("scanning...", COLOR_MUTED, 0, 0, scale=2, anchor=(0.5, 0.0), pos=(64, 56))
radar_extra1 = _label("", COLOR_CYAN, 0, 0, anchor=(0.5, 0.0), pos=(64, 100))
radar_extra2 = _label("", COLOR_HINT, 0, 0, anchor=(0.5, 0.0), pos=(64, 114))
radar_hint = _label("S2 next  S3 back", COLOR_HINT, 0, 0, anchor=(0.5, 1.0), pos=(64, 156))
radar_scene.append(radar_status)
radar_scene.append(radar_hello)
radar_scene.append(radar_focus)
radar_scene.append(radar_extra1)
radar_scene.append(radar_extra2)
radar_scene.append(radar_hint)

display.root_group = name_scene
display.refresh()
bl.value = True


def _fit_name(text, scale):
    max_chars = max(1, 128 // (6 * scale))
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "."


def refresh_radar_labels(rows, focus_row):
    if not ble_ok:
        radar_status.text = "BLE UNAVAILABLE"
        radar_status.color = 0xFF3333
        radar_hello.text = ""
        radar_focus.scale = 1
        radar_focus.text = "nameplate still works"
        radar_focus.color = COLOR_DIM
        radar_extra1.text = ""
        radar_extra2.text = ""
        return

    if not focus_row:
        radar_status.text = "SCANNING"
        radar_status.color = COLOR_MUTED
        radar_hello.text = ""
        radar_focus.scale = 1
        radar_focus.text = "scanning..."
        radar_focus.color = COLOR_MUTED
        radar_extra1.text = ""
        radar_extra2.text = ""
        return

    vip, is_found, _seen, _addr, name, met = focus_row
    if vip:
        radar_status.text = "VIP NEARBY"
        radar_status.color = COLOR_GOLD
        radar_focus.color = COLOR_GOLD
    elif is_found:
        radar_status.text = "FOUND"
        radar_status.color = COLOR_CYAN
        radar_focus.color = COLOR_CYAN
    else:
        radar_status.text = "MET"
        radar_status.color = COLOR_DIM
        radar_focus.color = COLOR_DIM

    radar_hello.text = "Hello,"
    radar_focus.scale = 2 if len(name) <= 10 else 1
    radar_focus.text = _fit_name(name, radar_focus.scale)

    extras = []
    for row in rows:
        if row[3] == focus_row[3]:
            continue
        tag = "vip" if row[0] else ("found" if row[1] else "met")
        extras.append("+ %s %s" % (row[4], tag))
    radar_extra1.text = extras[0] if len(extras) > 0 else ""
    radar_extra2.text = extras[1] if len(extras) > 1 else ""


def show_screen():
    display.root_group = radar_scene if screen_radar else name_scene


# ------------------------------------------------------------------
# LED status
# ------------------------------------------------------------------
def render_status_leds(t, now, rows, focus_row):
    if not ble_ok:
        return render_red_blink(t)
    if now < sparkle_until:
        return render_sparkle_green()
    if not rows:
        return render_cyan_chase(t)
    any_vip = False
    any_found = False
    for row in rows:
        if row[0]:
            any_vip = True
        if row[1]:
            any_found = True
    if any_vip or (focus_row and focus_row[0]):
        return render_pulse(GOLD, t, 2.4)
    if any_found:
        return render_pulse(CYAN, t, 3.2)
    return render_pulse(CYAN, t, 1.4)


# ------------------------------------------------------------------
# Main loop
# ------------------------------------------------------------------
sw1_prev = True
sw2_prev = True
sw3_prev = True
last_press = 0.0
last_display = 0.0

print("SocialRadar nameplate: %s" % DISPLAY_NAME)
print("  RADAR_NAME=%s  VIPs=%s" % (RADAR_NAME, ",".join(VIPS) if VIPS else "(none)"))

while True:
    now = time.monotonic()
    v1, v2, v3 = sw1.value, sw2.value, sw3.value
    if now - last_press > DEBOUNCE_S:
        if (not v1) and sw1_prev:
            led_mode = (led_mode + 1) % (1 + len(PATTERNS))
            last_press = now
            if led_mode == 0:
                print("LED mode: radar-status")
            else:
                print("LED mode:", PATTERNS[led_mode - 1])
        if (not v2) and sw2_prev:
            last_press = now
            if screen_radar:
                cycle_focus(in_range_peers())
            elif led_mode != 0:
                palette_idx = (palette_idx + 1) % len(PALETTES)
                print("palette:", PALETTES[palette_idx][0])
        if (not v3) and sw3_prev:
            screen_radar = not screen_radar
            show_screen()
            last_press = now
            print("screen:", "radar" if screen_radar else "nameplate")
    sw1_prev, sw2_prev, sw3_prev = v1, v2, v3

    poll_ble()
    now = time.monotonic()
    update_presence(now)
    if interrupt_demo:
        led_mode = 0
        interrupt_demo = False

    rows = in_range_peers()
    focus_row = choose_focus(rows)

    t = now
    if led_mode == 0:
        rgb_list = render_status_leds(t, now, rows, focus_row)
    else:
        rgb_list = render_pattern(PATTERNS[led_mode - 1], palette_idx, t)
    for i in range(5):
        pixels[i] = rgb_list[i]
    pixels.show()

    if now - last_display > DISPLAY_PERIOD_S:
        if screen_radar:
            refresh_radar_labels(rows, focus_row)
        display.refresh()
        last_display = now
