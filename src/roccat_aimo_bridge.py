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


# Vulcan AIMO: 144 Tasten, 6 Reihen x 21 Spalten (wie Vulcan Pro).
VULCAN_NUM_KEYS = 144


def set_vulcan_led_map(dev: hid.device, led_map: List[RGB]) -> None:
    """Setzt alle Tasten-Farben via LED-Interface (Eruption-Protokoll).

    Farben in Blöcken von 12 Tasten (2 Spalten), Farbteile sortiert
    (erst alle R, dann G, dann B). 6 Chunks à 60 Bytes, je 64-Byte-Report.
    """
    if len(led_map) < VULCAN_NUM_KEYS:
        raise ValueError(
            f"LED-Map zu kurz: {len(led_map)} < {VULCAN_NUM_KEYS}"
        )
    buffer = [0] * 448
    for i in range(VULCAN_NUM_KEYS):
        r, g, b = led_map[i]
        offset = ((i // 12) * 36) + (i % 12)
        buffer[offset] = r
        buffer[offset + 12] = g
        buffer[offset + 24] = b
    for cntr in range(6):
        chunk = buffer[cntr * 60 : (cntr + 1) * 60]
        tmp = [0] * 64
        if cntr < 1:
            tmp[0:4] = [0xA1, 0x01, 0x80, 0x01]
        else:
            tmp[0:4] = [0xA1, cntr + 1, 0x00, 0x00]
        tmp[4:64] = chunk
        dev.write(tmp)


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


def handle_poll(args: argparse.Namespace) -> int:
    entry = _pick_device(args.index)
    dev = open_device_by_entry(entry)
    try:
        state = read_device_state(dev)
        logger.info(json.dumps(state, indent=2))
    finally:
        dev.close()
    return 0


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
