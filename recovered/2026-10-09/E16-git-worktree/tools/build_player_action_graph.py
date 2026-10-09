#!/usr/bin/env python3
"""Build an evidence-typed Stonekeep player translation snapshot graph.

STONE-K292-D scope:
- ordinary forward/backward grid translation only;
- authoritative low static edge layer;
- serialized MSP/maze-prop directional clearance;
- serialized monster-linked spatial occupancy veto;
- per-cell pre-action handler gate.

A non-default cell+0x07 handler is classified SCRIPTED_UNRESOLVED even when
the current physical snapshot looks blocked/clear, because the handler runs
before ordinary translation and may mutate state or veto the action.

This tool does not model turns, inter-level transitions, specialized handler
semantics, or dynamic future states. It never emits a softlock verdict.
"""
from __future__ import annotations

import argparse
import collections
import json
import struct
from pathlib import Path

from inspect_level_save import CELL_SIZE, DIRECTIONS, DIRECTION_BY_NAME, parse

SPATIAL_RECORD_COUNT = 400
SPATIAL_RECORD_SIZE = 0x0C
SPATIAL_RECORD_BYTES = SPATIAL_RECORD_COUNT * SPATIAL_RECORD_SIZE  # 0x12C0
SPATIAL_GRID_DIM = 54
SPATIAL_GRID_HEAD_BYTES = SPATIAL_GRID_DIM * SPATIAL_GRID_DIM * 2  # 0x16C8
MSP_RECORD_SIZE = 0x30
SENTINEL_NONE = -100

FACING_INDEX = {"N": 0, "W": 1, "S": 2, "E": 3}
INDEX_FACING = {v: k for k, v in FACING_INDEX.items()}
OPPOSITE_INDEX = {0: 2, 1: 3, 2: 0, 3: 1}


def s16(buf: bytes, off: int) -> int:
    return struct.unpack_from("<h", buf, off)[0]


def _cell_bytes(data: bytes, info: dict) -> list[bytes]:
    grid = data[info["grid_start"]:info["grid_end"]]
    return [
        grid[i * CELL_SIZE:(i + 1) * CELL_SIZE]
        for i in range(info["cell_count"])
    ]


def _parse_runtime_pools(data: bytes, info: dict) -> dict:
    pos = info["grid_end"]
    minimum = pos + SPATIAL_RECORD_BYTES + 2 + SPATIAL_GRID_HEAD_BYTES + 2
    if minimum > len(data):
        raise ValueError("level save is truncated before serialized runtime pools")

    spatial_records = [
        struct.unpack_from("<6h", data, pos + i * SPATIAL_RECORD_SIZE)
        for i in range(SPATIAL_RECORD_COUNT)
    ]
    pos += SPATIAL_RECORD_BYTES

    spatial_free_head = s16(data, pos)
    pos += 2

    spatial_heads = struct.unpack_from(
        f"<{SPATIAL_GRID_DIM * SPATIAL_GRID_DIM}h", data, pos
    )
    pos += SPATIAL_GRID_HEAD_BYTES

    msp_count = struct.unpack_from("<H", data, pos)[0]
    pos += 2
    msp_end = pos + msp_count * MSP_RECORD_SIZE
    if msp_end > len(data):
        raise ValueError(
            f"truncated 0x30 MSP pool: count={msp_count} "
            f"needs end=0x{msp_end:X}, file=0x{len(data):X}"
        )
    msp_records = [
        data[pos + i * MSP_RECORD_SIZE:pos + (i + 1) * MSP_RECORD_SIZE]
        for i in range(msp_count)
    ]

    # Validate all serialized spatial grid chains, not just the active game
    # dimensions. This proves the parser against the full 54x54 runtime grid.
    active_spatial_records: set[int] = set()
    nonempty_spatial_cells = 0
    category_counts: collections.Counter[int] = collections.Counter()
    coordinate_mismatches = 0

    for row in range(SPATIAL_GRID_DIM):
        for column in range(SPATIAL_GRID_DIM):
            head = spatial_heads[row * SPATIAL_GRID_DIM + column]
            if head == -1:
                continue
            nonempty_spatial_cells += 1
            current = head
            seen: set[int] = set()
            while current != -1:
                if not 0 <= current < SPATIAL_RECORD_COUNT:
                    raise ValueError(
                        f"spatial head/link out of range at ({row},{column}): "
                        f"{current}"
                    )
                if current in seen:
                    raise ValueError(
                        f"cycle in spatial cell chain at ({row},{column}): "
                        f"record {current}"
                    )
                seen.add(current)
                active_spatial_records.add(current)
                monster, rec_col, rec_row, category, _, next_cell = (
                    spatial_records[current]
                )
                del monster
                if (rec_row, rec_col) != (row, column):
                    coordinate_mismatches += 1
                category_counts[category] += 1
                current = next_cell

    if coordinate_mismatches:
        raise ValueError(
            f"{coordinate_mismatches} spatial records disagree with grid-head "
            "coordinates"
        )

    return {
        "spatial_records": spatial_records,
        "spatial_free_head": spatial_free_head,
        "spatial_heads": spatial_heads,
        "active_spatial_records": active_spatial_records,
        "nonempty_spatial_cells": nonempty_spatial_cells,
        "spatial_category_counts": dict(sorted(category_counts.items())),
        "msp_count": msp_count,
        "msp_records": msp_records,
        "msp_data_start": pos,
        "msp_data_end": msp_end,
    }


def _spatial_categories(
    runtime: dict, rows: int, columns: int
) -> dict[tuple[int, int], frozenset[int]]:
    records = runtime["spatial_records"]
    heads = runtime["spatial_heads"]
    result: dict[tuple[int, int], frozenset[int]] = {}

    for row in range(rows):
        for column in range(columns):
            current = heads[row * SPATIAL_GRID_DIM + column]
            categories: set[int] = set()
            seen: set[int] = set()
            while current != -1:
                if current in seen:
                    raise ValueError("cycle encountered after spatial validation")
                seen.add(current)
                record = records[current]
                categories.add(record[3])
                current = record[5]
            result[(row, column)] = frozenset(categories)

    return result


def _msp_masks(cells: list[bytes], runtime: dict) -> list[int]:
    records = runtime["msp_records"]
    masks: list[int] = []

    for cell_index, cell in enumerate(cells):
        current = s16(cell, 0x11)
        mask = 0
        seen: set[int] = set()
        while current not in (SENTINEL_NONE, -1):
            if not 0 <= current < len(records):
                raise ValueError(
                    f"cell {cell_index} has MSP head/link {current} outside "
                    f"0..{len(records)-1}"
                )
            if current in seen:
                raise ValueError(
                    f"cycle in MSP chain for cell {cell_index}: record {current}"
                )
            seen.add(current)
            record = records[current]
            if s16(record, 0x02) == 1:
                # Engine sign-extends this byte before ORing it; the movement
                # masks used here live in the low byte, so preserving 8 bits
                # is sufficient for the tested predicates.
                mask |= record[0x18]
            current = s16(record, 0x10)
        masks.append(mask)

    return masks


def _forward_spatial_sets(facing: int) -> tuple[frozenset[int], frozenset[int]]:
    parity = facing & 1
    current = frozenset(
        {
            0x10 + facing,
            0x20 + facing,
            0x16 + parity,
            0x26 + parity,
            0x15,
            0x25,
        }
    )
    destination = frozenset({0x50, 0x40 + facing, 0x46 + parity})
    return current, destination


def _backward_spatial_sets(facing: int) -> tuple[frozenset[int], frozenset[int]]:
    movement_direction = OPPOSITE_INDEX[facing]
    parity = facing & 1
    current = frozenset(
        {
            0x10 + movement_direction,
            0x16 + parity,
            0x15,
        }
    )
    destination = frozenset(
        {
            0x50,
            0x30 + movement_direction,
            0x36 + parity,
            0x40 + facing,
            0x46 + parity,
        }
    )
    return current, destination


def _physical_state(
    *,
    action: str,
    facing: int,
    row: int,
    column: int,
    rows: int,
    columns: int,
    cells: list[bytes],
    msp_masks: list[int],
    spatial_categories: dict[tuple[int, int], frozenset[int]],
) -> tuple[str, int | None]:
    source = row * columns + column
    movement_direction = (
        facing if action == "FWD" else OPPOSITE_INDEX[facing]
    )
    direction_name = INDEX_FACING[movement_direction]
    direction = DIRECTION_BY_NAME[direction_name]
    _, dr, dc, static_mask, _, opposite_name = direction

    nr, nc = row + dr, column + dc

    # The primitive reads the source cell's low static direction bit. The
    # authoritative corpus is reciprocal; a mismatch is reported separately
    # rather than silently changing the primitive semantics.
    source_static = bool(cells[source][0x02] & static_mask)
    if not (0 <= nr < rows and 0 <= nc < columns):
        if source_static:
            return "STATIC_BLOCKED", None
        return "TOPOLOGY_BOUNDARY_VIOLATION", None

    destination = nr * columns + nc
    opposite_mask = DIRECTION_BY_NAME[opposite_name][3]
    destination_static = bool(cells[destination][0x02] & opposite_mask)

    if source_static != destination_static:
        return "TOPOLOGY_MISMATCH", destination
    if source_static:
        return "STATIC_BLOCKED", destination

    if action == "FWD":
        # 0x40EE0/0x410A0:
        # source MSP mask intersects (direction low | generic 0x10), or
        # destination mask intersects the opposite low bit.
        msp_blocked = bool(
            msp_masks[source] & (static_mask | 0x10)
        ) or bool(
            msp_masks[destination] & opposite_mask
        )
        source_categories, destination_categories = _forward_spatial_sets(facing)
    else:
        # Backward calls 0x40EE0 with the opposite facing; its non-facing
        # branch checks only the destination MSP mask against
        # (movement-direction low | 0x10).
        msp_blocked = bool(
            msp_masks[destination] & (static_mask | 0x10)
        )
        source_categories, destination_categories = _backward_spatial_sets(facing)

    if msp_blocked:
        return "RUNTIME_MSP_BLOCKED", destination

    if (
        spatial_categories[(row, column)] & source_categories
        or spatial_categories[(nr, nc)] & destination_categories
    ):
        return "RUNTIME_SPATIAL_BLOCKED", destination

    return "SNAPSHOT_TRANSLATION_CLEAR", destination


def build(path: Path, include_actions: bool = False) -> dict:
    info = parse(path)
    data = path.read_bytes()
    cells = _cell_bytes(data, info)
    rows = info["row_count"]
    columns = info["column_count"]

    runtime = _parse_runtime_pools(data, info)
    spatial_categories = _spatial_categories(runtime, rows, columns)
    msp_masks = _msp_masks(cells, runtime)

    evidence_counts: collections.Counter[str] = collections.Counter()
    physical_counts: collections.Counter[str] = collections.Counter()
    action_counts = {
        "FWD": collections.Counter(),
        "BACK": collections.Counter(),
    }
    physical_action_counts = {
        "FWD": collections.Counter(),
        "BACK": collections.Counter(),
    }
    actions: list[dict] = []
    clear_transitions: list[dict] = []

    for row in range(rows):
        for column in range(columns):
            source = row * columns + column
            handler = s16(cells[source], 0x07)

            for facing in range(4):
                for action in ("FWD", "BACK"):
                    physical_state, destination = _physical_state(
                        action=action,
                        facing=facing,
                        row=row,
                        column=column,
                        rows=rows,
                        columns=columns,
                        cells=cells,
                        msp_masks=msp_masks,
                        spatial_categories=spatial_categories,
                    )
                    physical_counts[physical_state] += 1
                    physical_action_counts[action][physical_state] += 1

                    # Pre-action IDs are VERIFIED from the ordinary input path.
                    pre_action_id = 3 if action == "FWD" else 5
                    if handler != 0:
                        state = "SCRIPTED_UNRESOLVED"
                    else:
                        state = physical_state

                    evidence_counts[state] += 1
                    action_counts[action][state] += 1

                    record = {
                        "source_cell": source,
                        "source_row": row,
                        "source_column": column,
                        "facing": INDEX_FACING[facing],
                        "action": action,
                        "pre_action_id": pre_action_id,
                        "source_handler": handler,
                        "physical_snapshot_state": physical_state,
                        "evidence_state": state,
                        "destination_cell": destination,
                    }
                    if include_actions:
                        actions.append(record)

                    if state == "SNAPSHOT_TRANSLATION_CLEAR":
                        clear_transitions.append(
                            {
                                "source_cell": source,
                                "source_facing": INDEX_FACING[facing],
                                "action": action,
                                "destination_cell": destination,
                                "destination_facing": INDEX_FACING[facing],
                            }
                        )

    output = {
        "path": info["path"],
        "sha256": info["sha256"],
        "rows": rows,
        "columns": columns,
        "cells": info["cell_count"],
        "states": info["cell_count"] * 4,
        "actions_per_state": 2,
        "total_translation_actions": info["cell_count"] * 8,
        "topology_reciprocal": info["topology"]["all_static_edges_reciprocal"],
        "serialized_runtime": {
            "spatial_record_count": SPATIAL_RECORD_COUNT,
            "spatial_record_size": SPATIAL_RECORD_SIZE,
            "spatial_free_head": runtime["spatial_free_head"],
            "spatial_grid_dimension": SPATIAL_GRID_DIM,
            "nonempty_spatial_cells": runtime["nonempty_spatial_cells"],
            "active_spatial_records": len(runtime["active_spatial_records"]),
            "spatial_category_counts": runtime["spatial_category_counts"],
            "msp_record_count": runtime["msp_count"],
            "msp_record_size": MSP_RECORD_SIZE,
            "cells_with_nonzero_msp_mask": sum(mask != 0 for mask in msp_masks),
            "msp_mask_histogram": {
                f"0x{mask:02X}": count
                for mask, count in sorted(collections.Counter(msp_masks).items())
            },
        },
        "evidence_state_counts": dict(sorted(evidence_counts.items())),
        "physical_snapshot_state_counts": dict(sorted(physical_counts.items())),
        "by_action": {
            action: dict(sorted(counts.items()))
            for action, counts in action_counts.items()
        },
        "physical_by_action": {
            action: dict(sorted(counts.items()))
            for action, counts in physical_action_counts.items()
        },
        "snapshot_clear_transitions": len(clear_transitions),
        "turn_actions_modeled": False,
        "inter_level_transitions_modeled": False,
        "specialized_handler_semantics_resolved": False,
        "softlock_analysis_authorized": False,
    }
    if include_actions:
        output["actions"] = actions
        output["clear_transitions"] = clear_transitions
    return output


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("save", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--actions", action="store_true")
    args = ap.parse_args()

    result = build(args.save, include_actions=args.actions)
    valid = (
        result["topology_reciprocal"]
        and "TOPOLOGY_MISMATCH" not in result["physical_snapshot_state_counts"]
        and "TOPOLOGY_BOUNDARY_VIOLATION"
        not in result["physical_snapshot_state_counts"]
    )

    if args.json:
        print(json.dumps({"valid": valid, **result}, indent=2, sort_keys=True))
    else:
        print(
            f"{'PASS' if valid else 'FAIL'} {result['path']}: "
            f"{result['rows']}x{result['columns']} "
            f"states={result['states']} "
            f"clear={result['snapshot_clear_transitions']} "
            f"softlock-authorized={result['softlock_analysis_authorized']}"
        )
        for action in ("FWD", "BACK"):
            print(f"  {action}: {result['by_action'][action]}")
        runtime = result["serialized_runtime"]
        print(
            f"  spatial: active={runtime['active_spatial_records']} "
            f"cells={runtime['nonempty_spatial_cells']} "
            f"free_head={runtime['spatial_free_head']}"
        )
        print(
            f"  MSP: count={runtime['msp_record_count']} "
            f"cells_with_mask={runtime['cells_with_nonzero_msp_mask']}"
        )

    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
