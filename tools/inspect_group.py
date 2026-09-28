#!/usr/bin/env python3
"""Inspect a Stonekeep CD-style GROUP container without modifying source data.

Evidence-backed CD layout:
  u16 entry_count
  entry_count * 22-byte directory records
  concatenated payload area
  4 trailing bytes

Each 22-byte directory record contains a 12-byte NUL-padded resource name and
an absolute cumulative payload-end offset at record +0x0E. The remaining six
metadata bytes are preserved but intentionally not assigned semantics here.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path

ENTRY_SIZE = 22
NAME_SIZE = 12
TRAILER_SIZE = 4


def parse(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 2 + TRAILER_SIZE:
        raise ValueError("file too small for GROUP header/trailer")

    count = struct.unpack_from("<H", data, 0)[0]
    directory_end = 2 + count * ENTRY_SIZE
    if directory_end + TRAILER_SIZE > len(data):
        raise ValueError("not a valid CD-style GROUP directory")

    entries = []
    payload_start = directory_end
    previous_end = directory_end
    for index in range(count):
        off = 2 + index * ENTRY_SIZE
        record = data[off:off + ENTRY_SIZE]
        raw_name = record[:NAME_SIZE]
        name = raw_name.split(b"\0", 1)[0].decode("ascii", "replace")
        cumulative_end = struct.unpack_from("<I", record, 0x0E)[0]
        if cumulative_end < previous_end:
            raise ValueError(
                f"non-monotonic cumulative end at entry {index}: "
                f"0x{cumulative_end:X} < 0x{previous_end:X}"
            )
        if cumulative_end > len(data) - TRAILER_SIZE:
            raise ValueError(
                f"payload end outside GROUP at entry {index}: 0x{cumulative_end:X}"
            )
        entries.append({
            "index": index,
            "name": name,
            "directory_offset": off,
            "metadata_12_13_hex": record[12:14].hex(),
            "payload_start": previous_end,
            "payload_end": cumulative_end,
            "payload_size": cumulative_end - previous_end,
            "metadata_18_21_hex": record[18:22].hex(),
        })
        previous_end = cumulative_end

    if count and previous_end != len(data) - TRAILER_SIZE:
        raise ValueError(
            f"last cumulative end 0x{previous_end:X} != filesize-4 "
            f"0x{len(data)-TRAILER_SIZE:X}"
        )

    return {
        "path": str(path),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "entry_count": count,
        "entry_size": ENTRY_SIZE,
        "directory_end": directory_end,
        "payload_area_size": (len(data) - TRAILER_SIZE) - payload_start,
        "trailer_hex": data[-TRAILER_SIZE:].hex(),
        "entries": entries,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("group", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    info = parse(args.group)
    if args.json:
        print(json.dumps(info, indent=2, sort_keys=True))
        return 0

    print(
        f"{info['path']}: entries={info['entry_count']} "
        f"directory_end=0x{info['directory_end']:X} size={info['size']}"
    )
    print(f"sha256={info['sha256']} trailer={info['trailer_hex']}")
    for entry in info["entries"]:
        print(
            f"{entry['index']:4} {entry['name']:<12} "
            f"[0x{entry['payload_start']:X},0x{entry['payload_end']:X}) "
            f"{entry['payload_size']} B"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
