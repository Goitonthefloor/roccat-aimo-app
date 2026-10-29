"""Regression tests for software animation timing without HID hardware."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import aimo_effects


class EffectTimingTests(unittest.TestCase):
    def test_duration_limited_animation_uses_elapsed_time_for_phase(self):
        clock = [0.0]
        frames = []

        def send(_dev, colors, _brightness):
            frames.append(colors[0])
            clock[0] += 0.2  # Slow HID transfer in addition to the frame interval.

        def sleep(delay):
            clock[0] += delay

        with patch.object(aimo_effects.time, "monotonic", side_effect=lambda: clock[0]), \
             patch.object(aimo_effects.time, "sleep", side_effect=sleep):
            aimo_effects.run_effect(
                {"product_id": 0x2E27}, None, "colorcycle",
                {"hue": 0, "sat": 1, "val": 1}, period=1,
                duration=0.3, frame_interval=0.05, send=send,
            )
        self.assertEqual(frames, [(255, 0, 0), (128, 255, 0)])


if __name__ == "__main__":
    unittest.main()
