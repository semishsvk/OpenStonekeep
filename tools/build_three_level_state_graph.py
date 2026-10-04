#!/usr/bin/env python3
"""Build STONE-K292-E.16 three-level state-qualified navigation bounds.

This is deliberately not a global dynamic-world proof.

VERIFIED_FROZEN_SNAPSHOT:
- LEVEL01 / LEVEL01A FWD/BACK use verified static+MSP+spatial+callback-return
  snapshot gates.
- turn edges use the verified 0x82BC3 physical precheck and are admitted only
  for callback paths already closed for turn actions (default h0 and h415).
- direct portal edges from E.15 are included when no producer qualification is
  required.
- all six E.15 same-interface return sequences are included as verified macros.
- LEVEL02 ordinary movement is NOT admitted because its initial monster-spatial
  callback materialization is not yet corpus-wide closed.

POTENTIAL_UPPER_BOUND:
- LEVEL01 / LEVEL01A use physically clear snapshot movement and turn gates,
  regardless of unresolved non-default turn callback return/state deltas.
- LEVEL02 uses reciprocal static topology only for ordinary FWD/BACK and allows
  all turns; MSP post-materializer zeroing, monster-spatial state and callbacks
  are explicit unresolved dimensions.
- all 12 E.15 portal edges are admitted.

SCC numbers are bounds for these graph abstractions only. They do not authorize
one-way or softlock verdicts.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_serialized_initial_transition_graph import (
    CALLBACK_ALLOW_HANDLERS,
    aggregate_msp,
    backward_block_sets,
    forward_block_sets,
    read_state,
    spatial_categories,
)
from build_three_level_portal_graph import build as build_e15
from inspect_level02_initial_state import LEVEL2_HANDLER_ASSIGNMENTS
from inspect_level02_runtime_tail import extract_named, parse_maz
from resolve_le_handler_dispatch import LE

EXPECTED_EXE_SHA = "5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2"
EXPECTED_LEVEL01_SHA = "2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9"
EXPECTED_LEVEL01A_SHA = "3d1753ca8a4ca49b3ccf9da0fc15bb08ac242301eff40586049379ceba635dc9"
EXPECTED_LEVEL02_MAZ_SHA = "2255a617c1470bc388fa33667944d9df7dac350b2f0a5943a95fc719ae475b84"

LOW = (0x08, 0x02, 0x04, 0x01)
OPPOSITE = (2, 3, 0, 1)
DELTA = ((-1, 0), (0, -1), (1, 0), (0, 1))
TURN_CALLBACK_ALLOW = {0, 415}

REGIONS = {
    "turn_precheck": (
        0x82BC3,
        0xB7,
        "3a0a92214ea557063e20a1a948a8b2540f259b00e4d2916cc1fccf9c83951dca",
    ),
    "msp_type_allocator": (
        0x11B40,
        0x208,
        "182cdc20de0424d2fb89c76d9ea5777ddf89326c48b282a12b46b71b16be2083",
    ),
}
EXPECTED_MASK_TABLE_SHA = "f692f6fbe8f5b96bcec84ff132a36f7f32addef0c25124046c1683a8b2ba5007"

# Exact type-switch result for every MSP type observed in LEVEL02.MAZ.
# "table" is object3+0x38D5, a 9x9 centered directional table indexed by
# (word3+4, word4+4). Constants are the BX movement-mask argument passed to
# allocator 0x116F0 before the later generic zero-only override.
LEVEL2_TYPE_PREZERO_MODE = {
    2: "table", 3: 0, 4: "table", 5: 0, 9: "table", 10: "table",
    12: 0, 13: 0, 14: 0, 15: 0x1F, 16: 0, 20: 0x1F,
    21: "table", 22: 0, 23: 0, 34: 0, 57: 0x1F, 94: 0,
    99: "table", 106: 0x1F, 111: 0x1F,
}

RETURN_MACROS = (
    # target spawn after L1 outbound, verified E.15 return result, outbound, return
    ((15, 3, 3, 0), (1, 3, 3, 0), 87, 411),
    ((15, 3, 25, 0), (1, 3, 25, 0), 88, 412),
    ((15, 22, 3, 2), (1, 22, 3, 2), 89, 415),
    ((15, 22, 25, 2), (1, 22, 25, 2), 90, 413),
    ((2, 7, 2, 0), (1, 10, 5, 2), 106, 144),
    ((2, 2, 18, 1), (1, 7, 24, 3), 107, 145),
)


def s16(buf: bytes, off: int) -> int:
    return struct.unpack_from("<h", buf, off)[0]


def read_runtime(le: LE, va: int, n: int) -> bytes:
    out = bytearray()
    cur = va
    rem = n
    while rem:
        for objnum, obj in enumerate(le.objects, 1):
            if obj["base"] <= cur < obj["base"] + obj["size"]:
                off = cur - obj["base"]
                take = min(
                    rem,
                    le.page_size - (off % le.page_size),
                    obj["size"] - off,
                )
                fo = le.object_file_offset(objnum, off)
                out += le.data[fo:fo + take]
                cur += take
                rem -= take
                break
        else:
            raise ValueError(f"VA 0x{cur:X} outside LE objects")
    return bytes(out)


def object_bytes(le: LE, objnum: int, off: int, n: int) -> bytes:
    out = bytearray()
    cur = off
    rem = n
    while rem:
        take = min(rem, le.page_size - (cur % le.page_size))
        fo = le.object_file_offset(objnum, cur)
        out += le.data[fo:fo + take]
        cur += take
        rem -= take
    return bytes(out)


def save_level(path: Path) -> dict:
    data, rows, cols, cells, spatial_records, heads, msp_records = read_state(path)
    masks, bad_msp, cycles_msp = aggregate_msp(cells, msp_records)
    spatial, bad_sp, cycles_sp, mismatch, dupes = spatial_categories(
        spatial_records, heads
    )
    errors = []
    if any((bad_msp, cycles_msp, bad_sp, cycles_sp, mismatch, dupes)):
        errors.append("serialized MSP/spatial validation failed")
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "rows": rows,
        "cols": cols,
        "cells": cells,
        "masks": masks,
        "spatial": spatial,
        "spatial_exact": True,
        "errors": errors,
    }


def level2_base(exe: Path, group02: Path) -> dict:
    _info, _entry, payload = extract_named(group02, "LEVEL02.MAZ")
    if hashlib.sha256(payload).hexdigest() != EXPECTED_LEVEL02_MAZ_SHA:
        raise ValueError("unexpected LEVEL02.MAZ SHA-256")

    parsed = parse_maz(payload)
    rows, cols = parsed["rows"], parsed["columns"]
    n = rows * cols
    cell02 = payload[6:6 + n]
    handlers = [0] * n
    for handler, row, col in LEVEL2_HANDLER_ASSIGNMENTS:
        handlers[row * cols + col] = handler

    exe_data = exe.read_bytes()
    le = LE(exe_data)
    table = object_bytes(le, 3, 0x38D5, 81)
    if hashlib.sha256(table).hexdigest() != EXPECTED_MASK_TABLE_SHA:
        raise ValueError("LEVEL02 MSP directional mask table mismatch")

    # Pre-zero allocator mask. The generic materializer later contains only a
    # zeroing override for +0x18, so these masks are conservative blockers:
    # a nonzero bit may disappear, but a zero bit is never created as blocked
    # by that later override.
    masks = [0] * n
    record_masks = []
    for index, (base, _poj, _monsters) in enumerate(parsed["msp"]):
        w = struct.unpack("<13h", base)
        mode = LEVEL2_TYPE_PREZERO_MODE.get(w[0])
        if mode is None:
            raise ValueError(f"LEVEL02 MSP type {w[0]} lacks allocator mode")
        if mode == "table":
            rr, cc = w[3] + 4, w[4] + 4
            if not (0 <= rr < 9 and 0 <= cc < 9):
                raise ValueError(
                    f"LEVEL02 MSP {index} directional lookup outside 9x9"
                )
            mask = table[rr * 9 + cc]
        else:
            mask = int(mode)
        contributes = w[7] == 1
        if contributes and 0 <= w[1] < rows and 0 <= w[2] < cols:
            masks[w[1] * cols + w[2]] |= mask
        record_masks.append({
            "index": index,
            "type": w[0],
            "row": w[1],
            "column": w[2],
            "contributes": contributes,
            "prezero_mask": mask,
        })

    cells = []
    for i in range(n):
        cell = bytearray(0x15)
        cell[0x02] = cell02[i]
        struct.pack_into("<h", cell, 0x07, handlers[i])
        cells.append(bytes(cell))

    nested = sum(len(x[2]) for x in parsed["msp"])
    standalone = len(parsed["monsters"])
    return {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "rows": rows,
        "cols": cols,
        "cells": cells,
        "masks": masks,
        "spatial": None,
        "spatial_exact": False,
        "msp_records": record_masks,
        "msp_count": len(record_masks),
        "monster_count": nested + standalone,
    }


def forward_sets(facing: int):
    parity = facing & 1
    return (
        {
            facing + 0x10, facing + 0x20,
            0x16 + parity, 0x26 + parity, 0x15, 0x25,
        },
        {0x50, facing + 0x40, 0x46 + parity},
    )


def backward_sets(facing: int):
    movement = OPPOSITE[facing]
    parity = facing & 1
    return (
        {movement + 0x10, 0x16 + parity, 0x15},
        {
            0x50, movement + 0x30, 0x36 + parity,
            facing + 0x40, 0x46 + parity,
        },
    )


def physical_move(level: dict, row: int, col: int, facing: int, action: str):
    move_dir = facing if action == "FWD" else OPPOSITE[facing]
    dr, dc = DELTA[move_dir]
    nr, nc = row + dr, col + dc
    if not (0 <= nr < level["rows"] and 0 <= nc < level["cols"]):
        return None, "BOUNDARY"

    i = row * level["cols"] + col
    j = nr * level["cols"] + nc
    if (
        level["cells"][i][0x02] & LOW[move_dir]
        or level["cells"][j][0x02] & LOW[OPPOSITE[move_dir]]
    ):
        return None, "STATIC_BLOCKED"

    if action == "FWD":
        msp = bool(
            level["masks"][i] & (LOW[move_dir] | 0x10)
            or level["masks"][j] & LOW[OPPOSITE[move_dir]]
        )
        src_set, dst_set = forward_sets(facing)
    else:
        msp = bool(level["masks"][j] & (LOW[move_dir] | 0x10))
        src_set, dst_set = backward_sets(facing)
    if msp:
        return None, "MSP_BLOCKED"

    if level["spatial"] is None:
        return None, "SPATIAL_UNRESOLVED"
    if (
        level["spatial"].get((row, col), ()) & src_set
        or level["spatial"].get((nr, nc), ()) & dst_set
    ):
        return None, "SPATIAL_BLOCKED"
    return (nr, nc, facing), "CLEAR"


def static_only_move(level: dict, row: int, col: int, facing: int, action: str):
    move_dir = facing if action == "FWD" else OPPOSITE[facing]
    dr, dc = DELTA[move_dir]
    nr, nc = row + dr, col + dc
    if not (0 <= nr < level["rows"] and 0 <= nc < level["cols"]):
        return None
    i = row * level["cols"] + col
    j = nr * level["cols"] + nc
    if (
        level["cells"][i][0x02] & LOW[move_dir]
        or level["cells"][j][0x02] & LOW[OPPOSITE[move_dir]]
    ):
        return None
    return (nr, nc, facing)


def turn_physical(level: dict, row: int, col: int, new_facing: int):
    i = row * level["cols"] + col

    # 0x12B20 called by 0x82BC3: aggregated MSP movement mask must not
    # intersect the LOW bit opposite the prospective new facing.
    if level["masks"][i] & LOW[OPPOSITE[new_facing]]:
        return False, "MSP_BLOCKED"

    if level["spatial"] is None:
        return False, "SPATIAL_UNRESOLVED"

    blockers = {0x40 + new_facing, 0x46 + (new_facing & 1), 0x45}
    if level["spatial"].get((row, col), ()) & blockers:
        return False, "SPATIAL_BLOCKED"
    return True, "CLEAR"


def state(level: int, row: int, col: int, facing: int):
    return (level, row, col, facing)


def strongly_connected_components(nodes, adjacency):
    sys.setrecursionlimit(max(50000, len(nodes) * 2))
    index = 0
    stack = []
    on_stack = set()
    indices = {}
    low = {}
    components = []

    def visit(v):
        nonlocal index
        indices[v] = low[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)
        for w in adjacency.get(v, ()):
            if w not in indices:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], indices[w])
        if low[v] == indices[v]:
            comp = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                comp.append(w)
                if w == v:
                    break
            components.append(comp)

    for v in nodes:
        if v not in indices:
            visit(v)
    return components


def graph_summary(nodes, adjacency):
    comps = strongly_connected_components(nodes, adjacency)
    sizes = sorted((len(c) for c in comps), reverse=True)
    largest = max(comps, key=len)
    return {
        "node_count": len(nodes),
        "edge_count": sum(len(v) for v in adjacency.values()),
        "scc_count": len(comps),
        "largest_scc_sizes": sizes[:20],
        "singleton_scc_count": sum(x == 1 for x in sizes),
        "zero_out_degree_states": sum(not adjacency.get(v) for v in nodes),
        "largest_scc_level_counts": dict(
            sorted(collections.Counter(v[0] for v in largest).items())
        ),
    }


def build(
    exe: Path,
    level01: Path,
    level01a: Path,
    gameinfo: Path,
    master: Path,
    group01: Path,
    group02: Path,
):
    errors = []
    exe_data = exe.read_bytes()
    if hashlib.sha256(exe_data).hexdigest() != EXPECTED_EXE_SHA:
        errors.append("unexpected SK.EXE SHA-256")

    l1 = save_level(level01)
    l15 = save_level(level01a)
    if l1["sha256"] != EXPECTED_LEVEL01_SHA:
        errors.append("unexpected LEVEL01.SAV SHA-256")
    if l15["sha256"] != EXPECTED_LEVEL01A_SHA:
        errors.append("unexpected LEVEL01A.SAV SHA-256")
    errors.extend(l1["errors"])
    errors.extend(l15["errors"])

    try:
        l2 = level2_base(exe, group02)
    except Exception as exc:
        errors.append(str(exc))
        l2 = None

    e15 = build_e15(
        exe, level01, level01a, gameinfo, master, group01, group02
    )
    if not e15.get("pass"):
        errors.append("E.15 validation failed")
    if e15.get("immediate_same_interface_return_count") != 6:
        errors.append("E.15 does not expose 6/6 immediate returns")

    le = LE(exe_data)
    regions = {}
    for name, (va, size, expected) in REGIONS.items():
        got = hashlib.sha256(read_runtime(le, va, size)).hexdigest()
        regions[name] = {
            "runtime_va": hex(va),
            "size": size,
            "sha256": got,
            "pass": got == expected,
        }
        if got != expected:
            errors.append(f"region hash mismatch: {name}")

    if l2 is None:
        return {"pass": False, "errors": errors, "region_validation": regions}

    levels = {1: l1, 15: l15, 2: l2}
    nodes = []
    for level_id, level in levels.items():
        for row in range(level["rows"]):
            for col in range(level["cols"]):
                for facing in range(4):
                    nodes.append(state(level_id, row, col, facing))

    verified = collections.defaultdict(set)
    potential = collections.defaultdict(set)
    counts = collections.Counter()

    for level_id, level in levels.items():
        for row in range(level["rows"]):
            for col in range(level["cols"]):
                handler = s16(
                    level["cells"][row * level["cols"] + col], 0x07
                )
                for facing in range(4):
                    src = state(level_id, row, col, facing)

                    for action in ("FWD", "BACK"):
                        dst, reason = physical_move(
                            level, row, col, facing, action
                        )
                        if (
                            dst is not None
                            and handler in ({0} | set(CALLBACK_ALLOW_HANDLERS))
                        ):
                            verified[src].add(state(level_id, *dst))
                            counts[f"verified_move_L{level_id}"] += 1
                        elif reason == "SPATIAL_UNRESOLVED":
                            counts["level2_move_spatial_unresolved"] += 1

                        if level_id == 2:
                            pdst = static_only_move(
                                level, row, col, facing, action
                            )
                        else:
                            pdst = dst
                        if pdst is not None:
                            potential[src].add(state(level_id, *pdst))
                            counts[f"potential_move_L{level_id}"] += 1
                            if (
                                handler
                                not in ({0} | set(CALLBACK_ALLOW_HANDLERS))
                            ):
                                counts["movement_callback_unresolved"] += 1

                    for delta in (1, 3):
                        new_facing = (facing + delta) & 3
                        turn_ok, turn_reason = turn_physical(
                            level, row, col, new_facing
                        )
                        if turn_ok and handler in TURN_CALLBACK_ALLOW:
                            verified[src].add(
                                state(level_id, row, col, new_facing)
                            )
                            counts[f"verified_turn_L{level_id}"] += 1
                        elif turn_ok and handler not in TURN_CALLBACK_ALLOW:
                            counts["turn_callback_unresolved"] += 1
                        elif turn_reason == "SPATIAL_UNRESOLVED":
                            counts["level2_turn_spatial_unresolved"] += 1

                        potential_turn = turn_ok if level_id != 2 else True
                        if potential_turn:
                            potential[src].add(
                                state(level_id, row, col, new_facing)
                            )
                            counts[f"potential_turn_L{level_id}"] += 1

    # E.15 transition-source edges.
    for edge in e15["edges"]:
        dindex = {"N": 0, "W": 1, "S": 2, "E": 3}[edge["direction"]]
        src = state(
            edge["source_level"], edge["source"][0], edge["source"][1], dindex
        )
        dst = state(edge["target_level"], *edge["target_spawn"])
        potential[src].add(dst)
        counts["portal_potential"] += 1
        if edge["outgoing_reachability"] in (
            "DIRECT_ENABLE_INITIAL_STATE",
            "IMMEDIATE_RECIPROCAL_VERIFIED",
        ):
            verified[src].add(dst)
            counts["portal_verified_direct"] += 1

    # E.15 full same-interface return sequences. These are macro transitions
    # from the exact target spawn after a successful LEVEL01 outbound portal.
    return_macro_records = []
    for src_tuple, dst_tuple, outbound, return_handler in RETURN_MACROS:
        src = tuple(src_tuple)
        dst = tuple(dst_tuple)
        verified[src].add(dst)
        potential[src].add(dst)
        return_macro_records.append({
            "outbound_handler": outbound,
            "return_handler": return_handler,
            "target_spawn_state": list(src),
            "verified_return_state": list(dst),
        })
        counts["return_macro_verified"] += 1

    vsummary = graph_summary(nodes, verified)
    psummary = graph_summary(nodes, potential)

    return {
        "state_count": len(nodes),
        "levels": {
            "1": {"rows": l1["rows"], "columns": l1["cols"]},
            "15": {"rows": l15["rows"], "columns": l15["cols"]},
            "2": {
                "rows": l2["rows"],
                "columns": l2["cols"],
                "msp_count": l2["msp_count"],
                "monster_count": l2["monster_count"],
                "spatial_state": "UNRESOLVED_FOR_CORPUS_WIDE_ORDINARY_GRAPH",
                "prezero_aggregate_mask_histogram": dict(
                    sorted(collections.Counter(l2["masks"]).items())
                ),
            },
        },
        "edge_counts": dict(sorted(counts.items())),
        "verified_frozen_snapshot": vsummary,
        "potential_upper_bound": psummary,
        "verified_return_macros": return_macro_records,
        "verified_return_macro_count": len(return_macro_records),
        "region_validation": regions,
        "scope": {
            "turn_physical_precheck": "VERIFIED",
            "turn_callback_allow": "VERIFIED_ONLY_FOR_H0_AND_H415",
            "level01_level01a_translation": "VERIFIED_SERIALIZED_SNAPSHOT",
            "level02_static_topology": "VERIFIED_BASE_MAZ",
            "level02_msp_allocator_prezero": "VERIFIED_CONSERVATIVE_BASE_MASK",
            "level02_spatial_ordinary_graph": "OPEN",
            "scc_semantics": "LOWER_AND_UPPER_GRAPH_BOUNDS_ONLY",
            "global_one_way_verdict_authorized": False,
            "global_softlock_verdict_authorized": False,
        },
        "errors": errors,
        "pass": not errors and len(return_macro_records) == 6,
    }


def main():
    ap = argparse.ArgumentParser()
    for name in (
        "exe", "level01", "level01a", "gameinfo",
        "master", "group01", "group02",
    ):
        ap.add_argument(
            "--" + name.replace("_", "-"),
            dest=name,
            type=Path,
            required=True,
        )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out = build(
        args.exe, args.level01, args.level01a, args.gameinfo,
        args.master, args.group01, args.group02,
    )
    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print(
            "PASS" if out["pass"] else "FAIL",
            f"states={out.get('state_count')}",
            f"verified_edges={out.get('verified_frozen_snapshot',{}).get('edge_count')}",
            f"potential_edges={out.get('potential_upper_bound',{}).get('edge_count')}",
            f"returns={out.get('verified_return_macro_count')}/6",
            f"errors={len(out['errors'])}",
        )
        if out.get("verified_frozen_snapshot"):
            print(" verified_scc", out["verified_frozen_snapshot"])
            print(" potential_scc", out["potential_upper_bound"])
    return 0 if out["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
