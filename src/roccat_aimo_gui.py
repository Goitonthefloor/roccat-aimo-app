#!/usr/bin/env python3
"""Roccat AIMO GTK4 RGB controller."""

import importlib.util
import importlib.machinery
import threading
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, GLib

import roccat_rgb


STATIC_CSS = """
.rgb-swatch {
  border-radius: 18px;
  min-height: 72px;
  border: 1px solid rgba(255, 255, 255, 0.28);
}
button.preset {
  border-radius: 999px;
  min-height: 34px;
}
button.preset-off {
  background-color: #2e2e2e;
  color: #f5f5f5;
}
button.preset-red {
  background-color: #e23b3b;
  color: #ffffff;
}
button.preset-green {
  background-color: #2f9e49;
  color: #ffffff;
}
button.preset-blue {
  background-color: #3d7eff;
  color: #ffffff;
}
button.preset-white {
  background-color: #f2f2f2;
  color: #1c1c1c;
}
button.action-secondary {
  background-color: #3c3c3c;
  color: #ffffff;
}
scale trough { min-height: 8px; }
scale.channel-red > trough > highlight { background: #e23b3b; }
scale.channel-green > trough > highlight { background: #3cba5a; }
scale.channel-blue > trough > highlight { background: #3d7eff; }
entry.hex-entry {
  font-family: monospace;
  font-size: 18px;
}
"""


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
        spec = importlib.util.spec_from_file_location("roccat_aimo_bridge", path,
            loader=importlib.machinery.SourceFileLoader("roccat_aimo_bridge", str(path)))
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
        timeout=15,
    )


class RoccatDeviceRow(Adw.ActionRow):
    def __init__(self, device: dict, index: int, on_select):
        super().__init__()
        self.device = device
        self.index = index
        self.on_select = on_select
        vid = int(device.get("vendor_id") or 0)
        pid = int(device.get("product_id") or 0)
        title = device.get("name")
        if pid in {item["product"] for item in roccat_rgb.PRODUCTS}:
            title = roccat_rgb.product_name(pid)
        elif not title or str(title).startswith("Unknown 0x"):
            title = roccat_rgb.product_name(pid, device.get("product_string"))
        self.set_title(str(title))
        kind = roccat_rgb.kind_for_product(pid)
        lights = {"kone": "11 LEDs", "vulcan": "144 keys"}.get(kind, "")
        subtitle = f"vendor 0x{vid:04x} product 0x{pid:04x}"
        if lights:
            subtitle = f"{subtitle} · {lights}"
        else:
            subtitle = f"RGB not supported yet · {subtitle}"
        device_type = roccat_rgb.device_type_for_product(pid)
        category = {"mouse": "Mouse", "keyboard": "Keyboard"}.get(device_type, "Device")
        subtitle = f"{category} · {subtitle}"
        self.set_subtitle(subtitle)
        self.set_activatable(True)
        self.connect("activated", lambda row: on_select(row))


class RoccatGui(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Roccat AIMO RGB")
        self.set_default_size(960, 640)
        self.selected_index = None
        self._busy = False
        self._closed = False
        self._preview_colors = [(0, 0, 0)] * 144
        self._selected_kind = ""
        self._updating_color = False
        self._effect_name = None
        self._effect_frame = 0
        self._effect_source = None
        self._effect_proc = None
        self._effect_gen = 0
        self._effect_restart = None
        self._effect_buttons = {}
        self.last_report = {}
        self._swatch_css = None

        self._install_css()

        root = Adw.NavigationSplitView()
        root.set_min_sidebar_width(200)
        root.set_max_sidebar_width(240)
        window_toolbar = Adw.ToolbarView()
        self.header_bar = Adw.HeaderBar()
        self.header_bar.set_decoration_layout(":minimize,maximize,close")
        window_toolbar.add_top_bar(self.header_bar)
        window_toolbar.set_content(root)
        self.set_content(window_toolbar)

        sidebar = Adw.NavigationPage(title="Devices")
        sb_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )
        header = Gtk.Box(spacing=8)
        self.refresh_btn = Gtk.Button()
        self.refresh_btn.set_child(
            Adw.ButtonContent(label="Refresh", icon_name="view-refresh-symbolic")
        )
        self.refresh_btn.set_tooltip_text("Refresh devices")
        self.refresh_btn.set_halign(Gtk.Align.START)
        self.refresh_btn.connect("clicked", lambda _: self.load_devices())
        header.append(self.refresh_btn)
        self.devices_store = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.devices_store.add_css_class("navigation-sidebar")
        self.devices_store.connect("row-activated", self._on_row_activated)
        device_scroll = Gtk.ScrolledWindow()
        device_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        device_scroll.set_vexpand(True)
        device_scroll.set_child(self.devices_store)
        self.empty_hint = Gtk.Label(label="Plug in a Kone AIMO or a Vulcan AIMO.")
        self.empty_hint.set_wrap(True)
        self.empty_hint.set_xalign(0)
        self.empty_hint.add_css_class("dim-label")
        sb_box.append(header)
        sb_box.append(device_scroll)
        sb_box.append(self.empty_hint)
        sidebar.set_child(sb_box)

        self.r = self._scale(255, "channel-red")
        self.g = self._scale(0, "channel-green")
        self.b = self._scale(0, "channel-blue")
        self.brightness = self._scale(255, None)
        self.speed = self._speed_scale(1.0)
        for scale in (self.r, self.g, self.b, self.brightness):
            scale.connect("value-changed", self._sync_preview)
        self.speed.connect("value-changed", self._on_speed_changed)

        self.zone = Adw.SpinRow.new_with_range(0, 143, 1)
        self.zone.set_digits(0)
        self.zone.set_title("Light")
        self.zone_row = self.zone
        self.zone.connect("notify::value", lambda *_args: self._sync_zone_hint())

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_top=8,
            margin_bottom=8,
            margin_start=16,
            margin_end=16,
        )
        self.device_title = Gtk.Label(label="RGB controller", xalign=0)
        self.device_title.add_css_class("title-2")
        self.device_title.set_wrap(True)
        self.device_subtitle = Gtk.Label(label="Choose a color, then send it to the lights.", xalign=0)
        self.device_subtitle.set_wrap(True)
        self.device_subtitle.add_css_class("dim-label")
        content.append(self.device_title)
        content.append(self.device_subtitle)

        self.swatch = Gtk.Box()
        self.swatch.add_css_class("rgb-swatch")
        self.swatch.set_size_request(-1, 72)
        self.swatch.set_hexpand(True)
        content.append(self.swatch)
        self.led_preview = Gtk.DrawingArea()
        self.led_preview.set_content_height(96)
        self.led_preview.set_draw_func(self._draw_lights)
        self.led_preview.set_tooltip_text("LED sequence preview; not a physical keyboard layout")
        content.append(self.led_preview)

        readout = Gtk.Box(spacing=12)
        readout.set_halign(Gtk.Align.CENTER)
        self.preview_label = Gtk.Label(label="#FF0000")
        self.preview_label.set_visible(False)
        self.hex_entry = Gtk.Entry()
        self.hex_entry.add_css_class("hex-entry")
        self.hex_entry.set_max_width_chars(7)
        self.hex_entry.set_width_chars(7)
        self.hex_entry.set_alignment(0.5)
        self.hex_entry.set_placeholder_text("#RRGGBB")
        self.hex_entry.set_tooltip_text("Type a hex color")
        self.hex_entry.connect("changed", self._on_hex_changed)
        readout.append(self.preview_label)
        readout.append(self.hex_entry)
        content.append(readout)

        self.preview_detail = Gtk.Label(label="Full brightness")
        self.preview_detail.add_css_class("dim-label")
        self.preview_detail.set_halign(Gtk.Align.CENTER)
        self.preview_detail.set_wrap(True)
        self.preview_detail.set_justify(Gtk.Justification.CENTER)
        content.append(self.preview_detail)

        presets = Gtk.Box(spacing=8, homogeneous=True)
        for label, color, css in (
            ("Off", (0, 0, 0), "preset-off"),
            ("Red", (255, 0, 0), "preset-red"),
            ("Green", (0, 255, 0), "preset-green"),
            ("Blue", (0, 0, 255), "preset-blue"),
            ("White", (255, 255, 255), "preset-white"),
        ):
            presets.append(self._preset_button(label, color, css))
        content.append(presets)

        effects = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                              column_spacing=8, row_spacing=8, max_children_per_line=4)
        for name in roccat_rgb.EFFECTS:
            button = Gtk.Button(label=roccat_rgb.EFFECT_LABELS[name])
            button.add_css_class("pill")
            button.connect("clicked", lambda _, chosen=name: self.start_effect(chosen))
            self._effect_buttons[name] = button
            effects.append(button)
        stop = Gtk.Button(label="Stop")
        stop.add_css_class("pill")
        stop.connect("clicked", lambda _: self.stop_effect(restore=True))
        effects.append(stop)
        content.append(effects)

        speed_group = Adw.PreferencesGroup()
        self.speed_value = self._add_channel(
            speed_group, "Speed", self.speed, format_value=self._format_speed, value_width=48
        )
        self.bpm = Adw.SpinRow.new_with_range(30, 240, 1)
        self.bpm.set_title("Beat tempo · BPM")
        self.bpm.set_subtitle("Beat mode; multiplied by Speed")
        self.bpm.set_value(120)
        self.bpm.connect("notify::value", lambda *_: self._settings_changed())
        speed_group.add(self.bpm)
        self.reverse = Adw.SwitchRow(title="Reverse flow")
        self.reverse.connect("notify::active", lambda *_: self._settings_changed())
        speed_group.add(self.reverse)
        content.append(speed_group)
        hint = Gtk.Label(label="Light by Push: whole-keyboard flash on key press. Host input permission required.", xalign=0, wrap=True)
        hint.add_css_class("dim-label")
        content.append(hint)

        color_group = Adw.PreferencesGroup(title="Color")
        self.red_value = self._add_channel(color_group, "Red", self.r)
        self.green_value = self._add_channel(color_group, "Green", self.g)
        self.blue_value = self._add_channel(color_group, "Blue", self.b)
        self.brightness_value = self._add_channel(color_group, "Brightness", self.brightness)
        content.append(color_group)

        light_group = Adw.PreferencesGroup(title="One light")
        light_group.add(self.zone)
        content.append(light_group)

        actions = Gtk.Box(spacing=12, homogeneous=True)
        all_btn = Gtk.Button(label="All lights")
        all_btn.add_css_class("suggested-action")
        all_btn.add_css_class("pill")
        all_btn.connect("clicked", lambda _: self.apply_all())
        one_btn = Gtk.Button(label="Selected light")
        one_btn.add_css_class("pill")
        one_btn.add_css_class("action-secondary")
        one_btn.connect("clicked", lambda _: self.apply_one())
        actions.append(all_btn)
        actions.append(one_btn)

        self.status_label = Gtk.Label(label="No device selected")
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.set_wrap(True)
        self.status_label.set_xalign(0)
        self.status_label.set_selectable(True)
        status_card = Gtk.Box()
        status_card.add_css_class("card")
        self.status_label.set_margin_top(10)
        self.status_label.set_margin_bottom(10)
        self.status_label.set_margin_start(12)
        self.status_label.set_margin_end(12)
        status_card.append(self.status_label)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(980)
        clamp.set_tightening_threshold(720)
        clamp.set_child(content)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        scrolled.set_child(clamp)

        bottom = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        bottom.set_margin_top(8)
        bottom.set_margin_bottom(8)
        bottom.set_margin_start(12)
        bottom.set_margin_end(12)
        bottom.append(actions)
        bottom.append(status_card)
        toolbar = Adw.ToolbarView()
        toolbar.set_content(scrolled)
        toolbar.add_bottom_bar(bottom)

        main_page = Adw.NavigationPage(title="RGB")
        main_page.set_child(toolbar)
        root.set_sidebar(sidebar)
        root.set_content(main_page)
        self.connect("close-request", self._on_close)
        self._sync_preview()
        self._sync_zone_hint()
        self._actions = actions
        self._effects_widget = effects
        self._set_controls()

    def _set_controls(self):
        enabled = self.selected_index is not None and self._selected_kind in {"kone", "vulcan"} and not self._busy
        self._actions.set_sensitive(enabled)
        self._effects_widget.set_sensitive(enabled)
        self.devices_store.set_sensitive(not self._busy)
        self.refresh_btn.set_sensitive(not self._busy)
        self._effect_buttons["reactive"].set_sensitive(self._selected_kind == "vulcan")

    def _settings_changed(self):
        if self._effect_name:
            self._schedule_effect_respawn()

    def _draw_lights(self, area, cr, width, height):
        colors = self._preview_colors
        columns = 24 if len(colors) > 11 else 11
        rows = (len(colors) + columns - 1) // columns
        for index, (r, g, b) in enumerate(colors):
            cr.set_source_rgb(r / 255, g / 255, b / 255)
            cr.rectangle((index % columns) * width / columns + 2,
                         (index // columns) * height / rows + 2,
                         max(1, width / columns - 4), max(1, height / rows - 4))
            cr.fill()

    def _run_command(self, args, callback):
        if self._busy:
            return
        self._busy = True
        self._set_controls()
        self._set_status("Working…")
        def done(result):
            self._busy = False
            if not self._closed:
                self._set_controls()
                if isinstance(result, Exception):
                    self._set_status(str(result))
                else:
                    callback(result)
            return False
        def worker():
            try:
                result = run_cli(args)
            except Exception as exc:
                result = exc
            GLib.idle_add(done, result)
        threading.Thread(target=worker, daemon=True).start()

    def _install_css(self) -> None:
        display = Gdk.Display.get_default()
        if display is None:
            return
        static = Gtk.CssProvider()
        static.load_from_string(STATIC_CSS)
        self._swatch_css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            display,
            static,
            Gtk.STYLE_PROVIDER_PRIORITY_USER,
        )
        Gtk.StyleContext.add_provider_for_display(
            display,
            self._swatch_css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1,
        )

    @staticmethod
    def _scale(value: float, css_class: str | None) -> Gtk.Scale:
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        scale.set_range(0, 255)
        scale.set_increments(1, 16)
        scale.set_round_digits(0)
        scale.set_draw_value(False)
        scale.set_hexpand(True)
        scale.set_value(value)
        if css_class:
            scale.add_css_class(css_class)
        return scale

    @staticmethod
    def _speed_scale(value: float) -> Gtk.Scale:
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        scale.set_range(0.25, 4.0)
        scale.set_increments(0.25, 0.5)
        scale.set_round_digits(2)
        scale.set_draw_value(False)
        scale.set_hexpand(True)
        scale.set_value(value)
        scale.set_tooltip_text("Effect speed, 0.25× to 4×")
        return scale

    @staticmethod
    def _format_speed(value: float) -> str:
        return f"{roccat_rgb.clamp_speed(value):.2f}×"

    def _effect_speed(self) -> float:
        return roccat_rgb.clamp_speed(self.speed.get_value())

    def _add_channel(
        self,
        group: Adw.PreferencesGroup,
        title: str,
        scale: Gtk.Scale,
        format_value=None,
        value_width: int = 36,
    ) -> Gtk.Label:
        row = Adw.PreferencesRow()
        row.set_activatable(False)
        row.set_selectable(False)
        box = Gtk.Box(spacing=12)
        box.set_margin_top(2)
        box.set_margin_bottom(2)
        box.set_margin_start(12)
        box.set_margin_end(12)
        name = Gtk.Label(label=title, xalign=0)
        name.set_size_request(92, -1)
        scale.set_hexpand(True)
        scale.set_valign(Gtk.Align.CENTER)
        formatter = format_value or (lambda amount: str(int(amount)))
        value = Gtk.Label(label=formatter(scale.get_value()), xalign=1)
        value.set_size_request(value_width, -1)
        value.add_css_class("numeric")
        value.add_css_class("dim-label")
        box.append(name)
        box.append(scale)
        box.append(value)
        row.set_child(box)
        group.add(row)
        return value

    def _preset_button(self, label: str, color: tuple[int, int, int], css: str) -> Gtk.Button:
        button = Gtk.Button(label=label)
        button.add_css_class("preset")
        button.add_css_class(css)
        button.set_hexpand(True)
        button.connect("clicked", lambda _, chosen=color: self.apply_preset(chosen))
        return button

    def _set_status(self, text: str) -> None:
        self.status_label.set_label(text)

    def _sync_preview(self, *_args) -> None:
        if self._updating_color:
            return
        red = int(self.r.get_value())
        green = int(self.g.get_value())
        blue = int(self.b.get_value())
        brightness = int(self.brightness.get_value())
        sent = roccat_rgb.scale_color(red, green, blue, brightness)
        chosen = f"#{red:02X}{green:02X}{blue:02X}"
        device_hex = f"#{sent[0]:02X}{sent[1]:02X}{sent[2]:02X}"
        self.preview_label.set_label(chosen)
        self.red_value.set_label(str(red))
        self.green_value.set_label(str(green))
        self.blue_value.set_label(str(blue))
        self.brightness_value.set_label(str(brightness))
        self._updating_color = True
        try:
            if self.hex_entry.get_text().upper() != chosen:
                self.hex_entry.set_text(chosen)
        finally:
            self._updating_color = False
        if self._effect_name:
            self._schedule_effect_respawn()
            return
        if brightness >= 255:
            self.preview_detail.set_label("Full brightness")
        else:
            percent = round(brightness * 100 / 255)
            self.preview_detail.set_label(f"Brightness {percent}% · device receives {device_hex}")
        self._preview_colors = [sent] * (11 if self._selected_kind == "kone" else 144)
        self.led_preview.queue_draw()
        if self._swatch_css is not None:
            self._swatch_css.load_from_string(
                ".rgb-swatch { background-color: " + device_hex + "; }"
            )

    def _on_hex_changed(self, entry: Gtk.Entry) -> None:
        if self._updating_color:
            return
        text = entry.get_text().strip()
        if text.startswith("#"):
            text = text[1:]
        if len(text) != 6:
            return
        try:
            value = int(text, 16)
        except ValueError:
            return
        self._updating_color = True
        try:
            self.r.set_value((value >> 16) & 255)
            self.g.set_value((value >> 8) & 255)
            self.b.set_value(value & 255)
        finally:
            self._updating_color = False
        self._sync_preview()

    def _sync_zone_hint(self) -> None:
        index = int(self.zone.get_value())
        if self._selected_kind == "kone" and 0 <= index < len(roccat_rgb.KONE_LED_NAMES):
            self.zone.set_subtitle(roccat_rgb.KONE_LED_NAMES[index])
        elif self._selected_kind == "vulcan":
            self.zone.set_subtitle(f"Key {index} of {roccat_rgb.VULCAN_KEY_COUNT}")
        else:
            self.zone.set_subtitle("Pick a device to name this light")

    def _clear_rows(self) -> None:
        while True:
            row = self.devices_store.get_row_at_index(0)
            if row is None:
                break
            self.devices_store.remove(row)

    def load_devices(self) -> None:
        if self._busy:
            return
        self.stop_effect(restore=False)
        self.selected_index = None
        self._selected_kind = ""
        self._clear_rows()
        self._set_controls()
        self._run_command(["list", "--json"], self._devices_loaded)

    def _devices_loaded(self, proc):
        devices, error = _load_bridge().parse_device_json(proc.stdout, proc.returncode, proc.stderr)
        if error:
            self.empty_hint.set_visible(True)
            self._set_status(f"Device scan failed: {error}")
            return
        if not devices:
            self.empty_hint.set_visible(True)
            self.device_title.set_label("RGB controller")
            self._set_status("No Roccat devices found")
            return
        for fallback, dev in enumerate(devices):
            index = int(dev["index"]) if "index" in dev else fallback
            self._append_device_row(dev, index)
        self.empty_hint.set_visible(False)
        first = self.devices_store.get_row_at_index(0)
        if isinstance(first, RoccatDeviceRow):
            self.select_device(first)
        else:
            self._set_status(f"Found {len(devices)} device(s)")

    def _append_device_row(self, device, index) -> None:
        row = RoccatDeviceRow(device, index, self.select_device)
        self.devices_store.append(row)

    def _on_row_activated(self, _box, row) -> None:
        if isinstance(row, RoccatDeviceRow):
            self.select_device(row)

    def select_device(self, row) -> None:
        self.stop_effect(restore=False)
        self.selected_index = row.index
        self.devices_store.select_row(row)
        pid = int(row.device.get("product_id") or 0)
        kind = roccat_rgb.kind_for_product(pid)
        self._selected_kind = kind
        if kind == "kone":
            self.zone.set_range(0, 10)
            self.zone_row.set_title("LED")
        elif kind == "vulcan":
            self.zone.set_range(0, 143)
            self.zone_row.set_title("Key")
        else:
            self.zone.set_range(0, 143)
            self.zone_row.set_title("Light")
        self._sync_zone_hint()
        title = row.get_title()
        self.device_title.set_label(str(title))
        self.device_subtitle.set_label(row.get_subtitle() or "")
        self._set_controls()
        self._sync_preview()
        self._set_status(f"Selected: {title}" if kind in {"kone", "vulcan"}
                         else f"Detected: {title}. RGB control is not supported for this model yet.")

    def _report(self, proc: subprocess.CompletedProcess[str], success: str) -> None:
        if proc.returncode == 0:
            text = (proc.stdout or success).strip()
            self._set_status(text or success)
            return
        err = (proc.stderr or proc.stdout or "command failed").strip()
        self._set_status(err)

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

    def _on_close(self, *_args) -> bool:
        self._closed = True
        self.stop_effect(restore=False)
        return False

    def _highlight_effect(self, name: str | None) -> None:
        for effect, button in self._effect_buttons.items():
            if effect == name:
                button.add_css_class("suggested-action")
            else:
                button.remove_css_class("suggested-action")

    def _effect_args(self) -> list[str]:
        return self._base_effect_args() + (["--reverse"] if self.reverse.get_active() else [])

    def _base_effect_args(self) -> list[str]:
        return [
            "effect",
            self._effect_name or "breathe",
            str(int(self.r.get_value())),
            str(int(self.g.get_value())),
            str(int(self.b.get_value())),
            "--brightness",
            str(int(self.brightness.get_value())),
            "--speed",
            f"{self._effect_speed():.2f}",
            "--bpm", str(int(self.bpm.get_value())),
            "--index",
            str(self.selected_index),
        ]

    def _on_speed_changed(self, *_args) -> None:
        self.speed_value.set_label(self._format_speed(self.speed.get_value()))
        if self._effect_name:
            self._schedule_effect_respawn()

    def _stop_effect_process(self) -> None:
        self._effect_gen += 1
        proc = self._effect_proc
        self._effect_proc = None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        if proc is not None and proc.stderr:
            proc.stderr.close()

    def _spawn_effect_process(self) -> None:
        self._stop_effect_process()
        if not self._effect_name:
            return
        try:
            proc = subprocess.Popen(
                [*resolve_cli(), *self._effect_args()],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception as exc:
            self.stop_effect(restore=False)
            self._set_status(f"Effect error: {exc}")
            return
        self._effect_proc = proc
        generation = self._effect_gen

        def check_exit():
            if generation != self._effect_gen:
                return False
            if proc.poll() is None:
                return True
            err = (proc.stderr.read() if proc.stderr else "").strip()
            if proc.stderr:
                proc.stderr.close()
            self._effect_proc = None
            self.stop_effect(restore=False)
            self._sync_preview()
            self._set_status(err or "Effect stopped")
            return False

        GLib.timeout_add(100, check_exit)

    def _schedule_effect_respawn(self) -> None:
        if self._effect_restart is not None:
            GLib.source_remove(self._effect_restart)
        self._effect_restart = GLib.timeout_add(200, self._respawn_effect)

    def _respawn_effect(self) -> bool:
        self._effect_restart = None
        if self._effect_name:
            self._spawn_effect_process()
        return False

    def _effect_tick(self) -> bool:
        if not self._effect_name:
            self._effect_source = None
            return False
        count = roccat_rgb.KONE_LED_COUNT if self._selected_kind == "kone" else roccat_rgb.VULCAN_KEY_COUNT
        colors = roccat_rgb.effect_colors(
            self._effect_name,
            int(self.r.get_value()),
            int(self.g.get_value()),
            int(self.b.get_value()),
            int(self.brightness.get_value()),
            self._effect_frame,
            count,
            self._effect_speed(),
            self.bpm.get_value(), self.reverse.get_active(),
        )
        self._preview_colors = colors
        self.led_preview.queue_draw()
        self._effect_frame += 1
        red, green, blue = colors[0]
        shown = f"#{red:02X}{green:02X}{blue:02X}"
        self.preview_detail.set_label("Waiting for keyboard input · hardware preview only" if self._effect_name == "reactive"
                                      else f"{roccat_rgb.EFFECT_LABELS[self._effect_name]} · {shown}")
        if self._swatch_css is not None:
            self._swatch_css.load_from_string(".rgb-swatch { background-color: " + shown + "; }")
        return True

    def start_effect(self, name: str) -> None:
        if self.selected_index is None or self._selected_kind not in {"kone", "vulcan"} or self._busy:
            return
        self.stop_effect(restore=False)
        self._effect_name = name
        self._effect_frame = 0
        self._highlight_effect(name)
        self._effect_source = GLib.timeout_add(84, self._effect_tick)
        self._spawn_effect_process()
        if self._effect_proc is not None:
            self._set_status(f"{roccat_rgb.EFFECT_LABELS[name]} running")

    def stop_effect(self, restore: bool = True) -> None:
        was_running = self._effect_name is not None
        self._effect_name = None
        if self._effect_restart is not None:
            GLib.source_remove(self._effect_restart)
            self._effect_restart = None
        if self._effect_source is not None:
            GLib.source_remove(self._effect_source)
            self._effect_source = None
        self._stop_effect_process()
        self._highlight_effect(None)
        if restore and was_running:
            self._sync_preview()
            self.apply_all()

    def apply_preset(self, color: tuple[int, int, int]) -> None:
        self.r.set_value(color[0])
        self.g.set_value(color[1])
        self.b.set_value(color[2])
        self._sync_preview()
        self.apply_all()

    def apply_all(self) -> None:
        if self.selected_index is None or self._selected_kind not in {"kone", "vulcan"} or self._busy:
            return
        self.stop_effect(restore=False)
        self._run_command(self._color_args(), lambda proc: self._report(proc, "RGB applied to all lights"))

    def apply_one(self) -> None:
        if self.selected_index is None or self._selected_kind not in {"kone", "vulcan"} or self._busy:
            return
        self.stop_effect(restore=False)
        self._run_command(self._color_args(int(self.zone.get_value())),
                          lambda proc: self._report(proc, "RGB applied to the selected light"))


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
