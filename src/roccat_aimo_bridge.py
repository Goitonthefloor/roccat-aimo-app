#!/usr/bin/env python3
"""Roccat AIMO userspace bridge for Linux."""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _ensure_local_modules() -> None:
    for parent in (
        Path(__file__).resolve().parent,
        Path("/app/lib/roccat-aimo-app"),
        Path.home() / ".local" / "lib" / "roccat-aimo-app",
        Path("/usr/lib/roccat-aimo-app"),
        Path("/usr/local/lib/roccat-aimo-app"),
    ):
        if (parent / "roccat_rgb.py").exists():
            parent_text = str(parent)
            if parent_text not in sys.path:
                sys.path.insert(0, parent_text)
            return


_ensure_local_modules()
import roccat_rgb

ROCCAT_VID = roccat_rgb.ROCCAT_VID
_vulcan_ready = set()

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
    name = roccat_rgb.product_name(product_id) if vendor_id == ROCCAT_VID else f"Unknown 0x{product_id:04x}"
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
        "kind": roccat_rgb.kind_for_product(product_id) if vendor_id == ROCCAT_VID else "unknown",
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


def send_feature_report(dev: Any, data: bytes) -> None:
    written = dev.send_feature_report(data)
    if isinstance(written, int) and written < 0:
        raise OSError(f"HID feature report 0x{data[0]:02x} failed")


def write_output_report(dev: Any, data: bytes) -> None:
    written = dev.write(data)
    if isinstance(written, int) and written < 0:
        raise OSError("HID output report failed")


def _init_delay() -> float:
    raw = os.environ.get("ROCCAT_AIMO_INIT_DELAY", "0.2")
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.2


def read_device_state(dev: Any) -> Dict[str, Any]:
    state: Dict[str, Any] = {}
    try:
        raw = dev.read(256, timeout_ms=200)
        state["last_report"] = list(raw)
        state["last_report_len"] = len(raw)
    except Exception as exc:
        state["read_error"] = str(exc)
    return state


def grouped_devices() -> List[Dict[str, Any]]:
    """One controller entry per physical device, with every HID interface attached."""
    groups: List[Dict[str, Any]] = []
    index_by_key: Dict[Tuple[int, int, str], int] = {}
    for raw in list_roccat_devices():
        vendor_id = int(raw.get("vendor_id") or 0)
        product_id = int(raw.get("product_id") or 0)
        serial = _json_safe(raw.get("serial_number")) or ""
        key = (vendor_id, product_id, serial)
        interface = {
            "interface_number": raw.get("interface_number"),
            "path": _json_safe(raw.get("path")),
            "vendor_id": vendor_id,
            "product_id": product_id,
        }
        if key not in index_by_key:
            index_by_key[key] = len(groups)
            described = describe_device(raw, len(groups))
            described["interfaces"] = [interface]
            groups.append(described)
            continue
        groups[index_by_key[key]]["interfaces"].append(interface)
    return groups


def _described_devices() -> List[Dict[str, Any]]:
    return grouped_devices()


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
    devices = grouped_devices()
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


def _open_interfaces(group: Dict[str, Any], interface_number: Optional[int] = None) -> List[Dict[str, Any]]:
    interfaces = list(group.get("interfaces") or [])
    if interface_number is None:
        return interfaces
    return [item for item in interfaces if item.get("interface_number") == interface_number]


def _color_key(group: Dict[str, Any]) -> str:
    serial = group.get("serial_number") or ""
    return f"{int(group.get('vendor_id') or 0):04x}:{int(group.get('product_id') or 0):04x}:{serial}"


def _load_colors(group: Dict[str, Any], count: int) -> List[Tuple[int, int, int]]:
    maps = load_state().get("color_maps") or {}
    current = maps.get(_color_key(group))
    if (
        isinstance(current, list)
        and len(current) == count
        and all(isinstance(item, list) and len(item) == 3 for item in current)
    ):
        return [tuple(int(channel) for channel in item) for item in current]  # type: ignore[misc]
    return [(0, 0, 0)] * count


def _save_colors(group: Dict[str, Any], colors: Sequence[Tuple[int, int, int]]) -> None:
    state = load_state()
    maps = dict(state.get("color_maps") or {})
    maps[_color_key(group)] = [list(color) for color in colors]
    state["color_maps"] = maps
    save_state(state)


def _apply_color_map(
    group: Dict[str, Any],
    color: Tuple[int, int, int],
    led: Optional[int],
) -> List[Tuple[int, int, int]]:
    kind = group.get("kind")
    count = roccat_rgb.KONE_LED_COUNT if kind == "kone" else roccat_rgb.VULCAN_KEY_COUNT
    colors = _load_colors(group, count)
    if led is None:
        return [color] * count
    if led < 0 or led >= count:
        raise ValueError(f"Light index {led} is out of range (0..{count - 1}).")
    colors[led] = color
    return colors


def _send_kone_colors(group: Dict[str, Any], colors: Sequence[Tuple[int, int, int]]) -> None:
    report = roccat_rgb.kone_color_report(colors)
    errors: List[str] = []
    for interface in _open_interfaces(group):
        try:
            dev = open_device_by_entry(interface)
        except Exception as exc:
            errors.append(str(exc))
            continue
        try:
            dev.get_feature_report(0x04, 3)
            send_feature_report(dev, roccat_rgb.KONE_INIT_REPORT)
            send_feature_report(dev, roccat_rgb.KONE_INIT_REPORT)
            send_feature_report(dev, report)
            dev.get_feature_report(0x04, 3)
            return
        except Exception as exc:
            errors.append(str(exc))
        finally:
            try:
                dev.close()
            except Exception:
                pass
    detail = "; ".join(errors) if errors else "no HID interface"
    raise OSError(f"could not set Kone AIMO LEDs: {detail}")


def _send_vulcan_colors(group: Dict[str, Any], colors: Sequence[Tuple[int, int, int]]) -> None:
    ready_key = _color_key(group)
    if ready_key not in _vulcan_ready:
        ctrl_interfaces = _open_interfaces(group, roccat_rgb.VULCAN_CTRL_INTERFACE)
        if not ctrl_interfaces:
            raise OSError("Vulcan control interface 1 was not found")
        dev = open_device_by_entry(ctrl_interfaces[0])
        try:
            delay = _init_delay()
            for report in roccat_rgb.VULCAN_INIT_REPORTS:
                send_feature_report(dev, report)
                if delay:
                    time.sleep(delay)
        finally:
            try:
                dev.close()
            except Exception:
                pass
        _vulcan_ready.add(ready_key)
    led_interfaces = _open_interfaces(group, roccat_rgb.VULCAN_LED_INTERFACE)
    if not led_interfaces:
        raise OSError("Vulcan LED interface 3 was not found")
    dev = open_device_by_entry(led_interfaces[0])
    try:
        for packet in roccat_rgb.vulcan_led_packets(colors):
            write_output_report(dev, packet)
    finally:
        try:
            dev.close()
        except Exception:
            pass


def paint_device(group: Dict[str, Any], color: Tuple[int, int, int], led: Optional[int]) -> str:
    kind = group.get("kind")
    colors = _apply_color_map(group, color, led)
    if kind == "kone":
        _send_kone_colors(group, colors)
        target = "all 11 LEDs" if led is None else roccat_rgb.KONE_LED_NAMES[led]
    elif kind == "vulcan":
        _send_vulcan_colors(group, colors)
        target = "all 144 keys" if led is None else f"key {led}"
    else:
        product = int(group.get("product_id") or 0)
        raise OSError(f"No RGB controller for product 0x{product:04x}")
    _save_colors(group, colors)
    red, green, blue = color
    return f"RGB {red},{green},{blue} on {group.get('name')} {target}"


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
    if _pick_device(args.index) is None:
        return 1
    print("DPI control is not part of the RGB controller.", file=sys.stderr)
    return 2


def _paint_from_args(args: argparse.Namespace, color: Tuple[int, int, int], led: Optional[int]) -> int:
    group = _pick_device(args.index)
    if group is None:
        return 1
    try:
        print(paint_device(group, color, led))
    except Exception as exc:
        print(f"ERROR: device command failed: {exc}", file=sys.stderr)
        return 1
    return 0


def handle_led(args: argparse.Namespace) -> int:
    brightness = roccat_rgb.clamp_channel(args.brightness)
    color = (brightness, brightness, brightness) if args.on else (0, 0, 0)
    return _paint_from_args(args, color, None)


def handle_rgb(args: argparse.Namespace) -> int:
    color = roccat_rgb.scale_color(args.r, args.g, args.b, args.brightness)
    return _paint_from_args(args, color, args.led)


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

    dpi_p = sub.add_parser("dpi", help="DPI changes are not implemented")
    dpi_p.add_argument("x", type=int)
    dpi_p.add_argument("y", type=int)
    dpi_p.add_argument("--index", type=int, default=0, help="Zero-based device index from list")
    dpi_p.set_defaults(func=handle_dpi)

    led_p = sub.add_parser("led", help="Turn every light on (white) or off")
    led_p.add_argument("on", type=int, choices=[0, 1])
    led_p.add_argument("--brightness", type=int, default=255)
    led_p.add_argument("--index", type=int, default=0, help="Zero-based device index from list")
    led_p.set_defaults(func=handle_led)

    rgb_p = sub.add_parser("rgb", help="Set RGB on a Kone AIMO or Vulcan AIMO")
    rgb_p.add_argument("r", type=int)
    rgb_p.add_argument("g", type=int)
    rgb_p.add_argument("b", type=int)
    rgb_p.add_argument("--led", type=int, default=None, help="One Kone LED (0-10) or Vulcan key (0-143)")
    rgb_p.add_argument("--brightness", type=int, default=255, help="Scale the color, 0-255")
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
