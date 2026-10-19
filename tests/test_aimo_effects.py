"""Tests fuer die AIMO-Effekt-Engine (aimo_effects.py).

Verifiziert ohne Hardware:
  - jede Render-Funktion liefert gueltige RGB-Farben in der richtigen Anzahl
  - scale_brightness skaliert wie Eruption (brightness/100)
  - backend_for erkennt Vulcan/Kone anhand der Produkt-ID
  - effect_names listet die AIMO-Software-Effekte

Hinweis (Merge-Reconciliation): Die Bridge-HID-Sendefunktionen
(set_vulcan_led_map / set_kone_led_map / VULCAN_NUM_KEYS) wurden durch die
roccat_rgb-Hardware-Engine (Remote B) ersetzt; die zugehoerigen
Protokoll-Assertions sind daher hier entfernt. Die Render-Engine selbst
(aimo_effects.py) bleibt unveraendert und wird hier getestet.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from aimo_effects import (  # noqa: E402
    backend_for,
    kone_num_leds,
    kone_position,
    render_breathing,
    render_colorcycle,
    render_gradient,
    render_static,
    render_wave,
    scale_brightness,
    vulcan_num_leds,
    vulcan_position,
)
from aimo_themes import theme_by_name  # noqa: E402

VULCAN_ENTRY = {"vendor_id": 0x1E7D, "product_id": 0x2E24, "path": "/dev/vulcan"}
KONE_ENTRY = {"vendor_id": 0x1E7D, "product_id": 0x2E27, "path": "/dev/kone"}


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


# --- Backend-Erkennung ------------------------------------------------------

def test_backend_for():
    n, pos, is_vulcan = backend_for(VULCAN_ENTRY)
    assert n == 143 and is_vulcan
    n, pos, is_vulcan = backend_for(KONE_ENTRY)
    assert n == 11 and not is_vulcan


# --- Effekt-Liste -----------------------------------------------------------

def test_effect_list():
    from aimo_effects import effect_names
    assert set(effect_names()) == {
        "static", "gradient", "breathing", "colorcycle", "wave",
    }
