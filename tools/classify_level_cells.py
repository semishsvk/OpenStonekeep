#!/usr/bin/env python3
"""Classify evidence-backed Stonekeep cell-region and actor-clearance layers.

STONE-K292-B deliberately exposes orthogonal evidence layers instead of
collapsing them into a guessed player-walkability rule.

Executable evidence:
- cell+0x00 bit 0x10 is used as a static actor-clearance/region gate and
  excludes interior cells from BMAP bit-0x01 initialization.
- cell+0x00 bit 0x80 is runtime-mutable and participates in the same
  monster-direction clearance gate.
- cell+0x02 high directional bits are tested together with the already
  verified low static-edge bits, but their exact gameplay subtype is OPEN.

This tool therefore does NOT label cells as floor/void/player-walkable and
does NOT perform softlock analysis.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from inspect_level_save import CELL_SIZE, parse

HIGH_MASKS = {
    "N": 0x80,
    "W": 0x20,
    "S": 0x40,
    "E": 0x10,
}


def _cells(path: Path, info: dict) -> list[bytes]:
    data = path.read_bytes()
    grid = data[info["grid_start"]:info["grid_end"]]
    return [
        grid[i * CELL_SIZE:(i + 1) * CELL_SIZE]
        for i in range(info["cell_count"])
    ]


def _components(nodes: set[int], rows: int, columns: int) -> list[int]:
    seen: set[int] = set()
    sizes: list[int] = []
    for start in nodes:
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        size = 0
        while stack:
            node = stack.pop()
            size += 1
            row, column = divmod(node, columns)
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = row + dr, column + dc
                if not (0 <= nr < rows and 0 <= nc < columns):
                    continue
                other = nr * columns + nc
                if other in nodes and other not in seen:
                    seen.add(other)
                    stack.append(other)
        sizes.append(size)
    return sorted(sizes, reverse=True)


def classify(path: Path) -> dict:
    info = parse(path)
    cells = _cells(path, info)
    rows = info["row_count"]
    columns = info["column_count"]
    directions = info["topology"]["directions"]

    bit01 = {i for i, cell in enumerate(cells) if cell[0x00] & 0x01}
    bit10 = {i for i, cell in enumerate(cells) if cell[0x00] & 0x10}
    bit80 = {i for i, cell in enumerate(cells) if cell[0x00] & 0x80}

    interior = {
        row * columns + column
        for row in range(1, rows - 1)
        for column in range(1, columns - 1)
    }
    static_actor_region = {i for i in interior if i not in bit10}

    # K292-B corpus invariant: every undirected adjacency that crosses the
    # cell0 bit-0x10 partition is sealed by the verified reciprocal low
    # static-edge bit. Count S/E only so every edge is visited once.
    cross_edges = sealed_cross_edges = cross_violations = 0
    for row in range(rows):
        for column in range(columns):
            i = row * columns + column
            for name in ("S", "E"):
                d = directions[name]
                nr = row + d["delta_row"]
                nc = column + d["delta_column"]
                if not (0 <= nr < rows and 0 <= nc < columns):
                    continue
                j = nr * columns + nc
                if bool(cells[i][0x00] & 0x10) == bool(cells[j][0x00] & 0x10):
                    continue

                opposite = directions[d["opposite"]]
                a = bool(cells[i][0x02] & d["static_mask"])
                b = bool(cells[j][0x02] & opposite["static_mask"])
                cross_edges += 1
                if a and b:
                    sealed_cross_edges += 1
                else:
                    cross_violations += 1

    # High directional bits are a second blocker/subtype layer used by the
    # executable together with low bits. K292-B proves only whether every
    # observed high bit is accompanied by its corresponding low static bit.
    high_seen = high_without_matching_low = 0
    high_by_direction: dict[str, int] = {}
    for name in info["topology"]["direction_order"]:
        low = directions[name]["static_mask"]
        high = HIGH_MASKS[name]
        count = 0
        for cell in cells:
            if cell[0x02] & high:
                count += 1
                high_seen += 1
                if not (cell[0x02] & low):
                    high_without_matching_low += 1
        high_by_direction[name] = count

    init_already = sum(i in bit01 for i in static_actor_region)

    return {
        "path": info["path"],
        "sha256": info["sha256"],
        "row_count": rows,
        "column_count": columns,
        "cell_count": info["cell_count"],
        "cell0": {
            "bit_0x01_bmap_linked": len(bit01),
            "bit_0x10_static_actor_clearance_region_gate": len(bit10),
            "bit_0x80_runtime_actor_clearance_blocker": len(bit80),
        },
        "static_actor_region": {
            "definition": "interior && !(cell+0x00 & 0x10)",
            "count": len(static_actor_region),
            "geometric_component_sizes": _components(
                static_actor_region, rows, columns
            ),
            "player_walkability_proven": False,
        },
        "bit_0x10_partition_boundary": {
            "cross_edges": cross_edges,
            "reciprocal_static_barriers": sealed_cross_edges,
            "violations": cross_violations,
            "all_cross_edges_sealed": cross_violations == 0,
        },
        "bmap_initialization_model": {
            "rule": "interior && !(cell0 & 0x10) => cell0 |= 0x01",
            "targets": len(static_actor_region),
            "already_set_0x01": init_already,
            "would_set_0x01": len(static_actor_region) - init_already,
            "bit_0x01_exact_semantics_proven": False,
        },
        "cell2_high_directional_blocker": {
            "masks": HIGH_MASKS,
            "set_by_direction": high_by_direction,
            "set_directional_bits_seen": high_seen,
            "high_without_matching_low": high_without_matching_low,
            "high_implies_low_in_this_save": high_without_matching_low == 0,
            "exact_subtype_semantics_proven": False,
        },
        "actor_clearance_model_partial": True,
        "player_movement_model_complete": False,
        "softlock_analysis_authorized": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("saves", nargs="+", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    results = [classify(path) for path in args.saves]
    ok = all(
        result["bit_0x10_partition_boundary"]["all_cross_edges_sealed"]
        for result in results
    )

    if args.json:
        print(json.dumps({"valid": ok, "results": results}, indent=2, sort_keys=True))
    else:
        for result in results:
            b = result["bit_0x10_partition_boundary"]
            c = result["cell0"]
            h = result["cell2_high_directional_blocker"]
            state = "PASS" if b["all_cross_edges_sealed"] else "FAIL"
            print(
                f"{state} {result['path']}: "
                f"{result['row_count']}x{result['column_count']} "
                f"bit10={c['bit_0x10_static_actor_clearance_region_gate']} "
                f"bit80={c['bit_0x80_runtime_actor_clearance_blocker']} "
                f"actor-region={result['static_actor_region']['count']} "
                f"bit10-cross={b['reciprocal_static_barriers']}/{b['cross_edges']} "
                f"high-without-low={h['high_without_matching_low']}"
            )

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
