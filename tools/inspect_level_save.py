#!/usr/bin/env python3
"""Inspect Stonekeep per-level SAV files without mutating source data.

Evidence-backed layout:
  u16 format_marker
  char version[5]
  u16 width
  u16 height
  width*height records of 21 bytes

The four signed 16-bit fields at offsets 0x0D, 0x0F, 0x11 and 0x13 are
structural linked-list heads. Semantic class names are intentionally left open.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path

CELL_SIZE = 0x15
SENTINEL_NONE = -100  # 0xFF9C
CHAIN_HEADS = {
    0x0D: {"runtime_stride": 0x2F, "next_offset": 0x18},
    0x0F: {"runtime_stride": 0x111, "next_offset": 0x3A},
    0x11: {"runtime_stride": 0x30, "next_offset": 0x10},
    0x13: {"runtime_stride": 0x66, "next_offset": 0x63},
}

def s16(buf: bytes, off: int) -> int:
    return struct.unpack_from("<h", buf, off)[0]

def parse(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 11:
        raise ValueError("file too small for level-save header")

    marker = struct.unpack_from("<H", data, 0)[0]
    version_raw = data[2:7]
    width, height = struct.unpack_from("<HH", data, 7)
    cell_count = width * height
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
        "width": width,
        "height": height,
        "cell_count": cell_count,
        "cell_size": CELL_SIZE,
        "grid_start": grid_start,
        "grid_end": grid_end,
        "post_grid_bytes": len(data) - grid_end,
        "chain_heads": chains,
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
        f"{info['path']}: {info['width']}x{info['height']} "
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
    for off, chain in info["chain_heads"].items():
        print(
            f"head {off}: stride=0x{chain['runtime_stride']:X} "
            f"next=0x{chain['next_offset']:X} "
            f"active={chain['active_cells']} "
            f"range={chain['min_active_head']}..{chain['max_active_head']}"
        )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
