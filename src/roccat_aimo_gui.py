#!/usr/bin/env python3
"""Roccat AIMO GTK4 GUI."""

import subprocess
import sys

import gi  # noqa: E402  (PyGObject muss vor gi.require_version importiert sein)

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw  # noqa: E402


class RoccatDeviceRow(Adw.ActionRow):
    def __init__(self, device: dict, index: int, on_select):
        super().__init__()
        self.device = device
        self.index = index
        self.on_select = on_select
        prod = (
            device.get("product_string")
            or f"Unknown 0x{device.get('product_id', 0):04x}"
        )
        self.set_title(prod)
        self.set_subtitle(
            f"vendor 0x{device.get('vendor_id', 0):04x} product 0x{device.get('product_id', 0):04x}"
        )
        btn = Gtk.Button(label="Select")
        btn.add_css_class("flat")
        btn.connect("clicked", lambda _: on_select(self))
        self.add_suffix(btn)


class RoccatGui(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Roccat AIMO")
        self.set_default_size(720, 520)
        self.selected_index = 0
        self.polling = False
        self.last_report = {}
        self.effect_proc = None

        root = Adw.NavigationSplitView()
        self.set_content(root)

        # Sidebar
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
        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.add_css_class("suggested-action")
        refresh_btn.connect("clicked", lambda _: self.load_devices())
        sb_box.append(refresh_btn)
        sb_box.append(self.devices_store)
        sidebar.set_child(sb_box)

        # Main content
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

        self.dpi_x = Gtk.SpinButton()
        self.dpi_x.set_range(100, 16000)
        self.dpi_x.set_increments(50, 100)
        self.dpi_x.set_value(1600)
        self.dpi_y = Gtk.SpinButton()
        self.dpi_y.set_range(100, 16000)
        self.dpi_y.set_increments(50, 100)
        self.dpi_y.set_value(1600)
        dpi_btn = Gtk.Button(label="Apply DPI")
        dpi_btn.connect("clicked", lambda _: self.apply_dpi())

        self.led_switch = Gtk.Switch()
        self.brightness = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.brightness.set_range(0, 255)
        self.brightness.set_value(255)
        led_btn = Gtk.Button(label="Apply LED")
        led_btn.connect("clicked", lambda _: self.apply_led())

        self.rgb_row = Gtk.SpinButton()
        self.rgb_row.set_range(0, 5)
        self.rgb_row.set_value(0)
        self.rgb_col = Gtk.SpinButton()
        self.rgb_col.set_range(0, 20)
        self.rgb_col.set_value(0)
        self.r = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.r.set_range(0, 255)
        self.r.set_value(0)
        self.g = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.g.set_range(0, 255)
        self.g.set_value(0)
        self.b = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.b.set_range(0, 255)
        self.b.set_value(0)
        rgb_btn = Gtk.Button(label="Apply RGB")
        rgb_btn.connect("clicked", lambda _: self.apply_rgb())

        # AIMO-Theme-Auswahl
        self.aimo_theme = Gtk.DropDown()
        try:
            from aimo_themes import theme_names

            self.aimo_themes = theme_names()
        except ImportError:
            self.aimo_themes = ["AIMO 1"]
        theme_model = Gtk.StringList.new(self.aimo_themes)
        self.aimo_theme.set_model(theme_model)
        self.aimo_theme.set_selected(0)
        self.aimo_dir = Gtk.DropDown()
        dir_model = Gtk.StringList.new(["horizontal", "vertical"])
        self.aimo_dir.set_model(dir_model)
        self.aimo_dir.set_selected(0)
        aimo_btn = Gtk.Button(label="Apply AIMO Theme")
        aimo_btn.connect("clicked", lambda _: self.apply_aimo())

        for widget in [
            Adw.PreferencesGroup.new(),
            self.status_label,
        ]:
            main_box.append(widget)

        dpi_group = Adw.PreferencesGroup.new()
        dpi_group.set_title("DPI")
        row = Adw.ActionRow(title="X")
        row.add_suffix(self.dpi_x)
        dpi_group.add(row)
        row = Adw.ActionRow(title="Y")
        row.add_suffix(self.dpi_y)
        dpi_group.add(row)
        dpi_group.add(Adw.PreferencesRow.new())
        dpi_group.get_child_last().set_child(dpi_btn)
        main_box.append(dpi_group)

        led_group = Adw.PreferencesGroup.new()
        led_group.set_title("LED")
        led_row = Adw.ActionRow(title="Enabled")
        led_row.add_suffix(self.led_switch)
        led_group.add(led_row)
        led_bright_row = Adw.ActionRow(title="Brightness")
        led_bright_row.add_suffix(self.brightness)
        led_group.add(led_bright_row)
        led_group.add(Adw.PreferencesRow.new())
        led_group.get_child_last().set_child(led_btn)
        main_box.append(led_group)

        rgb_group = Adw.PreferencesGroup.new()
        rgb_group.set_title("RGB")
        row = Adw.ActionRow(title="Row")
        row.add_suffix(self.rgb_row)
        rgb_group.add(row)
        row = Adw.ActionRow(title="Col")
        row.add_suffix(self.rgb_col)
        rgb_group.add(row)
        row = Adw.ActionRow(title="Red")
        row.add_suffix(self.r)
        rgb_group.add(row)
        row = Adw.ActionRow(title="Green")
        row.add_suffix(self.g)
        rgb_group.add(row)
        row = Adw.ActionRow(title="Blue")
        row.add_suffix(self.b)
        rgb_group.add(row)
        rgb_group.add(Adw.PreferencesRow.new())
        rgb_group.get_child_last().set_child(rgb_btn)
        main_box.append(rgb_group)

        aimo_group = Adw.PreferencesGroup.new()
        aimo_group.set_title("AIMO Theme")
        aimo_theme_row = Adw.ActionRow(title="Theme")
        aimo_theme_row.add_suffix(self.aimo_theme)
        aimo_group.add(aimo_theme_row)
        aimo_dir_row = Adw.ActionRow(title="Direction")
        aimo_dir_row.add_suffix(self.aimo_dir)
        aimo_group.add(aimo_dir_row)
        aimo_group.add(Adw.PreferencesRow.new())
        aimo_group.get_child_last().set_child(aimo_btn)
        main_box.append(aimo_group)

        # AIMO-Effekt-Auswahl (software-gerenderte LED-Maps)
        self.effect_sel = Gtk.DropDown()
        effect_model = Gtk.StringList.new(
            ["static", "gradient", "breathing", "colorcycle", "wave"]
        )
        self.effect_sel.set_model(effect_model)
        self.effect_sel.set_selected(0)
        self.effect_theme = Gtk.DropDown()
        self.effect_theme.set_model(Gtk.StringList.new(self.aimo_themes))
        self.effect_theme.set_selected(0)
        self.effect_dir = Gtk.DropDown()
        self.effect_dir.set_model(Gtk.StringList.new(["h", "v", "d"]))
        self.effect_dir.set_selected(0)
        self.effect_r = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.effect_r.set_range(0, 255)
        self.effect_r.set_value(255)
        self.effect_g = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.effect_g.set_range(0, 255)
        self.effect_g.set_value(0)
        self.effect_b = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.effect_b.set_range(0, 255)
        self.effect_b.set_value(0)
        self.effect_period = Gtk.SpinButton()
        self.effect_period.set_range(0.1, 60.0)
        self.effect_period.set_increments(0.1, 1.0)
        self.effect_period.set_value(2.0)
        self.effect_duration = Gtk.SpinButton()
        self.effect_duration.set_range(0, 3600)
        self.effect_duration.set_increments(1, 10)
        self.effect_duration.set_value(0)
        effect_btn = Gtk.Button(label="Apply Effect")
        effect_btn.connect("clicked", lambda _: self.apply_effect())

        effect_group = Adw.PreferencesGroup.new()
        effect_group.set_title("AIMO Effect")
        row = Adw.ActionRow(title="Effect")
        row.add_suffix(self.effect_sel)
        effect_group.add(row)
        row = Adw.ActionRow(title="Theme (gradient/wave)")
        row.add_suffix(self.effect_theme)
        effect_group.add(row)
        row = Adw.ActionRow(title="Direction")
        row.add_suffix(self.effect_dir)
        effect_group.add(row)
        row = Adw.ActionRow(title="Red")
        row.add_suffix(self.effect_r)
        effect_group.add(row)
        row = Adw.ActionRow(title="Green")
        row.add_suffix(self.effect_g)
        effect_group.add(row)
        row = Adw.ActionRow(title="Blue")
        row.add_suffix(self.effect_b)
        effect_group.add(row)
        row = Adw.ActionRow(title="Period (s)")
        row.add_suffix(self.effect_period)
        effect_group.add(row)
        row = Adw.ActionRow(title="Duration (s, 0=endless)")
        row.add_suffix(self.effect_duration)
        effect_group.add(row)
        effect_group.add(Adw.PreferencesRow.new())
        effect_group.get_child_last().set_child(effect_btn)
        main_box.append(effect_group)

        main_page.set_child(main_box)
        root.set_sidebar(sidebar)
        root.set_content(main_page)

    def load_devices(self):
        self.devices_store.remove_all()
        try:
            payload = subprocess.check_output(["roccat-aimo-cli", "list"], text=True)
        except Exception as exc:
            self._append_device_row({"product_string": f"ERROR: {exc}"}, 0)
            return
        devices = []
        current = {}
        for line in payload.splitlines():
            if (
                line.startswith("1. ")
                or line.startswith("2. ")
                or line.startswith("3. ")
                or line.startswith("0. ")
            ):
                if current:
                    devices.append(current)
                current = {"title": line.split(" ", 1)[1]}
            elif line.strip().startswith("manufacturer:"):
                current["manufacturer"] = line.split(":", 1)[1].strip()
            elif line.strip().startswith("product:"):
                current["product"] = line.split(":", 1)[1].strip()
            elif line.strip().startswith("vendor_id:"):
                current["vendor"] = line.split(":", 1)[1].strip()
            elif line.strip().startswith("product_id:"):
                current["product_id"] = line.split(":", 1)[1].strip()
        if current:
            devices.append(current)
        for idx, dev in enumerate(devices):
            self._append_device_row(dev, idx)

    def _append_device_row(self, device, index):
        row = RoccatDeviceRow(device, index, lambda w: self.select_device(w))
        self.devices_store.append(row)
        self.devices_store.show()

    def select_device(self, row):
        self.selected_index = row.index
        self.status_label.set_label(
            f"Selected: {row.device.get('product_string') or row.device.get('title')}"
        )

    def apply_dpi(self):
        x = int(self.dpi_x.get_value())
        y = int(self.dpi_y.get_value())
        try:
            subprocess.check_output(
                [
                    "roccat-aimo-cli",
                    "dpi",
                    str(x),
                    str(y),
                    "--index",
                    str(self.selected_index),
                ],
                text=True,
            )
            self.status_label.set_label(f"DPI applied: {x}/{y}")
        except Exception as exc:
            self.status_label.set_label(f"DPI error: {exc}")

    def apply_led(self):
        on = 1 if self.led_switch.get_active() else 0
        brightness = int(self.brightness.get_value())
        try:
            subprocess.check_output(
                [
                    "roccat-aimo-cli",
                    "led",
                    str(on),
                    "--brightness",
                    str(brightness),
                    "--index",
                    str(self.selected_index),
                ],
                text=True,
            )
            self.status_label.set_label(f"LED applied: on={on} brightness={brightness}")
        except Exception as exc:
            self.status_label.set_label(f"LED error: {exc}")

    def apply_rgb(self):
        row = int(self.rgb_row.get_value())
        col = int(self.rgb_col.get_value())
        r = int(self.r.get_value())
        g = int(self.g.get_value())
        b = int(self.b.get_value())
        try:
            subprocess.check_output(
                [
                    "roccat-aimo-cli",
                    "rgb",
                    str(row),
                    str(col),
                    str(r),
                    str(g),
                    str(b),
                    "--index",
                    str(self.selected_index),
                ],
                text=True,
            )
            self.status_label.set_label(f"RGB applied: ({row},{col}) = {r},{g},{b}")
        except Exception as exc:
            self.status_label.set_label(f"RGB error: {exc}")

    def apply_aimo(self):
        theme = self.aimo_themes[self.aimo_theme.get_selected()]
        direction = "h" if self.aimo_dir.get_selected() == 0 else "v"
        try:
            subprocess.check_output(
                [
                    "roccat-aimo-cli",
                    "aimo",
                    theme,
                    "--direction",
                    direction,
                    "--index",
                    str(self.selected_index),
                ],
                text=True,
            )
            self.status_label.set_label(f"AIMO theme applied: {theme} ({direction})")
        except Exception as exc:
            self.status_label.set_label(f"AIMO error: {exc}")

    def apply_effect(self):
        """Wendet einen AIMO-Effekt an (Hintergrundprozess).

        Animierte Effekte laufen als eigener Prozess; ein vorheriger
        Effekt-Prozess wird beendet, damit sich nicht zwei Loops ueberschreiben.
        """
        effect = ["static", "gradient", "breathing", "colorcycle", "wave"][
            self.effect_sel.get_selected()
        ]
        theme = self.aimo_themes[self.effect_theme.get_selected()]
        direction = ["h", "v", "d"][self.effect_dir.get_selected()]
        r = int(self.effect_r.get_value())
        g = int(self.effect_g.get_value())
        b = int(self.effect_b.get_value())
        period = self.effect_period.get_value()
        duration = int(self.effect_duration.get_value())

        cmd = ["roccat-aimo-cli", "effect", effect]
        if effect in ("static", "breathing"):
            cmd += [str(r), str(g), str(b)]
        if effect == "gradient":
            cmd += [theme, "--direction", direction]
        if effect == "wave":
            cmd += ["--mode", "gradient", "--theme", theme,
                    "--direction", direction]
        if effect in ("breathing", "colorcycle", "wave"):
            cmd += ["--period", str(period), "--duration", str(duration)]
        cmd += ["--index", str(self.selected_index)]

        # Vorherigen Effekt-Prozess beenden, falls noch aktiv.
        if self.effect_proc is not None and self.effect_proc.poll() is None:
            self.effect_proc.terminate()
        try:
            self.effect_proc = subprocess.Popen(cmd)
            self.status_label.set_label(
                f"AIMO effect applied: {effect} (theme={theme}, dir={direction})"
            )
        except Exception as exc:
            self.status_label.set_label(f"AIMO effect error: {exc}")


class RoccatApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.Goitonthefloor.roccat.aimo")
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)

    def do_activate(self, gui=None):
        if gui is None:
            gui = RoccatGui(self)
        gui.present()


def main():
    app = RoccatApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())