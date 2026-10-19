"""AIMO-Effekt-Engine: software-gerenderte per-key LED-Maps.

Reproduziert die in EFFEKTE.md definierten AIMO-Effekte im "AIMO-Stil":

  E1  gradient     - Farbverlauf ueber einen AIMO-Theme (Farbstopps)
  E2  static       - konstante Einzelfarbe (Spezialfall gradient)
  E3  wave         - Welle ueber das LED-Grid
  E4  breathing    - Atmen (Helligkeits-Envelope auf einer Basisfarbe)
  E5  colorcycle   - Farbzyklus (Hue-Rotation)

Prinzip (Eruption-Ansatz, siehe EFFEKTE.md): Jeder Effekt wird pro Frame auf
einer per-key LED-Map berechnet und ueber die geraetespezifische send_led_map
uebertragen. Es gibt keinen "Ein-Modus-Command" - die Animation liegt in
Software.

Evidenz (Quellen):
  - roccat_vulcan_1xx.rs  (Eruption): 143 Keys, 6x21-Grid, send_led_map
    448-B-Puffer, Header [0xa1,0x01,0x01,0xb4], 7 Chunks a 64 B, 65-B-Report.
  - roccat_kone_aimo.rs   (Eruption): 11 LEDs, 46-B-Feature-Report 0x0d,
    RGBA x 11 + Helligkeit.
  - aimo_themes.py        (E1): 10 Themes x 3 Farbstopps aus aimo_color_theme.dat.

Keine erfundenen Effekte - jede Render-Funktion ist durch EFFEKTE.md belegt.
"""

from __future__ import annotations

import math
import time
from typing import Callable, List, Optional, Sequence, Tuple

from aimo_themes import RGB, gradient_color, theme_by_name

# --- Geraete-LED-Abstraktion ----------------------------------------------

# Vulcan: 143 Keys, Grid 6 Reihen x 21 Spalten (Eruption NUM_KEYS=143).
# Vereinfachtes Positionsmodell analog zur bestehenden apply_aimo_theme():
#   row = i // 21, col = i % 21.
def vulcan_num_leds() -> int:
    return 143


def vulcan_position(i: int) -> Tuple[float, float]:
    """Normierte (u, v) Position einer Vulcan-LED, je 0.0..1.0."""
    row = i // 21
    col = i % 21
    return (col / 20.0, row / 5.0)


# Kone: 11 LEDs (LED_0..LED_10), linearer Ring/Stripe (Eruption).
def kone_num_leds() -> int:
    return 11


def kone_position(i: int) -> Tuple[float, float]:
    """Normierte (u, v) Position einer Kone-LED (lineares Band)."""
    n = max(1, kone_num_leds() - 1)
    return (i / n, 0.0)


# --- Farb-Helfer -----------------------------------------------------------

def rgb_to_hsv(r: int, g: int, b: int) -> Tuple[float, float, float]:
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    h = 0.0
    if d != 0.0:
        if mx == r:
            h = ((g - b) / d) % 6.0
        elif mx == g:
            h = (b - r) / d + 2.0
        else:
            h = (r - g) / d + 4.0
        h *= 60.0
    s = 0.0 if mx == 0.0 else d / mx
    return (h % 360.0, s, mx)


def hsv_to_rgb(h: float, s: float, v: float) -> RGB:
    h = h % 360.0
    c = v * s
    x = c * (1.0 - abs((h / 60.0) % 2.0 - 1.0))
    m = v - c
    if h < 60.0:
        r, g, b = c, x, 0.0
    elif h < 120.0:
        r, g, b = x, c, 0.0
    elif h < 180.0:
        r, g, b = 0.0, c, x
    elif h < 240.0:
        r, g, b = 0.0, x, c
    elif h < 300.0:
        r, g, b = x, 0.0, c
    else:
        r, g, b = c, 0.0, x
    return (
        int(round((r + m) * 255.0)),
        int(round((g + m) * 255.0)),
        int(round((b + m) * 255.0)),
    )


def _clamp_color(color: RGB) -> RGB:
    return (
        max(0, min(255, int(color[0]))),
        max(0, min(255, int(color[1]))),
        max(0, min(255, int(color[2]))),
    )


def scale_brightness(led_map: Sequence[RGB], brightness: int) -> List[RGB]:
    """Multipliziert alle Farben mit brightness/100 (Eruption-Verhalten)."""
    b = max(0, min(100, int(brightness))) / 100.0
    if b >= 1.0:
        return [tuple(c) for c in led_map]
    return [
        (int(c[0] * b), int(c[1] * b), int(c[2] * b)) for c in led_map
    ]


# --- Effekt-Render-Funktionen ----------------------------------------------
# Jede Render-Funktion: render(phase, params, pos, num_leds) -> List[RGB]
#   phase  : gleitender Loop-Fortschritt in 0.0..1.0 (0 = Loop-Anfang)
#   pos    : Callable[i] -> (u, v) normierte Position
# Alle liefern rohe RGB ohne Helligkeitsskalierung (skaliert der Aufrufer).


def render_static(
    phase: float, params: dict, pos: Callable, num_leds: int
) -> List[RGB]:
    color = _clamp_color(params["color"])
    return [color] * num_leds


def render_gradient(
    phase: float, params: dict, pos: Callable, num_leds: int
) -> List[RGB]:
    stops = params["stops"]
    direction = params.get("direction", "h")
    out: List[RGB] = []
    for i in range(num_leds):
        u, v = pos(i)
        t = v if direction == "v" else u
        out.append(gradient_color(stops, t))
    return out


def render_breathing(
    phase: float, params: dict, pos: Callable, num_leds: int
) -> List[RGB]:
    base = _clamp_color(params["color"])
    lo = params.get("min", 0.0)   # 0.0..1.0
    hi = params.get("max", 1.0)   # 0.0..1.0
    # sin-Glocke: 0 -> 1 -> 0 ueber eine Periode.
    env = lo + (hi - lo) * (0.5 - 0.5 * math.cos(2.0 * math.pi * phase))
    color = (
        int(round(base[0] * env)),
        int(round(base[1] * env)),
        int(round(base[2] * env)),
    )
    return [color] * num_leds


def render_colorcycle(
    phase: float, params: dict, pos: Callable, num_leds: int
) -> List[RGB]:
    base_hue = params.get("hue", 0.0)
    sat = params.get("sat", 1.0)
    val = params.get("val", 1.0)
    hue = (base_hue + phase * 360.0) % 360.0
    color = hsv_to_rgb(hue, sat, val)
    return [color] * num_leds


def render_wave(
    phase: float, params: dict, pos: Callable, num_leds: int
) -> List[RGB]:
    mode = params.get("mode", "hue")  # 'hue' | 'gradient'
    direction = params.get("direction", "h")  # 'h' | 'v' | 'd'
    spread = params.get("spread", 1.0)
    sat = params.get("sat", 1.0)
    val = params.get("val", 1.0)
    base_hue = params.get("hue", 0.0)
    stops = params.get("stops")
    out: List[RGB] = []
    for i in range(num_leds):
        u, v = pos(i)
        if direction == "v":
            spatial = v
        elif direction == "d":
            spatial = (u + v) / 2.0
        else:
            spatial = u
        t = (spatial + phase) % 1.0
        if mode == "gradient" and stops:
            out.append(gradient_color(stops, t))
        else:  # hue
            hue = (base_hue + t * 360.0 * spread) % 360.0
            out.append(hsv_to_rgb(hue, sat, val))
    return out


EFFECT_RENDERERS = {
    "static": render_static,
    "gradient": render_gradient,
    "breathing": render_breathing,
    "colorcycle": render_colorcycle,
    "wave": render_wave,
}

# Effekte ohne Animation (ein Frame, kein Loop).
STATIC_EFFECTS = {"static", "gradient"}

EFFECT_HELP: dict = {
    "static": "static R G B [--brightness N]",
    "gradient": "gradient THEME [--direction h|v] [--brightness N]",
    "breathing": "breathing R G B [--period S] [--min N] [--max N] [--brightness N] [--duration S]",
    "colorcycle": "colorcycle [--period S] [--brightness N] [--duration S]",
    "wave": "wave [--mode hue|gradient] [--theme THEME] [--direction h|v|d] [--period S] [--brightness N] [--duration S]",
}


def effect_names() -> List[str]:
    return list(EFFECT_RENDERERS.keys())


def _parse_theme(stops_arg: Optional[str]) -> List[RGB]:
    """Theme-Argument -> Liste von 0..n RGB-Stopps.

    Akzeptiert einen Theme-Namen/Index (aus aimo_themes) ODER eine
    kommagetrennte Liste 'r,g,b;r,g,b;...'.
    """
    if stops_arg is None:
        raise ValueError("Themen- oder Stopp-Liste fehlt (THEME).")
    s = stops_arg.strip()
    if ";" in s:
        stops = []
        for part in s.split(";"):
            part = part.strip()
            if not part:
                continue
            nums = [int(x) for x in part.split(",")]
            if len(nums) != 3:
                raise ValueError(f"Ungueltiger Stopp: {part!r} (erwarte r,g,b)")
            stops.append((nums[0], nums[1], nums[2]))
        if not stops:
            raise ValueError("Keine gueltigen Stopps gefunden.")
        return stops
    return list(theme_by_name(s)["colors"])


def resolve_effect_params(effect: str, args) -> dict:
    """Baut den params-dict fuer einen Effekt aus den CLI-Args."""
    p: dict = {}
    if effect == "static":
        p["color"] = (args.r, args.g, args.b)
    elif effect == "gradient":
        p["stops"] = _parse_theme(args.theme)
        p["direction"] = args.direction
    elif effect == "breathing":
        p["color"] = (args.r, args.g, args.b)
        p["min"] = args.min / 100.0
        p["max"] = args.max / 100.0
    elif effect == "colorcycle":
        p["hue"] = args.hue
        p["sat"] = 1.0
        p["val"] = 1.0
    elif effect == "wave":
        p["mode"] = args.mode
        p["direction"] = args.direction
        p["spread"] = args.spread
        if args.mode == "gradient":
            p["stops"] = _parse_theme(args.theme)
    else:
        raise ValueError(f"Unbekannter Effekt: {effect}")
    return p


# --- Geraete-Loop ----------------------------------------------------------

def backend_for(entry: dict) -> Tuple[int, Callable[[int], Tuple[float, float]], bool]:
    """Liefert (num_leds, position_fn, is_vulcan) fuer ein Geraete-Entry.

    Vulcan-IDs: 0x2E24 (Vulcan AIMO), 0x2E26 (Vulcan 120), 0x2E2A (Vulcan TKL).
    Kone AIMO: 0x2E27.
    """
    pid = entry.get("product_id")
    if pid in (0x2E24, 0x2E26, 0x2E2A):
        return vulcan_num_leds(), vulcan_position, True
    return kone_num_leds(), kone_position, False


def run_effect(
    entry: dict,
    dev,
    effect: str,
    params: dict,
    *,
    brightness: int = 100,
    period: float = 2.0,
    duration: float = 0.0,
    frame_interval: float = 0.05,
    send: Callable,
) -> int:
    """Fuehrt einen Effekt auf einem Geraet aus (Loop fuer Animationen).

    send(dev, led_map, brightness): geraetespezifische Uebertragung.
    duration<=0 => endlos (bis KeyboardInterrupt).
    """
    renderer = EFFECT_RENDERERS[effect]
    num_leds, pos, is_vulcan = backend_for(entry)

    t_start = time.monotonic()
    frame = 0
    try:
        while True:
            if duration > 0:
                phase = ((frame * frame_interval) % period) / period
            else:
                phase = ((time.monotonic() - t_start) % period) / period

            led_map = renderer(phase, params, pos, num_leds)
            led_map = scale_brightness(led_map, brightness)
            send(dev, led_map, brightness)

            if effect in STATIC_EFFECTS:
                break  # ein Frame genuegt fuer statische Effekte

            if duration > 0 and (time.monotonic() - t_start) >= duration:
                break

            time.sleep(frame_interval)
            frame += 1
    except KeyboardInterrupt:
        return 0
    return 0
