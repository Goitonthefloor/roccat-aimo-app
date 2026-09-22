#!/usr/bin/env python3
"""CLI and HID report tests. No hardware required."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import roccat_aimo_bridge as bridge


class FakeDevice:
    def __init__(self, fail_open_path=False, fail_open=False, fail_write=False, read_value=None):
        self.fail_open_path = fail_open_path
        self.fail_open = fail_open
        self.fail_write = fail_write
        self.read_value = [0x04, 0x01] if read_value is None else read_value
        self.opened = None
        self.written = []
        self.closed = False

    def open_path(self, path):
        if self.fail_open_path:
            raise OSError("open_path failed")
        self.opened = ("path", path)

    def open(self, vendor_id, product_id):
        if self.fail_open:
            raise OSError("open failed")
        self.opened = ("ids", vendor_id, product_id)

    def write(self, data):
        if self.fail_write:
            raise OSError("write failed")
        payload = list(data)
        self.written.append(payload)
        return len(payload)

    def read(self, length, timeout_ms=0):
        return list(self.read_value)

    def close(self):
        self.closed = True


class FakeHid:
    def __init__(self, devices, fail_open_path=False, fail_open=False, fail_write=False):
        self.devices = devices
        self.fail_open_path = fail_open_path
        self.fail_open = fail_open
        self.fail_write = fail_write
        self.created = []

    def enumerate(self):
        return list(self.devices)

    def device(self):
        dev = FakeDevice(self.fail_open_path, self.fail_open, self.fail_write)
        self.created.append(dev)
        return dev


def kone_device():
    return {
        "vendor_id": 0x1E7D,
        "product_id": 0x2E27,
        "path": b"/dev/hidraw3",
        "product_string": "ROCCAT Kone AIMO",
        "manufacturer_string": b"ROCCAT",
        "release_number": 1,
        "interface_number": 1,
    }


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "devices.json"
        os.environ["ROCCAT_AIMO_STATE"] = str(self.state)
        self.fake = FakeHid([kone_device()])
        bridge._hid = self.fake

    def tearDown(self):
        bridge._hid = None
        os.environ.pop("ROCCAT_AIMO_STATE", None)
        self.tmp.cleanup()

    def test_list_json_survives_bytes_paths_and_names_device(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = bridge.main(["list", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload[0]["name"], "Kone AIMO")
        self.assertEqual(payload[0]["index"], 0)
        self.assertEqual(payload[0]["path"], "/dev/hidraw3")
        self.assertEqual(payload[0]["manufacturer_string"], "ROCCAT")
        saved = json.loads(self.state.read_text())
        self.assertEqual(saved["devices"][0]["product_id"], 0x2E27)

    def test_list_text_uses_zero_based_index_and_split_ids(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = bridge.main(["list"])
        text = stdout.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("[0] Kone AIMO", text)
        self.assertIn("vendor_id: 0x1e7d", text)
        self.assertIn("product_id: 0x2e27", text)
        self.assertNotIn("vendor_id: 0x1e7d product_id:", text)

    def test_list_without_devices_exits_nonzero(self):
        self.fake.devices = []
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = bridge.main(["list"])
        self.assertEqual(code, 1)
        self.assertIn("No Roccat devices found.", stdout.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as json_out:
            json_code = bridge.main(["list", "--json"])
        self.assertEqual(json_code, 1)
        self.assertEqual(json.loads(json_out.getvalue()), [])

    def test_other_vendor_is_ignored(self):
        self.fake.devices = [{"vendor_id": 0x046D, "product_id": 0xC52B, "path": b"/dev/hidraw0"}]
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = bridge.main(["list", "--json"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(stdout.getvalue()), [])

    def test_dpi_report_starts_with_report_id_and_clamps(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = bridge.main(["dpi", "10", "99999", "--index", "0"])
        self.assertEqual(code, 0)
        self.assertIn("DPI set to 100/16000", stdout.getvalue())
        written = self.fake.created[-1].written[0]
        self.assertEqual(written[0], 0x04)
        self.assertEqual(written[1:3], [0x03, 0x04])
        self.assertEqual(written[3:7], [0x00, 0x64, 0x3E, 0x80])
        self.assertTrue(self.fake.created[-1].closed)

    def test_led_off_clamps_brightness(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = bridge.main(["led", "0", "--brightness", "999", "--index", "0"])
        self.assertEqual(code, 0)
        self.assertIn("LED OFF at 255", stdout.getvalue())
        self.assertEqual(self.fake.created[-1].written[0], [0x04, 0x07, 0x00, 0xFF])

    def test_rgb_clamps_coordinates_and_channels(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code = bridge.main(["rgb", "-4", "40", "300", "-1", "10", "--index", "0"])
        self.assertEqual(code, 0)
        self.assertEqual(self.fake.created[-1].written[0], [0x04, 0x0B, 0, 20, 255, 0, 10])

    def test_index_out_of_range_does_not_write(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = bridge.main(["dpi", "800", "800", "--index", "3"])
        self.assertEqual(code, 1)
        self.assertIn("out of range", stderr.getvalue())
        self.assertEqual(self.fake.created, [])

    def test_open_falls_back_to_vendor_product_when_path_fails(self):
        self.fake.fail_open_path = True
        with contextlib.redirect_stdout(io.StringIO()):
            code = bridge.main(["poll", "--index", "0"])
        self.assertEqual(code, 0)
        opened = [dev.opened for dev in self.fake.created]
        self.assertIn(("ids", 0x1E7D, 0x2E27), opened)

    def test_write_error_is_reported(self):
        self.fake.fail_write = True
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = bridge.main(["dpi", "800", "800"])
        self.assertEqual(code, 1)
        self.assertIn("device command failed", stderr.getvalue())

    def test_corrupt_state_is_replaced(self):
        self.state.write_text("{not json")
        self.assertEqual(bridge.load_state(), {"devices": []})
        with contextlib.redirect_stdout(io.StringIO()):
            bridge.bridge_once(None)
        saved = json.loads(self.state.read_text())
        self.assertEqual(saved["devices"][0]["name"], "Kone AIMO")

    def test_bridge_once_logs_only_when_devices_change(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            first = bridge.bridge_once(None)
            second = bridge.bridge_once(first)
        self.assertEqual(first, second)
        self.assertEqual(stdout.getvalue().count("Tracking"), 1)

    def test_gui_search_includes_source_tree_and_flatpak(self):
        paths = bridge.gui_search_paths()
        self.assertEqual(paths[0], ROOT / "src")
        self.assertIn(Path("/app/lib/roccat-aimo-app"), paths)

    def test_parse_device_json_accepts_empty_array_with_nonzero_status(self):
        devices, error = bridge.parse_device_json("[]\n", 1, "No Roccat devices found.")
        self.assertEqual(devices, [])
        self.assertIsNone(error)

    def test_parse_device_json_reports_hid_error(self):
        devices, error = bridge.parse_device_json("", 1, "ERROR: hidapi is required.")
        self.assertEqual(devices, [])
        self.assertIn("hidapi", error)

    def test_help_and_live_list_from_subprocess(self):
        help_proc = subprocess.run(
            [sys.executable, str(ROOT / "src" / "roccat_aimo_bridge.py"), "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(help_proc.returncode, 0, help_proc.stderr)
        self.assertIn("list", help_proc.stdout)

        env = os.environ.copy()
        env["ROCCAT_AIMO_STATE"] = str(Path(self.tmp.name) / "live.json")
        list_proc = subprocess.run(
            [sys.executable, str(ROOT / "src" / "roccat_aimo_bridge.py"), "list", "--json"],
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        self.assertEqual(list_proc.returncode, 1, list_proc.stderr)
        self.assertEqual(json.loads(list_proc.stdout), [])

    def test_missing_hid_module_fails_cleanly(self):
        code = r"""
import builtins, runpy, sys
real = builtins.__import__
def hooked(name, globals=None, locals=None, fromlist=(), level=0):
    if name in {"hid", "hidraw"}:
        raise ImportError("blocked for test")
    return real(name, globals, locals, fromlist, level)
builtins.__import__ = hooked
sys.argv = ["roccat-aimo-cli", "list", "--json"]
runpy.run_path(sys.argv[1] if False else %r, run_name="__main__")
""" % str(ROOT / "src" / "roccat_aimo_bridge.py")
        proc = subprocess.run([sys.executable, "-c", code], text=True, capture_output=True, check=False)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("hidapi is required", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
