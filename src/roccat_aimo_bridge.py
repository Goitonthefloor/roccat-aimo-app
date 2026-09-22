#!/usr/bin/env python3
"""Roccat AIMO userspace bridge for Linux."""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROCCAT_VID = 0x1E7D
PRODUCTS = [
    # Kone AIMO
    {"name": "Kone AIMO", "vendor": ROCCAT_VID, "product": 0x2E27},
    # Vulcan AIMO series
    {"name": "Vulcan AIMO", "vendor": ROCCAT_VID, "product": 0x2E24},
    {"name": "Vulcan 120 AIMO", "vendor": ROCCAT_VID, "product": 0x2E26},
    {"name": "Vulcan TKL AIMO", "vendor": ROCCAT_VID, "product": 0x2E2A},
]

_hid: Any = None


def state_path() -> Path:
    override = os.environ.get("ROCCAT_AIMO_STATE")
    if override:
        return Path(override)
    return Path.home() / ".local" / "state" / "roccat-aimo" / "devices.json"


def require_hid() -> Any:
    """Return the hidapi module. On Linux prefer the hidraw backend."""
    global _hid
    if _hid is not None:
        return _hid
    errors: List[str] = []
    candidates = ["hidraw", "hid"] if sys.platform.startswith("linux") else ["hid"]
    for name in candidates:
        try:
            module = __import__(name)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            continue
        _hid = module
        return _hid
    detail = "; ".join(errors) if errors else "import failed"
    print(f"ERROR: hidapi is required. Install python-hidapi. ({detail})", file=sys.stderr)
    raise SystemExit(1)


def ensure_state_dir() -> None:
    state_path().parent.mkdir(parents=True, exist_ok=True)


def load_state() -> Dict[str, Any]:
    path = state_path()
    if not path.exists():
        return {"devices": []}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"devices": []}
    if not isinstance(data, dict):
        return {"devices": []}
    return data


def save_state(state: Dict[str, Any]) -> None:
    ensure_state_dir()
    state_path().write_text(json.dumps(state, indent=2) + "\n")


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (int, float, str, bool)):
        return value
    if isinstance(value, bytes):
        return os.fsdecode(value)
    return str(value)


def describe_device(raw: Dict[str, Any], index: int) -> Dict[str, Any]:
    product_id = int(raw.get("product_id") or 0)
    vendor_id = int(raw.get("vendor_id") or 0)
    known = next(
        (item for item in PRODUCTS if item["product"] == product_id and item["vendor"] == vendor_id),
        None,
    )
    name = known["name"] if known else f"Unknown 0x{product_id:04x}"
    return {
        "index": index,
        "name": name,
        "vendor_id": vendor_id,
        "product_id": product_id,
        "product_string": _json_safe(raw.get("product_string")),
        "manufacturer_string": _json_safe(raw.get("manufacturer_string")),
        "release_number": _json_safe(raw.get("release_number")),
        "interface_number": _json_safe(raw.get("interface_number")),
        "path": _json_safe(raw.get("path")),
    }


def list_roccat_devices() -> List[Dict[str, Any]]:
    hid = require_hid()
    devices = []
    for entry in hid.enumerate():
        if int(entry.get("vendor_id") or 0) != ROCCAT_VID:
            continue
        devices.append(dict(entry))
    return devices


def format_device_table(devices: List[Dict[str, Any]]) -> str:
    if not devices:
        return "No Roccat devices found.\n"
    lines = [f"Found {len(devices)} Roccat device(s):"]
    for dev in devices:
        lines.append(f"[{dev['index']}] {dev['name']}")
        lines.append(f"    manufacturer: {dev.get('manufacturer_string')}")
        lines.append(f"    product: {dev.get('product_string')}")
        lines.append(f"    vendor_id: 0x{int(dev.get('vendor_id') or 0):04x}")
        lines.append(f"    product_id: 0x{int(dev.get('product_id') or 0):04x}")
        lines.append(f"    path: {dev.get('path')}")
    return "\n".join(lines) + "\n"


def parse_device_json(stdout: str, returncode: int, stderr: str = "") -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Interpret `list --json` output. A JSON array wins over the exit code."""
    text = (stdout or "").strip()
    if text:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return [], f"Device list was not valid JSON ({exc})"
        if isinstance(data, list) and all(isinstance(item, dict) for item in data):
            return data, None
        return [], "Device list was not a JSON array"
    if returncode != 0:
        err = (stderr or stdout or "Device scan failed").strip()
        return [], err or "Device scan failed"
    return [], None


def open_device_by_entry(entry: Dict[str, Any]) -> Any:
    hid = require_hid()
    path = entry.get("path")
    candidates: List[Any] = []
    if isinstance(path, bytes) and path:
        candidates.extend([path, os.fsdecode(path)])
    elif isinstance(path, str) and path:
        candidates.extend([path, os.fsencode(path)])
    errors: List[str] = []
    for candidate in candidates:
        dev = hid.device()
        try:
            dev.open_path(candidate)
            return dev
        except Exception as exc:
            errors.append(str(exc))
            try:
                dev.close()
            except Exception:
                pass
    dev = hid.device()
    try:
        dev.open(int(entry["vendor_id"]), int(entry["product_id"]))
    except Exception as exc:
        detail = "; ".join(errors)
        suffix = f" (path errors: {detail})" if detail else ""
        raise OSError(f"could not open HID device: {exc}{suffix}") from exc
    return dev


def send_hid_report(dev: Any, report_id: int, data: bytes) -> None:
    """Write an output report. The first byte is the report id, as hid_write requires."""
    payload = bytes([report_id & 0xFF]) + bytes(data)
    written = dev.write(payload)
    if isinstance(written, int) and written < 0:
        raise OSError(f"HID write failed for report 0x{report_id:02x}")


def set_kone_aimo_dpi(dev: Any, x: int, y: int) -> Tuple[int, int]:
    x = max(100, min(16000, int(x)))
    y = max(100, min(16000, int(y)))
    data = bytes([
        0x03,
        0x04,
        (x >> 8) & 0xFF, x & 0xFF,
        (y >> 8) & 0xFF, y & 0xFF,
    ])
    send_hid_report(dev, 0x04, data)
    return x, y


def set_kone_aimo_led(dev: Any, enabled: bool, brightness: int = 255) -> int:
    brightness = max(0, min(255, int(brightness)))
    state = 0x01 if enabled else 0x00
    data = bytes([0x07, state, brightness])
    send_hid_report(dev, 0x04, data)
    return brightness


def set_vulcan_key_rgb(dev: Any, row: int, col: int, r: int, g: int, b: int) -> Tuple[int, int, int, int, int]:
    row = max(0, min(5, int(row)))
    col = max(0, min(20, int(col)))
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    data = bytes([0x0B, row, col, r, g, b])
    send_hid_report(dev, 0x04, data)
    return row, col, r, g, b


def read_device_state(dev: Any) -> Dict[str, Any]:
    state: Dict[str, Any] = {}
    try:
        raw = dev.read(256, timeout_ms=200)
        state["last_report"] = list(raw)
        state["last_report_len"] = len(raw)
    except Exception as exc:
        state["read_error"] = str(exc)
    return state


def _described_devices() -> List[Dict[str, Any]]:
    return [describe_device(raw, index) for index, raw in enumerate(list_roccat_devices())]


def _persist_described(devices: List[Dict[str, Any]]) -> None:
    state = load_state()
    state["devices"] = devices
    save_state(state)


def handle_list(args: argparse.Namespace) -> int:
    devices = _described_devices()
    _persist_described(devices)
    if args.json:
        print(json.dumps(devices))
    else:
        sys.stdout.write(format_device_table(devices))
    return 0 if devices else 1


def bridge_once(previous: Optional[str]) -> str:
    devices = _described_devices()
    blob = json.dumps(devices, sort_keys=True)
    if blob != previous:
        _persist_described(devices)
        print(f"Tracking {len(devices)} Roccat device(s)", flush=True)
    return blob


def handle_bridge(_: argparse.Namespace) -> int:
    previous: Optional[str] = None
    try:
        while True:
            previous = bridge_once(previous)
            time.sleep(1)
    except KeyboardInterrupt:
        return 0


def _pick_device(index: int) -> Optional[Dict[str, Any]]:
    devices = list_roccat_devices()
    if not devices:
        print("No Roccat devices found.", file=sys.stderr)
        return None
    if index < 0 or index >= len(devices):
        print(
            f"Device index {index} is out of range (0..{len(devices) - 1}).",
            file=sys.stderr,
        )
        return None
    return devices[index]


def _run_on_device(index: int, action: Any) -> int:
    entry = _pick_device(index)
    if entry is None:
        return 1
    try:
        dev = open_device_by_entry(entry)
    except Exception as exc:
        print(f"ERROR: could not open device {index}: {exc}", file=sys.stderr)
        return 1
    try:
        return int(action(dev))
    except Exception as exc:
        print(f"ERROR: device command failed: {exc}", file=sys.stderr)
        return 1
    finally:
        try:
            dev.close()
        except Exception:
            pass


def handle_dpi(args: argparse.Namespace) -> int:
    def action(dev: Any) -> int:
        x, y = set_kone_aimo_dpi(dev, args.x, args.y)
        print(f"DPI set to {x}/{y} on index {args.index}")
        return 0

    return _run_on_device(args.index, action)


def handle_led(args: argparse.Namespace) -> int:
    def action(dev: Any) -> int:
        brightness = set_kone_aimo_led(dev, bool(args.on), args.brightness)
        state = "ON" if args.on else "OFF"
        print(f"LED {state} at {brightness} on index {args.index}")
        return 0

    return _run_on_device(args.index, action)


def handle_rgb(args: argparse.Namespace) -> int:
    def action(dev: Any) -> int:
        row, col, r, g, b = set_vulcan_key_rgb(dev, args.row, args.col, args.r, args.g, args.b)
        print(f"RGB set to {r},{g},{b} at row={row} col={col}")
        return 0

    return _run_on_device(args.index, action)


def handle_poll(args: argparse.Namespace) -> int:
    def action(dev: Any) -> int:
        print(json.dumps(read_device_state(dev), indent=2))
        return 0

    return _run_on_device(args.index, action)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="roccat-aimo-cli", description="Roccat AIMO CLI")
    sub = parser.add_subparsers(dest="command")

    list_p = sub.add_parser("list", help="List Roccat devices")
    list_p.add_argument("--json", action="store_true", help="Print devices as a JSON array")
    list_p.set_defaults(func=handle_list)

    dpi_p = sub.add_parser("dpi", help="Set DPI on Kone AIMO")
    dpi_p.add_argument("x", type=int)
    dpi_p.add_argument("y", type=int)
    dpi_p.add_argument("--index", type=int, default=0, help="Zero-based device index from list")
    dpi_p.set_defaults(func=handle_dpi)

    led_p = sub.add_parser("led", help="Toggle LED on Kone AIMO")
    led_p.add_argument("on", type=int, choices=[0, 1])
    led_p.add_argument("--brightness", type=int, default=255)
    led_p.add_argument("--index", type=int, default=0, help="Zero-based device index from list")
    led_p.set_defaults(func=handle_led)

    rgb_p = sub.add_parser("rgb", help="Set per-key RGB on Vulcan AIMO")
    rgb_p.add_argument("row", type=int)
    rgb_p.add_argument("col", type=int)
    rgb_p.add_argument("r", type=int)
    rgb_p.add_argument("g", type=int)
    rgb_p.add_argument("b", type=int)
    rgb_p.add_argument("--index", type=int, default=0, help="Zero-based device index from list")
    rgb_p.set_defaults(func=handle_rgb)

    poll_p = sub.add_parser("poll", help="Read HID report")
    poll_p.add_argument("--index", type=int, default=0, help="Zero-based device index from list")
    poll_p.set_defaults(func=handle_poll)

    gui_p = sub.add_parser("gui", help="Open GTK4 GUI")
    gui_p.set_defaults(func=lambda _: handle_gui())

    bridge_p = sub.add_parser("bridge", help="Run userspace bridge/daemon")
    bridge_p.set_defaults(func=handle_bridge)

    return parser


def gui_search_paths() -> List[Path]:
    return [
        Path(__file__).resolve().parent,
        Path("/app/lib/roccat-aimo-app"),
        Path.home() / ".local" / "lib" / "roccat-aimo-app",
        Path("/usr/lib/roccat-aimo-app"),
        Path("/usr/local/lib/roccat-aimo-app"),
    ]


def handle_gui() -> int:
    for parent in gui_search_paths():
        if (parent / "roccat_aimo_gui.py").exists():
            sys.path.insert(0, str(parent))
            break
    try:
        from roccat_aimo_gui import main as gui_main
    except ImportError as exc:
        print(f"GUI dependencies missing: {exc}", file=sys.stderr)
        return 1
    return gui_main()


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
