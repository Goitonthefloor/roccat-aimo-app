#!/usr/bin/env python3
"""Roccat AIMO userspace bridge for Linux."""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("roccat-aimo")
logging.basicConfig(level=logging.INFO)

try:
    from aimo_themes import RGB, gradient_color
except ImportError:
    # Fallback, falls aimo_themes nicht im selben Verzeichnis liegt.
    from typing import Tuple

    RGB = Tuple[int, int, int]

    def gradient_color(stops, t):
        t = max(0.0, min(1.0, t))
        if len(stops) == 1:
            return stops[0]
        n = len(stops) - 1
        seg = t * n
        idx = min(int(seg), n - 1)
        local = seg - idx
        c0, c1 = stops[idx], stops[idx + 1]
        return (
            int(round(c0[0] + (c1[0] - c0[0]) * local)),
            int(round(c0[1] + (c1[1] - c0[1]) * local)),
            int(round(c0[2] + (c1[2] - c0[2]) * local)),
        )

try:
    import hid
except Exception:
    logger.error("hidapi is required. Install python-hidapi.")
    sys.exit(1)

ROCCAT_VID = 0x1E7D
PRODUCTS = [
    # Kone AIMO
    {"name": "Kone AIMO", "vendor": ROCCAT_VID, "product": 0x2E27},
    # Vulcan AIMO series
    {"name": "Vulcan AIMO", "vendor": ROCCAT_VID, "product": 0x2E24},
    {"name": "Vulcan 120 AIMO", "vendor": ROCCAT_VID, "product": 0x2E26},
    {"name": "Vulcan TKL AIMO", "vendor": ROCCAT_VID, "product": 0x2E2A},
]
STATE_PATH = Path.home() / ".local" / "state" / "roccat-aimo" / "devices.json"


def ensure_state_dir() -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_state() -> Dict[str, Any]:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"devices": []}


def save_state(state: Dict[str, Any]) -> None:
    ensure_state_dir()
    STATE_PATH.write_text(json.dumps(state, indent=2))


def list_roccat_devices() -> List[Dict[str, Any]]:
    devices = []
    for d in hid.enumerate():
        if d.get("vendor_id") == ROCCAT_VID:
            devices.append(
                {
                    "vendor_id": d.get("vendor_id"),
                    "product_id": d.get("product_id"),
                    "path": d.get("path"),
                    "product_string": d.get("product_string"),
                    "manufacturer_string": d.get("manufacturer_string"),
                    "release_number": d.get("release_number"),
                    "interface_number": d.get("interface_number"),
                }
            )
    return devices


def open_device_by_entry(entry: Dict[str, Any]) -> hid.device:
    dev = hid.device()
    try:
        dev.open_path(entry["path"])
    except Exception:
        dev.open(entry["vendor_id"], entry["product_id"])
    return dev


def send_hid_report(dev: hid.device, report_id: int, data: bytes) -> None:
    payload = bytes([report_id]) + data
    dev.write([0x00] + list(payload))


def set_kone_aimo_dpi(dev: hid.device, x: int, y: int) -> None:
    x = max(100, min(16000, int(x)))
    y = max(100, min(16000, int(y)))
    data = bytes(
        [
            0x03,
            0x04,
            (x >> 8) & 0xFF,
            x & 0xFF,
            (y >> 8) & 0xFF,
            y & 0xFF,
        ]
    )
    send_hid_report(dev, 0x04, data)


def set_kone_aimo_led(dev: hid.device, enabled: bool, brightness: int = 255) -> None:
    brightness = max(0, min(255, int(brightness)))
    state = 0x01 if enabled else 0x00
    data = bytes([0x07, state, brightness])
    send_hid_report(dev, 0x04, data)


def set_vulcan_key_rgb(
    dev: hid.device, row: int, col: int, r: int, g: int, b: int
) -> None:
    row = max(0, min(5, int(row)))
    col = max(0, min(20, int(col)))
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    data = bytes([0x0B, row, col, r, g, b])
    send_hid_report(dev, 0x04, data)


# Vulcan AIMO: 143 Tasten (Eruption NUM_KEYS=143), Grid 6 Reihen x 21 Spalten.
VULCAN_NUM_KEYS = 143

# Kone AIMO: 11 LEDs (LED_0..LED_10).
KONE_NUM_LEDS = 11


def set_vulcan_led_map(dev: hid.device, led_map: List[RGB]) -> None:
    """Setzt alle Tasten-Farben via LED-Interface (aktuelles Eruption-Protokoll).

    Eruption roccat_vulcan_1xx.rs: 448-B-Puffer, Header [0xa1,0x01,0x01,0xb4],
    Farben in 12er-Blöcken (offset = (i//12)*36 + (i%12)), Farbteile sortiert
    (R, dann +12 G, dann +24 B), 7 Chunks à 64 B, je als 65-B-Report
    (Report-ID 0x00 + 64 B). Farben mit brightness/100 skaliert.
    """
    if len(led_map) < VULCAN_NUM_KEYS:
        raise ValueError(
            f"LED-Map zu kurz: {len(led_map)} < {VULCAN_NUM_KEYS}"
        )
    buffer = [0] * 448
    buffer[0:4] = [0xA1, 0x01, 0x01, 0xB4]
    for i in range(VULCAN_NUM_KEYS):
        r, g, b = led_map[i]
        offset = ((i // 12) * 36) + (i % 12)
        buffer[offset + 4] = r
        buffer[offset + 4 + 12] = g
        buffer[offset + 4 + 24] = b
    for bytes_ in (buffer[i : i + 64] for i in range(0, len(buffer), 64)):
        tmp = [0] * 65
        tmp[1:65] = bytes_
        dev.write(tmp)


def set_kone_led_map(dev: hid.device, led_map: List[RGB]) -> None:
    """Setzt alle Kone-AIMO-LEDs (Eruption-Protokoll).

    Eruption roccat_kone_aimo.rs: 46-B-Feature-Report
    [0x0d, 0x2e, RGBA x 11 (+ Helligkeit via Alpha/Scale)] auf dem
    Control-Interface.
    """
    if len(led_map) < KONE_NUM_LEDS:
        raise ValueError(
            f"LED-Map zu kurz: {len(led_map)} < {KONE_NUM_LEDS}"
        )
    report = [0x0D, 0x2E]
    for r, g, b in led_map[:KONE_NUM_LEDS]:
        # Alpha = maximale Helligkeit 255 (ungesättigt); Helligkeit wird
        # bereits als globaler Multiplikator in der Effekt-Engine angewendet.
        report.extend([r, g, b, 0xFF])
    payload = bytes(report)
    try:
        dev.send_feature_report(payload)
    except AttributeError:
        # Fallback: als Output-Report schreiben.
        send_hid_report(dev, payload[0], payload[1:])


def _send_led_map_for(dev: hid.device, led_map: List[RGB], _brightness: int) -> None:
    """Vermittelt zwischen Vulcan- und Kone-send_led_map.

    Die Effekt-Engine hat die Helligkeit bereits auf die Farben angewendet;
    hier wird nur das passende geraetespezifische Protokoll gewaehlt.
    """
    if len(led_map) == VULCAN_NUM_KEYS:
        set_vulcan_led_map(dev, led_map)
    elif len(led_map) == KONE_NUM_LEDS:
        set_kone_led_map(dev, led_map)
    else:
        raise ValueError(f"Unbekannte LED-Map-Groesse: {len(led_map)}")


def apply_aimo_theme(dev: hid.device, theme: dict, direction: str = "h") -> None:
    """Legt ein AIMO-Farbthema als Gradient über die Tastatur.

    direction: 'h' = horizontal (Spalten), 'v' = vertikal (Reihen).
    """
    stops = theme["colors"]
    led_map: List[RGB] = []
    for i in range(VULCAN_NUM_KEYS):
        row = i // 21
        col = i % 21
        if direction == "v":
            t = row / 5.0
        else:
            t = col / 20.0
        led_map.append(gradient_color(stops, t))
    set_vulcan_led_map(dev, led_map)


def read_device_state(dev: hid.device) -> Dict[str, Any]:
    state: Dict[str, Any] = {}
    try:
        raw = dev.read(256, timeout_ms=200)
        state["last_report"] = list(raw)
        state["last_report_len"] = len(raw)
    except Exception as exc:
        state["read_error"] = str(exc)
    return state


def handle_list(_: argparse.Namespace) -> int:
    devices = list_roccat_devices()
    if not devices:
        logger.info("No Roccat devices found.")
        return 1
    logger.info(f"Found {len(devices)} Roccat device(s):")
    for idx, dev in enumerate(devices, 1):
        prod = next(
            (p for p in PRODUCTS if p["product"] == dev.get("product_id")), None
        )
        name = prod["name"] if prod else f"Unknown 0x{dev.get('product_id', 0):04x}"
        print(f"{idx}. {name}")
        logger.debug(f"manufacturer: {dev.get('manufacturer_string')}")
        logger.debug(f"product: {dev.get('product_string')}")
        print(
            f"   vendor_id: 0x{dev.get('vendor_id', 0):04x} product_id: 0x{dev.get('product_id', 0):04x}"
        )
        logger.debug(f"path: {dev.get('path')}")
    state = load_state()
    state["devices"] = devices
    save_state(state)
    return 0


def handle_bridge(_: argparse.Namespace) -> int:
    try:
        while True:
            list_roccat_devices()
            time.sleep(1)
    except KeyboardInterrupt:
        return 0


def _pick_device(index: int) -> Dict[str, Any]:
    devices = list_roccat_devices()
    if not devices:
        raise SystemExit("No Roccat devices found.")
    index = max(0, min(index, len(devices) - 1))
    return devices[index]


def handle_dpi(args: argparse.Namespace) -> int:
    entry = _pick_device(args.index)
    dev = open_device_by_entry(entry)
    try:
        set_kone_aimo_dpi(dev, args.x, args.y)
        logger.info(f"DPI set to {args.x}/{args.y} on index {args.index}")
    finally:
        dev.close()
    return 0


def handle_led(args: argparse.Namespace) -> int:
    entry = _pick_device(args.index)
    dev = open_device_by_entry(entry)
    try:
        set_kone_aimo_led(dev, args.on, args.brightness)
        state = "ON" if args.on else "OFF"
        logger.info(f"LED {state} at {args.brightness} on index {args.index}")
    finally:
        dev.close()
    return 0


def handle_rgb(args: argparse.Namespace) -> int:
    entry = _pick_device(args.index)
    dev = open_device_by_entry(entry)
    try:
        set_vulcan_key_rgb(dev, args.row, args.col, args.r, args.g, args.b)
        logger.info(f"RGB set to {args.r},{args.g},{args.b} at row={args.row} col={args.col}")
    finally:
        dev.close()
    return 0


def handle_aimo(args: argparse.Namespace) -> int:
    try:
        from aimo_themes import theme_by_name, theme_names
    except ImportError:
        logger.error("aimo_themes.py fehlt (im selben Verzeichnis wie die Bridge).")
        return 1
    try:
        theme = theme_by_name(args.theme)
    except KeyError as exc:
        logger.error(f"{exc}. Verfügbar: {', '.join(theme_names())}")
        return 1
    entry = _pick_device(args.index)
    dev = open_device_by_entry(entry)
    try:
        apply_aimo_theme(dev, theme, args.direction)
        logger.info(
            f"AIMO-Theme '{theme['name']}' ({args.direction}) auf index {args.index}"
        )
    finally:
        dev.close()
    return 0


def handle_effect(args: argparse.Namespace) -> int:
    try:
        import aimo_effects
    except ImportError:
        logger.error(
            "aimo_effects.py fehlt (im selben Verzeichnis wie die Bridge)."
        )
        return 1
    try:
        params = aimo_effects.resolve_effect_params(args.effect, args)
    except (ValueError, KeyError) as exc:
        logger.error(str(exc))
        return 1
    from aimo_effects import (
        STATIC_EFFECTS,
        run_effect,
    )

    entry = _pick_device(args.index)
    dev = open_device_by_entry(entry)
    try:
        run_effect(
            entry,
            dev,
            args.effect,
            params,
            brightness=args.brightness,
            # Animations-Parameter existieren nur bei animierten Effekten;
            # fuer statische (static/gradient) nutze die Defaults von run_effect.
            period=getattr(args, "period", 2.0),
            duration=getattr(args, "duration", 0.0),
            frame_interval=getattr(args, "frame_interval", 0.05),
            send=_send_led_map_for,
        )
        if args.effect not in STATIC_EFFECTS:
            logger.info(
                f"AIMO-Effekt '{args.effect}' bis Ctrl-C/Duration auf index "
                f"{args.index}"
            )
        else:
            logger.info(
                f"AIMO-Effekt '{args.effect}' auf index {args.index}"
            )
    finally:
        dev.close()
    return 0


def handle_effect_list(_: argparse.Namespace) -> int:
    try:
        from aimo_effects import EFFECT_HELP, effect_names
    except ImportError:
        logger.error("aimo_effects.py fehlt.")
        return 1
    for name in effect_names():
        print(f"{name:<12} {EFFECT_HELP[name]}")
    return 0


def handle_poll(args: argparse.Namespace) -> int:
    entry = _pick_device(args.index)
    dev = open_device_by_entry(entry)
    try:
        state = read_device_state(dev)
        logger.info(json.dumps(state, indent=2))
    finally:
        dev.close()
    return 0


def _add_effect_subparsers(parent: argparse.ArgumentParser) -> None:
    """Konfiguriert die `effect`-Subcommands (je AIMO-Effekt ein Befehl).

    Statische Effekte (static, gradient) senden einen Frame; animierte
    (breathing, colorcycle, wave) laufen als Loop bis --duration oder Ctrl-C.
    """
    esh = parent.add_subparsers(dest="effect", required=True)

    def _common(p, animated: bool = False):
        p.add_argument("--brightness", type=int, default=100, help="0..100")
        p.add_argument("--index", type=int, default=0)
        if animated:
            p.add_argument("--period", type=float, default=2.0, help="Loop-Periode in s")
            p.add_argument("--duration", type=float, default=0.0, help="0 = endlos")
            p.add_argument("--frame-interval", type=float, default=0.05, help="s")

    p = esh.add_parser("static", help="Constante Einzelfarbe (E2)")
    p.add_argument("r", type=int)
    p.add_argument("g", type=int)
    p.add_argument("b", type=int)
    _common(p)
    p.set_defaults(func=handle_effect)

    p = esh.add_parser("gradient", help="AIMO-Theme-Gradient (E1)")
    p.add_argument("theme", help="Theme-Name/-Index oder 'r,g,b;r,g,b;...'")
    p.add_argument("--direction", choices=["h", "v"], default="h")
    _common(p)
    p.set_defaults(func=handle_effect)

    p = esh.add_parser("breathing", help="Atmen / Pulse (E4)")
    p.add_argument("r", type=int)
    p.add_argument("g", type=int)
    p.add_argument("b", type=int)
    p.add_argument("--min", type=int, default=0, help="min. Helligkeit 0..100")
    p.add_argument("--max", type=int, default=100, help="max. Helligkeit 0..100")
    _common(p, animated=True)
    p.set_defaults(func=handle_effect)

    p = esh.add_parser("colorcycle", help="Farbzyklus / Hue-Rotation (E5)")
    p.add_argument("--hue", type=float, default=0.0, help="Start-Hue 0..360")
    p.add_argument("--sat", type=float, default=1.0, help="Saettigung 0..1")
    _common(p, animated=True)
    p.set_defaults(func=handle_effect)

    p = esh.add_parser("wave", help="Welle ueber das Grid (E3)")
    p.add_argument("--mode", choices=["hue", "gradient"], default="hue")
    p.add_argument("--theme", default=None, help="fuer mode=gradient")
    p.add_argument("--direction", choices=["h", "v", "d"], default="h")
    p.add_argument("--spread", type=float, default=1.0, help="Farb-Ausbreitung")
    p.add_argument("--sat", type=float, default=1.0, help="Saettigung 0..1")
    p.add_argument("--hue", type=float, default=0.0, help="Start-Hue 0..360")
    _common(p, animated=True)
    p.set_defaults(func=handle_effect)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="roccat-aimo-cli", description="Roccat AIMO CLI"
    )
    sub = parser.add_subparsers(dest="command")

    list_p = sub.add_parser("list", help="List Roccat devices")
    list_p.set_defaults(func=handle_list)

    dpi_p = sub.add_parser("dpi", help="Set DPI on Kone AIMO")
    dpi_p.add_argument("x", type=int)
    dpi_p.add_argument("y", type=int)
    dpi_p.add_argument("--index", type=int, default=0)
    dpi_p.set_defaults(func=handle_dpi)

    led_p = sub.add_parser("led", help="Toggle LED on Kone AIMO")
    led_p.add_argument("on", type=int, choices=[0, 1])
    led_p.add_argument("--brightness", type=int, default=255)
    led_p.add_argument("--index", type=int, default=0)
    led_p.set_defaults(func=handle_led)

    rgb_p = sub.add_parser("rgb", help="Set per-key RGB on Vulcan AIMO")
    rgb_p.add_argument("row", type=int)
    rgb_p.add_argument("col", type=int)
    rgb_p.add_argument("r", type=int)
    rgb_p.add_argument("g", type=int)
    rgb_p.add_argument("b", type=int)
    rgb_p.add_argument("--index", type=int, default=0)
    rgb_p.set_defaults(func=handle_rgb)

    aimo_p = sub.add_parser(
        "aimo", help="Apply an AIMO color theme (gradient) across the keyboard"
    )
    aimo_p.add_argument("theme", help="Theme name or 1-based index")
    aimo_p.add_argument(
        "--direction",
        choices=["h", "v"],
        default="h",
        help="Gradient direction: h=horizontal (default), v=vertical",
    )
    aimo_p.add_argument("--index", type=int, default=0)
    aimo_p.set_defaults(func=handle_aimo)

    effect_p = sub.add_parser(
        "effect", help="Apply an AIMO effect (software-rendered LED map)"
    )
    _add_effect_subparsers(effect_p)

    effect_list_p = sub.add_parser(
        "effect-list", help="List available AIMO effects with usage"
    )
    effect_list_p.set_defaults(func=handle_effect_list)

    poll_p = sub.add_parser("poll", help="Read HID report")
    poll_p.add_argument("--index", type=int, default=0)
    poll_p.set_defaults(func=handle_poll)

    gui_p = sub.add_parser("gui", help="Open GTK4 GUI")
    gui_p.set_defaults(func=lambda _: handle_gui())

    bridge_p = sub.add_parser("bridge", help="Run userspace bridge/daemon")
    bridge_p.set_defaults(func=handle_bridge)

    return parser


def handle_gui() -> int:
    candidates = [
        Path.home() / ".local" / "lib" / "roccat-aimo-app",
        Path("/usr/lib/roccat-aimo-app"),
        Path("/usr/local/lib/roccat-aimo-app"),
    ]
    for parent in candidates:
        mod = parent / "roccat_aimo_gui.py"
        if mod.exists():
            sys.path.insert(0, str(parent))
            break
    try:
        from roccat_aimo_gui import main as gui_main
    except ImportError as exc:
        logger.error(f"GUI dependencies missing: {exc}")
        return 1
    return gui_main()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
