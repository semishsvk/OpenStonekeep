# STONE-K292-E.2 — movement callback return-semantics closure

- Date: 2026-10-01
- Status: **PASS — callback return/veto layer closed for starter movement scope**
- Knowledge classification: GAME-SPECIFIC
- Scope: actions 2/3/4/5 for the 59 K292-E.1 movement-candidate source handlers

## Result

K292-C proved that cell+0x07 selects the per-cell action callback and that
forward/backward pre-actions can abort ordinary movement when the callback
returns zero. K292-E.1 resolved all relevant dispatch slots through LE fixups.

Coverage-complete static executable tracing now gives:

- movement-candidate source handlers: **59/59**
- control-flow families: **16**
- actions classified per handler: 2, 3, 4, 5
- handler/action return cells: **236**
- UNKNOWN return cells: **0**
- action 3 (forward pre) RETURN_0 handlers: **0**
- action 5 (backward pre) RETURN_0 handlers: **0**

All 236 traced movement-action calls return success/nonzero (RETURN_1).

Therefore, for the two authoritative starter saves, the non-default
cell-handler **return value** does not veto ordinary forward/backward movement
on any current low-static-clear candidate edge.

## Important separation

RETURN_1 does not mean NO_SIDE_EFFECT. Several handlers mutate cell/world state
or trigger events before delegating to a success-returning common path.

Directly observed examples include:

- handlers 110/111: actions 3 and 5 can write per-cell state;
- handler 112: action 3 can execute event/state work before the 0x99C9D allow path;
- handler 115: movement actions can pass conditional state/event work before handler 14;
- handler 410: conditional state/event work precedes the default allow path;
- handler 415: movement branches can mutate state before an allow-returning path.

Complete side-effect/state-transition semantics are intentionally not claimed
by this checkpoint.

## Common terminal families

The 59 handlers collapse into 16 evidence groups whose movement paths terminate
through already traced success-returning families, including:

- DAAAA -> 0x6BAF5 -> default 0x6A96A;
- 0x6DFC4 -> 0x6BAF5 -> default;
- 0x6B5EE -> 0x6BAF5 -> default;
- 0x618F2, 0xC22A4, 0x99C9D, 0x9A0D7 and 0x66F8A allow chains;
- wrapper chains through handlers 13/14/15/16 and the 0x4F035 family;
- the direct shared setter family used by IDs 21..24, which terminates with EAX=1.

Zero-return paths found in several helpers are tied to non-movement action IDs
such as 0x0F, 0x15 or 0x1F rather than 2/3/4/5.

## Tooling

Added:

- tools/validate_handler_action_evidence.py
- tests/test_validate_handler_action_evidence.py

The validator re-runs the E.1 LE resolver, verifies the authoritative SK.EXE
and starter-save SHA-256 set, re-derives the 59 current movement-candidate
source handlers and requires exact, duplicate-free evidence-group coverage.

Authoritative validation:

    handlers=59/59
    families=16
    action_cells=236
    unknown=0
    pre3_return0=0
    pre5_return0=0
    errors=0

Synthetic regression: **3 PASS**.

## Evidence classification

VERIFIED for the authoritative starter corpus:

- all 59 movement-candidate source handlers have resolved dispatch targets;
- actions 2/3/4/5 have complete return classification;
- all 236 classified calls return RETURN_1;
- no handler return-value veto exists for forward pre action 3;
- no handler return-value veto exists for backward pre action 5.

PARTIAL:

- movement callback side-effect/state-transition semantics.

OPEN:

- complete per-handler state deltas;
- live MSP/maze-prop directional clearance per candidate edge;
- live monster-linked spatial occupancy categories per candidate edge;
- dynamic state-qualified transition graph;
- final one-way and softlock verdicts.

## Navigation consequence

For the current starter-save candidate graph, SCRIPTED must now be split into
orthogonal evidence:

- callback_return_gate = ALLOW for actions 3/5;
- callback_side_effect = state/event semantics still evidence-dependent.

The handler-return gate is no longer an unresolved movement blocker for these
states. MSP/maze-prop clearance and monster-linked spatial occupancy remain
independent runtime gates.

## Gate

handler_target_resolution = VERIFIED

movement_callback_return_semantics = VERIFIED

movement_callback_pre_veto_unresolved = false

movement_callback_side_effect_semantics = PARTIAL

runtime_physical_clearance = OPEN

one_way_verdict_authorized = false

softlock_verdict_authorized = false

## Next — STONE-K292-E.3

Resolve movement-relevant callback side effects into explicit state deltas,
then combine them with MSP/maze-prop and monster-spatial occupancy evidence to
build the first state-qualified transition edges.
