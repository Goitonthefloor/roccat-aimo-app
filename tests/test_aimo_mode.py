#!/usr/bin/env python3
"""Unit tests for the AIMO-Modus skill profile (src/aimo_mode.py)."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import aimo_mode


class AimoModeTests(unittest.TestCase):
    def test_signature_colours_match_reverse_engineering_report(self):
        # docs/aimo_reverse_engineering.md Zeile 38: erste Farbstopps laut
        # Rohbytes (255,0,0), (255,80,0), (230,140,0).
        self.assertEqual(
            aimo_mode.AIMO_SIGNATURE,
            ((255, 0, 0), (255, 80, 0), (230, 140, 0)),
        )
        self.assertEqual(
            aimo_mode.signature_theme_string(),
            "255,0,0;255,80,0;230,140,0",
        )

    def test_cli_args_are_deterministic_wave_gradient(self):
        args = aimo_mode.aimo_cli_args(0, 100)
        self.assertEqual(args[0], "aimo-effect")
        self.assertEqual(args[1], "wave")
        self.assertIn("--mode", args)
        self.assertEqual(args[args.index("--mode") + 1], "gradient")
        self.assertIn("--theme", args)
        self.assertEqual(args[args.index("--theme") + 1], "255,0,0;255,80,0;230,140,0")
        self.assertEqual(args[args.index("--index") + 1], "0")
        self.assertEqual(args[args.index("--brightness") + 1], "100")

    def test_cli_args_brightness_clamped_and_index_fallback(self):
        self.assertEqual(aimo_mode.aimo_cli_args(3, 999)[-1], "3")
        self.assertEqual(
            aimo_mode.aimo_cli_args(3, 999)[aimo_mode.aimo_cli_args(3, 999).index("--brightness") + 1],
            "100",
        )
        # None-Index -> 0, negative Helligkeit -> 0.
        self.assertEqual(aimo_mode.aimo_cli_args(None, -5)[aimo_mode.aimo_cli_args(None, -5).index("--index") + 1], "0")
        self.assertEqual(aimo_mode.aimo_cli_args(None, -5)[aimo_mode.aimo_cli_args(None, -5).index("--brightness") + 1], "0")

    def test_preview_colors_kone_and_vulcan_counts(self):
        kone = aimo_mode.aimo_preview_colors("kone", 0, 255)
        self.assertEqual(len(kone), 11)
        vulcan = aimo_mode.aimo_preview_colors("vulcan", 0, 255)
        self.assertGreater(len(vulcan), 100)
        # Alle geclamped und nicht-negativ.
        for color in (*kone, *vulcan[:10]):
            for channel in color:
                self.assertGreaterEqual(channel, 0)
                self.assertLessEqual(channel, 255)

    def test_preview_brightness_scales(self):
        vulcan = aimo_mode.aimo_preview_colors("vulcan", 0, 128)
        full = aimo_mode.aimo_preview_colors("vulcan", 0, 255)
        self.assertEqual(len(vulcan), len(full))
        # Bei gedimmter Helligkeit dürfen nicht alle Kanäle voll ausgesteuert sein.
        self.assertTrue(any(ch < 255 for color in vulcan for ch in color))

    def test_available_skills_covers_documented_families(self):
        names = [s["name"] for s in aimo_mode.available_skills()]
        self.assertTrue({"gradient", "wave", "breathing", "colorcycle"}.issubset(names))


if __name__ == "__main__":
    unittest.main()