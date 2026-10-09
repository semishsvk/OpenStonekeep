#!/usr/bin/env python3
"""Validate K292-E.10 state producers for the three blocked LEVEL01 portals."""
from __future__ import annotations
import argparse, hashlib, json, struct, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_le_handler_dispatch import LE

EXPECTED_EXE_SHA = "5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2"
EXPECTED_LEVEL01_SHA = "2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9"
CELL_SIZE = 0x15
DISPATCH_OBJECT = 3
DISPATCH_OFFSET = 0xF16A

PORTALS = {
    87: {
        "cell": (2, 3),
        "initial_selector4": 0,
        "selector5_payload": 0,
        "action15_gate": "selector4_nonzero",
        "target_runtime": 0x5F3B9,
    },
    106: {
        "cell": (11, 5),
        "initial_selector4": -1,
        "selector5_payload": 166,
        "action15_gate": "selector4_not_minus1",
        "target_runtime": 0x5F027,
    },
    107: {
        "cell": (7, 25),
        "initial_selector4": -1,
        "selector5_payload": 166,
        "action15_gate": "selector4_not_minus1",
        "target_runtime": 0x5F08B,
    },
}

REGIONS = {
    "current_cell_activation_dispatch": (
        0x6A3DF, 0x54,
        "ec15ccc66875ef9f0415b42b7a741dd8778866f5ec113e0207eccab880433599",
    ),
    "selector4_activation_producer": (
        0x6A433, 0xE3,
        "11d9bb8179ca003204d4e0b2d74d7f440e42f61eb555baec38b6e133f36109a3",
    ),
    "alternate_object_gate": (
        0x27D8D, 0x65,
        "e5e21a9d1b7649f0198094e86da3b8b0acd50eca0757299eda592606266b55e5",
    ),
    "input_dispatch_callsite": (
        0x32134, 0x22,
        "8fa78f1183b83c6d76d9e7b5cf2d4b0dde06a9955dc80c9c18af748bb4cb845f",
    ),
    "secondary_dispatch_wrapper": (
        0x49D17, 9,
        "5f89619b5a73802ac776de3b754f157b8dee63aa7089e1ed03f14738b5f5a920",
    ),
    "reciprocal_handler85": (
        0x3D2EA, 0x74,
        "775e4bc84aa519bf72d76036163c2056b97462583d9bce05e829b55630d3b4e3",
    ),
    "reciprocal_handler114": (
        0x5F3FD, 0x24,
        "fbdaa156a483fc9100b582dffc71a0d260f00db60ecf574d52c2e46a5cb4087a",
    ),
}


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


def resolve_dispatch(le: LE, handler: int) -> int:
    page, base = le.page_for_object_offset(DISPATCH_OBJECT, DISPATCH_OFFSET)
    src = base + handler * 4
    matches = [f for f in le.parse_fixup_page(page) if src in f["sources"]]
    if len(matches) != 1:
        raise ValueError(f"handler {handler}: dispatch fixups={len(matches)}")
    f = matches[0]
    if not (
        (f["type"] & 0x0F) == 0x07
        and f["target_kind"] == 0
        and f["target_object"] == 1
        and (f["flags"] & 0x10)
    ):
        raise ValueError(f"handler {handler}: unexpected dispatch fixup")
    return le.objects[0]["base"] + f["target_offset"]


def producer_next_selector4(value: int) -> int:
    """0x6A433: selector4 == 1 -> -1, otherwise -> +1."""
    return -1 if value == 1 else 1


def action15_allows(handler: int, value: int) -> bool:
    if handler == 87:
        return value != 0
    if handler in (106, 107):
        return value != -1
    raise ValueError(f"unsupported portal handler {handler}")


def alternate_gate_possible(payload: int) -> bool:
    return 0x99 <= payload <= 0xAE


def parse_level(path: Path):
    data = path.read_bytes()
    rows, cols = struct.unpack_from("<HH", data, 7)
    end = 11 + rows * cols * CELL_SIZE
    if end > len(data):
        raise ValueError("truncated level grid")
    cells = [
        data[11 + i * CELL_SIZE:11 + (i + 1) * CELL_SIZE]
        for i in range(rows * cols)
    ]
    return data, rows, cols, cells


def inspect(exe: Path, level01: Path) -> dict:
    exe_data = exe.read_bytes()
    exe_sha = hashlib.sha256(exe_data).hexdigest()
    le = LE(exe_data)
    errors = []

    if exe_sha != EXPECTED_EXE_SHA:
        errors.append("unexpected SK.EXE SHA-256")

    level_data, rows, cols, cells = parse_level(level01)
    level_sha = hashlib.sha256(level_data).hexdigest()
    if level_sha != EXPECTED_LEVEL01_SHA:
        errors.append("unexpected LEVEL01 SHA-256")

    region_validation = {}
    for name, (va, size, expected) in REGIONS.items():
        got = hashlib.sha256(read_runtime(le, va, size)).hexdigest()
        ok = got == expected
        region_validation[name] = {
            "runtime_va": hex(va),
            "size": size,
            "sha256": got,
            "pass": ok,
        }
        if not ok:
            errors.append(f"region hash mismatch: {name}")

    portals = []
    for handler, spec in PORTALS.items():
        row, col = spec["cell"]
        cell = cells[row * cols + col]
        observed_handler = struct.unpack_from("<h", cell, 0x07)[0]
        selector4 = struct.unpack_from("<h", cell, 0x09)[0]
        selector5 = struct.unpack_from("<h", cell, 0x0B)[0]
        target = resolve_dispatch(le, handler)

        after = producer_next_selector4(selector4)
        second = producer_next_selector4(after)
        rec = {
            "handler_id": handler,
            "cell": [row, col],
            "observed_handler": observed_handler,
            "selector4_initial": selector4,
            "selector5_payload": selector5,
            "resolved_handler_runtime": hex(target),
            "producer_success_selector4": after,
            "producer_second_success_selector4": second,
            "action15_initial_allow": action15_allows(handler, selector4),
            "action15_after_success_allow": action15_allows(handler, after),
            "action15_after_second_success_allow": action15_allows(handler, second),
            "alternate_gate_possible_for_payload": alternate_gate_possible(selector5),
        }

        if observed_handler != handler:
            errors.append(
                f"handler {handler}: source cell contains {observed_handler}"
            )
        if selector4 != spec["initial_selector4"]:
            errors.append(f"handler {handler}: unexpected selector4 {selector4}")
        if selector5 != spec["selector5_payload"]:
            errors.append(f"handler {handler}: unexpected selector5 {selector5}")
        if target != spec["target_runtime"]:
            errors.append(f"handler {handler}: dispatch target mismatch")
        if not rec["action15_after_success_allow"]:
            errors.append(
                f"handler {handler}: producer success does not enable action15"
            )
        portals.append(rec)

    return {
        "exe_sha256": exe_sha,
        "level01_sha256": level_sha,
        "portals": portals,
        "region_validation": region_validation,
        "producer": {
            "entry_runtime": "0x6A3DF",
            "mutation_runtime": "0x6A433",
            "selected_record_base": "0x19E2E0",
            "selected_record_stride": 0x2F,
            "selection_handle_global": "0x1BC6A8",
            "selection_handle_none": -5,
            "cell_payload_selector": 5,
            "cell_state_selector": 4,
            "success_mutation":
                "selector4 = -1 if selector4 == 1 else +1",
            "direct_gate":
                "s16(selected_record+0x00) == selector5_payload",
            "alternate_gate":
                "0x27D8D(selected_record_index,payload) != 0; "
                "structurally possible only for payload 0x99..0xAE and "
                "selected-record type 0xAF with matching bit state",
            "state_scope": "RUNTIME_SELECTION_QUALIFIED",
        },
        "reciprocal_neighbor_result":
            "handlers 85/114 do not provide the missing direct selector4 "
            "producer for these three source cells",
        "producer_mechanism": "VERIFIED" if not errors else "FAILED",
        "producer_reachability": "STATE_QUALIFIED_RUNTIME_SELECTION",
        "errors": errors,
        "pass": not errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", type=Path, required=True)
    ap.add_argument("--level01", type=Path, required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out = inspect(args.exe, args.level01)

    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print(
            "PASS" if out["pass"] else "FAIL",
            f"portals={len(out['portals'])}",
            f"regions={len(out['region_validation'])}",
            f"errors={len(out['errors'])}",
        )
        for p in out["portals"]:
            print(
                " h%d cell=%s s4=%d payload=%d -> %d action15=%s "
                "second=%d action15_2=%s alt=%s"
                % (
                    p["handler_id"], p["cell"], p["selector4_initial"],
                    p["selector5_payload"], p["producer_success_selector4"],
                    p["action15_after_success_allow"],
                    p["producer_second_success_selector4"],
                    p["action15_after_second_success_allow"],
                    p["alternate_gate_possible_for_payload"],
                )
            )
    return 0 if out["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
