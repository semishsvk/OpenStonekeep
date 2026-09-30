# STONE-K292-C — Player translation clearance and per-cell event layer

- Date: 2026-09-30
- Status: **PASS — VERIFIED ordinary player translation call-chain**
- Knowledge classification: GAME-SPECIFIC
- Scope: forward/backward grid translation, prechecks, per-cell event dispatch

## Purpose

K292-C identifies the ordinary player translation path and separates:

1. the direct static edge test;
2. runtime MSP/maze-prop clearance;
3. monster-linked spatial occupancy veto;
4. per-cell action/event callbacks.

The result is intentionally not yet a final softlock solver.

## Forward translation primitive

The main input path calls the forward primitive at raw 0xB0CE3 from
approximately 0x5FE15.

The primitive:

1. reads live facing from 0x1BC6AE;
2. selects the verified low static direction mask;
3. reads cell selector 2, i.e. cell+0x02;
4. succeeds iff the selected low static bit is clear;
5. on success adds the facing column/row deltas to:
   - column 0x1BC69A
   - row    0x1BC698.

Therefore the ordinary forward grid-step primitive directly tests the
VERIFIED low cell+0x02 static edge layer.

## Backward translation primitive

The backward primitive begins near raw 0xB100F and is called from the main
input path around 0x5FEC6.

It:

1. reads live facing;
2. selects the opposite low static direction mask;
3. reads cell+0x02;
4. succeeds iff that opposite low static bit is clear;
5. subtracts the facing deltas from the live column/row globals.

Thus ordinary backward translation uses the same low static edge model in the
opposite direction.

## What the primitive does NOT directly test

Within the verified forward/backward translation primitives there is no direct
read of:

- cell+0x00 bit 0x10;
- cell+0x00 bit 0x80 / combined 0x90 actor gate;
- the high secondary cell+0x02 direction bit;
- cell+0x01 mutable directional selectors 10..13.

This is an important actor-policy distinction: the monster directional
clearance routine is stricter/different from the direct player translation
primitive.

This does NOT mean those layers can never influence player movement. Runtime
prechecks and custom per-cell handlers remain capable of vetoing or mutating
state.

## Forward/backward prechecks

Before calling the translation primitive, the main input handler calls:

- forward precheck near 0xB128B;
- backward precheck near 0xB1410.

Both first invoke the direction-aware helper near 0x40EE0.

### MSP/maze-prop clearance

The 0x40EE0 path calls helper 0x410A0.

0x410A0:

- obtains cell selector 8, already mapped to the cell+0x11 MSP/maze-prop chain;
- walks the 0x30-byte MSP pool via next offset 0x10;
- for active records, accumulates record byte +0x18 as a directional mask;
- evaluates the requested direction/mode against that mask.

The player precheck therefore has a VERIFIED runtime MSP/maze-prop clearance
layer independent of the direct low static edge primitive.

### Monster-linked spatial occupancy index

The forward/backward prechecks also inspect a grid-indexed pool:

- grid heads begin at 0x193E80;
- grid addressing uses row * 0x6C + column * 2;
- linked records are 0x0C bytes at 0x195F38;
- record +0x0A is the next-in-cell link;
- record +0x06 is compared against blocking category IDs.

The insertion path around 0xD1921 links these 0x0C-byte records back into the
0x111 monster runtime record at monster offset +0xF3.

Therefore this structure is a VERIFIED **monster-linked spatial occupancy
index**. The player prechecks scan the current and candidate destination cell
and veto selected spatial categories. Exact designer-facing names for those
category IDs remain OPEN.

## Per-cell action/event handler — cell+0x07

Function 0x6C5CC computes a cell pointer, reads signed word cell+0x07, indexes
the function-pointer table at 0xF16A, and stores the selected handler into
global function pointer 0x1B9DF4.

Engine initialization sets 0x1B9DF4 to object-1 virtual 0x2C36A, which maps to
the default handler visible around raw 0x6A96A. Level/cell setup also loads
table entry 0 from 0xF16A as the default.

The main player input path invokes this handler:

- action 3 before forward movement; return 0 aborts the action;
- action 2 after successful forward movement;
- action 5 before backward movement; return 0 aborts the action;
- the corresponding post-action path uses action 4.

The default handler returns success, while non-default table entries may
implement cell-specific logic.

Therefore cell+0x07 is a VERIFIED **per-cell action/event handler index** and
the callback is a separate runtime/script veto/trigger layer, not static
topology.

### Starter corpus

LEVEL01.SAV:
- SHA-256 2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9
- 754 cells
- handler index 0: 673 cells
- non-default handlers: 81 cells
- 52 unique handler indices
- range 0..116

LEVEL01A.SAV:
- SHA-256 3d1753ca8a4ca49b3ccf9da0fc15bb08ac242301eff40586049379ceba635dc9
- 754 cells
- handler index 0: 736 cells
- non-default handlers: 18 cells
- 16 unique handler indices
- range 0..419

The dramatic change in handler distribution between the two starter states is
direct evidence that script/event state is materially relevant to navigation.

## Mutable cell+0x01 state

The routine near 0x6ADE5 copies the direction-selector table [10,11,12,13],
uses live facing/opposite facing, mutates low cell+0x02 state in several
branches, and sets the corresponding cell+0x01 directional selector.

This proves cell+0x01 is maintained as directional mutable state alongside
edge mutations.

However, no direct selector-10..13 read is present in the ordinary
forward/backward physical translation/precheck chain described above.

Current classification:

- cell+0x01: VERIFIED mutable directional state;
- direct ordinary player translation consumer: NOT OBSERVED;
- indirect custom handler use: possible and remains OPEN.

## Turn path

The turn precheck near 0xB11C3 computes the prospective facing, calls helper
0x41120 to inspect the current cell's MSP chain/orientation mask, and scans the
same monster-linked spatial index for selected blocker categories.

The turn executor near 0xB0E99 updates facing after animation/state work.

Rotation therefore has its own runtime occupancy constraints and must not be
modeled as a free graph operation without evidence.

## Player movement evidence model

For ordinary translation the current evidence is:

STATIC:
- low cell+0x02 direction bit = direct forward/backward primitive barrier.

RUNTIME PHYSICAL:
- cell+0x11 MSP/maze-prop directional clearance;
- monster-linked 0x0C spatial occupancy records / category veto.

SCRIPT/EVENT:
- signed cell+0x07 handler index;
- per-cell action callback can veto/trigger movement behavior.

OTHER ACTOR POLICY:
- cell0 0x10/0x80 and high cell+0x02 blockers are VERIFIED for monster
  actor-clearance, but are not directly consumed by the ordinary player
  translation primitive.

STATE TRACKING:
- cell+0x01 directional state is written with edge-state mutations but has no
  direct read in the generic translation path found so far.

## Tooling change

tools/inspect_level_save.py now reports the cell+0x07 event-handler field:

- default index;
- non-default cell count;
- unique handler count;
- min/max handler index;
- full index histogram.

tests/test_inspect_level_save.py includes a synthetic non-default handler
fixture. No original game/save data is committed.

## Evidence classification

VERIFIED:
- forward and backward direct translation use low cell+0x02 masks;
- successful primitives mutate live row/column by direction deltas;
- MSP/maze-prop chain participates in pre-movement clearance;
- the 0x0C spatial pool is linked to monster records and is scanned by player
  prechecks;
- cell+0x07 selects the per-cell action/event callback;
- the callback return value can veto pre-movement action handling;
- cell+0x01 direction state is written by edge-state mutation logic.

STRUCTURAL:
- selected 0x0C record category IDs represent runtime spatial blockers;
- specialized cell+0x07 handlers can encode navigation-affecting scripted
  behavior.

OPEN:
- exact meaning of every 0x0C blocker category ID;
- exact semantics of cell+0x01 in non-default handlers;
- full state machine for specialized cell+0x07 handlers;
- dynamic door/transition graph across every reachable state;
- final one-way/softlock analysis.

## K292-D gate

The next safe step is to construct an **evidence-typed player edge graph**:

- STATIC_BLOCKED — low static edge set;
- STATIC_CLEAR_RUNTIME_GATED — low static edge clear but runtime occupancy/
  event evaluation still required;
- SCRIPTED — edge/cell behavior depends on non-default handler state.

K292-D may analyze static candidate components, but must not report a CRITICAL
softlock until the relevant runtime/event state has been evaluated.

## Framework candidate

K292-C strengthens the NavigationEvidence / NavigationIR candidate with
actor-policy separation:

- primitive static edge policy;
- runtime physical occupancy;
- per-cell event/script veto;
- actor-specific blocker layers;
- mutable edge state;
- evidence level on every graph edge.

Promotion to OpenRemaster Framework remains cross-game evidence-gated.
