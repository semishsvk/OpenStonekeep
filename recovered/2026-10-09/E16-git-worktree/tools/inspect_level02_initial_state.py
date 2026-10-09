#!/usr/bin/env python3
"""Inspect Stonekeep LEVEL02 base resource and initial transition state.

STONE-K292-E.13 scope:
- prove the no-save -> LEVEL02.MAZ fallback path;
- bind MASTER LEVEL02.MAZ to GROUP02;
- extract and validate the raw LEVEL02.MAZ resource;
- reconstruct the two generic grid planes used by the MAZ materializer;
- apply the level-2 initializer's verified cell-handler assignments;
- resolve and validate the two level-2 return transition handlers.

This tool intentionally does not claim that the typed MAZ tail has already
been fully reconstructed into MSP / monster-spatial runtime pools.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inspect_group import parse as parse_group
from resolve_le_handler_dispatch import LE

EXPECTED_EXE_SHA = "5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2"
EXPECTED_MASTER_SHA = "d29db8dd09ec20ed0eadbb3187924e1d83b766481051da42c3ac5a49f703e350"
EXPECTED_GROUP02_SHA = "ae4fadcddfb3f722330cbcda1362e8ed4b77a1642de5b20aa4f668151fbea425"
EXPECTED_LEVEL02_MAZ_SHA = "2255a617c1470bc388fa33667944d9df7dac350b2f0a5943a95fc719ae475b84"

MASTER_ENTRY_SIZE = 20
MASTER_NAME_SIZE = 12
MASTER_TRAILER_SIZE = 4
LEVEL_NAME_OBJECT = 3
LEVEL_NAME_OFFSET = 0x5D44
LEVEL_NAME_STRIDE = 9
LEVEL_INIT_OBJECT = 3
LEVEL_INIT_OFFSET = 0xF10E
DISPATCH_OBJECT = 3
DISPATCH_OFFSET = 0xF16A

LOW = (0x08, 0x02, 0x04, 0x01)
HIGH = (0x80, 0x20, 0x40, 0x10)
OPPOSITE = (2, 3, 0, 1)
DELTA = ((-1, 0), (0, -1), (1, 0), (0, 1))
DIR_NAME = ("N", "W", "S", "E")

REGIONS = {
    "level_loader_save_or_maz": (
        0x5D2F1, 0x87,
        "dd2ddbdde96d0e5583330b7eced464988b1c07a5e133f45647da7dc7a93a5cf1",
    ),
    "maz_grid_materializer": (
        0x6D86F, 0x3D7,
        "6634d6be41689dacfe0b2ecdcccbb81de30c0a00473da819f90ece52f0e2d94d",
    ),
    "level02_initializer": (
        0x5F68A, 0x9D5,
        "a7f9ed552de1c9e0b1bb38748336ea875271c424477f81aa964f812f78d4edc4",
    ),
    "level02_transition_wrappers": (
        0x6005F, 0x38,
        "fbf620ec72701f5bc07e09373b10b4de451ae65aab596d3017ac62447db4e0c8",
    ),
    "transition_common_family": (
        0x3CFEE, 0x9A,
        "36a2889a901c1c4be9c5f4b88868942e9226d6d779ddffb9b21478958b8fb7fa",
    ),
}

# Sequential 0x3DFBA(handler,row,column) writes made by the level-2 initializer
# on the new-level path. Two cells are intentionally overwritten later.
LEVEL2_HANDLER_ASSIGNMENTS = (
    (117, 6, 22), (150, 10, 13), (151, 10, 14), (120, 10, 17),
    (54, 4, 10), (53, 5, 10), (121, 19, 6), (122, 19, 1),
    (123, 20, 1), (124, 21, 1), (125, 22, 1), (126, 10, 3),
    (54, 11, 10), (53, 12, 10), (127, 4, 25), (150, 7, 25),
    (151, 8, 25), (148, 7, 25), (149, 8, 25), (130, 19, 25),
    (131, 20, 18), (132, 22, 4), (133, 22, 6), (134, 20, 6),
    (135, 20, 8), (136, 21, 4), (137, 22, 5), (138, 21, 6),
    (139, 20, 7), (140, 19, 19), (141, 22, 19), (142, 24, 23),
    (143, 25, 23), (144, 6, 2), (145, 2, 17), (146, 16, 23),
    (147, 19, 23), (54, 13, 22), (53, 14, 22), (85, 26, 23),
    (150, 1, 20), (151, 1, 21), (148, 4, 6), (149, 5, 6),
    (128, 20, 10), (129, 21, 10), (128, 24, 11), (129, 25, 11),
    (128, 24, 17), (129, 25, 17), (2, 5, 23), (2, 7, 23),
    (2, 9, 23), (2, 11, 23),
)

LEVEL2_TRANSITIONS = (
    {
        "handler_id": 144,
        "source": (6, 2),
        "direction_index": 2,
        "target_level": 1,
        "target_spawn": (10, 5, 2),
        "incoming_level1_handler": 106,
        "incoming_spawn": (7, 2, 0),
        "handler_runtime": 0x6005F,
    },
    {
        "handler_id": 145,
        "source": (2, 17),
        "direction_index": 3,
        "target_level": 1,
        "target_spawn": (7, 24, 3),
        "incoming_level1_handler": 107,
        "incoming_spawn": (2, 18, 1),
        "handler_runtime": 0x60080,
    },
)


def read_runtime(le: LE, va: int, n: int) -> bytes:
    out = bytearray()
    cur = va
    rem = n
    while rem:
        found = None
        for objnum, obj in enumerate(le.objects, 1):
            if obj["base"] <= cur < obj["base"] + obj["size"]:
                found = (objnum, obj, cur - obj["base"])
                break
        if found is None:
            raise ValueError(f"VA 0x{cur:X} outside LE objects")
        objnum, obj, off = found
        take = min(rem, le.page_size - (off % le.page_size), obj["size"] - off)
        fo = le.object_file_offset(objnum, off)
        out += le.data[fo:fo + take]
        cur += take
        rem -= take
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


def resolve_off32_slot(le: LE, objnum: int, table_off: int, index: int) -> int:
    page, base = le.page_for_object_offset(objnum, table_off)
    src = base + index * 4
    matches = [f for f in le.parse_fixup_page(page) if src in f["sources"]]
    if len(matches) != 1:
        raise ValueError(f"table 0x{table_off:X} index {index}: fixups={len(matches)}")
    f = matches[0]
    if not (
        (f["type"] & 0x0F) == 0x07
        and f["target_kind"] == 0
        and f["target_offset"] is not None
        and 1 <= f["target_object"] <= len(le.objects)
    ):
        raise ValueError(f"table 0x{table_off:X} index {index}: unexpected fixup")
    obj = le.objects[f["target_object"] - 1]
    return obj["base"] + f["target_offset"]


def parse_master(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 2 + MASTER_TRAILER_SIZE:
        raise ValueError("MASTER too small")
    count = struct.unpack_from("<H", data, 0)[0]
    expected = 2 + count * MASTER_ENTRY_SIZE + MASTER_TRAILER_SIZE
    if expected != len(data):
        raise ValueError(f"MASTER size mismatch: expected {expected}, got {len(data)}")
    records = []
    for index in range(count):
        p = 2 + index * MASTER_ENTRY_SIZE
        rec = data[p:p + MASTER_ENTRY_SIZE]
        name = rec[:MASTER_NAME_SIZE].split(b"\0", 1)[0].decode("ascii", "replace")
        group_id = struct.unpack_from("<H", rec, 18)[0]
        records.append({"index": index, "name": name, "group_id": group_id})
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "entry_count": count,
        "records": records,
        "trailer_hex": data[-MASTER_TRAILER_SIZE:].hex(),
    }


def parse_maz_grid(payload: bytes) -> dict:
    if len(payload) < 6:
        raise ValueError("MAZ too small")
    marker = payload[:2]
    rows, columns = struct.unpack_from("<HH", payload, 2)
    count = rows * columns
    end = 6 + count * 2
    if end > len(payload):
        raise ValueError("MAZ truncated before two grid planes")
    cell02 = payload[6:6 + count]
    cell00 = payload[6 + count:6 + count * 2]
    handlers = [0] * count
    for handler, row, column in LEVEL2_HANDLER_ASSIGNMENTS:
        if not (0 <= row < rows and 0 <= column < columns):
            raise ValueError(f"handler {handler} cell out of bounds: {(row, column)}")
        handlers[row * columns + column] = handler
    return {
        "marker": marker,
        "rows": rows,
        "columns": columns,
        "cell_count": count,
        "cell02": cell02,
        "cell00": cell00,
        "handlers": handlers,
        "typed_tail_offset": end,
    }


def portal_marker(grid: dict, transition: dict) -> dict:
    row, column = transition["source"]
    didx = transition["direction_index"]
    dr, dc = DELTA[didx]
    nr, nc = row + dr, column + dc
    if not (0 <= nr < grid["rows"] and 0 <= nc < grid["columns"]):
        raise ValueError("portal neighbor out of bounds")
    src = grid["cell02"][row * grid["columns"] + column]
    dst = grid["cell02"][nr * grid["columns"] + nc]
    od = OPPOSITE[didx]
    reciprocal = bool(
        (src & LOW[didx]) and (src & HIGH[didx])
        and (dst & LOW[od]) and (dst & HIGH[od])
    )
    return {
        "source": [row, column],
        "direction": DIR_NAME[didx],
        "adjacent": [nr, nc],
        "source_cell02": src,
        "adjacent_cell02": dst,
        "source_low": bool(src & LOW[didx]),
        "source_high": bool(src & HIGH[didx]),
        "adjacent_low": bool(dst & LOW[od]),
        "adjacent_high": bool(dst & HIGH[od]),
        "reciprocal_low_high": reciprocal,
    }


def inspect(exe: Path, master: Path, group02: Path) -> dict:
    errors = []
    exe_data = exe.read_bytes()
    exe_sha = hashlib.sha256(exe_data).hexdigest()
    if exe_sha != EXPECTED_EXE_SHA:
        errors.append("unexpected SK.EXE SHA-256")
    le = LE(exe_data)

    m = parse_master(master)
    if m["sha256"] != EXPECTED_MASTER_SHA:
        errors.append("unexpected MASTER SHA-256")
    level_master = [r for r in m["records"] if r["name"] == "LEVEL02.MAZ"]
    if len(level_master) != 1:
        errors.append(f"MASTER LEVEL02.MAZ records={len(level_master)}")
        master_record = None
    else:
        master_record = level_master[0]
        if master_record["index"] != 811 or master_record["group_id"] != 2:
            errors.append(f"unexpected MASTER LEVEL02 mapping: {master_record}")

    group_data = group02.read_bytes()
    group_sha = hashlib.sha256(group_data).hexdigest()
    if group_sha != EXPECTED_GROUP02_SHA:
        errors.append("unexpected GROUP02 SHA-256")
    gi = parse_group(group02)
    hits = [e for e in gi["entries"] if e["name"] == "LEVEL02.MAZ"]
    if len(hits) != 1:
        errors.append(f"GROUP02 LEVEL02.MAZ entries={len(hits)}")
        entry = None
        payload = b""
    else:
        entry = hits[0]
        payload = group_data[entry["payload_start"]:entry["payload_end"]]

    maz_sha = hashlib.sha256(payload).hexdigest()
    if maz_sha != EXPECTED_LEVEL02_MAZ_SHA:
        errors.append("unexpected LEVEL02.MAZ SHA-256")
    try:
        grid = parse_maz_grid(payload)
    except Exception as exc:
        errors.append(str(exc))
        grid = None

    if grid is not None:
        if grid["marker"] != b"ON":
            errors.append(f"unexpected MAZ marker {grid['marker']!r}")
        if (grid["rows"], grid["columns"]) != (30, 27):
            errors.append(
                f"unexpected LEVEL02 dimensions {(grid['rows'], grid['columns'])}"
            )
        if sum(h != 0 for h in grid["handlers"]) != 52:
            errors.append("unexpected final non-default handler-cell count")

    level_name = object_bytes(
        le, LEVEL_NAME_OBJECT,
        LEVEL_NAME_OFFSET + 2 * LEVEL_NAME_STRIDE,
        LEVEL_NAME_STRIDE,
    ).split(b"\0", 1)[0].decode("ascii")
    if level_name != "level02":
        errors.append(f"level init slot 2 name is {level_name!r}")
    try:
        init_runtime = resolve_off32_slot(le, LEVEL_INIT_OBJECT, LEVEL_INIT_OFFSET, 2)
    except Exception as exc:
        init_runtime = None
        errors.append(str(exc))
    if init_runtime != 0x5F68A:
        errors.append(f"unexpected LEVEL02 initializer {init_runtime!r}")

    regions = {}
    for name, (va, size, expected) in REGIONS.items():
        got = hashlib.sha256(read_runtime(le, va, size)).hexdigest()
        ok = got == expected
        regions[name] = {
            "runtime_va": hex(va), "size": size, "sha256": got, "pass": ok
        }
        if not ok:
            errors.append(f"region hash mismatch: {name}")

    transitions = []
    if grid is not None:
        for spec in LEVEL2_TRANSITIONS:
            handler = spec["handler_id"]
            try:
                target = resolve_off32_slot(le, DISPATCH_OBJECT, DISPATCH_OFFSET, handler)
            except Exception as exc:
                target = None
                errors.append(str(exc))
            row, column = spec["source"]
            observed = grid["handlers"][row * grid["columns"] + column]
            marker = portal_marker(grid, spec)
            incoming_row, incoming_col, incoming_facing = spec["incoming_spawn"]
            if observed != handler:
                errors.append(
                    f"handler {handler}: reconstructed source cell contains {observed}"
                )
            if target != spec["handler_runtime"]:
                errors.append(
                    f"handler {handler}: runtime {target!r} != "
                    f"0x{spec['handler_runtime']:X}"
                )
            if not marker["reciprocal_low_high"]:
                errors.append(f"handler {handler}: portal marker is not reciprocal")
            if marker["adjacent"] != [incoming_row, incoming_col]:
                errors.append(
                    f"handler {handler}: portal adjacent {marker['adjacent']} "
                    f"!= incoming spawn cell {[incoming_row, incoming_col]}"
                )
            # Incoming facing must point from the arrival cell back toward the
            # transition-source cell, i.e. opposite of the source gate.
            if incoming_facing != OPPOSITE[spec["direction_index"]]:
                errors.append(f"handler {handler}: incoming facing is not reciprocal")

            transitions.append({
                "handler_id": handler,
                "handler_runtime": hex(target) if target is not None else None,
                "source": list(spec["source"]),
                "direction": DIR_NAME[spec["direction_index"]],
                "marker": marker,
                "source_level": 2,
                "target_level": spec["target_level"],
                "target_spawn": list(spec["target_spawn"]),
                "incoming_level1_handler": spec["incoming_level1_handler"],
                "incoming_spawn": list(spec["incoming_spawn"]),
                "action15_gate": "DIRECT_COMMON_FAMILY_ALLOW",
                "physical_msp_spatial_after_open": "E14_NOT_YET_RECONSTRUCTED",
            })

    return {
        "exe_sha256": exe_sha,
        "master": {
            "sha256": m["sha256"],
            "entry_count": m["entry_count"],
            "level02_record": master_record,
        },
        "group02": {
            "sha256": group_sha,
            "entry_count": gi["entry_count"],
            "directory_end": gi["directory_end"],
            "level02_entry": entry,
        },
        "level02_maz": {
            "sha256": maz_sha,
            "size": len(payload),
            "marker": (
                grid["marker"].decode("ascii", "replace") if grid is not None else None
            ),
            "rows": grid["rows"] if grid is not None else None,
            "columns": grid["columns"] if grid is not None else None,
            "cell_count": grid["cell_count"] if grid is not None else None,
            "typed_tail_offset": grid["typed_tail_offset"] if grid is not None else None,
        },
        "initializer": {
            "level_name": level_name,
            "runtime": hex(init_runtime) if init_runtime is not None else None,
            "handler_write_count": len(LEVEL2_HANDLER_ASSIGNMENTS),
            "final_nondefault_handler_cells": (
                sum(h != 0 for h in grid["handlers"]) if grid is not None else None
            ),
            "unique_handler_ids": len(set(h for h, _, _ in LEVEL2_HANDLER_ASSIGNMENTS)),
        },
        "return_transitions": transitions,
        "return_transition_count": len(transitions),
        "region_validation": regions,
        "state_scope": {
            "base_grid": "VERIFIED",
            "initial_handler_map": "VERIFIED",
            "return_transition_payloads": "VERIFIED",
            "special_portal_markers": "VERIFIED",
            "msp_monster_runtime_tail": "OPEN_E14",
            "one_way_verdict_authorized": False,
            "softlock_verdict_authorized": False,
        },
        "errors": errors,
        "pass": not errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", type=Path, required=True)
    ap.add_argument("--master", type=Path, required=True)
    ap.add_argument("--group02", type=Path, required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out = inspect(args.exe, args.master, args.group02)
    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print(
            "PASS" if out["pass"] else "FAIL",
            f"level02={out['level02_maz']['rows']}x{out['level02_maz']['columns']}",
            f"handler_writes={out['initializer']['handler_write_count']}",
            f"return_transitions={out['return_transition_count']}",
            f"regions={len(out['region_validation'])}",
            f"errors={len(out['errors'])}",
        )
        for t in out["return_transitions"]:
            print(
                f" h{t['handler_id']} {t['source']} {t['direction']} -> "
                f"L{t['target_level']} {t['target_spawn']} "
                f"marker={t['marker']['reciprocal_low_high']}"
            )
    return 0 if out["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
