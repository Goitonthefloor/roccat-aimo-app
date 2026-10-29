"""GUI-to-bridge device selection safety regressions; fake HID only."""
import contextlib
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import roccat_aimo_bridge as bridge

pytestmark = pytest.mark.skipif(not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")), reason="GTK requires a display")


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="GUI passes stale enumeration index to bridge")
def test_gui_selection_survives_enumeration_reorder(monkeypatch, tmp_path):
    import roccat_aimo_gui as gui

    def device(serial, path):
        return {"vendor_id": 0x1e7d, "product_id": 0x2e27,
                "serial_number": serial, "path": path, "interface_number": 1}

    selected = device("A", b"/mock/a")
    other = device("B", b"/mock/b")
    opened = []

    class Handle:
        def open_path(self, path):
            opened.append(os.fsdecode(path))
        def send_feature_report(self, data):
            return len(data)
        def write(self, data):
            return len(data)
        def close(self):
            pass

    class Hid:
        devices = [selected, other]
        def enumerate(self):
            return self.devices
        def device(self):
            return Handle()

    hid = Hid()
    monkeypatch.setattr(bridge, "_hid", hid)
    monkeypatch.setenv("ROCCAT_AIMO_STATE", str(tmp_path / "state.json"))
    monkeypatch.setenv("ROCCAT_AIMO_INIT_DELAY", "0")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert bridge.main(["list", "--json"]) == 0
    listed = json.loads(out.getvalue())
    assert listed[0]["serial_number"] == "A"
    value = SimpleNamespace(get_value=lambda: 255)
    window = SimpleNamespace(r=value, g=value, b=value, brightness=value,
                             selected_index=listed[0]["index"])
    args = gui.RoccatGui._color_args(window)
    hid.devices = [other, selected]
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        code = bridge.main(args)
    assert code != 0 or opened == ["/mock/a"], f"selected A, but opened {opened}"
    assert "/mock/b" not in opened
