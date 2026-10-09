#!/usr/bin/env python3
"""Build K292-E.11 conditional starter portal transition graph."""
from __future__ import annotations
import argparse, collections, json
from pathlib import Path

from build_serialized_initial_transition_graph import (
    read_state,
    aggregate_msp,
    spatial_categories,
    forward_block_sets,
)
from inspect_transition_handlers import TRANSITIONS
from inspect_portal_enable_state import inspect as inspect_portal_enable
from inspect_portal_state_producers import inspect as inspect_producers

DIRS = {
    0: ("N", -1, 0, 0x08, 0x04),
    1: ("W", 0, -1, 0x02, 0x01),
    2: ("S", 1, 0, 0x04, 0x08),
    3: ("E", 0, 1, 0x01, 0x02),
}


def physical_after_low_clear(path: Path, row: int, col: int, didx: int) -> dict:
    (
        _data, rows, cols, cells, spatial_records, heads, msp_records
    ) = read_state(path)
    msp_masks, msp_invalid, msp_cycles = aggregate_msp(cells, msp_records)
    (
        by_cell, spatial_invalid, spatial_cycles,
        spatial_mismatch, spatial_dupes,
    ) = spatial_categories(spatial_records, heads)

    name, dr, dc, low, opposite_low = DIRS[didx]
    nr, nc = row + dr, col + dc
    if not (0 <= nr < rows and 0 <= nc < cols):
        raise ValueError("portal destination outside level grid")

    i = row * cols + col
    j = nr * cols + nc

    # E.9 clears only the reciprocal LOW bits. MSP and spatial state are
    # independent, so evaluate those verified precheck layers directly.
    msp_blocked = bool(
        (msp_masks[i] & (low | 0x10))
        or (msp_masks[j] & opposite_low)
    )

    source_categories = set(by_cell.get((row, col), ()))
    destination_categories = set(by_cell.get((nr, nc), ()))
    src_block, dst_block = forward_block_sets(didx)
    spatial_blocked = bool(
        (source_categories & src_block)
        or (destination_categories & dst_block)
    )

    validation_errors = []
    if msp_invalid:
        validation_errors.append(f"msp_invalid={msp_invalid[:5]}")
    if msp_cycles:
        validation_errors.append(f"msp_cycles={msp_cycles[:5]}")
    if spatial_invalid:
        validation_errors.append(f"spatial_invalid={spatial_invalid[:5]}")
    if spatial_cycles:
        validation_errors.append(f"spatial_cycles={spatial_cycles[:5]}")
    if spatial_mismatch:
        validation_errors.append(
            f"spatial_coordinate_mismatch={spatial_mismatch[:5]}"
        )
    if spatial_dupes:
        validation_errors.append(
            f"spatial_duplicate_refs={spatial_dupes[:5]}"
        )

    return {
        "direction": name,
        "destination": [nr, nc],
        "source_msp_mask": msp_masks[i],
        "destination_msp_mask": msp_masks[j],
        "source_spatial_categories": sorted(source_categories),
        "destination_spatial_categories": sorted(destination_categories),
        "msp_blocked_after_low_clear": msp_blocked,
        "spatial_blocked_after_low_clear": spatial_blocked,
        "physical_clear_after_low_clear": not (
            msp_blocked or spatial_blocked
        ),
        "validation_errors": validation_errors,
    }


def build(exe: Path, level01: Path, level01a: Path) -> dict:
    errors = []
    e9 = inspect_portal_enable(exe, level01, level01a)
    e10 = inspect_producers(exe, level01)
    if not e9.get("pass"):
        errors.append("E.9 validation failed")
    if not e10.get("pass"):
        errors.append("E.10 validation failed")

    action15 = {
        (x["source_level"], x["handler_id"]):
            bool(x["serialized_action15_allow"])
        for x in e9["portal_markers"]
    }
    producer = {
        x["handler_id"]: x
        for x in e10["portals"]
    }

    paths = {1: level01, 15: level01a}
    transitions = []
    counts = collections.Counter()

    for t in TRANSITIONS:
        (
            source_level, handler, row, col, didx, target_level,
            target_row, target_col, target_facing, _handler_va,
        ) = t
        physical = physical_after_low_clear(
            paths[source_level], row, col, didx
        )
        if physical["validation_errors"]:
            errors.extend(
                f"L{source_level} h{handler}: {e}"
                for e in physical["validation_errors"]
            )

        initial_allow = action15[(source_level, handler)]
        if initial_allow:
            enable_class = "DIRECT_ACTION15_ENABLE"
            producer_required = False
            producer_state = "NOT_REQUIRED"
            action15_after_required_state = True
        else:
            enable_class = "E10_PRODUCER_CONDITIONAL"
            producer_required = True
            p = producer.get(handler)
            if p is None:
                errors.append(
                    f"L{source_level} h{handler}: missing E.10 producer"
                )
                producer_state = "MISSING"
                action15_after_required_state = False
            else:
                producer_state = "RUNTIME_SELECTION_QUALIFIED"
                action15_after_required_state = bool(
                    p["action15_after_success_allow"]
                )

        executable_after_enable = bool(
            action15_after_required_state
            and physical["physical_clear_after_low_clear"]
        )

        if initial_allow:
            counts["direct_enable"] += 1
        else:
            counts["producer_conditional"] += 1
        if physical["physical_clear_after_low_clear"]:
            counts["physical_clear_after_open"] += 1
        else:
            counts["physical_blocked_after_open"] += 1
        if executable_after_enable:
            counts["transition_commit_reached_after_required_enable"] += 1

        transitions.append({
            "source_level": source_level,
            "handler_id": handler,
            "source": [row, col],
            "direction": physical["direction"],
            "target_level": target_level,
            "staged_target": [target_row, target_col, target_facing],
            "serialized_action15_allow": initial_allow,
            "enable_class": enable_class,
            "producer_required": producer_required,
            "producer_state": producer_state,
            "action15_after_required_state":
                action15_after_required_state,
            "physical_after_low_clear": physical,
            "transition_commit_reached_after_required_enable":
                executable_after_enable,
            "state_path": (
                [
                    "CLOSED_SPECIAL",
                    "ACTION15_ALLOW",
                    "OPENING",
                    "OPEN_ARMED",
                    "FORWARD_PRECHECK_CLEAR",
                    "ACTION3",
                    "TRANSLATION",
                    "ACTION2",
                    "LEVEL_TRANSFER",
                ]
                if not producer_required
                else [
                    "CLOSED_SPECIAL_ACTION15_BLOCKED",
                    "E10_RUNTIME_SELECTION_GATE",
                    "SELECTOR4_TO_1",
                    "ACTION15_ALLOW",
                    "OPENING",
                    "OPEN_ARMED",
                    "FORWARD_PRECHECK_CLEAR",
                    "ACTION3",
                    "TRANSLATION",
                    "ACTION2",
                    "LEVEL_TRANSFER",
                ]
            ),
        })

    if counts["physical_clear_after_open"] != len(TRANSITIONS):
        errors.append("not all portal interfaces are physically clear after LOW clear")
    if counts["transition_commit_reached_after_required_enable"] != len(
        TRANSITIONS
    ):
        errors.append("not all portals reach transition commit after required enable")

    target_counts = collections.Counter(
        (x["source_level"], x["target_level"]) for x in transitions
    )

    return {
        "transition_count": len(transitions),
        "counts": dict(counts),
        "level_transition_counts": {
            f"{a}->{b}": n for (a, b), n in sorted(target_counts.items())
        },
        "transitions": transitions,
        "graph_semantics": {
            "direct_enableable_portals":
                "E.9 serialized action15 already ALLOW",
            "producer_conditional_portals":
                "E.10 successful runtime-selection-qualified producer "
                "must set selector4 before action15",
            "post_open_physical_test":
                "E.9 reciprocal LOW clear applied; E.3 MSP and E.4 "
                "monster-spatial rules evaluated without treating LOW as closed",
            "transition_commit":
                "E.8 action2 -> A2DC7 -> A2BA6 -> event8 -> 0x5DC10",
            "guaranteed_runtime_selection_reachability": False,
            "one_way_verdict_authorized": False,
            "softlock_verdict_authorized": False,
        },
        "errors": errors,
        "pass": not errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", type=Path, required=True)
    ap.add_argument("--level01", type=Path, required=True)
    ap.add_argument("--level01a", type=Path, required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out = build(args.exe, args.level01, args.level01a)

    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        c = out["counts"]
        print(
            "PASS" if out["pass"] else "FAIL",
            f"portals={out['transition_count']}",
            f"direct={c.get('direct_enable', 0)}",
            f"producer_conditional={c.get('producer_conditional', 0)}",
            f"physical_clear_after_open={c.get('physical_clear_after_open', 0)}",
            "commit_after_required_enable="
            f"{c.get('transition_commit_reached_after_required_enable', 0)}",
            f"errors={len(out['errors'])}",
        )
    return 0 if out["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
