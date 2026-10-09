import importlib.util
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "build_three_level_state_graph.py"
spec = importlib.util.spec_from_file_location("e16", TOOL)
e16 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(e16)


def tiny_level():
    cells = []
    for _ in range(4):
        c = bytearray(0x15)
        cells.append(bytes(c))
    return {
        "rows": 2,
        "cols": 2,
        "cells": cells,
        "masks": [0, 0, 0, 0],
        "spatial": {(0, 0): (), (0, 1): (), (1, 0): (), (1, 1): ()},
        "spatial_exact": True,
    }


def test_scc_two_components():
    nodes = [("a",), ("b",), ("c",)]
    adj = {
        ("a",): {("b",)},
        ("b",): {("a",)},
        ("c",): set(),
    }
    comps = e16.strongly_connected_components(nodes, adj)
    assert sorted(sorted(x) for x in comps) == [[("a",), ("b",)], [("c",)]]


def test_static_only_move_respects_reciprocal_low_bits():
    level = tiny_level()
    assert e16.static_only_move(level, 0, 0, 3, "FWD") == (0, 1, 3)

    cells = list(level["cells"])
    c = bytearray(cells[0])
    c[0x02] |= 0x01
    cells[0] = bytes(c)
    level["cells"] = cells
    assert e16.static_only_move(level, 0, 0, 3, "FWD") is None


def test_turn_precheck_uses_opposite_new_facing_msp_bit():
    level = tiny_level()
    # prospective facing N=0 checks opposite(S) LOW=0x04.
    level["masks"][0] = 0x04
    ok, reason = e16.turn_physical(level, 0, 0, 0)
    assert not ok
    assert reason == "MSP_BLOCKED"

    level["masks"][0] = 0
    ok, reason = e16.turn_physical(level, 0, 0, 0)
    assert ok
    assert reason == "CLEAR"


def test_level2_allocator_type_coverage_and_return_macros():
    assert set(e16.LEVEL2_TYPE_PREZERO_MODE) == {
        2, 3, 4, 5, 9, 10, 12, 13, 14, 15, 16,
        20, 21, 22, 23, 34, 57, 94, 99, 106, 111,
    }
    assert len(e16.RETURN_MACROS) == 6
    assert {x[2] for x in e16.RETURN_MACROS} == {87, 88, 89, 90, 106, 107}
