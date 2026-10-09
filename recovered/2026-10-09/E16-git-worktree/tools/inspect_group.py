#!/usr/bin/env python3
"""Inspect a Stonekeep CD-style GROUP container without modifying source data.

Evidence-backed CD layout:
  u16 entry_count
  entry_count * 22-byte directory records
  concatenated payload area
  4 trailing bytes

Each 22-byte directory record contains a 12-byte NUL-padded resource name and
an absolute payload-start offset at record +0x0E. The payload for entry i is
[offset[i], offset[i+1]); for the final entry it is
[offset[last], filesize-4). Duplicate offsets represent zero-length resources.

The installed DATA GROUP is the CD GROUP with exactly the directory prefix
removed; payload bytes and the 4-byte trailer are preserved.
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
    payload_limit = len(data) - TRAILER_SIZE
    if directory_end + TRAILER_SIZE > len(data):
        raise ValueError("not a valid CD-style GROUP directory")

    raw_entries = []
    for index in range(count):
        off = 2 + index * ENTRY_SIZE
        record = data[off:off + ENTRY_SIZE]
        raw_name = record[:NAME_SIZE]
        name = raw_name.split(b"\0", 1)[0].decode("ascii", "replace")
        payload_start = struct.unpack_from("<I", record, 0x0E)[0]
        raw_entries.append({
            "index": index,
            "name": name,
            "directory_offset": off,
            "metadata_12_13_hex": record[12:14].hex(),
            "payload_start": payload_start,
            "metadata_18_21_hex": record[18:22].hex(),
        })

    if count:
        if raw_entries[0]["payload_start"] != directory_end:
            raise ValueError(
                "first payload start does not equal directory end: "
                f"0x{raw_entries[0]['payload_start']:X} != 0x{directory_end:X}"
            )
        previous = directory_end
        for entry in raw_entries:
            start = entry["payload_start"]
            if start < previous:
                raise ValueError(
                    f"non-monotonic payload start at entry {entry['index']}: "
                    f"0x{start:X} < 0x{previous:X}"
                )
            if start > payload_limit:
                raise ValueError(
                    f"payload start outside GROUP at entry {entry['index']}: "
                    f"0x{start:X}"
                )
            previous = start

    entries = []
    for index, entry in enumerate(raw_entries):
        start = entry["payload_start"]
        end = (
            raw_entries[index + 1]["payload_start"]
            if index + 1 < count
            else payload_limit
        )
        if end < start:
            raise ValueError(
                f"negative payload interval at entry {index}: "
                f"0x{start:X}..0x{end:X}"
            )
        entries.append({
            **entry,
            "payload_end": end,
            "payload_size": end - start,
            "installed_payload_start": start - directory_end,
            "installed_payload_end": end - directory_end,
        })

    return {
        "path": str(path),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "entry_count": count,
        "entry_size": ENTRY_SIZE,
        "directory_end": directory_end,
        "payload_area_size": payload_limit - directory_end,
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
