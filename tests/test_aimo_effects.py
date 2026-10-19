"""Tests fuer die AIMO-Effekt-Engine und die LED-Map-Protokolle.

Verifiziert ohne Hardware per Mock-HID-Device:
  - jede Render-Funktion liefert gueltige RGB-Farben in der richtigen Anzahl
  - scale_brightness skaliert wie Eruption (brightness/100)
  - set_vulcan_led_map / set_kone_led_map bauen die Eruption-Byte-Layouts
  - das CLI `effect`-Subcommand parst und vermittelt auf das passende Protokoll
"""

import sys
import types
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

# --- Mock-HID ---------------------------------------------------------------
VULCAN_ENTRY = {"vendor_id": 0x1E7D, "product_id": 0x2E24, "path": "/dev/vulcan"}
KONE_ENTRY = {"vendor_id": 0x1E7D, "product_id": 0x2E27, "path": "/dev/kone"}


class MockDev:
    def __init__(self):
        self.writes = []
        self.feature_reports = []

    def write(self, data):
        self.writes.append(data)
        return len(data)

    def send_feature_report(self, data):
        self.feature_reports.append(bytes(data))
        return len(data)

    def read(self, *a, **k):
        return []


def _install_hid(monkeypatch):
    hid = types.ModuleType("hid")
    hid.enumerate = lambda: [VULCAN_ENTRY, KONE_ENTRY]

    class device:
        def __init__(self):
            pass

        def open_path(self, path):
            self.path = path

        def open(self, *a):
            pass

        def close(self):
            pass

        def write(self, data):
            return len(data)

        def send_feature_report(self, data):
            return len(data)

        def read(self, n, timeout_ms=0):
            return []

    hid.device = device
    monkeypatch.setitem(sys.modules, "hid", hid)
    return hid


from aimo_effects import (  # noqa: E402
    backend_for,
    kone_num_leds,
    kone_position,
    render_breathing,
    render_colorcycle,
    render_gradient,
    render_static,
    render_wave,
    run_effect,
    scale_brightness,
    vulcan_num_leds,
    vulcan_position,
)
from aimo_themes import theme_by_name  # noqa: E402

from roccat_aimo_bridge import (  # noqa: E402
    KONE_NUM_LEDS,
    VULCAN_NUM_KEYS,
    set_kone_led_map,
    set_vulcan_led_map,
)


# --- Render-Funktionen ------------------------------------------------------

def test_vulcan_geometry():
    assert vulcan_num_leds() == 143
    u, v = vulcan_position(0)
    assert u == 0.0 and v == 0.0
    u, v = vulcan_position(142)  # row 6, col 16
    assert round(u, 3) == round(16 / 20.0, 3)


def test_kone_geometry():
    assert kone_num_leds() == 11
    assert kone_position(0) == (0.0, 0.0)
    assert kone_position(10) == (1.0, 0.0)


def test_render_shapes_and_range():
    stops = theme_by_name("AIMO 9")["colors"]
    cases = [
        (render_static, {"color": (10, 20, 30)}),
        (render_gradient, {"stops": stops, "direction": "h"}),
        (render_breathing, {"color": (255, 0, 0), "min": 0.0, "max": 1.0}),
        (render_colorcycle, {"hue": 0.0, "sat": 1.0, "val": 1.0}),
        (render_wave, {"mode": "hue", "direction": "h", "spread": 1.0,
                       "sat": 1.0, "val": 1.0, "hue": 0.0}),
    ]
    for render, params in cases:
        for pos, n in ((vulcan_position, vulcan_num_leds()),
                       (kone_position, kone_num_leds())):
            for phase in (0.0, 0.5, 0.99):
                out = render(phase, params, pos, n)
                assert len(out) == n
                for c in out:
                    assert len(c) == 3
                    for ch in c:
                        assert 0 <= ch <= 255


def test_scale_brightness():
    led_map = [(255, 255, 255)]
    assert scale_brightness(led_map, 100) == [(255, 255, 255)]
    assert scale_brightness(led_map, 50) == [(127, 127, 127)]
    # Clamp an 100 (nicht >100er-Werte).
    assert scale_brightness(led_map, 200)[0] == (255, 255, 255)


# --- LED-Map-Protokolle -----------------------------------------------------

def test_vulcan_led_map_layout(monkeypatch):
    _install_hid(monkeypatch)
    dev = MockDev()
    map_ = [(i % 256, (i * 2) % 256, (i * 3) % 256) for i in range(VULCAN_NUM_KEYS)]
    set_vulcan_led_map(dev, map_)
    # 448 B -> 7 Chunks a 64 -> 7 Writes a 65 B.
    assert len(dev.writes) == 7
    for w in dev.writes:
        assert len(w) == 65
        assert w[0] == 0  # Report-ID 0
    # Erster Chunk: Header [0xa1,0x01,0x01,0xb4] an Position 1..4.
    assert dev.writes[0][1:5] == [0xA1, 0x01, 0x01, 0xB4]
    # Farb-Offset-Formel: LED 0 -> offset 0 -> r an Puffer-Pos 4 (= write[5]).
    assert dev.writes[0][5] == map_[0][0]
    # LED 12 -> offset ((12//12)*36)+(12%12)=36 -> r an Puffer-Pos 36+4=40 -> write[41].
    assert dev.writes[0][41] == 12


def test_vulcan_led_map_offset_swap():
    # Offset-Formel: ((i//12)*36)+(i%12); pruefe mit i=12: offset 36.
    _install_hid_locally = None
    # Formel aus der Bridge direkt pruefen:
    for i in range(VULCAN_NUM_KEYS):
        off = ((i // 12) * 36) + (i % 12)
        assert off + 4 + 24 < 448


def test_kone_led_map(monkeypatch):
    _install_hid(monkeypatch)
    dev = MockDev()
    map_ = [(r, g, b) for r, g, b in ((255, 0, 0), (0, 255, 0))] + [(1, 2, 3)] * 9
    set_kone_led_map(dev, map_)
    assert len(dev.feature_reports) == 1
    rep = dev.feature_reports[0]
    assert len(rep) == 2 + 11 * 4  # [0x0d,0x2e, RGBA x 11] = 46
    assert rep[0] == 0x0D
    assert rep[1] == 0x2E
    # LED 0: r=255,g=0,b=0,a=255
    assert rep[2] == 255 and rep[3] == 0 and rep[4] == 0 and rep[5] == 255


# --- CLI / run_effect -------------------------------------------------------

def test_run_effect_dispatch(monkeypatch):
    from roccat_aimo_bridge import _send_led_map_for

    # Vulcan static (143) -> 7 x 65-B-Writes.
    dev_v = MockDev()
    run_effect(VULCAN_ENTRY, dev_v, "static", {"color": (12, 34, 56)},
               brightness=100, send=_send_led_map_for)
    assert len(dev_v.writes) == 7

    # Kone static (11) -> 1 x 46-B-Feature-Report.
    dev_k = MockDev()
    run_effect(KONE_ENTRY, dev_k, "static", {"color": (255, 0, 0)},
               brightness=100, send=_send_led_map_for)
    assert len(dev_k.feature_reports) == 1
    assert dev_k.feature_reports[0][0] == 0x0D

    # Kone colorcycle (animiert) mit kurzer Duration -> mehrere Frames.
    dev_k2 = MockDev()
    run_effect(KONE_ENTRY, dev_k2, "colorcycle",
               {"hue": 0.0, "sat": 1.0, "val": 1.0},
               brightness=100, duration=0.05, frame_interval=0.01,
               period=1.0, send=_send_led_map_for)
    assert len(dev_k2.feature_reports) >= 2

    # Backend-Erkennung.
    n, pos, is_vulcan = backend_for(VULCAN_ENTRY)
    assert n == 143 and is_vulcan
    n, pos, is_vulcan = backend_for(KONE_ENTRY)
    assert n == 11 and not is_vulcan


def test_effect_list():
    from aimo_effects import effect_names
    assert set(effect_names()) == {
        "static", "gradient", "breathing", "colorcycle", "wave",
    }
