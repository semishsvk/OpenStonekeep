import importlib.util
from pathlib import Path

TOOL = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "build_conditional_portal_graph.py"
)
spec = importlib.util.spec_from_file_location("tool", TOOL)
tool = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(tool)


def clear_physical(*_args, **_kwargs):
    return {
        "direction": "S",
        "destination": [3, 3],
        "source_msp_mask": 0,
        "destination_msp_mask": 0,
        "source_spatial_categories": [],
        "destination_spatial_categories": [],
        "msp_blocked_after_low_clear": False,
        "spatial_blocked_after_low_clear": False,
        "physical_clear_after_low_clear": True,
        "validation_errors": [],
    }


def test_direct_and_producer_conditional_composition(monkeypatch):
    monkeypatch.setattr(
        tool,
        "TRANSITIONS",
        [
            (1, 88, 2, 25, 2, 15, 3, 25, 0, 0x5E868),
            (1, 106, 11, 5, 0, 2, 7, 2, 0, 0x5F027),
        ],
    )
    monkeypatch.setattr(
        tool,
        "inspect_portal_enable",
        lambda *_args: {
            "pass": True,
            "portal_markers": [
                {
                    "source_level": 1,
                    "handler_id": 88,
                    "serialized_action15_allow": True,
                },
                {
                    "source_level": 1,
                    "handler_id": 106,
                    "serialized_action15_allow": False,
                },
            ],
        },
    )
    monkeypatch.setattr(
        tool,
        "inspect_producers",
        lambda *_args: {
            "pass": True,
            "portals": [
                {
                    "handler_id": 106,
                    "action15_after_success_allow": True,
                }
            ],
        },
    )
    monkeypatch.setattr(tool, "physical_after_low_clear", clear_physical)

    out = tool.build(Path("SK.EXE"), Path("L1"), Path("L1A"))
    assert out["pass"]
    assert out["counts"]["direct_enable"] == 1
    assert out["counts"]["producer_conditional"] == 1
    assert out["counts"]["physical_clear_after_open"] == 2
    assert out["counts"]["transition_commit_reached_after_required_enable"] == 2


def test_missing_producer_fails(monkeypatch):
    monkeypatch.setattr(
        tool,
        "TRANSITIONS",
        [(1, 106, 11, 5, 0, 2, 7, 2, 0, 0x5F027)],
    )
    monkeypatch.setattr(
        tool,
        "inspect_portal_enable",
        lambda *_args: {
            "pass": True,
            "portal_markers": [{
                "source_level": 1,
                "handler_id": 106,
                "serialized_action15_allow": False,
            }],
        },
    )
    monkeypatch.setattr(
        tool,
        "inspect_producers",
        lambda *_args: {"pass": True, "portals": []},
    )
    monkeypatch.setattr(tool, "physical_after_low_clear", clear_physical)

    out = tool.build(Path("SK.EXE"), Path("L1"), Path("L1A"))
    assert not out["pass"]
    assert any("missing E.10 producer" in e for e in out["errors"])


def test_post_open_physical_block_fails_closed(monkeypatch):
    monkeypatch.setattr(
        tool,
        "TRANSITIONS",
        [(15, 411, 2, 3, 2, 1, 3, 3, 0, 0x4F8FC)],
    )
    monkeypatch.setattr(
        tool,
        "inspect_portal_enable",
        lambda *_args: {
            "pass": True,
            "portal_markers": [{
                "source_level": 15,
                "handler_id": 411,
                "serialized_action15_allow": True,
            }],
        },
    )
    monkeypatch.setattr(
        tool,
        "inspect_producers",
        lambda *_args: {"pass": True, "portals": []},
    )

    blocked = clear_physical()
    blocked["msp_blocked_after_low_clear"] = True
    blocked["physical_clear_after_low_clear"] = False
    monkeypatch.setattr(
        tool, "physical_after_low_clear", lambda *_args, **_kwargs: blocked
    )

    out = tool.build(Path("SK.EXE"), Path("L1"), Path("L1A"))
    assert not out["pass"]
    assert out["counts"]["physical_blocked_after_open"] == 1
