#!/usr/bin/env python3
"""Roccat AIMO GTK4 GUI."""

import importlib.util
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw


def _load_bridge():
    """Load the CLI module from source, Flatpak, or the installed script."""
    loaded = sys.modules.get("roccat_aimo_bridge")
    if loaded is not None and hasattr(loaded, "parse_device_json"):
        return loaded
    try:
        import roccat_aimo_bridge

        return roccat_aimo_bridge
    except ImportError:
        pass
    candidates = [Path(__file__).resolve().with_name("roccat_aimo_bridge.py")]
    found = shutil.which("roccat-aimo-cli")
    if found:
        candidates.append(Path(found))
    candidates.extend(
        [
            Path("/app/bin/roccat-aimo-cli"),
            Path("/usr/bin/roccat-aimo-cli"),
            Path.home() / ".local" / "bin" / "roccat-aimo-cli",
        ]
    )
    for path in candidates:
        if not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location("roccat_aimo_bridge", path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules["roccat_aimo_bridge"] = module
        spec.loader.exec_module(module)
        return module
    raise ImportError("roccat_aimo_bridge is not installed next to the GUI")


def resolve_cli() -> list[str]:
    override = os.environ.get("ROCCAT_AIMO_CLI")
    if override:
        return shlex.split(override)
    found = shutil.which("roccat-aimo-cli")
    if found:
        return [found]
    sibling = Path(__file__).resolve().with_name("roccat_aimo_bridge.py")
    if sibling.exists():
        return [sys.executable, str(sibling)]
    return ["roccat-aimo-cli"]


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*resolve_cli(), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def _center(widget: Gtk.Widget) -> Gtk.Widget:
    widget.set_valign(Gtk.Align.CENTER)
    return widget


class RoccatDeviceRow(Adw.ActionRow):
    def __init__(self, device: dict, index: int, on_select):
        super().__init__()
        self.device = device
        self.index = index
        self.on_select = on_select
        vid = int(device.get("vendor_id") or 0)
        pid = int(device.get("product_id") or 0)
        title = device.get("name") or device.get("product_string") or f"Unknown 0x{pid:04x}"
        self.set_title(str(title))
        self.set_subtitle(f"vendor 0x{vid:04x} product 0x{pid:04x}")
        btn = Gtk.Button(label="Select")
        btn.add_css_class("flat")
        btn.connect("clicked", lambda _: on_select(self))
        self.add_suffix(_center(btn))


class RoccatGui(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Roccat AIMO")
        self.set_default_size(720, 560)
        self.selected_index = 0
        self.last_report = {}

        root = Adw.NavigationSplitView()
        self.set_content(root)

        sidebar = Adw.NavigationPage(title="Devices")
        sb_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )
        self.devices_store = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.devices_store.add_css_class("boxed-list")
        self.refresh_btn = Gtk.Button(label="Refresh")
        self.refresh_btn.add_css_class("suggested-action")
        self.refresh_btn.connect("clicked", lambda _: self.load_devices())
        sb_box.append(self.refresh_btn)
        sb_box.append(self.devices_store)
        sidebar.set_child(sb_box)

        main_page = Adw.NavigationPage(title="Device Control")
        main_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )
        self.status_label = Gtk.Label(label="No device selected")
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.set_wrap(True)
        self.status_label.set_xalign(0)
        main_box.append(self.status_label)

        self.r = self._scale(255)
        self.g = self._scale(0)
        self.b = self._scale(0)
        self.brightness = self._scale(255)
        self.zone = Gtk.SpinButton()
        self.zone.set_range(0, 143)
        self.zone.set_increments(1, 12)
        self.zone.set_value(0)

        color_group = Adw.PreferencesGroup(title="RGB controller")
        color_group.add(self._suffix_row("Red", self.r))
        color_group.add(self._suffix_row("Green", self.g))
        color_group.add(self._suffix_row("Blue", self.b))
        color_group.add(self._suffix_row("Brightness", self.brightness))
        self.zone_row = self._suffix_row("Light", self.zone)
        color_group.add(self.zone_row)
        main_box.append(color_group)

        preset_group = Adw.PreferencesGroup(title="Presets")
        preset_row = Adw.ActionRow(title="Color")
        for label, color in (
            ("Off", (0, 0, 0)),
            ("Red", (255, 0, 0)),
            ("Green", (0, 255, 0)),
            ("Blue", (0, 0, 255)),
            ("White", (255, 255, 255)),
        ):
            button = Gtk.Button(label=label)
            button.connect("clicked", lambda _, chosen=color: self.apply_preset(chosen))
            preset_row.add_suffix(_center(button))
        preset_group.add(preset_row)
        main_box.append(preset_group)

        apply_group = Adw.PreferencesGroup(title="Apply")
        all_btn = Gtk.Button(label="All lights")
        all_btn.add_css_class("suggested-action")
        all_btn.connect("clicked", lambda _: self.apply_all())
        one_btn = Gtk.Button(label="Selected light")
        one_btn.connect("clicked", lambda _: self.apply_one())
        apply_group.add(self._suffix_row("", all_btn))
        apply_group.add(self._suffix_row("", one_btn))
        main_box.append(apply_group)

        main_page.set_child(main_box)
        root.set_sidebar(sidebar)
        root.set_content(main_page)

    @staticmethod
    def _scale(value: float) -> Gtk.Scale:
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        scale.set_range(0, 255)
        scale.set_value(value)
        scale.set_draw_value(True)
        scale.set_size_request(160, -1)
        return scale

    @staticmethod
    def _suffix_row(title: str, widget: Gtk.Widget) -> Adw.ActionRow:
        row = Adw.ActionRow(title=title)
        row.add_suffix(_center(widget))
        return row

    def _clear_rows(self) -> None:
        while True:
            row = self.devices_store.get_row_at_index(0)
            if row is None:
                break
            self.devices_store.remove(row)

    def load_devices(self) -> None:
        self._clear_rows()
        try:
            proc = run_cli(["list", "--json"])
        except Exception as exc:
            self.status_label.set_label(f"Device scan failed: {exc}")
            return
        devices, error = _load_bridge().parse_device_json(proc.stdout, proc.returncode, proc.stderr)
        if error:
            self.status_label.set_label(f"Device scan failed: {error}")
            return
        if not devices:
            self.status_label.set_label("No Roccat devices found")
            return
        for fallback, dev in enumerate(devices):
            index = int(dev["index"]) if "index" in dev else fallback
            self._append_device_row(dev, index)
        self.status_label.set_label(f"Found {len(devices)} device(s)")

    def _append_device_row(self, device, index) -> None:
        row = RoccatDeviceRow(device, index, self.select_device)
        self.devices_store.append(row)

    def select_device(self, row) -> None:
        self.selected_index = row.index
        kind = row.device.get("kind")
        if kind == "kone":
            self.zone.set_range(0, 10)
            self.zone_row.set_title("LED")
        else:
            self.zone.set_range(0, 143)
            self.zone_row.set_title("Key" if kind == "vulcan" else "Light")
        title = row.device.get("name") or row.device.get("product_string") or row.get_title()
        self.status_label.set_label(f"Selected: {title}")

    def _report(self, proc: subprocess.CompletedProcess[str], success: str) -> None:
        if proc.returncode == 0:
            text = (proc.stdout or success).strip()
            self.status_label.set_label(text or success)
            return
        err = (proc.stderr or proc.stdout or "command failed").strip()
        self.status_label.set_label(err)

    def _color_args(self, led: int | None = None) -> list[str]:
        args = [
            "rgb",
            str(int(self.r.get_value())),
            str(int(self.g.get_value())),
            str(int(self.b.get_value())),
            "--brightness",
            str(int(self.brightness.get_value())),
            "--index",
            str(self.selected_index),
        ]
        if led is not None:
            args.extend(["--led", str(led)])
        return args

    def apply_preset(self, color: tuple[int, int, int]) -> None:
        self.r.set_value(color[0])
        self.g.set_value(color[1])
        self.b.set_value(color[2])
        self.apply_all()

    def apply_all(self) -> None:
        try:
            proc = run_cli(self._color_args())
        except Exception as exc:
            self.status_label.set_label(f"RGB error: {exc}")
            return
        self._report(proc, "RGB applied to all lights")

    def apply_one(self) -> None:
        try:
            proc = run_cli(self._color_args(int(self.zone.get_value())))
        except Exception as exc:
            self.status_label.set_label(f"RGB error: {exc}")
            return
        self._report(proc, "RGB applied to the selected light")


class RoccatApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.Goitonthefloor.roccat.aimo")
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)

    def do_activate(self):
        windows = self.get_windows()
        if windows:
            windows[0].present()
            return
        window = RoccatGui(self)
        window.load_devices()
        window.present()


def main():
    app = RoccatApp()
    # `roccat-aimo-cli gui` leaves "gui" in argv. Gtk would treat that as a
    # file to open and exit with "This application can not open files."
    program = sys.argv[0] if sys.argv else "roccat-aimo"
    return app.run([program])


if __name__ == "__main__":
    sys.exit(main())
