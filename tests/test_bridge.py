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
import roccat_rgb


class FakeDevice:
    def __init__(self, fail_open_path=False, fail_open=False, fail_write=False, read_value=None):
        self.fail_open_path = fail_open_path
        self.fail_open = fail_open
        self.fail_write = fail_write
        self.read_value = [0x04, 0x01] if read_value is None else read_value
        self.opened = None
        self.written = []
        self.features = []
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

    def send_feature_report(self, data):
        if self.fail_write:
            raise OSError("write failed")
        payload = list(data)
        self.features.append(payload)
        return len(payload)

    def get_feature_report(self, report_id, size):
        self.features.append(("get", report_id, size))
        return [report_id, 1, 0]

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
        bridge._vulcan_ready.clear()
        os.environ["ROCCAT_AIMO_INIT_DELAY"] = "0"

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
        self.assertEqual(payload[0]["kind"], "kone")
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

    def test_dpi_is_rejected_without_a_hid_write(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = bridge.main(["dpi", "1600", "1600", "--index", "0"])
        self.assertEqual(code, 2)
        self.assertIn("RGB controller", stderr.getvalue())
        self.assertEqual(self.fake.created, [])

    def test_led_off_sends_kone_feature_report(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = bridge.main(["led", "0", "--brightness", "999", "--index", "0"])
        self.assertEqual(code, 0)
        self.assertIn("RGB 0,0,0", stdout.getvalue())
        reports = [item for item in self.fake.created[-1].features if isinstance(item, list)]
        color = reports[-1]
        self.assertEqual(color[:2], [0x0D, 0x2E])
        self.assertEqual(len(color), 46)
        self.assertEqual(color[2:6], [0, 0, 0, 0])
        self.assertTrue(self.fake.created[-1].closed)

    def test_rgb_clamps_and_keeps_other_kone_leds(self):
        with contextlib.redirect_stdout(io.StringIO()):
            first = bridge.main(["rgb", "300", "-1", "10", "--led", "0", "--index", "0"])
            second = bridge.main(["rgb", "0", "255", "0", "--led", "1", "--brightness", "128", "--index", "0"])
        self.assertEqual(first, 0)
        self.assertEqual(second, 0)
        reports = [item for item in self.fake.created[-1].features if isinstance(item, list) and item[0] == 0x0D]
        color = reports[-1]
        self.assertEqual(color[2:6], [255, 0, 10, 0])
        self.assertEqual(color[6:10], [0, 128, 0, 0])

    def test_effect_envelopes_and_rainbow_shift(self):
        breathe_off = roccat_rgb.effect_colors("breathe", 255, 0, 0, 255, 0, 11)[0]
        breathe_peak = roccat_rgb.effect_colors("breathe", 255, 0, 0, 255, 36, 11)[0]
        pulse_off = roccat_rgb.effect_colors("pulse", 255, 0, 0, 255, 0, 11)[0]
        pulse_peak = roccat_rgb.effect_colors("pulse", 255, 0, 0, 255, 12, 11)[0]
        self.assertEqual(breathe_off, (0, 0, 0))
        self.assertEqual(breathe_peak, (255, 0, 0))
        self.assertEqual(pulse_off, (0, 0, 0))
        self.assertEqual(pulse_peak, (255, 0, 0))
        self.assertLess(
            roccat_rgb.effect_colors("pulse", 255, 0, 0, 255, 3, 11)[0][0],
            roccat_rgb.effect_colors("breathe", 255, 0, 0, 255, 9, 11)[0][0],
        )
        rainbow = roccat_rgb.effect_colors("rainbow", 0, 0, 0, 255, 0, 11)
        self.assertEqual(rainbow[0], (255, 0, 0))
        self.assertNotEqual(rainbow[0], rainbow[5])
        wide = roccat_rgb.effect_colors("rainbow", 0, 0, 0, 255, 0, 144)
        self.assertEqual(wide[0], (255, 0, 0))
        self.assertEqual(wide[72], (0, 255, 255))
        slow = roccat_rgb.effect_colors("rainbow", 0, 0, 0, 255, 12, 11, 1.0)[0]
        fast = roccat_rgb.effect_colors("rainbow", 0, 0, 0, 255, 12, 11, 4.0)[0]
        self.assertNotEqual(slow, fast)
        self.assertEqual(roccat_rgb.clamp_speed(9), 4.0)
        self.assertEqual(roccat_rgb.clamp_speed(0), 0.25)

    def test_pulse_effect_sends_changing_kone_frames(self):
        os.environ["ROCCAT_AIMO_EFFECT_INTERVAL"] = "0"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = bridge.main(
                ["effect", "pulse", "255", "0", "0", "--frames", "4", "--speed", "4", "--index", "0"]
            )
        self.assertEqual(code, 0)
        reports = []
        for dev in self.fake.created:
            for item in dev.features:
                if isinstance(item, list) and item and item[0] == 0x0D:
                    reports.append(item)
        self.assertGreaterEqual(len(reports), 2)
        self.assertEqual(reports[0][2:5], [0, 0, 0])
        self.assertEqual(reports[-1][2:5], [255, 0, 0])
        self.assertIn("FRAME 0 0 0", stdout.getvalue())
        self.assertIn("FRAME 255 0 0", stdout.getvalue())

    def test_rainbow_effect_colors_separate_kone_leds(self):
        os.environ["ROCCAT_AIMO_EFFECT_INTERVAL"] = "0"
        with contextlib.redirect_stdout(io.StringIO()):
            code = bridge.main(["effect", "rainbow", "255", "255", "255", "--frames", "1", "--index", "0"])
        self.assertEqual(code, 0)
        report = next(
            item
            for dev in self.fake.created
            for item in dev.features
            if isinstance(item, list) and item and item[0] == 0x0D
        )
        self.assertEqual(report[2:5], [255, 0, 0])
        self.assertNotEqual(report[2:5], report[2 + 5 * 4:5 + 5 * 4])

    def test_effect_without_device_does_not_open_hid(self):
        self.fake.devices = []
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = bridge.main(["effect", "breathe", "255", "0", "0", "--frames", "3"])
        self.assertEqual(code, 1)
        self.assertIn("No Roccat devices found.", stderr.getvalue())
        self.assertEqual(self.fake.created, [])

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
            code = bridge.main(["rgb", "255", "0", "0"])
        self.assertEqual(code, 1)
        self.assertIn("device command failed", stderr.getvalue())

    def test_vulcan_rgb_uses_led_interface_after_init(self):
        self.fake.devices = [
            {
                "vendor_id": 0x1E7D,
                "product_id": 0x307A,
                "path": b"0001:0005:01",
                "interface_number": 1,
                "product_string": "Vulcan 100 AIMO",
            },
            {
                "vendor_id": 0x1E7D,
                "product_id": 0x307A,
                "path": b"0001:0005:03",
                "interface_number": 3,
                "product_string": "Vulcan 100 AIMO",
            },
        ]
        with contextlib.redirect_stdout(io.StringIO()):
            code = bridge.main(["rgb", "0", "0", "255", "--index", "0"])
        self.assertEqual(code, 0)
        ctrl = next(dev for dev in self.fake.created if dev.opened and dev.opened[1] in (b"0001:0005:01", "0001:0005:01"))
        led = next(dev for dev in self.fake.created if dev.opened and dev.opened[1] in (b"0001:0005:03", "0001:0005:03"))
        feature_ids = [item[0] for item in ctrl.features if isinstance(item, list)]
        self.assertEqual(feature_ids[0], 0x15)
        self.assertEqual(feature_ids[-1], 0x13)
        self.assertEqual(len(led.written), 7)
        self.assertEqual(led.written[0][:5], [0x00, 0xA1, 0x01, 0x01, 0xB4])
        self.assertEqual(led.written[0][5], 0)
        self.assertEqual(led.written[0][5 + 24], 255)
        self.assertTrue(all(len(packet) == 65 for packet in led.written))

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
