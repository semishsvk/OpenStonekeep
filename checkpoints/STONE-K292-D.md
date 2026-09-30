# STONE-K292-D — Evidence-typed player edge graph

- Date: 2026-09-30
- Status: **PASS — candidate player edge graph constructed; softlock verdict remains gated**
- Knowledge classification: GAME-SPECIFIC
- Scope: serialized player-navigation evidence graph, not final runtime reachability

## Purpose

K292-D converts the K292-C player-movement call-chain into an explicit directed
graph without collapsing different evidence layers.

Each in-bounds directed cell edge is classified as exactly one of:

- `STATIC_BLOCKED`
  - the verified low `cell+0x02` directional bit is set on the reciprocal pair;
  - the ordinary forward/backward player primitive rejects this direction.
- `STATIC_CLEAR_RUNTIME_GATED`
  - the low static bit is clear;
  - the source cell uses the default event handler;
  - runtime MSP/maze-prop clearance and monster-linked spatial occupancy still
    have to be evaluated.
- `SCRIPTED`
  - the low static bit is clear;
  - the source cell has a non-default `cell+0x07` handler;
  - the pre-movement callback can veto or alter behavior.

`STATIC_MISMATCH` is retained as a corruption/evidence failure class, although
both authoritative starter saves contain zero mismatches.

## Actor-policy separation

K292-D deliberately does **not** suppress a player candidate edge because of:

- `cell+0x00 & 0x10`;
- `cell+0x00 & 0x80`;
- the high directional nibble of `cell+0x02`.

K292-B proved those layers in monster actor-clearance. K292-C found no direct
read of them in the ordinary player translation primitive. They are therefore
reported as actor-specific evidence, not promoted into player policy.

Likewise, `cell+0x01` mutable directional state is not interpreted as a direct
player barrier because K292-C found it being maintained alongside edge-state
mutations but did not find a direct generic translation read.

## Script evidence

The graph is directed because the pre-movement callback belongs to the source
cell.

For every static-clear undirected pair, K292-D therefore records whether only
one endpoint has a non-default handler. Such a pair is a
**script-asymmetric candidate**, not a proven one-way edge.

A destination non-default handler is reported separately as
`destination_handler_present`. No assumption is made that the post-move action
automatically reloads and invokes that destination handler in the same step.

## Authoritative corpus validation

### LEVEL01.SAV

- SHA-256: `2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9`
- grid: 26 x 29 = 754 cells
- undirected static:
  - blocked: 774
  - clear: 679
  - mismatch: 0
- directed in-bounds edges:
  - `STATIC_BLOCKED`: 1548
  - `STATIC_CLEAR_RUNTIME_GATED`: 1231
  - `SCRIPTED`: 127
- non-default handler cells: 81
- static-clear undirected pairs with handler asymmetry: **71**
- directed candidate edges entering non-default-handler cells: 324
- static-clear candidate components:
  - count: 153
  - largest: 138, 106, 83, 59, 29, 20, 17, 15
  - isolated cells: 117

### LEVEL01A.SAV

- SHA-256: `3d1753ca8a4ca49b3ccf9da0fc15bb08ac242301eff40586049379ceba635dc9`
- grid: 26 x 29 = 754 cells
- undirected static:
  - blocked: 434
  - clear: 1019
  - mismatch: 0
- directed in-bounds edges:
  - `STATIC_BLOCKED`: 868
  - `STATIC_CLEAR_RUNTIME_GATED`: 2016
  - `SCRIPTED`: 22
- non-default handler cells: 18
- static-clear undirected pairs with handler asymmetry: **22**
- directed candidate edges entering non-default-handler cells: 72
- static-clear candidate components:
  - count: 131
  - largest: 469, 19, 19, 19, 19, 17, 15, 7
  - isolated cells: 110

The component counts are **candidate static topology only**. Runtime clearance
and scripts are unresolved, so component separation is not a softlock verdict.

## Tooling

Added:

- `tools/build_navigation_evidence.py`
- `tests/test_build_navigation_evidence.py`

The tool supports summary output and JSON. `--edges` adds per-directed-edge
records with:

- source/destination coordinates;
- evidence class;
- source/destination handler IDs;
- serialized MSP/monster chain heads;
- actor-specific monster-only flags.

No original Stonekeep data is committed.

Synthetic regression: **4 PASS**

Coverage:

1. all static-clear internal edges remain runtime-gated;
2. a non-default source handler makes only the outgoing candidate edges
   `SCRIPTED`;
3. a reciprocal static blocked pair is removed from the candidate graph;
4. monster-only `0x10/0x80/high` evidence does not silently become player
   policy.

## Evidence classification

VERIFIED:

- low `cell+0x02` controls direct ordinary player translation;
- source non-default `cell+0x07` is a pre-movement script gate;
- MSP and monster-linked occupancy remain runtime prechecks;
- low static reciprocity is preserved in both starter saves.

STRUCTURAL:

- 71 LEVEL01 and 22 LEVEL01A static-clear pairs have source-handler asymmetry;
- static-clear connected components are useful candidate topology partitions.

OPEN:

- outcomes of each non-default handler;
- live MSP orientation/clearance state for every edge;
- live monster-linked occupancy category state;
- dynamic transitions between scripted/runtime states;
- proven one-way edges;
- proven softlocks.

## Safety gate

`one_way_verdict_authorized = false`

`softlock_verdict_authorized = false`

K292-D may identify **candidate** asymmetries only. A CRITICAL transition or
softlock may be issued only after the relevant handler/runtime state is
resolved.

## Next gate — STONE-K292-E

Resolve the script/runtime state needed to turn candidate edges into validated
runtime transitions:

1. enumerate the non-default handler IDs occurring on static-clear candidate
   edges;
2. map those IDs to handler function pointers;
3. classify movement actions 2/3/4/5 per handler as allow/veto/state mutation;
4. resolve MSP directional mask state and monster spatial categories for the
   same edges;
5. produce the first state-qualified player transition graph;
6. only then run CRITICAL one-way/softlock validation.

## Framework candidate

K292-D strengthens the proposed `NavigationEvidence` / `NavigationIR` model:

- directed edge;
- actor policy;
- static barrier evidence;
- runtime physical gate;
- script precondition;
- destination event evidence;
- evidence level;
- unresolved-state reasons.

Promotion to OpenRemaster Framework remains cross-game evidence-gated.
