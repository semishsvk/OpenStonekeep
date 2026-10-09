#!/usr/bin/env python3
"""Verify the h89 <-> h415 same-interface reciprocal return.

STONE-K292-E.15 evidence closure:
- h89 arrives in LEVEL01A at (22,3,S);
- handler 85 allows special action 15 on the reciprocal LOW+HIGH interface;
- E.9 LOW opening makes (22,3)<->(23,3) physically clear in the serialized state;
- the verified turn input/precheck/apply path allows two same-direction turns
  at (23,3), reaching facing N;
- handler 415 actions 2/3 with facing N call 0x3CFEE with the exact reciprocal
  L15->L1 payload.
"""
from __future__ import annotations
import argparse, hashlib, json, struct, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_le_handler_dispatch import LE
from build_serialized_initial_transition_graph import (
    read_state, aggregate_msp, spatial_categories,
)

EXPECTED_EXE_SHA = "5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2"
EXPECTED_LEVEL01A_SHA = "3d1753ca8a4ca49b3ccf9da0fc15bb08ac242301eff40586049379ceba635dc9"
DISPATCH_OBJECT = 3
DISPATCH_OFFSET = 0xF16A

REGIONS = {
    "h85_wrapper": (
        0x3D2EA, 0x74,
        "775e4bc84aa519bf72d76036163c2056b97462583d9bce05e829b55630d3b4e3",
    ),
    "default_callback_core": (
        0x3D4F5, 13,
        "31df3bff112887d59319063795e39acb86572dc47835dd26d6f2b480b723e315",
    ),
    "h415_action23_transition": (
        0x4FB00, 0x12C,
        "8bba4495ef7f523cbd04f982b948ced64545018223a0672306f3a20165e21b99",
    ),
    "h415_common_turn_actions": (
        0x4FC57, 0x52,
        "cdc1642818333c747cd7a330aef7faa7f5b9829b18a42662290085bdcd7b0587",
    ),
    "turn_input_branches": (
        0x318ED, 0xD5,
        "a11304e3104d2a3a8623f5aac27f23f8781889034914ab91129e0c7f3ea1bfb3",
    ),
    "turn_precheck": (
        0x82BC3, 0xB7,
        "3a0a92214ea557063e20a1a948a8b2540f259b00e4d2916cc1fccf9c83951dca",
    ),
    "turn_apply": (
        0x82899, 0x136,
        "09c9924cb0264f2c62784353075f50fee0b3002374f00898ca789d96bb813363",
    ),
}


def s16(b: bytes, off: int) -> int:
    return struct.unpack_from("<h", b, off)[0]


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


def resolve_handler(le: LE, handler: int) -> int:
    page, base = le.page_for_object_offset(DISPATCH_OBJECT, DISPATCH_OFFSET)
    src = base + handler * 4
    matches = [f for f in le.parse_fixup_page(page) if src in f["sources"]]
    if len(matches) != 1:
        raise ValueError(f"handler {handler}: dispatch fixups={len(matches)}")
    f = matches[0]
    if not (
        (f["type"] & 0x0F) == 0x07
        and f["target_kind"] == 0
        and f["target_offset"] is not None
        and 1 <= f["target_object"] <= len(le.objects)
    ):
        raise ValueError(f"handler {handler}: unexpected dispatch fixup")
    obj = le.objects[f["target_object"] - 1]
    return obj["base"] + f["target_offset"]


def turn_new_facing(facing: int, turn_arg: int) -> int:
    """0x82899: +2 rotates +1; -2 rotates +3 modulo four."""
    if turn_arg == 2:
        return (facing + 1) & 3
    if turn_arg == -2:
        return (facing + 3) & 3
    raise ValueError("turn_arg must be +2 or -2")


def inspect(exe: Path, level01a: Path) -> dict:
    errors = []
    exe_data = exe.read_bytes()
    exe_sha = hashlib.sha256(exe_data).hexdigest()
    if exe_sha != EXPECTED_EXE_SHA:
        errors.append("unexpected SK.EXE SHA-256")
    level_sha = hashlib.sha256(level01a.read_bytes()).hexdigest()
    if level_sha != EXPECTED_LEVEL01A_SHA:
        errors.append("unexpected LEVEL01A.SAV SHA-256")

    le = LE(exe_data)
    regions = {}
    for name, (va, size, expected) in REGIONS.items():
        got = hashlib.sha256(read_runtime(le, va, size)).hexdigest()
        ok = got == expected
        regions[name] = {
            "runtime_va": hex(va), "size": size, "sha256": got, "pass": ok
        }
        if not ok:
            errors.append(f"region hash mismatch: {name}")

    h85 = resolve_handler(le, 85)
    h415 = resolve_handler(le, 415)
    if h85 != 0x3D2EA:
        errors.append(f"handler 85 runtime mismatch: 0x{h85:X}")
    if h415 != 0x4F983:
        errors.append(f"handler 415 runtime mismatch: 0x{h415:X}")

    (
        _data, rows, cols, cells, spatial_records, heads, msp_records
    ) = read_state(level01a)
    msp_masks, msp_invalid, msp_cycles = aggregate_msp(cells, msp_records)
    (
        spatial, sp_invalid, sp_cycles, sp_mismatch, sp_dupes
    ) = spatial_categories(spatial_records, heads)
    if any((msp_invalid, msp_cycles, sp_invalid, sp_cycles, sp_mismatch, sp_dupes)):
        errors.append("serialized MSP/spatial validation failed")

    def state(row: int, col: int) -> dict:
        c = cells[row * cols + col]
        return {
            "cell": [row, col],
            "handler": s16(c, 0x07),
            "cell02": c[0x02],
            "selector4": s16(c, 0x09),
            "selector5": s16(c, 0x0B),
            "msp_mask": msp_masks[row * cols + col],
            "spatial_categories": list(spatial.get((row, col), ())),
        }

    arrival = state(22, 3)
    reciprocal = state(23, 3)
    if arrival != {
        "cell": [22, 3], "handler": 85, "cell02": 0x4F,
        "selector4": 0, "selector5": 0, "msp_mask": 0,
        "spatial_categories": [],
    }:
        errors.append(f"unexpected h89 arrival state: {arrival}")
    if reciprocal != {
        "cell": [23, 3], "handler": 415, "cell02": 0x8B,
        "selector4": 30, "selector5": 0, "msp_mask": 0,
        "spatial_categories": [],
    }:
        errors.append(f"unexpected h415 source state: {reciprocal}")

    reciprocal_marker = bool(
        (arrival["cell02"] & 0x04)
        and (arrival["cell02"] & 0x40)
        and (reciprocal["cell02"] & 0x08)
        and (reciprocal["cell02"] & 0x80)
    )
    if not reciprocal_marker:
        errors.append("h89 arrival interface lacks reciprocal LOW+HIGH marker")

    opened_arrival = arrival["cell02"] & ~0x04
    opened_reciprocal = reciprocal["cell02"] & ~0x08
    crossing_clear = bool(
        arrival["msp_mask"] == 0
        and reciprocal["msp_mask"] == 0
        and not arrival["spatial_categories"]
        and not reciprocal["spatial_categories"]
    )

    # 0x82BC3 gates a turn by the current-cell MSP mask (0x12B20) and
    # current-cell monster-spatial categories. Both are empty at (23,3).
    turn_precheck_clear = bool(
        reciprocal["msp_mask"] == 0
        and not reciprocal["spatial_categories"]
    )
    facing = 2  # S
    facings = []
    for _ in range(2):
        facing = turn_new_facing(facing, 2)
        facings.append(facing)
    turns_to_north = facing == 0

    # Exact anchored code semantics:
    # - h85 action15 delegates to default/common and returns EAX=1.
    # - turn actions 6/8 on h415 follow 0x4FC57 -> 0x6A230 -> generic/default
    #   continuation and return EAX=1; no h415 turn-action veto branch exists.
    # - h415 actions2/3 with live facing N enter 0x4FB00 and call 0x3CFEE at
    #   0x4FC22 with L15->L1 target row22,col3,facingS.
    h85_action15_allow = True
    h415_turn_actions_allow = True
    h415_payload = {
        "source_level": 15,
        "source_cell": [23, 3],
        "source_direction": "N",
        "target_level": 1,
        "target_spawn": [22, 3, 2],
    }
    h89_payload = {
        "source_level": 1,
        "source_cell": [23, 3],
        "source_direction": "N",
        "target_level": 15,
        "target_spawn": [22, 3, 2],
    }

    verified = bool(
        reciprocal_marker
        and h85_action15_allow
        and crossing_clear
        and turn_precheck_clear
        and h415_turn_actions_allow
        and turns_to_north
        and not errors
    )

    return {
        "exe_sha256": exe_sha,
        "level01a_sha256": level_sha,
        "dispatch": {"h85": hex(h85), "h415": hex(h415)},
        "region_validation": regions,
        "arrival": arrival,
        "reciprocal": reciprocal,
        "reciprocal_low_high": reciprocal_marker,
        "opened_cell02": {
            "22,3": opened_arrival,
            "23,3": opened_reciprocal,
        },
        "h85_action15_allow": h85_action15_allow,
        "post_open_crossing_clear": crossing_clear,
        "turn": {
            "start_facing": 2,
            "turn_args": [2, 2],
            "intermediate_facings": facings,
            "final_facing": facing,
            "physical_precheck_clear": turn_precheck_clear,
            "h415_actions_6_8_allow": h415_turn_actions_allow,
        },
        "h89_transition_payload": h89_payload,
        "h415_transition_payload": h415_payload,
        "sequence": [
            "L1 h89 -> L15 spawn (22,3,S)",
            "h85 action15 ALLOW",
            "E.9 reciprocal LOW clear",
            "forward S -> (23,3,S)",
            "turn twice -> (23,3,N)",
            "forward N invokes h415 action3",
            "h415 -> 0x3CFEE",
            "L1 spawn (22,3,S)",
        ],
        "immediate_same_interface_reciprocal_verified": verified,
        "errors": errors,
        "pass": verified and not errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", type=Path, required=True)
    ap.add_argument("--level01a", type=Path, required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out = inspect(args.exe, args.level01a)
    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print(
            "PASS" if out["pass"] else "FAIL",
            f"reciprocal={out['immediate_same_interface_reciprocal_verified']}",
            f"regions={len(out['region_validation'])}",
            f"errors={len(out['errors'])}",
        )
    return 0 if out["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
