#!/usr/bin/env python3
"""GTK window tests. Requires a display (xvfb is enough)."""

import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

HAS_DISPLAY = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
if HAS_DISPLAY:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw

    import roccat_aimo_gui as gui


def _script(path: Path, body: str) -> str:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


@unittest.skipUnless(HAS_DISPLAY, "GTK window test needs DISPLAY or WAYLAND_DISPLAY")
class GuiTests(unittest.TestCase):
    def test_window_lists_json_devices_and_surfaces_scan_errors(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        ok = _script(
            base / "ok-cli",
            """#!/bin/sh
case "$1" in
  list)
    printf '%s\\n' '[{"index":0,"name":"Kone AIMO","vendor_id":7805,"product_id":11815,"product_string":"ROCCAT Kone AIMO"}]'
    exit 0
    ;;
  rgb)
    echo "RGB $2,$3,$4 brightness $6 index $8"
    exit 0
    ;;
  *)
    echo "unexpected $*" >&2
    exit 2
    ;;
esac
""",
        )
        bad = _script(
            base / "bad-cli",
            """#!/bin/sh
echo "ERROR: hidapi is required" >&2
exit 1
""",
        )
        broken = _script(
            base / "broken-cli",
            """#!/bin/sh
echo 'not-json'
exit 0
""",
        )

        os.environ["ROCCAT_AIMO_CLI"] = ok
        self.addCleanup(os.environ.pop, "ROCCAT_AIMO_CLI", None)

        class Probe(gui.RoccatApp):
            def __init__(self):
                super().__init__()
                self.failure = None
                self.title = None
                self.subtitle = None
                self.preview = None
                self.zone_title = None
                self.zone_subtitle = None
                self.hex_green = None
                self.dpi_status = None
                self.error_status = None
                self.invalid_status = None
                self.error_rows = None

            def do_activate(self):
                try:
                    super().do_activate()
                    window = self.get_windows()[0]
                    row = window.devices_store.get_row_at_index(0)
                    self.title = row.get_title()
                    self.subtitle = row.get_subtitle()
                    window.select_device(row)
                    window.r.set_value(255)
                    window.g.set_value(0)
                    window.b.set_value(0)
                    window.brightness.set_value(255)
                    self.preview = window.preview_label.get_label()
                    self.zone_title = window.zone.get_title()
                    self.zone_subtitle = window.zone.get_subtitle()
                    window.hex_entry.set_text("#00FF00")
                    self.hex_green = int(window.g.get_value())
                    window.r.set_value(255)
                    window.g.set_value(0)
                    window.b.set_value(0)
                    window.apply_all()
                    self.dpi_status = window.status_label.get_label()
                    os.environ["ROCCAT_AIMO_CLI"] = bad
                    window.load_devices()
                    self.error_rows = window.devices_store.get_row_at_index(0)
                    self.error_status = window.status_label.get_label()
                    os.environ["ROCCAT_AIMO_CLI"] = broken
                    window.load_devices()
                    self.invalid_status = window.status_label.get_label()
                except Exception as exc:
                    self.failure = exc
                finally:
                    self.quit()

        app = Probe()
        app.run([])
        self.assertIsNone(app.failure)
        self.assertEqual(app.title, "Kone AIMO")
        self.assertIn("0x1e7d", app.subtitle)
        self.assertIn("0x2e27", app.subtitle)
        self.assertIn("11 LEDs", app.subtitle)
        self.assertEqual(app.preview, "#FF0000")
        self.assertEqual(app.zone_title, "LED")
        self.assertEqual(app.zone_subtitle, "Wheel")
        self.assertEqual(app.hex_green, 255)
        self.assertIn("RGB 255,0,0 brightness 255 index 0", app.dpi_status)
        self.assertIsNone(app.error_rows)
        self.assertIn("hidapi", app.error_status)
        self.assertIn("not valid JSON", app.invalid_status)

    def test_cli_gui_command_stays_open(self):
        proc = subprocess.Popen(
            [sys.executable, str(ROOT / "src" / "roccat_aimo_bridge.py"), "gui"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            time.sleep(1.2)
            self.assertIsNone(proc.poll(), "gui command exited before the window could stay open")
        finally:
            proc.terminate()
            try:
                _, stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                _, stderr = proc.communicate(timeout=5)
        self.assertNotIn("can not open files", stderr)
        self.assertNotIn("Traceback", stderr)

    def test_resolve_cli_uses_source_tree_when_uninstalled(self):
        previous_cli = os.environ.pop("ROCCAT_AIMO_CLI", None)
        previous_path = os.environ.get("PATH", "")

        def restore():
            os.environ["PATH"] = previous_path
            if previous_cli is None:
                os.environ.pop("ROCCAT_AIMO_CLI", None)
            else:
                os.environ["ROCCAT_AIMO_CLI"] = previous_cli

        self.addCleanup(restore)
        path_parts = [part for part in previous_path.split(os.pathsep) if part]
        os.environ["PATH"] = os.pathsep.join(
            part for part in path_parts if not Path(part, "roccat-aimo-cli").exists()
        )
        resolved = gui.resolve_cli()
        self.assertEqual(resolved[-1], str(ROOT / "src" / "roccat_aimo_bridge.py"))


if __name__ == "__main__":
    unittest.main()
