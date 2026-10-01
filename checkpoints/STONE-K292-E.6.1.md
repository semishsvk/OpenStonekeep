# STONE-K292-E.6.1 — movement callback effect-surface closure

- Date: 2026-10-01
- Status: **PASS — 59/59 movement-source handlers classified for actions 2/3/4/5 at the direct-write / indirect-effect surface**
- Knowledge classification: GAME-SPECIFIC
- Scope: all K292-E.2 movement-candidate source handlers in the authoritative starter corpus

## Purpose

E.6 tranche 1 froze exact direct state deltas for six handlers and established the selector -> serialized-cell-field API. The validator subsequently gained a second 20-handler evidence tranche. E.6.1 closes the remaining 33 handlers so that every movement-source handler has an evidence-backed action-surface classification.

This is **not** complete semantic closure of every indirect helper. The result separates:

- exact direct serialized-cell writes;
- explicit indirect/event helper calls;
- dynamic global callback invocation;
- evidence-backed absence of a direct cell-setter write on the traced movement path.

`NO_DIRECT_WRITE_OBSERVED` remains negative evidence and is not promoted to `ABSENT_VERIFIED`.

## Coverage

Movement-source handler universe from K292-E.2:

- tranche 1: **6** handlers
- tranche 2: **20** handlers
- tranche 3: **33** handlers
- union: **59/59**
- overlap between tranches: **0**
- movement actions per handler: **2, 3, 4, 5**
- action cells represented: **236/236**

The exact 59-ID union matches the K292-E.2 movement-source set.

## Executable anchors

`tools/validate_callback_state_delta_manifest.py` now carries:

- tranche 1 executable regions: 13
- tranche 2 executable regions: 17
- tranche 3 executable regions: 26
- total exact byte-region SHA-256 anchors: **56**

Independent revalidation against authoritative `SK.EXE`
SHA-256 `5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2`:

    anchors=56
    pass=56
    fail=0

The validator also requires exact 14-entry getter/setter selector tables and exact disjoint 59-handler coverage.

## Tranche 3 result

The final 33 handlers collapse into six evidence families.

### AC4AA movement family — 14 handlers

Handlers:

`2, 3, 21, 22, 23, 24, 94, 98, 99, 100, 101, 102, 103, 109`

All relevant wrappers reach runtime core `0xAC4AA` for movement actions.

For actions 2/3/5:

- no direct cell-setter write is observed in the movement path;
- the path reaches the common dynamic callback / default chain.

For action 4:

- the core conditionally calls `0x2A7FA` when its direction/mode condition matches live facing;
- it then reaches the common dynamic callback / default chain.

The direct setter in the `0xAF87F` family used by handlers 21..24 is gated by non-movement action `0x38`; it is not executed for actions 2/3/4/5.

The direct setter in `0x6A2FB` is likewise reached by non-movement action `0x13`, not actions 2/3/4/5.

Handler 109's direct setter branch is gated by non-movement action `0x38`; movement actions delegate through `0x6A227 -> 0x6A183 -> 0xAC4AA`.

### Default dynamic-callback family — 7 handlers

Handlers:

`60, 86, 95, 96, 97, 104, 105`

For actions 2/3/4/5 these handlers reach runtime `0x3D4F5` without a direct cell write in their movement branch.

`0x3D4F5` performs:

    call *[0x1B9DDC]
    -> default continuation

Therefore these movement paths are not classified as side-effect-free. They contain an unresolved **dynamic global callback** before the default continuation.

Direct setter branches observed in handlers 60, 86, 96 and 105 are gated by non-movement action IDs and do not execute for 2/3/4/5.

### 3CFEE movement family — 6 handlers

Handlers:

`87, 89, 90, 411, 412, 413`

Movement core runtime `0x3CFEE` gives:

- action 2: conditional helper/event `0xA2DC7`, then `0x3D4F5`;
- action 3: conditional helper/event `0xA2D76`, then `0x3D4F5`;
- action 4: `0x3D4F5`;
- action 5: `0x3D4F5`.

No direct `0x3C231` cell-setter write is observed on these action paths.

Handler-specific branches before `0x3CFEE` in 87/89 are gated by non-movement action IDs. Handlers 90 and 411..413 are direct/simple movement wrappers.

### AC4AA -> 3CFEE composite family — 3 handlers

Handlers:

`88, 106, 107`

For movement actions each wrapper first calls the AC4AA path and then the 3CFEE path.

Consequences:

- action 2: first dynamic callback, conditional `0xA2DC7`, then second dynamic callback;
- action 3: first dynamic callback, conditional `0xA2D76`, then second dynamic callback;
- action 4: conditional `0x2A7FA`, first dynamic callback, then second dynamic callback;
- action 5: first dynamic callback, then second dynamic callback.

No direct cell-setter write is observed in the traced movement wrapper/core path.

This double-callback structure is retained explicitly because collapsing it to a single generic "allow" event would lose state-order evidence.

### Handler-13 inheritance — 2 handlers

Handlers:

`92, 113`

Their own mutation-heavy branches are gated by non-movement actions `0x43/0x44` and `0x3A` respectively. Actions 2/3/4/5 delegate to handler 13 and inherit the E.6 tranche-2 CELL_VARIANT semantics:

- actions 2/3: no wrapper prewrite observed;
- actions 4/5: inherited conditional indirect-event path.

### 6BAD7 movement-default family — handler 108

Handler 108 delegates to runtime `0x6BAD7`.

After its read/guard setup, actions 2/3/4/5 are all below the first custom action range at `0x18` and branch to `0x6BA90 -> 0x3D4F5`.

The direct setters at runtime `0x6BBCB` and `0x6BD2C` belong to later non-movement action families and are not reachable from movement actions 2/3/4/5.

Thus movement actions have no direct cell write observed, but still invoke the unresolved dynamic callback through `0x3D4F5`.

## Direct serialized-cell mutation inventory

Across all three tranches, direct movement-path serialized-cell writes are currently verified for handler IDs:

`91, 110, 111, 115, 116, 410, 415`

That is **7/59 handler IDs**.

Examples already frozen in E.6 include:

- 110/111: action 3 writes cell(14,8) selector 5 = 1; action 5 writes = 2;
- 91: conditional cell(5,9) selector 4, 1 -> 2;
- 115/116: conditional cell(8,10) selector 5, 1 -> 2;
- 410: conditional cell(16,3) selector 4, 0 -> 1;
- 415: action-dependent direct writes including the row-23 multi-cell selector-1 update.

The other **52 handler IDs** have no direct serialized-cell setter write observed on their traced actions 2/3/4/5. This is not proof of semantic purity: many have explicit indirect event/helper calls or the dynamic callback.

## Negative-evidence boundary

The following are intentionally distinct:

- `DIRECT_CELL_WRITE`: exact target field/value is executable-evidenced;
- `INDIRECT_EVENT`: helper/event invocation is exact, downstream state target remains to be resolved;
- `INDIRECT_GLOBAL_CALLBACK`: exact dynamic call site is verified, runtime target/state delta remains unresolved;
- `NO_DIRECT_WRITE_OBSERVED`: no direct common cell-setter write on the traced path; indirect effects are not excluded.

No not-found result is converted into `ABSENT_VERIFIED`.

## Tooling

Updated:

- `tools/validate_callback_state_delta_manifest.py`
- `tests/test_validate_callback_state_delta_manifest.py`

New validator invariants:

- tranche 3 contains exactly 33 handlers;
- all three tranches are disjoint;
- union equals the exact 59 movement-source IDs;
- 26 new tranche-3 executable anchors are checked;
- total anchor set is 56 unique spans;
- representative indirect-effect semantics are regression-checked.

## Evidence classification

VERIFIED:

- complete 59/59 movement-handler effect-surface coverage for actions 2/3/4/5;
- exact direct serialized-cell writes already represented in the manifest;
- exact indirect call sites described above;
- exact 56 executable-region anchors;
- exact disjoint tranche coverage;
- no new direct cell-setter write in tranche 3 movement paths.

PARTIAL:

- downstream state deltas of indirect helpers/events;
- runtime target and state effects of `*[0x1B9DDC]`;
- complete state semantics of `0x2A7FA`, `0xA2DC7`, `0xA2D76`;
- downstream semantics of event helpers already identified in tranches 1/2;
- multi-step dynamic world-state graph.

## Gate

`serialized_initial_translation_graph = VERIFIED_STATE_QUALIFIED`

`movement_callback_return_semantics = VERIFIED`

`movement_callback_effect_surface_coverage = VERIFIED_59_OF_59`

`movement_callback_direct_write_manifest = VERIFIED_FOR_TRACED_MOVEMENT_PATHS`

`movement_callback_indirect_helper_semantics = PARTIAL`

`movement_callback_state_delta_semantics = PARTIAL`

`dynamic_state_graph = NOT_AUTHORIZED`

`one_way_verdict_authorized = false`

`softlock_verdict_authorized = false`

## Next — STONE-K292-E.6.2

Resolve the high-impact indirect state-effect roots in impact order:

1. dynamic callback slot `0x1B9DDC` — broadest fan-out across movement handlers;
2. `0x2A7FA` — action-4 event family used across multiple handler families;
3. `0xA2DC7` and `0xA2D76` — 3CFEE action-2/action-3 paths;
4. tranche-1 event helpers `0x6A73A`, `0x9C984`, `0x41B44`, `0x34228`, `0xA91F3`;
5. tranche-2 world/event continuations, especially handler 91.

Promote a helper to an explicit state delta only when its concrete writes/targets are directly evidenced. Then compose those deltas with E.5 MSP/spatial state and turn transitions before authorizing multi-step one-way or softlock analysis.
