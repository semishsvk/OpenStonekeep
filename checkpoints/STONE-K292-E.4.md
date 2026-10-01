# STONE-K292-E.4 — monster-linked spatial occupancy closure

- Date: 2026-10-01
- Status: **PASS — serialized/load-state spatial occupancy decoded**
- Knowledge classification: GAME-SPECIFIC
- Scope: monster-linked spatial occupancy gate used by ordinary player forward/backward prechecks

## Serialized layout

The level loader at raw 0x8B9B6 reads immediately after the 21-byte cell grid:

- 0x12C0 bytes into runtime pool 0x195F38
- one u16 state/free-list value into 0x1BC4E8
- 0x16C8 bytes into runtime head grid 0x193E80

These sizes resolve exactly to:

- **400 x 0x0C spatial records**
- **54 x 54 x signed-u16 grid heads**

For the starter saves:

- record pool: [0x3DE5, 0x50A5)
- u16 state/free-list head: 0x50A5
- 54x54 head grid: [0x50A7, 0x676F)

The head-grid address helper at raw 0xD1BD7 computes:

    head = base + row*0x6C + column*2

which is exactly row*54 + column in signed-u16 elements.

## Record linkage and coordinate evidence

Player prechecks read:

- record+0x06: category ID
- record+0x0A: next record in the same spatial cell

The 54x54 grid uses -1 as the empty head sentinel.

Across both authoritative starter saves:

- active head cells: 5 per save
- LEVEL01 linked records: 15
- LEVEL01A linked records: 14
- invalid links: 0
- chain cycles: 0
- duplicate linked-record ambiguity: 0
- record/grid coordinate mismatches: **0/29**

For every linked record, record+0x02/+0x04 equals the column/row of the 54x54
head cell that reaches it. This independently verifies the pool as a spatial
index rather than an unrelated record list.

K292-C already tied these spatial records back to monster runtime records, so
the layer remains classified as monster-linked spatial occupancy.

## Blocking category policy

The forward and backward player prechecks compare record+0x06 against
direction-dependent category families.

Forward current-cell categories include:

- facing + 0x10
- facing + 0x20
- parity family 0x16/0x17
- parity family 0x26/0x27
- constants 0x15 and 0x25

Forward destination categories include:

- 0x50
- facing + 0x40
- parity family 0x46/0x47

Backward uses a different policy because requested movement direction is
opposite live facing. Its destination checks additionally include:

- requested + 0x30
- parity family 0x36/0x37
- live_facing + 0x40
- parity family 0x46/0x47
- 0x50

Therefore forward/backward occupancy is orientation-dependent and must not be
collapsed to a single unoriented occupied/free bit.

## Authoritative corpus

### LEVEL01.SAV

SHA-256:
2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9

- free/state head value: 34
- active 54x54 head cells: 5
- linked records: 15
- linked category histogram:
  - 0x26: 4
  - 0x27: 3
  - 0x36: 4
  - 0x37: 3
  - 0x40: 1
- static-clear oriented candidate edges: 1,358
- forward spatial-clear: 1,350
- forward spatial-blocked: **8**
- backward spatial-clear: 1,351
- backward spatial-blocked: **7**
- oriented edges affected by either policy: 14

### LEVEL01A.SAV

SHA-256:
3d1753ca8a4ca49b3ccf9da0fc15bb08ac242301eff40586049379ceba635dc9

- free/state head value: 14
- active 54x54 head cells: 5
- linked records: 14
- linked category histogram:
  - 0x26: 2
  - 0x27: 5
  - 0x36: 2
  - 0x37: 5
- static-clear oriented candidate edges: 2,038
- forward spatial-clear: 2,033
- forward spatial-blocked: **5**
- backward spatial-clear: 2,033
- backward spatial-blocked: **5**
- oriented edges affected by either policy: 10

## Input-order consequence

The main movement path calls the physical precheck before the cell callback:

Forward:

    B128B physical precheck
    action 3 callback
    B0CE3 translation
    action 2 callback

Backward:

    B140F physical precheck
    action 5 callback
    B100F translation
    action 4 callback

Therefore a physical MSP/spatial block prevents the pre-movement callback from
running on that attempt. Conversely, once the physical precheck succeeds, an
action-3/5 callback may mutate world state, but E.2 proves its return value does
not veto movement for the current 59-handler starter scope.

This ordering permits a precise serialized initial-state one-step transition
classification while still requiring state deltas for subsequent transitions.

## Tooling

Added:

- tools/inspect_monster_spatial_clearance.py
- tests/test_inspect_monster_spatial_clearance.py

Synthetic regression: **4 PASS**.

## Evidence classification

VERIFIED:

- 400 x 0x0C serialized spatial-record pool
- u16 pool/free-list state immediately after it
- 54x54 signed-u16 head grid
- row*54+column head addressing
- -1 empty-head sentinel
- record+0x06 category field as consumed by player prechecks
- record+0x0A cell-chain next link
- exact forward/backward blocker comparisons in the ordinary prechecks
- zero record/grid coordinate mismatches in both starter saves
- the corpus counts above
- physical precheck occurs before action 3/5 callback

STATE-QUALIFIED:

- per-edge occupancy clear/blocked results for the serialized starter state

OPEN:

- future runtime occupancy changes
- designer-facing names for category families
- complete callback state deltas
- multi-step dynamic state graph

## Gate

handler_target_resolution = VERIFIED

movement_callback_return_semantics = VERIFIED

serialized_msp_clearance = VERIFIED_STATE_QUALIFIED

serialized_monster_spatial_clearance = VERIFIED_STATE_QUALIFIED

serialized_initial_one_step_transition_model = READY_TO_BUILD

one_way_verdict_authorized = false

softlock_verdict_authorized = false

## Next — STONE-K292-E.5

Combine static edge evidence, E.2 callback-return evidence, E.3 MSP state and
E.4 monster spatial occupancy into the first orientation-aware serialized
initial-state player transition graph. Keep callback side effects as explicit
post-precheck state-delta uncertainty for subsequent transitions.
