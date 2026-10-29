"""Regression for single custom RGB stops passed to software effects."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aimo_effects import kone_position, render_gradient, resolve_effect_params
from roccat_aimo_bridge import build_parser


def test_cli_gradient_accepts_single_custom_color_stop():
    args = build_parser().parse_args(["aimo-effect", "gradient", "255,0,0"])
    params = resolve_effect_params("gradient", args)
    assert render_gradient(0, params, kone_position, 11) == [(255, 0, 0)] * 11
