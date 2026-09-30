#!/usr/bin/env python3
"""Inspect Stonekeep per-level SAV files without mutating source data.

Evidence-backed layout:
  u16 format_marker
  char version[5]
  u16 row_count
  u16 column_count
  row_count*column_count records of 21 bytes

K291-D direction model:
  direction 0 = N
  direction 1 = W
  direction 2 = S
  direction 3 = E

Cell fields used here:
  +0x01  mutable directional bitfield (N=0x01, W=0x02, S=0x04, E=0x08)
  +0x02  static directional edge/barrier mask (N=0x08, W=0x02, S=0x04, E=0x01)
  +0x03..+0x06 direction-indexed byte tuple in N,W,S,E order
  +0x07  signed per-cell action/event handler index
  +0x0D  POJ/object-instance chain head
  +0x0F  monster-instance chain head
  +0x11  MSP/maze-prop instance chain head
  +0x13  typed 0x66-pool chain head; semantic umbrella remains open

The static edge mask is evidence-backed but is not, by itself, a complete
player-walkability model. Dynamic edge state and runtime objects must be
considered by later connectivity/movement work.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

CELL_SIZE = 0x15
SENTINEL_NONE = -100  # 0xFF9C

# (name, delta_row, delta_column, static_mask@+0x02, dynamic_mask@+0x01, opposite)
DIRECTIONS = (
    ("N", -1, 0, 0x08, 0x01, "S"),
    ("W", 0, -1, 0x02, 0x02, "E"),
    ("S", 1, 0, 0x04, 0x04, "N"),
    ("E", 0, 1, 0x01, 0x08, "W"),
)
DIRECTION_BY_NAME = {d[0]: d for d in DIRECTIONS}

CHAIN_HEADS = {
    0x0D: {"runtime_stride": 0x2F, "next_offset": 0x18, "semantic_class": "poj_object"},
    0x0F: {"runtime_stride": 0x111, "next_offset": 0x3A, "semantic_class": "monster"},
    0x11: {"runtime_stride": 0x30, "next_offset": 0x10, "semantic_class": "msp_maze_prop"},
    0x13: {"runtime_stride": 0x66, "next_offset": 0x63, "semantic_class": None},
}


def s16(buf: bytes, off: int) -> int:
    return struct.unpack_from("<h", buf, off)[0]


def _cell_index(row: int, column: int, columns: int) -> int:
    return row * columns + column


def _topology_summary(cells: list[bytes], rows: int, columns: int) -> dict:
    directions: dict[str, dict] = {}
    for name, dr, dc, mask, dynamic_mask, opposite_name in DIRECTIONS:
        opposite_mask = DIRECTION_BY_NAME[opposite_name][3]
        internal = reciprocal = mismatches = both_set = both_clear = 0
        dynamic_set = 0
        tuple_non_default = 0
        direction_index = [d[0] for d in DIRECTIONS].index(name)

        for row in range(rows):
            for column in range(columns):
                cell = cells[_cell_index(row, column, columns)]
                if cell[0x01] & dynamic_mask:
                    dynamic_set += 1
                if cell[0x03 + direction_index] != 0x9C:
                    tuple_non_default += 1

                nr, nc = row + dr, column + dc
                if not (0 <= nr < rows and 0 <= nc < columns):
                    continue
                other = cells[_cell_index(nr, nc, columns)]
                a = bool(cell[0x02] & mask)
                b = bool(other[0x02] & opposite_mask)
                internal += 1
                if a == b:
                    reciprocal += 1
                else:
                    mismatches += 1
                if a and b:
                    both_set += 1
                if not a and not b:
                    both_clear += 1

        # Boundary cells for this direction.
        if name == "N":
            boundary = [cells[_cell_index(0, c, columns)] for c in range(columns)]
        elif name == "S":
            boundary = [cells[_cell_index(rows - 1, c, columns)] for c in range(columns)]
        elif name == "W":
            boundary = [cells[_cell_index(r, 0, columns)] for r in range(rows)]
        else:  # E
            boundary = [cells[_cell_index(r, columns - 1, columns)] for r in range(rows)]

        boundary_set = sum(bool(cell[0x02] & mask) for cell in boundary)
        directions[name] = {
            "direction_index": direction_index,
            "delta_row": dr,
            "delta_column": dc,
            "static_mask": mask,
            "dynamic_mask": dynamic_mask,
            "opposite": opposite_name,
            "internal_adjacencies": internal,
            "reciprocal_adjacencies": reciprocal,
            "reciprocity_mismatches": mismatches,
            "both_static_bits_set": both_set,
            "both_static_bits_clear": both_clear,
            "boundary_cells": len(boundary),
            "boundary_static_bits_set": boundary_set,
            "dynamic_bits_set": dynamic_set,
            "tuple_non_default_0x9c": tuple_non_default,
        }

    # Count each undirected adjacency once via S and E.
    static_set_edges = static_clear_edges = static_mismatch_edges = 0
    for row in range(rows):
        for column in range(columns):
            cell = cells[_cell_index(row, column, columns)]
            for name in ("S", "E"):
                _, dr, dc, mask, _, opposite_name = DIRECTION_BY_NAME[name]
                nr, nc = row + dr, column + dc
                if not (0 <= nr < rows and 0 <= nc < columns):
                    continue
                other = cells[_cell_index(nr, nc, columns)]
                opposite_mask = DIRECTION_BY_NAME[opposite_name][3]
                a = bool(cell[0x02] & mask)
                b = bool(other[0x02] & opposite_mask)
                if a != b:
                    static_mismatch_edges += 1
                elif a:
                    static_set_edges += 1
                else:
                    static_clear_edges += 1

    return {
        "direction_order": [d[0] for d in DIRECTIONS],
        "directions": directions,
        "undirected_static_edges_set": static_set_edges,
        "undirected_static_edges_clear": static_clear_edges,
        "undirected_static_edge_mismatches": static_mismatch_edges,
        "all_static_edges_reciprocal": static_mismatch_edges == 0,
    }


def parse(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 11:
        raise ValueError("file too small for level-save header")

    marker = struct.unpack_from("<H", data, 0)[0]
    version_raw = data[2:7]
    row_count, column_count = struct.unpack_from("<HH", data, 7)
    cell_count = row_count * column_count
    grid_start = 11
    grid_end = grid_start + cell_count * CELL_SIZE
    if grid_end > len(data):
        raise ValueError(
            f"truncated grid: need {grid_end} bytes, have {len(data)}"
        )

    grid = data[grid_start:grid_end]
    cells = [
        grid[i * CELL_SIZE:(i + 1) * CELL_SIZE]
        for i in range(cell_count)
    ]

    handler_values = [s16(cell, 0x07) for cell in cells]
    handler_non_default = [value for value in handler_values if value != 0]
    handler_counts = {}
    for value in handler_values:
        handler_counts[str(value)] = handler_counts.get(str(value), 0) + 1

    chains = {}
    for off, meta in CHAIN_HEADS.items():
        values = [s16(cell, off) for cell in cells]
        active = [v for v in values if v not in (SENTINEL_NONE, -1)]
        chains[f"0x{off:02X}"] = {
            **meta,
            "sentinel": SENTINEL_NONE,
            "active_cells": len(active),
            "unique_active_heads": len(set(active)),
            "min_active_head": min(active) if active else None,
            "max_active_head": max(active) if active else None,
        }

    return {
        "path": str(path),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "format_marker": marker,
        "version_raw_hex": version_raw.hex(),
        "version_ascii": version_raw.rstrip(b"\0").decode("ascii", "replace"),
        # Compatibility aliases retained from the earlier inspector. K291-D
        # establishes that the first serialized dimension is rows and the
        # second is columns for runtime row-major addressing.
        "width": row_count,
        "height": column_count,
        "row_count": row_count,
        "column_count": column_count,
        "cell_count": cell_count,
        "cell_size": CELL_SIZE,
        "grid_start": grid_start,
        "grid_end": grid_end,
        "post_grid_bytes": len(data) - grid_end,
        "event_handler": {
            "cell_offset": 0x07,
            "default_index": 0,
            "non_default_cells": len(handler_non_default),
            "unique_indices": len(set(handler_values)),
            "min_index": min(handler_values) if handler_values else None,
            "max_index": max(handler_values) if handler_values else None,
            "counts": handler_counts,
            "semantic_class": "per_cell_action_event_handler",
        },
        "chain_heads": chains,
        "topology": _topology_summary(cells, row_count, column_count),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("save", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    info = parse(args.save)

    if args.json:
        print(json.dumps(info, indent=2, sort_keys=True))
        return 0

    print(
        f"{info['path']}: rows={info['row_count']} columns={info['column_count']} "
        f"= {info['cell_count']} cells"
    )
    print(
        f"marker={info['format_marker']} version={info['version_ascii']} "
        f"cell_size={info['cell_size']}"
    )
    print(
        f"grid=[0x{info['grid_start']:X},0x{info['grid_end']:X}) "
        f"sha256={info['sha256']}"
    )
    topo = info["topology"]
    print(
        "directions=" + ",".join(topo["direction_order"]) + " "
        f"static_edge_reciprocal={topo['all_static_edges_reciprocal']} "
        f"set_edges={topo['undirected_static_edges_set']} "
        f"clear_edges={topo['undirected_static_edges_clear']} "
        f"mismatches={topo['undirected_static_edge_mismatches']}"
    )
    for name in topo["direction_order"]:
        d = topo["directions"][name]
        print(
            f"dir {name}: static=0x{d['static_mask']:02X} "
            f"dynamic=0x{d['dynamic_mask']:02X} "
            f"delta=({d['delta_row']:+d},{d['delta_column']:+d}) "
            f"boundary={d['boundary_static_bits_set']}/{d['boundary_cells']}"
        )
    event = info["event_handler"]
    print(
        f"cell+0x07 event_handler: default={event['default_index']} "
        f"non_default={event['non_default_cells']} "
        f"unique={event['unique_indices']} "
        f"range={event['min_index']}..{event['max_index']}"
    )
    for off, chain in info["chain_heads"].items():
        semantic = chain["semantic_class"] or "unknown"
        print(
            f"head {off}: class={semantic} stride=0x{chain['runtime_stride']:X} "
            f"next=0x{chain['next_offset']:X} "
            f"active={chain['active_cells']} "
            f"range={chain['min_active_head']}..{chain['max_active_head']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
