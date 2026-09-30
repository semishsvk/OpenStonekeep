import importlib.util
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

MODULE = TOOLS / "build_player_action_graph.py"
spec = importlib.util.spec_from_file_location("build_player_action_graph", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

ROWS = 3
COLS = 3
CENTER = 1 * COLS + 1


def _base_cell(row: int, column: int) -> bytearray:
    cell = bytearray([0] * 0x15)
    mask = 0
    if row == 0:
        mask |= 0x08
    if column == 0:
        mask |= 0x02
    if row == ROWS - 1:
        mask |= 0x04
    if column == COLS - 1:
        mask |= 0x01
    cell[0x02] = mask
    cell[0x03:0x07] = b"\x9c" * 4
    for off in (0x0D, 0x0F, 0x11, 0x13):
        struct.pack_into("<h", cell, off, -100)
    return cell


def make_save(
    path: Path,
    *,
    scripted: bool = False,
    static_north: bool = False,
    msp_north: bool = False,
    spatial_north: bool = False,
) -> None:
    cells = [_base_cell(r, c) for r in range(ROWS) for c in range(COLS)]

    if scripted:
        struct.pack_into("<h", cells[CENTER], 0x07, 42)

    if static_north:
        cells[CENTER][0x02] |= 0x08
        north = 0 * COLS + 1
        cells[north][0x02] |= 0x04

    msp_records = []
    if msp_north:
        record = bytearray([0] * 0x30)
        struct.pack_into("<h", record, 0x02, 1)
        struct.pack_into("<h", record, 0x10, -100)
        record[0x18] = 0x08
        msp_records.append(bytes(record))
        struct.pack_into("<h", cells[CENTER], 0x11, 0)

    data = bytearray()
    data += struct.pack("<H", 2)
    data += b"1.05\0"
    data += struct.pack("<HH", ROWS, COLS)
    for cell in cells:
        data += cell

    spatial = [bytearray(struct.pack("<6h", -1, -1, -1, 0, -1, -1))
               for _ in range(400)]
    heads = [-1] * (54 * 54)

    if spatial_north:
        # Facing N forward source veto includes category 0x26.
        spatial[0] = bytearray(
            struct.pack("<6h", 0, 1, 1, 0x26, -1, -1)
        )
        heads[1 * 54 + 1] = 0

    for record in spatial:
        data += record
    data += struct.pack("<h", -1)
    data += struct.pack("<2916h", *heads)
    data += struct.pack("<H", len(msp_records))
    for record in msp_records:
        data += record

    path.write_bytes(data)


def _center_fwd_north(result: dict) -> dict:
    for action in result["actions"]:
        if (
            action["source_cell"] == CENTER
            and action["facing"] == "N"
            and action["action"] == "FWD"
        ):
            return action
    raise AssertionError("center/N/FWD action missing")


def test_snapshot_clear(tmp_path: Path) -> None:
    path = tmp_path / "clear.SAV"
    make_save(path)
    result = mod.build(path, include_actions=True)
    action = _center_fwd_north(result)
    assert action["physical_snapshot_state"] == "SNAPSHOT_TRANSLATION_CLEAR"
    assert action["evidence_state"] == "SNAPSHOT_TRANSLATION_CLEAR"
    assert result["softlock_analysis_authorized"] is False


def test_static_blocker(tmp_path: Path) -> None:
    path = tmp_path / "static.SAV"
    make_save(path, static_north=True)
    action = _center_fwd_north(mod.build(path, include_actions=True))
    assert action["physical_snapshot_state"] == "STATIC_BLOCKED"


def test_msp_blocker(tmp_path: Path) -> None:
    path = tmp_path / "msp.SAV"
    make_save(path, msp_north=True)
    action = _center_fwd_north(mod.build(path, include_actions=True))
    assert action["physical_snapshot_state"] == "RUNTIME_MSP_BLOCKED"


def test_spatial_blocker(tmp_path: Path) -> None:
    path = tmp_path / "spatial.SAV"
    make_save(path, spatial_north=True)
    result = mod.build(path, include_actions=True)
    action = _center_fwd_north(result)
    assert action["physical_snapshot_state"] == "RUNTIME_SPATIAL_BLOCKED"
    assert result["serialized_runtime"]["active_spatial_records"] == 1
    assert result["serialized_runtime"]["spatial_category_counts"] == {0x26: 1}


def test_script_handler_has_evidence_precedence(tmp_path: Path) -> None:
    path = tmp_path / "scripted.SAV"
    make_save(path, static_north=True, scripted=True)
    action = _center_fwd_north(mod.build(path, include_actions=True))
    assert action["physical_snapshot_state"] == "STATIC_BLOCKED"
    assert action["source_handler"] == 42
    assert action["pre_action_id"] == 3
    assert action["evidence_state"] == "SCRIPTED_UNRESOLVED"


def test_spatial_coordinate_mismatch_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.SAV"
    make_save(path, spatial_north=True)
    data = bytearray(path.read_bytes())
    grid_end = 11 + ROWS * COLS * 0x15
    # record0 stores column at +2; corrupt it while grid head still says (1,1)
    struct.pack_into("<h", data, grid_end + 2, 2)
    path.write_bytes(data)
    try:
        mod.build(path)
    except ValueError as exc:
        assert "coordinates" in str(exc)
    else:
        raise AssertionError("corrupt spatial coordinates were accepted")
