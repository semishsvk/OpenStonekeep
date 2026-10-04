import importlib.util
from pathlib import Path

TOOL = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "inspect_h89_reciprocal_return.py"
)
spec = importlib.util.spec_from_file_location("tool", TOOL)
tool = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(tool)


def test_plus_turns_from_south_reach_north():
    facing = 2
    facing = tool.turn_new_facing(facing, 2)
    assert facing == 3
    facing = tool.turn_new_facing(facing, 2)
    assert facing == 0


def test_minus_turns_from_south_reach_north():
    facing = 2
    facing = tool.turn_new_facing(facing, -2)
    assert facing == 1
    facing = tool.turn_new_facing(facing, -2)
    assert facing == 0


def test_invalid_turn_argument_rejected():
    try:
        tool.turn_new_facing(2, 1)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_evidence_region_manifest_complete():
    assert set(tool.REGIONS) == {
        "h85_wrapper",
        "default_callback_core",
        "h415_action23_transition",
        "h415_common_turn_actions",
        "turn_input_branches",
        "turn_precheck",
        "turn_apply",
    }
