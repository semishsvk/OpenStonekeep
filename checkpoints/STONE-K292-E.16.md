# STONE-K292-E.16 — three-level state-qualified navigation bounds

- Date: 2026-10-04
- Status: **PASS — three-level oriented-state graph bounds built; 6/6 portal-arrival escape macros remain VERIFIED**
- Knowledge classification: GAME-SPECIFIC
- Scope: LEVEL01 / LEVEL01A / LEVEL02 ordinary translation, turn, and portal composition without overclaiming unresolved dynamic state

## Result

E.16 composes the verified movement, turn and portal evidence into the first
three-level oriented-state graph.

The graph contains:

- LEVEL01: 26 x 29 x 4 = 3,016 oriented states
- LEVEL01A: 26 x 29 x 4 = 3,016 oriented states
- LEVEL02: 30 x 27 x 4 = 3,240 oriented states
- total: **9,272 oriented states**

Two deliberately different graph layers are emitted.

### VERIFIED_FROZEN_SNAPSHOT

This layer contains only edges whose required evidence is already closed for
the represented state:

- LEVEL01 and LEVEL01A FWD/BACK use the serialized static + MSP +
  monster-spatial + movement-callback-return snapshot gates;
- turn physical precheck uses the verified 0x82BC3 semantics;
- turn callback success is admitted only for already closed h0/default and
  h415 paths;
- E.15 portal edges are admitted when the source enable path is not still
  producer-qualified;
- all six E.15 same-interface return sequences are admitted as verified macro
  transitions;
- LEVEL02 ordinary movement/turn is intentionally not admitted because
  corpus-wide initial monster-spatial materialization remains open.

Authoritative result:

- states: **9,272**
- edges: **17,980**
- SCC count: **3,733**
- largest SCC sizes:
  **1876, 424, 378, 269, 236, 148, 116, 80, 74, 74, 74, 73, 68, 68, 60, ...**
- largest SCC level distribution: **LEVEL01A only, 1,876 states**
- singleton SCCs: **3,441**
- zero-out-degree states: **3,413**

These counts are a conservative lower graph, not a claim that the zero-out
states are gameplay dead ends.

### POTENTIAL_UPPER_BOUND

This layer adds transitions that are structurally possible but still depend on
unresolved state/callback evidence:

- LEVEL01/LEVEL01A physically clear turns despite unresolved non-default turn
  callback semantics;
- all 12 E.15 portal edges;
- LEVEL02 ordinary translation using reciprocal base static topology only;
- LEVEL02 turns without assuming unresolved MSP/spatial/callback veto state.

Authoritative result:

- states: **9,272**
- edges: **28,143**
- SCC count: **508**
- largest SCC sizes:
  **1876, 552, 424, 344, 329, 324, 296, 236, 116, 116, 104, 80, 76, ...**
- largest SCC level distribution: **LEVEL01A only, 1,876 states**
- singleton SCCs: **34**
- zero-out-degree states: **14**

These counts are an upper connectivity bound, not evidence that all potential
edges execute in a real runtime state.

## Turn precheck closure

E.15 resolved the h89 local turn path. E.16 generalizes the physical turn
precheck directly from runtime 0x82BC3.

For prospective new facing D:

1. helper 0x12B20 aggregates current-cell MSP movement state;
2. the MSP mask must not contain the LOW bit opposite D;
3. current-cell monster-spatial records are scanned;
4. categories blocking the turn are:
   - 0x40 + D
   - 0x46 / 0x47 by facing parity
   - 0x45

This physical test is independent of the current-cell callback.

Non-default callback success/state deltas for turn actions are still not
coverage-complete, so E.16 does not silently promote every physically clear
turn into the verified graph.

## LEVEL02 MSP base evidence

The generic MSP allocator type switch at runtime 0x11B40 was resolved through
LE fixups for every MSP type observed in LEVEL02.MAZ.

For directional allocator branches, the initial movement-mask argument is read
from the 9 x 9 byte table at object3+0x38D5, indexed by:

    (MAZ word3 + 4, MAZ word4 + 4)

The allocator writes this BX value to runtime MSP record+0x18.

The generic materializer contains a later path that can zero +0x18, and
LEVEL01.SAV represents an already runtime-evolved starter snapshot. Therefore
E.16 freezes the allocator result only as:

VERIFIED_CONSERVATIVE_BASE_PREZERO_MASK

It is useful for identifying possible blockers but is not used to assert
complete LEVEL02 ordinary movement in the verified graph.

LEVEL02 aggregate conservative cell-mask histogram:

- 0x00: 793 cells
- 0x01: 1
- 0x10: 7
- 0x16: 4
- 0x19: 1
- 0x1F: 4

The combined values 0x16 and 0x19 are OR aggregates of multiple contributing
MSPs in the same cell.

## LEVEL02 spatial state

E.14 proved:

- LEVEL02 MSP count = 93
- nested monsters = 4
- standalone monsters = 57
- total initial monster records represented by the MAZ tail = 61
- the two known LEVEL02 return portal interfaces are physically clear after
  LOW opening

However, the complete runtime 0x0C spatial-record category placement for all 61
initial monsters has not yet been reconstructed corpus-wide.

Therefore:

level02_spatial_ordinary_graph = OPEN

and ordinary LEVEL02 movement/turn edges remain outside the verified lower
graph.

## Portal escape invariant

The six E.15 return sequences are represented as verified macro transitions
from the exact target spawn after a successful LEVEL01 outbound portal:

- h87 target -> h411 return
- h88 target -> h412 return
- h89 target -> h415 return
- h90 target -> h413 return
- h106 target -> h144 return
- h107 target -> h145 return

Result:

verified_portal_arrival_escape = 6/6

This preserves the E.15 conclusion that none of the six known LEVEL01 outbound
portal interfaces is intrinsically one-way after its outbound transition
executes.

## Edge-accounting highlights

Authoritative E.16 run records:

- verified LEVEL01 move edges: **2,653**
- verified LEVEL01A move edges: **4,062**
- verified LEVEL01 turn edges: **5,364**
- verified LEVEL01A turn edges: **5,886**
- potential LEVEL01 turns: **5,976**
- potential LEVEL01A turns: **6,022**
- unresolved non-default turn callback opportunities: **748**
- potential LEVEL02 static-only move edges: **2,932**
- potential LEVEL02 turn edges: **6,480**
- LEVEL02 move attempts reaching unresolved spatial stage: **2,862**
- LEVEL02 turns reaching unresolved spatial stage after conservative MSP check:
  **6,426**
- potential portal edges: **12**
- direct verified portal-source edges: **9**
- verified same-interface return macros: **6**

## Executable anchors

E.16 validates:

- turn physical precheck
  - runtime 0x82BC3
  - 0xB7 bytes
  - SHA-256
    3a0a92214ea557063e20a1a948a8b2540f259b00e4d2916cc1fccf9c83951dca

- MSP type allocator switch
  - runtime 0x11B40
  - 0x208 bytes
  - SHA-256
    182cdc20de0424d2fb89c76d9ea5777ddf89326c48b282a12b46b71b16be2083

- LEVEL02 directional movement-mask table
  - object3+0x38D5
  - 81 bytes
  - SHA-256
    f692f6fbe8f5b96bcec84ff132a36f7f32addef0c25124046c1683a8b2ba5007

## Reproducibility

Added:

- tools/build_three_level_state_graph.py
- tests/test_build_three_level_state_graph.py

Canonical HomePC corpus run:

    PASS states=9272 verified_edges=17980 potential_edges=28143 returns=6/6 errors=0

Regression execution:

- HomePC Python has no installed pytest module.
- The fixture-free E.16 + E.15 regression modules were imported directly and
  every zero-argument test_* function was executed.
- Result: **12/12 PASS, 0 skipped**.

No dependency was installed or source corpus modified for this validation.

## Evidence classification

VERIFIED:

- three-level oriented state count = 9,272;
- LEVEL01 / LEVEL01A serialized-snapshot ordinary translation layer;
- generalized turn physical precheck;
- h0/h415 turn callback allow scope already closed by prior evidence;
- E.15 12-edge portal inventory;
- six same-interface return macro transitions;
- executable MSP allocator switch and directional mask table;
- the exact lower/upper graph counts above.

STATE-QUALIFIED:

- all LEVEL01 / LEVEL01A ordinary movement and turn results based on serialized
  starter runtime state;
- E.10 producer-gated outbound portal availability;
- SCC/escape observations within the explicitly represented state dimensions.

CONSERVATIVE / BOUND ONLY:

- LEVEL02 allocator pre-zero MSP masks;
- LEVEL02 static-only upper-bound ordinary navigation;
- upper-bound SCC structure.

OPEN:

- exact generic post-allocation MSP zero override for all LEVEL02 records;
- complete LEVEL02 initial monster-spatial category materialization;
- non-default turn callback return/state-delta coverage;
- dynamic actor/MSP changes beyond frozen snapshots;
- progression outside LEVEL01 / LEVEL01A / LEVEL02;
- global one-way and softlock verdicts.

## Gate

three_level_oriented_states = 9272 VERIFIED

verified_frozen_snapshot_edges = 17980

potential_upper_bound_edges = 28143

verified_portal_arrival_escape = 6/6

turn_physical_precheck = VERIFIED

level02_spatial_ordinary_graph = OPEN

scc_result = BOUNDED_NOT_GLOBAL_VERDICT

global_one_way_verdict_authorized = false

global_softlock_verdict_authorized = false

## Next — STONE-K292-E.17

Reconstruct the complete initial LEVEL02 monster-spatial runtime category layer
from the MAZ monster records and the 0x76980 placement path.

Use that result to promote LEVEL02 ordinary movement/turn edges from the
potential layer into a state-qualified verified initial-level layer.

Then close the remaining non-default turn callback return/state-delta families
needed by reachable three-level states before attempting stronger SCC or
escape claims.
