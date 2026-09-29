import importlib.util
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

MODULE_PATH = TOOLS / "validate_level_topology.py"
spec = importlib.util.spec_from_file_location("validate_level_topology", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def make_2x2(path: Path, *, mismatch=False, boundary_hole=False, dynamic=False) -> None:
    # Row-major 2x2. Outer boundary set, four internal edges clear.
    masks = [0x0A, 0x09, 0x06, 0x05]
    cells = []
    for mask in masks:
        cell = bytearray([0] * 0x15)
        cell[0x02] = mask
        cell[0x03:0x07] = b"\x9c\x9c\x9c\x9c"
        for off in (0x0D, 0x0F, 0x11, 0x13):
            struct.pack_into("<h", cell, off, -100)
        cells.append(cell)
    if mismatch:
        cells[0][0x02] |= 0x01  # cell0 E set, cell1 W clear
    if boundary_hole:
        cells[0][0x02] &= ~0x08  # remove top-row N barrier
    if dynamic:
        cells[0][0x01] |= 0x08  # mutable E state

    data = bytearray(struct.pack("<H", 2) + b"1.05\0" + struct.pack("<HH", 2, 2))
    for cell in cells:
        data += cell
    path.write_bytes(data)


def test_valid_static_topology(tmp_path: Path) -> None:
    p = tmp_path / "ok.SAV"
    make_2x2(p)
    out = mod.validate_path(p)
    assert out["valid_static_topology"] is True
    assert out["movement_model_complete"] is False
    assert out["errors"] == []
    assert out["static_edges"] == {"set": 0, "clear": 4, "mismatched": 0}


def test_reciprocity_failure_is_error(tmp_path: Path) -> None:
    p = tmp_path / "bad_edge.SAV"
    make_2x2(p, mismatch=True)
    out = mod.validate_path(p)
    assert out["valid_static_topology"] is False
    assert out["static_edges"]["mismatched"] == 1
    assert any(e["code"] == "STATIC_EDGE_RECIPROCITY" for e in out["errors"])


def test_boundary_hole_is_error(tmp_path: Path) -> None:
    p = tmp_path / "bad_boundary.SAV"
    make_2x2(p, boundary_hole=True)
    out = mod.validate_path(p)
    assert out["valid_static_topology"] is False
    assert any(e["code"] == "BOUNDARY_CLOSURE" and e["direction"] == "N" for e in out["errors"])


def test_mutable_state_is_reported_not_static_failure(tmp_path: Path) -> None:
    p = tmp_path / "dynamic.SAV"
    make_2x2(p, dynamic=True)
    out = mod.validate_path(p)
    assert out["valid_static_topology"] is True
    assert out["mutable_direction_bits"]["E"] == 1
    assert any(w["code"] == "MUTABLE_DIRECTION_STATE_PRESENT" for w in out["warnings"])
