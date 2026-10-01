#!/usr/bin/env python3
"""Verify Stonekeep starter-level default callback selection through LE fixups.

The ordinary callback chain at runtime 0x3D4F5 first calls *[0x1B9DDC].
This tool proves which callback is installed for level IDs 1 and 15 by
following the executable's own per-level init table and relocation records.

Read-only evidence tool; it never patches original bytes.
"""
from __future__ import annotations
import argparse, hashlib, json, struct, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_le_handler_dispatch import LE

EXPECTED_EXE_SHA = "5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2"

LEVEL_INIT_TABLE_OBJECT = 3
LEVEL_INIT_TABLE_OFFSET = 0xF10E
LOADER_DISPATCH_VA = 0x44F2D
CALLBACK_GLOBAL = 0x1B9DDC
EXPECTED_LEVELS = {
    1: {"name": "LEVEL01", "init_runtime": 0x5DD09, "callback_runtime": 0x5E867},
    15: {"name": "LEVEL01A", "init_runtime": 0x4F69A, "callback_runtime": 0x4F861},
}
ASSIGN_OPCODE = bytes.fromhex("c705dc9d1b00")
EXPECTED_LOADER_PREFIX = bytes.fromhex(
    "0fbf05a0c61b00"      # movsx eax, [0x1BC6A0]
    "ff14850ef10000"      # call *0xF10E(,eax,4), relocated to object 3
)


def object_for_runtime(le: LE, va: int):
    for n, obj in enumerate(le.objects, 1):
        if obj["base"] <= va < obj["base"] + obj["size"]:
            return n, obj, va - obj["base"]
    raise ValueError(f"runtime VA 0x{va:X} outside LE objects")


def read_runtime(le: LE, va: int, size: int) -> bytes:
    out = bytearray()
    while size:
        objnum, obj, off = object_for_runtime(le, va)
        page_remaining = le.page_size - (off % le.page_size)
        take = min(size, page_remaining, obj["size"] - off)
        fo = le.object_file_offset(objnum, off)
        chunk = le.data[fo:fo + take]
        if len(chunk) != take:
            raise ValueError("truncated mapped object bytes")
        out += chunk
        va += take
        size -= take
    return bytes(out)


def source_fixups(le: LE, objnum: int, object_offset: int):
    page_idx, page_off = le.page_for_object_offset(objnum, object_offset)
    matches = [
        f for f in le.parse_fixup_page(page_idx)
        if page_off in f["sources"]
    ]
    return page_idx, page_off, matches


def require_internal_off32(matches, label: str):
    if len(matches) != 1:
        raise ValueError(f"{label}: expected one fixup, got {len(matches)}")
    f = matches[0]
    if not (
        (f["type"] & 0x0F) == 0x07
        and f["target_kind"] == 0
        and (f["flags"] & 0x10)
        and f["target_offset"] is not None
        and 1 <= f["target_object"] <= len(matches.__self__.objects)  # unreachable; kept out below
    ):
        pass
    return f


def validate_fixup_shape(le: LE, f: dict, label: str):
    ok = (
        (f["type"] & 0x0F) == 0x07
        and f["target_kind"] == 0
        and (f["flags"] & 0x10)
        and f["target_offset"] is not None
        and 1 <= f["target_object"] <= len(le.objects)
    )
    if not ok:
        raise ValueError(f"{label}: unsupported fixup shape")
    return f


def resolve_internal(le: LE, objnum: int, object_offset: int, label: str):
    page_idx, page_off, matches = source_fixups(le, objnum, object_offset)
    if len(matches) != 1:
        raise ValueError(f"{label}: expected one fixup, got {len(matches)}")
    f = validate_fixup_shape(le, matches[0], label)
    target_obj = le.objects[f["target_object"] - 1]
    if f["target_offset"] >= target_obj["size"]:
        raise ValueError(f"{label}: target outside object")
    return {
        "source_page_1based": page_idx + 1,
        "source_page_offset": page_off,
        "target_object": f["target_object"],
        "target_object_offset": f["target_offset"],
        "target_runtime": target_obj["base"] + f["target_offset"],
        "type": f["type"],
        "flags": f["flags"],
    }


def verify(exe: Path):
    data = exe.read_bytes()
    errors = []
    sha = hashlib.sha256(data).hexdigest()
    if sha != EXPECTED_EXE_SHA:
        errors.append("unexpected SK.EXE SHA-256")
    try:
        le = LE(data)
    except Exception as e:
        return {"pass": False, "errors": errors + [f"LE parse failed: {e}"]}

    # Verify the loader consumes live level ID 0x1BC6A0 and indexes the
    # relocation-sensitive object-3 init table.
    try:
        loader_bytes = read_runtime(le, LOADER_DISPATCH_VA, len(EXPECTED_LOADER_PREFIX))
        if loader_bytes != EXPECTED_LOADER_PREFIX:
            errors.append("loader dispatch bytes mismatch")
        objnum, obj, _ = object_for_runtime(le, LOADER_DISPATCH_VA)
        disp_runtime = LOADER_DISPATCH_VA + 10  # disp32 of ff 14 85 disp32
        _, _, disp_obj_off = object_for_runtime(le, disp_runtime)
        loader_fix = resolve_internal(le, objnum, disp_obj_off, "loader init-table reference")
        if not (
            loader_fix["target_object"] == LEVEL_INIT_TABLE_OBJECT
            and loader_fix["target_object_offset"] == LEVEL_INIT_TABLE_OFFSET
        ):
            errors.append("loader does not resolve to expected level-init table")
    except Exception as e:
        loader_fix = None
        errors.append(str(e))

    levels = {}
    for level_id, expected in EXPECTED_LEVELS.items():
        row = {"level_id": level_id, "name": expected["name"]}
        try:
            slot_off = LEVEL_INIT_TABLE_OFFSET + level_id * 4
            slot = resolve_internal(
                le, LEVEL_INIT_TABLE_OBJECT, slot_off,
                f"level {level_id} init slot",
            )
            init_runtime = slot["target_runtime"]
            row["init_slot"] = slot
            row["init_runtime"] = init_runtime
            if init_runtime != expected["init_runtime"]:
                errors.append(
                    f"level {level_id}: init target 0x{init_runtime:X} != "
                    f"expected 0x{expected['init_runtime']:X}"
                )

            init_prefix = read_runtime(le, init_runtime, 0x30)
            loc = init_prefix.find(ASSIGN_OPCODE)
            if loc < 0:
                raise ValueError(
                    f"level {level_id}: callback-global assignment not found near init entry"
                )
            # c7 05 <absolute-destination> <relocated-imm32>; the relocation
            # source is the immediate field six bytes after the opcode.
            imm_runtime = init_runtime + loc + 6
            init_objnum, _, init_imm_off = object_for_runtime(le, imm_runtime)
            cbfix = resolve_internal(
                le, init_objnum, init_imm_off,
                f"level {level_id} callback assignment",
            )
            callback_runtime = cbfix["target_runtime"]
            row["callback_assignment_runtime"] = init_runtime + loc
            row["callback_fixup"] = cbfix
            row["callback_runtime"] = callback_runtime
            row["callback_first_byte"] = read_runtime(le, callback_runtime, 1).hex()
            row["callback_is_single_ret_entry"] = row["callback_first_byte"] == "c3"
            if callback_runtime != expected["callback_runtime"]:
                errors.append(
                    f"level {level_id}: callback target 0x{callback_runtime:X} != "
                    f"expected 0x{expected['callback_runtime']:X}"
                )
            if not row["callback_is_single_ret_entry"]:
                errors.append(f"level {level_id}: callback entry is not RET")
        except Exception as e:
            errors.append(str(e))
        levels[str(level_id)] = row

    return {
        "exe": str(exe),
        "exe_sha256": sha,
        "loader_dispatch_runtime": hex(LOADER_DISPATCH_VA),
        "level_index_global": hex(0x1BC6A0),
        "level_init_table": {
            "object": LEVEL_INIT_TABLE_OBJECT,
            "object_offset": hex(LEVEL_INIT_TABLE_OFFSET),
        },
        "callback_global": hex(CALLBACK_GLOBAL),
        "loader_fixup": loader_fix,
        "levels": levels,
        "errors": errors,
        "pass": not errors,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True, type=Path)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    out = verify(a.exe)
    if a.json:
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print(
            ("PASS" if out["pass"] else "FAIL"),
            "levels=%d errors=%d" % (len(out["levels"]), len(out["errors"])),
        )
        for k, v in out["levels"].items():
            print(
                " level=%s init=0x%X callback=0x%X ret=%s"
                % (
                    k,
                    v.get("init_runtime", 0),
                    v.get("callback_runtime", 0),
                    v.get("callback_is_single_ret_entry", False),
                )
            )
    return 0 if out["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
