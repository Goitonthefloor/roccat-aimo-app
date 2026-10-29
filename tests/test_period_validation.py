"""CLI period validation must happen before any device lookup."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import roccat_aimo_bridge as bridge


@pytest.mark.parametrize("effect,args", [
    ("breathing", ["255", "0", "0"]),
    ("colorcycle", []),
    ("wave", []),
])
@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "-inf", "1e999", "abc"])
def test_invalid_period_rejected_before_device_lookup(effect, args, value, capsys):
    with patch.object(bridge, "_pick_device") as pick:
        with pytest.raises(SystemExit) as exc:
            bridge.main(["aimo-effect", effect, *args, "--period=" + value])
    assert exc.value.code == 2
    assert "period must be a finite number greater than zero" in capsys.readouterr().err
    pick.assert_not_called()


@pytest.mark.parametrize("effect,args", [
    ("breathing", ["255", "0", "0"]),
    ("colorcycle", []),
    ("wave", []),
])
def test_positive_and_default_period_are_accepted(effect, args):
    parser = bridge.build_parser()
    assert parser.parse_args(["aimo-effect", effect, *args]).period == 2.0
    assert parser.parse_args(["aimo-effect", effect, *args, "--period", "0.125"]).period == 0.125
