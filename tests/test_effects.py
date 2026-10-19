import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import roccat_rgb as rgb
import roccat_input as inputs


class EffectTests(unittest.TestCase):
    def frame(self, name, frame=0, **kwargs):
        return rgb.effect_colors(name, 255, 80, 40, 200, frame, 144, **kwargs)

    def test_all_effects_respect_brightness_and_count(self):
        for effect in rgb.EFFECTS:
            for frame in (0, 1, 37, 1234):
                colors = self.frame(effect, frame)
                self.assertEqual(len(colors), 144)
                self.assertTrue(all(0 <= c <= 200 for color in colors for c in color))

    def test_flow_moves_and_reverses(self):
        self.assertNotEqual(self.frame("rainbow-flow"), self.frame("rainbow-flow", 12))
        self.assertEqual(self.frame("rainbow-flow", 12, reverse=True), self.frame("rainbow-flow", 84))

    def test_cycle_is_uniform_and_wave_is_spatial(self):
        self.assertEqual(len(set(self.frame("cycle"))), 1)
        self.assertGreater(len(set(self.frame("wave"))), 1)

    def test_beat_tempo_and_speed(self):
        self.assertEqual(self.frame("beat", 0), self.frame("beat", 6, bpm=120))
        self.assertEqual(self.frame("beat", 0), self.frame("beat", 3, bpm=120, speed=2))
        self.assertNotEqual(self.frame("beat", 0), self.frame("beat", 3, bpm=120))

    def test_push_starts_dark_lights_on_press_and_fades(self):
        self.assertEqual(self.frame("reactive"), [(0, 0, 0)] * 144)
        peak = self.frame("reactive", 12, last_press=12)
        fading = self.frame("reactive", 18, last_press=12)
        self.assertGreater(peak[0][0], fading[0][0])
        self.assertGreater(fading[0][0], 0)
        self.assertEqual(self.frame("reactive", 24, last_press=12), [(0, 0, 0)] * 144)

    def test_input_ignores_release_repeat_and_sync(self):
        event = lambda kind, value: inputs.EVENT.pack(0, 0, kind, 30, value)
        for data in (event(1, 0), event(1, 2), event(0, 1)):
            self.assertFalse(inputs.is_key_press(data))
        self.assertTrue(inputs.is_key_press(event(0, 0) + event(1, 1)))

    def test_reader_drains_and_closes(self):
        reader = inputs.KeyPressReader.__new__(inputs.KeyPressReader)
        reader.fds = [42]
        with mock.patch.object(inputs.os, "read", side_effect=[inputs.EVENT.pack(0, 0, 1, 30, 1), BlockingIOError]):
            self.assertTrue(reader.pressed())
        with mock.patch.object(inputs.os, "close") as close:
            reader.close()
            close.assert_called_once_with(42)
        self.assertEqual(reader.fds, [])
