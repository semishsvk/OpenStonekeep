import importlib.util
from pathlib import Path

TOOL = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "inspect_portal_state_producers.py"
)
spec = importlib.util.spec_from_file_location("tool", TOOL)
tool = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(tool)


def test_selector4_producer_toggle():
    assert tool.producer_next_selector4(0) == 1
    assert tool.producer_next_selector4(-1) == 1
    assert tool.producer_next_selector4(1) == -1


def test_action15_gate_semantics():
    assert not tool.action15_allows(87, 0)
    assert tool.action15_allows(87, 1)
    assert tool.action15_allows(87, -1)

    for handler in (106, 107):
        assert not tool.action15_allows(handler, -1)
        assert tool.action15_allows(handler, 1)


def test_alternate_gate_payload_range():
    assert not tool.alternate_gate_possible(0)
    assert tool.alternate_gate_possible(166)
    assert tool.alternate_gate_possible(0x99)
    assert tool.alternate_gate_possible(0xAE)
    assert not tool.alternate_gate_possible(0xAF)


def test_manifest_initial_states():
    assert tool.PORTALS[87]["initial_selector4"] == 0
    assert tool.PORTALS[87]["selector5_payload"] == 0
    assert tool.PORTALS[106]["initial_selector4"] == -1
    assert tool.PORTALS[106]["selector5_payload"] == 166
    assert tool.PORTALS[107]["initial_selector4"] == -1
    assert tool.PORTALS[107]["selector5_payload"] == 166
