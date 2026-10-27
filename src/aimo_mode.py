"""AIMO-Modus-Fähigkeiten ("Skills") — datengetriebene AIMO-Modus-Logik.

Trägt die Erkenntnisse aus docs/aimo_reverse_engineering.md in strukturierter
Form, damit die GUI den AIMO-Signatur-Modus über eine einzige Quelle aufruft
statt Effekt und Farben doppelt hart zu kodieren.

Definition (bewusste Näherung, keine Originaltreue — siehe REA-Doku):
  "AIMO-Modus" = software-gerenderte Wave über den AIMO-Signatur-Farbverlauf
  Rot -> Orange -> Gelb über das ganze Gerät. Dass dies exakt dem adaptiven
  AIMO-Smart-Algorithmus der Original-Swarm entspricht, ist durch den
  statischen REA-Run NICHT belegt (docs/aimo_reverse_engineering.md,
  Zeilen 11, 17, 42, 55).

Evidenz (aus docs/aimo_reverse_engineering.md):
  - Signatur-Farbstopps (255,0,0) -> (255,80,0) -> (230,140,0): erste Stopps
    laut Rohbytes von aimo_color_theme.dat (REA-Doku Zeile 38).
  - AIMO-Effekte sind Gradienten-Farbverläufe (E1 in EFFEKTE.md); Wave nutzt
    die vorhandene render_wave-Engine (docs/EFFEKTE.md, aimo_effects.py).
  - Übertragung je Frame über die gerätespezifische send_led_map (Side A).

Die Liste der dokumentierten Effektfamilien (`available_skills`) ist eine
Inventarliste der durch EFFEKTE.md/REA nachbildbaren Fähigkeiten, keine
Zusage über Original-Umsetzung einzelner Varianten.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from aimo_effects import (
    kone_num_leds,
    kone_position,
    render_wave,
    vulcan_num_leds,
    vulcan_position,
)

Score = Tuple[int, int, int]

# Rot -> Orange -> Gelb: die drei ersten Farbstopps aus aimo_color_theme.dat
# (REA-Doku Zeile 38). Datengebundene Signatur-Näherung, kein Originalbeleg.
AIMO_SIGNATURE: Tuple[Score, Score, Score] = (
    (255, 0, 0),
    (255, 80, 0),
    (230, 140, 0),
)


def signature_theme_string() -> str:
    """Kommagetrennte Stopp-Liste 'r,g,b;r,g,b;r,g,b' für die CLI (--theme)."""
    return ";".join(f"{r},{g},{b}" for r, g, b in AIMO_SIGNATURE)


def aimo_cli_args(index: Optional[int], brightness_percent: int) -> List[str]:
    """CLI-Argumente, die den AIMO-Signatur-Modus auf Gerät `index` starten."""
    brightness = max(0, min(100, int(brightness_percent)))
    return [
        "aimo-effect",
        "wave",
        "--mode",
        "gradient",
        "--theme",
        signature_theme_string(),
        "--direction",
        "h",
        "--brightness",
        str(brightness),
        "--index",
        str(index if index is not None else 0),
    ]


def aimo_preview_colors(
    kind: str,
    frame: int,
    brightness: int = 255,
    frame_divisor: int = 24,
) -> List[Score]:
    """Vorschau-Farben je Frame für den AIMO-Signatur-Verlauf.

    `kind` ist "kone" oder "vulcan"; verwendet dieselbe render_wave-Engine
    wie der eigentliche CLI-Pfad, damit Vorschau und Gerätebild übereinstimmen.
    """
    if kind == "kone":
        num, pos = kone_num_leds(), kone_position
    else:
        num, pos = vulcan_num_leds(), vulcan_position
    phase = ((frame % max(1, frame_divisor)) / float(max(1, frame_divisor))) % 1.0
    frame_colors = render_wave(
        phase,
        {
            "mode": "gradient",
            "direction": "h",
            "spread": 1.0,
            "stops": list(AIMO_SIGNATURE),
            "sat": 1.0,
            "val": 1.0,
        },
        pos,
        num,
    )
    brightness = max(0, min(255, int(brightness)))
    if brightness >= 255:
        return [(r, g, b) for r, g, b in frame_colors]
    factor = brightness / 255.0
    return [(int(r * factor), int(g * factor), int(b * factor)) for r, g, b in frame_colors]


def available_skills() -> List[dict]:
    """Inventarliste der dokumentierten AIMO-Effektfähigkeiten (nur Referenz)."""
    return [
        {"name": "gradient", "family": "E1", "evidenz": "BELEGT (REA)"},
        {"name": "static", "family": "E2", "evidenz": "BELEGT (Eruption)"},
        {"name": "wave", "family": "E3", "evidenz": "BELEGT (Eruption); Swarm-Namen ungesichert"},
        {"name": "breathing", "family": "E4", "evidenz": "BELEGT (Eruption); Swarm-Bezug ungesichert"},
        {"name": "colorcycle", "family": "E5", "evidenz": "BELEGT (Eruption); Swarm-Bezug ungesichert"},
    ]