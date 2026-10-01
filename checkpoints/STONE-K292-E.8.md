# STONE-K292-E.8 — starter portal / level-transition payload closure

- Date: 2026-10-01
- Status: **PASS — transition commit semantics verified; portal unlock remains open**
- Knowledge classification: GAME-SPECIFIC
- Scope: movement handlers in LEVEL01 / LEVEL01A that enter the `0x3CFEE -> 0xA2DC7 -> 0xA2BA6` transition family

## Result

E.8 separates two mechanisms that were previously conflated:

1. **level-transition commit** — now VERIFIED;
2. **mutation that makes the initially closed portal edge traversable** — still OPEN.

Nine starter-save movement handlers resolve to the transition family. Their
source cell, direction gate, target level and staged target row/column/facing
are now frozen against the executable LE relocations and the authoritative
starter saves.

## Transition commit chain

The common family at runtime `0x3CFEE` dispatches movement actions by facing:

- matching action 3 enters `0xA2D76` pre-transition/event work;
- matching action 2 enters `0xA2DC7` transition payload work.

`0xA2DC7` calls `0xA2BA6` with the destination payload. `0xA2BA6` writes:

- staged column -> `0x1BC404`;
- staged row -> `0x1BC406`;
- staged facing -> `0x1BC414`;

and queues event type 8.

The event dispatch table is relocation-sensitive. Its type-8 entry resolves to
runtime `0x853A0`. That consumer loads source/target level fields from the event
and calls runtime `0x5DC10(source_level, target_level)`.

`0x5DC10` performs the level transfer and copies the staged player transform to
live state:

- staged column -> live column `0x1BC69A`;
- staged row -> live row `0x1BC698`;
- staged facing -> live facing `0x1BC6AE`;
- target level -> live current-level `0x1BC6A0`.

Therefore the source level, target level and staged player spawn/facing below
are VERIFIED transition semantics rather than inferred labels.

## Verified starter transitions

| Source | Handler | Source cell | Direction gate | Target | Staged target `(row,col,facing)` |
| --- | ---: | --- | --- | --- | --- |
| LEVEL01 (1) | 87 | (2,3) | S | LEVEL01A (15) | (3,3,0) |
| LEVEL01 (1) | 88 | (2,25) | S | LEVEL01A (15) | (3,25,0) |
| LEVEL01 (1) | 89 | (23,3) | N | LEVEL01A (15) | (22,3,2) |
| LEVEL01 (1) | 90 | (23,25) | N | LEVEL01A (15) | (22,25,2) |
| LEVEL01 (1) | 106 | (11,5) | N | level 2 | (7,2,0) |
| LEVEL01 (1) | 107 | (7,25) | W | level 2 | (2,18,1) |
| LEVEL01A (15) | 411 | (2,3) | S | LEVEL01 (1) | (3,3,0) |
| LEVEL01A (15) | 412 | (2,25) | S | LEVEL01 (1) | (3,25,0) |
| LEVEL01A (15) | 413 | (23,25) | N | LEVEL01 (1) | (22,25,2) |

Resolved handler runtime targets:

- 87 -> `0x5F3B9`
- 88 -> `0x5E868`
- 89 -> `0x5E8D2`
- 90 -> `0x5E92E`
- 106 -> `0x5F027`
- 107 -> `0x5F08B`
- 411 -> `0x4F8FC`
- 412 -> `0x4F91A`
- 413 -> `0x4F925`

## Serialized portal state

For all nine transition handlers, the direction selected by the transition
family is closed by the verified low `cell+0x02` static-edge bit in the source
cell **and** the reciprocal low bit is set in the adjacent cell.

Authoritative result:

- transition sources checked: **9/9**
- source low-static edge closed: **9/9**
- reciprocal adjacent edge closed: **9/9**
- closed on both sides: **9/9**

This is consistent with E.5 excluding these interfaces from the serialized
initial ordinary-translation graph.

It also means that knowing the transition payload is insufficient to claim a
currently traversable portal. A state change or alternate transition path must
first make the action sequence reachable.

## `0xA2D76` boundary

Direct tracing of `0xA2D76` found no direct common-cell-setter write to
`cell+0x02`. It queues event type `0x14` and invokes transition/presentation
helpers, but E.8 does **not** promote that path to the portal unlock mechanism.

Current evidence classification:

- `A2D76 is the direct low-static portal unlock`: **FALSIFIED**;
- `A2D76 or its queued work may participate indirectly in later state change`:
  **OPEN**.

## Reproducibility

Added:

- `tools/inspect_transition_handlers.py`
- `tests/test_inspect_transition_handlers.py`

The validator requires the authoritative hashes:

- SK.EXE `5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2`
- LEVEL01.SAV `2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9`
- LEVEL01A.SAV `3d1753ca8a4ca49b3ccf9da0fc15bb08ac242301eff40586049379ceba635dc9`

It validates:

- LE-resolved dispatch target for all nine handlers;
- **11/11** exact executable code-region SHA-256 anchors;
- relocation of the event-type-8 consumer to runtime `0x853A0`;
- exact handler ID at each source cell;
- source and reciprocal low-static closure at every portal interface.

Authoritative run:

    PASS transitions=9 closed_both=9 regions=11 errors=0

Synthetic/structural regression: **4 PASS**.

## Evidence classification

VERIFIED:

- nine transition-handler dispatch targets;
- action-2 transition payload family;
- staged destination column/row/facing writes;
- event type 8 -> `0x853A0` -> `0x5DC10` level-transfer chain;
- live player/current-level state transfer;
- source/target level and staged target payloads in the table above;
- all nine portal interfaces are reciprocally low-static-closed in the
  serialized starter snapshots.

FALSIFIED:

- `0xA2D76` directly clears the low `cell+0x02` portal edge.

OPEN:

- exact producer that clears/mutates the portal edge or otherwise makes the
  transition action sequence reachable;
- asynchronous/event-mediated effects downstream of the pre-transition path;
- multi-step portal state machines;
- dynamic reachability, one-way and softlock verdicts.

## Gate

`level_transition_payload_semantics = VERIFIED`

`starter_transition_handler_count = 9`

`serialized_transition_interfaces_closed_both_sides = 9/9`

`portal_unlock_semantics = OPEN`

`dynamic_state_graph = NOT_AUTHORIZED`

`one_way_verdict_authorized = false`

`softlock_verdict_authorized = false`

## Next — STONE-K292-E.9

Trace callers of the generic low-edge mutation families and bind them to the
nine transition interfaces. Require direct evidence of either reciprocal
`cell+0x02` mutation or a verified alternative path that bypasses ordinary
translation before promoting a portal from CLOSED_SERIALIZED to an enabled
dynamic transition state.
