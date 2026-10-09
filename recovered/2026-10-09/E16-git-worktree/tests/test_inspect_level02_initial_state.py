import importlib.util
import struct
from pathlib import Path

TOOL = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "inspect_level02_initial_state.py"
)
spec = importlib.util.spec_from_file_location("tool", TOOL)
tool = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(tool)


def make_level02_payload() -> bytes:
    rows, columns = 30, 27
    n = rows * columns
    cell02 = bytearray(n)
    cell00 = bytearray(n)

    # h144 source (6,2) S -> adjacent (7,2): reciprocal LOW+HIGH.
    cell02[6 * columns + 2] = 0x47
    cell02[7 * columns + 2] = 0x8F

    # h145 source (2,17) E -> adjacent (2,18): reciprocal LOW+HIGH.
    cell02[2 * columns + 17] = 0x1D
    cell02[2 * columns + 18] = 0x2F

    return (
        b"ON"
        + struct.pack("<HH", rows, columns)
        + bytes(cell02)
        + bytes(cell00)
        + b"\0\0"
    )


def test_level02_grid_and_handler_overlay():
    grid = tool.parse_maz_grid(make_level02_payload())
    assert (grid["rows"], grid["columns"], grid["cell_count"]) == (30, 27, 810)
    assert grid["handlers"][6 * 27 + 2] == 144
    assert grid["handlers"][2 * 27 + 17] == 145
    assert sum(h != 0 for h in grid["handlers"]) == 52


def test_level02_portal_markers_are_reciprocal():
    grid = tool.parse_maz_grid(make_level02_payload())
    for transition in tool.LEVEL2_TRANSITIONS:
        marker = tool.portal_marker(grid, transition)
        assert marker["reciprocal_low_high"]


def test_initializer_overwrite_order_is_preserved():
    grid = tool.parse_maz_grid(make_level02_payload())
    # The initializer first writes 150/151 to these cells, then replaces them.
    assert grid["handlers"][7 * 27 + 25] == 148
    assert grid["handlers"][8 * 27 + 25] == 149


def test_master_parser(tmp_path: Path):
    records = []
    for name, group in ((b"A.POJ", 1), (b"LEVEL02.MAZ", 2)):
        rec = bytearray(tool.MASTER_ENTRY_SIZE)
        rec[:len(name)] = name
        struct.pack_into("<H", rec, 18, group)
        records.append(rec)
    data = struct.pack("<H", 2) + b"".join(records) + b"\0\0\0\0"
    path = tmp_path / "MASTER"
    path.write_bytes(data)
    parsed = tool.parse_master(path)
    assert parsed["entry_count"] == 2
    assert parsed["records"][1]["name"] == "LEVEL02.MAZ"
    assert parsed["records"][1]["group_id"] == 2
