import importlib.util
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

MODULE = TOOLS / "classify_level_cells.py"
spec = importlib.util.spec_from_file_location("classify_level_cells", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def make_2x2(
    path: Path,
    *,
    flags: list[int],
    masks: list[int],
    high_without_low: bool = False,
) -> None:
    data = bytearray(struct.pack("<H", 2) + b"1.05\0" + struct.pack("<HH", 2, 2))
    for i in range(4):
        cell = bytearray([0] * 0x15)
        cell[0x00] = flags[i]
        cell[0x02] = masks[i]
        cell[0x03:0x07] = b"\x9c\x9c\x9c\x9c"
        if high_without_low and i == 0:
            cell[0x02] |= 0x10  # E high subtype; E low 0x01 remains clear
        for off in (0x0D, 0x0F, 0x11, 0x13):
            struct.pack_into("<h", cell, off, -100)
        data += cell
    path.write_bytes(data)


def test_bit10_cross_boundary_is_sealed(tmp_path: Path) -> None:
    p = tmp_path / "sealed.SAV"
    # Left cells !0x10, right cells 0x10. E/W crossing is sealed.
    make_2x2(
        p,
        flags=[0, 0x10, 0, 0x10],
        masks=[0x0B, 0x0B, 0x07, 0x07],
    )
    out = mod.classify(p)
    assert out["bit_0x10_partition_boundary"]["cross_edges"] == 2
    assert out["bit_0x10_partition_boundary"]["reciprocal_static_barriers"] == 2
    assert out["bit_0x10_partition_boundary"]["violations"] == 0


def test_open_bit10_cross_edge_is_violation(tmp_path: Path) -> None:
    p = tmp_path / "open.SAV"
    make_2x2(
        p,
        flags=[0, 0x10, 0, 0x10],
        masks=[0x0A, 0x09, 0x06, 0x05],
    )
    out = mod.classify(p)
    assert out["bit_0x10_partition_boundary"]["cross_edges"] == 2
    assert out["bit_0x10_partition_boundary"]["violations"] == 2


def test_bit80_is_separate_from_bit10(tmp_path: Path) -> None:
    p = tmp_path / "runtime.SAV"
    make_2x2(
        p,
        flags=[0x80, 0, 0, 0],
        masks=[0x0A, 0x09, 0x06, 0x05],
    )
    out = mod.classify(p)
    assert out["cell0"]["bit_0x80_runtime_actor_clearance_blocker"] == 1
    assert out["cell0"]["bit_0x10_static_actor_clearance_region_gate"] == 0


def test_high_subtype_without_low_is_reported_not_named(tmp_path: Path) -> None:
    p = tmp_path / "high.SAV"
    make_2x2(
        p,
        flags=[0, 0, 0, 0],
        masks=[0x0A, 0x09, 0x06, 0x05],
        high_without_low=True,
    )
    out = mod.classify(p)
    high = out["cell2_high_directional_blocker"]
    assert high["high_without_matching_low"] == 1
    assert high["exact_subtype_semantics_proven"] is False
    assert out["player_movement_model_complete"] is False
    assert out["softlock_analysis_authorized"] is False
