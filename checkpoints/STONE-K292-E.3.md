# STONE-K292-E.3 — serialized MSP/maze-prop clearance closure

- Date: 2026-10-01
- Status: **PASS — serialized/load-state MSP clearance decoded**
- Knowledge classification: GAME-SPECIFIC
- Scope: player movement MSP/maze-prop gate in the authoritative starter saves

## Loader layout

The level loader at raw 0x8B9B6 independently fixes the post-grid order:

1. 21-byte cell grid;
2. 0x12C0 bytes into the monster-linked spatial-record pool;
3. u16 state value;
4. 0x16C8 bytes into the grid-head array;
5. u16 MSP count;
6. MSP count * 0x30 bytes into runtime pool 0x1B5210.

For the 26x29 starter saves the grid ends at 0x3DE5, therefore:

- MSP count offset: **0x676F**
- MSP record start: **0x6771**
- MSP record size: **0x30**
- MSP count: **250**
- MSP record end: **0x9651**

The same offsets/count hold in LEVEL01.SAV and LEVEL01A.SAV.

## Chain and mask semantics

K291-C already proved cell+0x11 is the head into this 0x30-byte pool and
record+0x10 is the next link.

Helper 0x410A0 proves the movement-relevant aggregation rule:

- walk the cell+0x11 chain until sentinel -100;
- only records with s16(record+0x02) == 1 contribute;
- OR byte record+0x18 across contributing records.

The resulting mask is then tested by the player precheck.

The executable contains direct writes to runtime record+0x18 (for example raw
0x3FE1D and 0x3FE3A), so this field is runtime mutable. This checkpoint
therefore classifies the saved bytes as **SERIALIZED_LOAD_STATE**, not eternal
static topology.

## Forward versus backward policy

The verified low direction masks are N=0x08, W=0x02, S=0x04, E=0x01.

For a forward move in direction D, 0x40EE0/0x410A0 require:

- source aggregated mask does not intersect (D | 0x10), and
- destination aggregated mask does not intersect opposite(D).

For the backward caller, requested direction is live_facing+2. The non-equal
branch tests the destination aggregated mask against:

- requested direction |
- live facing |
- 0x10.

Forward and backward traversal are therefore explicitly orientation/state
dependent and must not be collapsed into one unoriented edge property.

## Authoritative corpus

### LEVEL01.SAV

SHA-256:
2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9

MSP pool:

- 250 records
- type histogram: type 1 = 249, type 0 = 1
- type-1 +0x18 masks:
  - 0x00: 228
  - 0x01: 1
  - 0x02: 1
  - 0x04: 3
  - 0x08: 6
  - 0x10: 6
  - 0x1F: 4
- active cell+0x11 heads: 105
- unique active heads: 105
- invalid links: 0
- chain cycles: 0
- maximum observed chain length: 5

Aggregated non-empty cell masks:

- 0x00: 91
- 0x08: 2
- 0x0C: 2
- 0x10: 2
- 0x11: 1
- 0x12: 1
- 0x18: 1
- 0x1C: 1
- 0x1F: 4

Among 1,358 low-static-clear oriented candidate edges:

- forward clear: 1,328
- forward MSP-blocked: **30**
- backward clear: 1,336
- backward MSP-blocked: **22**
- oriented edges affected by either policy: 38
- affected undirected interfaces: 19

### LEVEL01A.SAV

SHA-256:
3d1753ca8a4ca49b3ccf9da0fc15bb08ac242301eff40586049379ceba635dc9

MSP pool:

- 250 records
- type histogram: type 1 = 250
- type-1 +0x18 masks:
  - 0x00: 248
  - 0x02: 1
  - 0x1F: 1
- active cell+0x11 heads: 44
- unique active heads: 44
- invalid links: 0
- chain cycles: 0
- maximum observed chain length: 3

Among 2,038 low-static-clear oriented candidate edges:

- forward clear: 2,036
- forward MSP-blocked: **2**
- backward clear: 2,036
- backward MSP-blocked: **2**
- oriented edges affected by either policy: 3
- affected undirected interfaces: 2

## Tooling

Added:

- tools/inspect_msp_clearance.py
- tests/test_inspect_msp_clearance.py

Synthetic regression: **4 PASS**.

The tool reconstructs the serialized MSP pool from loader-defined offsets,
validates every cell-linked chain, derives the per-cell aggregated mask and
classifies forward/backward MSP evidence only on reciprocal low-static-clear
candidate edges.

## Evidence classification

VERIFIED:

- serialized MSP count/pool layout for the starter saves;
- cell+0x11 -> 0x30 record chain;
- record+0x10 next link;
- contributing record condition s16(+0x02)==1;
- record+0x18 OR aggregation;
- forward and backward mask tests used by the player precheck;
- record+0x18 is runtime mutable;
- the corpus counts above.

STATE-QUALIFIED:

- per-edge clear/blocked results from the serialized load-state snapshot.

OPEN:

- subsequent runtime changes to MSP masks;
- exact designer-facing type names of every MSP record;
- monster-linked spatial occupancy category resolution;
- complete dynamic state-transition graph.

## Navigation consequence

The generic K292-D class STATIC_CLEAR_RUNTIME_GATED can now be refined with a
separate MSP state field. For the serialized starter state, most static-clear
edges are MSP-clear, but a small concrete subset is physically gated by MSP
state.

The MSP evidence must remain orientation-aware:

- FORWARD_MSP_CLEAR / FORWARD_MSP_BLOCKED
- BACKWARD_MSP_CLEAR / BACKWARD_MSP_BLOCKED

This is independent of the already VERIFIED callback return gate.

## Gate

handler_target_resolution = VERIFIED

movement_callback_return_semantics = VERIFIED

serialized_msp_clearance = VERIFIED_STATE_QUALIFIED

monster_spatial_occupancy = OPEN

one_way_verdict_authorized = false

softlock_verdict_authorized = false

## Next — STONE-K292-E.4

Decode the serialized 0x12C0 monster-linked spatial-record block and 0x16C8
grid-head array, resolve the blocking category IDs used by forward/backward
prechecks, and combine that layer with static edges, callback-return evidence
and serialized MSP state.
