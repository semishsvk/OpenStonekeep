import importlib.util
import struct
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "inspect_level_save.py"
spec = importlib.util.spec_from_file_location("inspect_level_save", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def make_single_cell_save(path: Path) -> None:
    cell = bytearray([0] * 0x15)
    cell[0x00] = 0x10
    cell[0x02] = 0x0F  # all four static edge bits present on a 1x1 boundary
    cell[0x03:0x07] = bytes([1, 2, 3, 4])
    struct.pack_into("<h", cell, 0x07, 42)
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


def make_2x2_reciprocal_save(path: Path) -> None:
    # Row-major cells. Only the outer boundary has static edge bits set;
    # all four internal undirected adjacencies are clear on both sides.
    masks = [0x0A, 0x09, 0x06, 0x05]
    cells = []
    for i, mask in enumerate(masks):
        cell = bytearray([0] * 0x15)
        cell[0x02] = mask
        cell[0x03:0x07] = bytes([10 + i, 20 + i, 30 + i, 40 + i])
        for off in (0x0D, 0x0F, 0x11, 0x13):
            struct.pack_into("<h", cell, off, -100)
        cells.append(cell)

    data = bytearray()
    data += struct.pack("<H", 2)
    data += b"1.05\0"
    data += struct.pack("<HH", 2, 2)
    for cell in cells:
        data += cell
    path.write_bytes(data)


def test_parse_minimal_level_save(tmp_path: Path) -> None:
    save = tmp_path / "LEVELXX.SAV"
    make_single_cell_save(save)

    info = mod.parse(save)

    assert info["format_marker"] == 2
    assert info["version_ascii"] == "1.05"
    assert info["width"] == 1
    assert info["height"] == 1
    assert info["row_count"] == 1
    assert info["column_count"] == 1
    assert info["cell_count"] == 1
    assert info["cell_size"] == 0x15
    assert info["grid_start"] == 0x0B
    assert info["grid_end"] == 0x20
    assert info["post_grid_bytes"] == 4

    assert info["event_handler"]["semantic_class"] == "per_cell_action_event_handler"
    assert info["event_handler"]["default_index"] == 0
    assert info["event_handler"]["non_default_cells"] == 1
    assert info["event_handler"]["unique_indices"] == 1
    assert info["event_handler"]["min_index"] == 42
    assert info["event_handler"]["max_index"] == 42
    assert info["event_handler"]["counts"] == {"42": 1}

    assert info["chain_heads"]["0x0D"]["semantic_class"] == "poj_object"
    assert info["chain_heads"]["0x0D"]["min_active_head"] == 12
    assert info["chain_heads"]["0x0F"]["semantic_class"] == "monster"
    assert info["chain_heads"]["0x0F"]["min_active_head"] == 7
    assert info["chain_heads"]["0x11"]["semantic_class"] == "msp_maze_prop"
    assert info["chain_heads"]["0x11"]["min_active_head"] == 3
    assert info["chain_heads"]["0x13"]["semantic_class"] is None
    assert info["chain_heads"]["0x13"]["active_cells"] == 0

    topo = info["topology"]
    assert topo["direction_order"] == ["N", "W", "S", "E"]
    assert topo["directions"]["N"]["static_mask"] == 0x08
    assert topo["directions"]["W"]["static_mask"] == 0x02
    assert topo["directions"]["S"]["static_mask"] == 0x04
    assert topo["directions"]["E"]["static_mask"] == 0x01
    assert topo["directions"]["N"]["dynamic_mask"] == 0x01
    assert topo["directions"]["W"]["dynamic_mask"] == 0x02
    assert topo["directions"]["S"]["dynamic_mask"] == 0x04
    assert topo["directions"]["E"]["dynamic_mask"] == 0x08
    assert topo["all_static_edges_reciprocal"] is True


def test_static_edge_reciprocity_and_boundary(tmp_path: Path) -> None:
    save = tmp_path / "LEVEL2X2.SAV"
    make_2x2_reciprocal_save(save)
    info = mod.parse(save)
    topo = info["topology"]

    assert info["row_count"] == 2
    assert info["column_count"] == 2
    assert topo["all_static_edges_reciprocal"] is True
    assert topo["undirected_static_edge_mismatches"] == 0
    assert topo["undirected_static_edges_clear"] == 4
    assert topo["undirected_static_edges_set"] == 0
    for name in ("N", "W", "S", "E"):
        d = topo["directions"][name]
        assert d["reciprocity_mismatches"] == 0
        assert d["boundary_static_bits_set"] == d["boundary_cells"]


def test_detects_static_edge_mismatch(tmp_path: Path) -> None:
    save = tmp_path / "LEVELBAD.SAV"
    make_2x2_reciprocal_save(save)
    data = bytearray(save.read_bytes())
    # Cell 0 E side becomes set while cell 1 W remains clear.
    data[0x0B + 0x02] |= 0x01
    save.write_bytes(data)

    topo = mod.parse(save)["topology"]
    assert topo["all_static_edges_reciprocal"] is False
    assert topo["undirected_static_edge_mismatches"] == 1
    assert topo["directions"]["E"]["reciprocity_mismatches"] == 1
    assert topo["directions"]["W"]["reciprocity_mismatches"] == 1


def test_rejects_truncated_grid(tmp_path: Path) -> None:
    save = tmp_path / "broken.SAV"
    save.write_bytes(struct.pack("<H", 2) + b"1.05\0" + struct.pack("<HH", 2, 2))

    try:
        mod.parse(save)
    except ValueError as exc:
        assert "truncated grid" in str(exc)
    else:
        raise AssertionError("truncated grid was accepted")
