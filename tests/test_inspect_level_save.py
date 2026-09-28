import importlib.util
import struct
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "inspect_level_save.py"
spec = importlib.util.spec_from_file_location("inspect_level_save", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def make_save(path: Path) -> None:
    cell = bytearray([0] * 0x15)
    cell[0x00] = 0x10
    cell[0x02] = 0x04
    cell[0x03:0x07] = bytes([1, 2, 3, 4])
    struct.pack_into("<h", cell, 0x0D, 12)
    struct.pack_into("<h", cell, 0x0F, 7)
    struct.pack_into("<h", cell, 0x11, 3)
    struct.pack_into("<h", cell, 0x13, -100)

    data = bytearray()
    data += struct.pack("<H", 2)
    data += b"1.05\0"
    data += struct.pack("<HH", 1, 1)
    data += cell
    data += b"tail"
    path.write_bytes(data)


def test_parse_minimal_level_save(tmp_path: Path) -> None:
    save = tmp_path / "LEVELXX.SAV"
    make_save(save)

    info = mod.parse(save)

    assert info["format_marker"] == 2
    assert info["version_ascii"] == "1.05"
    assert info["width"] == 1
    assert info["height"] == 1
    assert info["cell_count"] == 1
    assert info["cell_size"] == 0x15
    assert info["grid_start"] == 0x0B
    assert info["grid_end"] == 0x20
    assert info["post_grid_bytes"] == 4

    assert info["chain_heads"]["0x0D"]["min_active_head"] == 12
    assert info["chain_heads"]["0x0F"]["semantic_class"] == "monster"
    assert info["chain_heads"]["0x0F"]["min_active_head"] == 7
    assert info["chain_heads"]["0x11"]["min_active_head"] == 3
    assert info["chain_heads"]["0x13"]["active_cells"] == 0


def test_rejects_truncated_grid(tmp_path: Path) -> None:
    save = tmp_path / "broken.SAV"
    save.write_bytes(struct.pack("<H", 2) + b"1.05\0" + struct.pack("<HH", 2, 2))

    try:
        mod.parse(save)
    except ValueError as exc:
        assert "truncated grid" in str(exc)
    else:
        raise AssertionError("truncated grid was accepted")
