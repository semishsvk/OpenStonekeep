#!/usr/bin/env python3
"""Validate evidence-backed static Stonekeep level-cell topology invariants.

K292-A deliberately validates only what K291-D proved:
- serialized grid direction order N,W,S,E;
- reciprocal low-nibble static edge bits in cell+0x02;
- matching outer-boundary closure bits.

It reports, but does not interpret as static walls:
- mutable directional bits in cell+0x01;
- direction-indexed tuple activity at cell+0x03..+0x06.

This is not a final player-movement or softlock solver.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from inspect_level_save import parse


def validate_info(info: dict) -> dict:
    topo = info["topology"]
    errors: list[dict] = []
    warnings: list[dict] = []

    if topo["undirected_static_edge_mismatches"]:
        errors.append({
            "code": "STATIC_EDGE_RECIPROCITY",
            "count": topo["undirected_static_edge_mismatches"],
            "message": "one or more internal static edges disagree with the opposite cell",
        })

    for name in topo["direction_order"]:
        d = topo["directions"][name]
        missing = d["boundary_cells"] - d["boundary_static_bits_set"]
        if missing:
            errors.append({
                "code": "BOUNDARY_CLOSURE",
                "direction": name,
                "count": missing,
                "message": "outer boundary cells are missing the verified static barrier bit",
            })
        if d["dynamic_bits_set"]:
            warnings.append({
                "code": "MUTABLE_DIRECTION_STATE_PRESENT",
                "direction": name,
                "count": d["dynamic_bits_set"],
                "message": "mutable cell+0x01 direction bits are present; do not collapse them into static topology",
            })

    return {
        "path": info["path"],
        "sha256": info["sha256"],
        "row_count": info["row_count"],
        "column_count": info["column_count"],
        "cell_count": info["cell_count"],
        "direction_order": topo["direction_order"],
        "static_edges": {
            "set": topo["undirected_static_edges_set"],
            "clear": topo["undirected_static_edges_clear"],
            "mismatched": topo["undirected_static_edge_mismatches"],
        },
        "boundary": {
            name: {
                "set": topo["directions"][name]["boundary_static_bits_set"],
                "total": topo["directions"][name]["boundary_cells"],
            }
            for name in topo["direction_order"]
        },
        "mutable_direction_bits": {
            name: topo["directions"][name]["dynamic_bits_set"]
            for name in topo["direction_order"]
        },
        "direction_tuple_non_default_0x9c": {
            name: topo["directions"][name]["tuple_non_default_0x9c"]
            for name in topo["direction_order"]
        },
        "errors": errors,
        "warnings": warnings,
        "valid_static_topology": not errors,
        "movement_model_complete": False,
    }


def validate_path(path: Path) -> dict:
    return validate_info(parse(path))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("saves", nargs="+", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    results = [validate_path(path) for path in args.saves]
    ok = all(result["valid_static_topology"] for result in results)

    if args.json:
        print(json.dumps({"valid": ok, "results": results}, indent=2, sort_keys=True))
    else:
        for result in results:
            state = "PASS" if result["valid_static_topology"] else "FAIL"
            e = result["static_edges"]
            print(
                f"{state} {result['path']}: "
                f"{result['row_count']}x{result['column_count']} cells={result['cell_count']} "
                f"edges(set={e['set']},clear={e['clear']},mismatch={e['mismatched']})"
            )
            print(
                "  boundary " + ", ".join(
                    f"{name}={entry['set']}/{entry['total']}"
                    for name, entry in result["boundary"].items()
                )
            )
            print(
                "  mutable " + ", ".join(
                    f"{name}={count}"
                    for name, count in result["mutable_direction_bits"].items()
                )
            )
            for error in result["errors"]:
                print(f"  ERROR {error['code']}: {error['message']} count={error['count']}")
            for warning in result["warnings"]:
                print(f"  WARN {warning['code']}: {warning['message']} count={warning['count']}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
