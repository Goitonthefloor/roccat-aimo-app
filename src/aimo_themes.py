"""AIMO-Farbthemen und Gradient-Interpolation.

Rekonstruiert aus Rocket Swarm `data/Swarm/aimo_color_theme.dat` (REA-Analyse).
Jedes Theme ist ein Farbverlauf (Gradient) mit 3 Farbstopps.
Farben sind 16-bit pro Kanal in der .dat; hier als 8-bit RGB-Tupel.
"""

from __future__ import annotations

from typing import List, Tuple

RGB = Tuple[int, int, int]

# 10 AIMO-Themes, je 3 Farbstopps (8-bit RGB).
AIMO_THEMES: List[dict] = [
    {"name": "AIMO 1", "colors": [(255, 255, 255), (255, 255, 255), (230, 230, 140)]},
    {"name": "AIMO 2", "colors": [(0, 0, 0), (75, 75, 75), (150, 150, 150)]},
    {"name": "AIMO 3", "colors": [(90, 90, 19), (157, 157, 20), (175, 175, 13)]},
    {"name": "AIMO 4", "colors": [(197, 197, 11), (241, 241, 127), (208, 208, 1)]},
    {"name": "AIMO 5", "colors": [(246, 246, 255), (249, 249, 194), (245, 245, 104)]},
    {"name": "AIMO 6", "colors": [(200, 200, 255), (100, 100, 255), (0, 0, 255)]},
    {"name": "AIMO 7", "colors": [(0, 0, 255), (0, 0, 255), (245, 245, 76)]},
    {"name": "AIMO 8", "colors": [(246, 246, 126), (249, 249, 194), (0, 0, 0)]},
    {"name": "AIMO 9", "colors": [(0, 0, 127), (0, 0, 255), (244, 244, 0)]},
    {"name": "AIMO 10", "colors": [(244, 244, 0), (244, 244, 0), (246, 246, 120)]},
]


def lerp(a: float, b: float, t: float) -> float:
    """Lineare Interpolation zwischen a und b."""
    return a + (b - a) * t


def gradient_color(
    stops: List[RGB], t: float
) -> RGB:
    """Farbe eines Gradienten an Position t (0.0..1.0).

    Interpoliert linear zwischen den Farbstopps.
    """
    t = max(0.0, min(1.0, t))
    if len(stops) == 1:
        return stops[0]
    n = len(stops) - 1
    seg = t * n
    idx = min(int(seg), n - 1)
    local = seg - idx
    c0, c1 = stops[idx], stops[idx + 1]
    return (
        int(round(lerp(c0[0], c1[0], local))),
        int(round(lerp(c0[1], c1[1], local))),
        int(round(lerp(c0[2], c1[2], local))),
    )


def theme_by_name(name: str) -> dict:
    """Theme per Name oder Index (1-basiert) finden."""
    for t in AIMO_THEMES:
        if t["name"].lower() == name.lower():
            return t
    try:
        idx = int(name) - 1
        if 0 <= idx < len(AIMO_THEMES):
            return AIMO_THEMES[idx]
    except ValueError:
        pass
    raise KeyError(f"Unbekanntes AIMO-Theme: {name!r}")


def theme_names() -> List[str]:
    return [t["name"] for t in AIMO_THEMES]
