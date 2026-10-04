# STONE-K292-E.15 — three-level portal graph and h89 reciprocal closure

- Date: 2026-10-04
- Status: **PASS — all 6/6 LEVEL01 outbound portal interfaces have an immediate same-interface return after the outbound transition executes**
- Knowledge classification: GAME-SPECIFIC
- Scope: LEVEL01 / LEVEL01A / LEVEL02 portal transitions composed from E.8–E.14

## Result

E.15 composes the verified portal and transition evidence into the first
three-level Stonekeep transition graph.

The graph now contains **12 verified/conditional portal edges**:

- LEVEL01 -> LEVEL01A: 4
- LEVEL01A -> LEVEL01: 4
- LEVEL01 -> LEVEL02: 2
- LEVEL02 -> LEVEL01: 2

Every one of the six LEVEL01 outbound portal interfaces has a verified
immediate same-interface return:

| LEVEL01 outbound | Target-level reciprocal | Result |
| ---: | ---: | --- |
| h87 | h411 | IMMEDIATE_SAME_INTERFACE_RETURN_VERIFIED |
| h88 | h412 | IMMEDIATE_SAME_INTERFACE_RETURN_VERIFIED |
| h89 | h415 | IMMEDIATE_SAME_INTERFACE_RETURN_VERIFIED |
| h90 | h413 | IMMEDIATE_SAME_INTERFACE_RETURN_VERIFIED |
| h106 | h144 | IMMEDIATE_SAME_INTERFACE_RETURN_VERIFIED |
| h107 | h145 | IMMEDIATE_SAME_INTERFACE_RETURN_VERIFIED |

For these six interfaces, the hypothesis that the portal itself becomes a
one-way trap after a successful outbound transition is **FALSIFIED**.

This is not a global softlock or global one-way proof for the game.

## Previously closed five pairs

E.13/E.14 closed the two LEVEL02 returns:

- h106 <-> h144
- h107 <-> h145

The existing LEVEL01 / LEVEL01A transition inventory directly closed:

- h87 <-> h411
- h88 <-> h412
- h90 <-> h413

E.15 closes the remaining h89 case.

## h89 -> h415 reciprocal

### Outbound h89

Verified E.8 payload:

    LEVEL01 h89
    source cell (23,3)
    gate N
      -> LEVEL01A
      -> spawn (22,3,S)

The serialized LEVEL01A arrival cell is:

    (22,3)
    handler 85
    cell+0x02 = 0x4F
    MSP aggregate = 0
    spatial categories = none

The adjacent cell is:

    (23,3)
    handler 415
    cell+0x02 = 0x8B
    selector4 = 30
    MSP aggregate = 0
    spatial categories = none

The S/N interface is reciprocal LOW+HIGH:

- (22,3) S: LOW 0x04 + HIGH 0x40
- (23,3) N: LOW 0x08 + HIGH 0x80

### h85 special opening

Handler 85 resolves through LE fixups to runtime 0x3D2EA.

For action 15 it has no wrapper-specific veto and reaches the default/common
handler path. The anchored common path returns EAX=1.

Therefore action 15 is ALLOW on the arrival cell.

E.9 then clears:

- (22,3) S LOW
- (23,3) N LOW

while preserving the HIGH marker bits.

After that LOW clear, the crossing is physically clear in the authoritative
LEVEL01A snapshot:

- MSP blocker: false
- monster-spatial blocker: false

The player can therefore cross S into (23,3,S).

## Turn closure at h415

The turn input branches call runtime 0x82BC3 before applying rotation at
0x82899.

0x82BC3 tests:

1. current-cell MSP state through 0x12B20 for the prospective facing;
2. current-cell monster-spatial categories.

At LEVEL01A (23,3):

- MSP aggregate = 0
- spatial category list = empty

Therefore the physical turn precheck is CLEAR for both turn directions.

Runtime 0x82899 updates facing as:

- turn argument +2: facing = (facing + 1) mod 4
- turn argument -2: facing = (facing + 3) mod 4

Two turns in either same direction transform:

    S -> E -> N

or:

    S -> W -> N

The current-cell callback is h415. Actions 6/8 do not enter its transition-only
2/3 branch or a turn veto branch. They continue through 0x4FC57 -> 0x6A230 ->
generic/default handling and return success/nonzero.

Thus S -> N rotation on (23,3) is VERIFIED executable.

## h415 transition payload

Handler 415 resolves to runtime 0x4F983.

For movement actions 2/3 with live facing N, the h415 wrapper enters 0x4FB00,
performs its directly evidenced state updates, then calls the already verified
transition common family 0x3CFEE at 0x4FC22.

The call payload decodes as:

    source level = 15
    source cell = (23,3)
    source direction = N
    target level = 1
    target row = 22
    target column = 3
    target facing = S

Therefore:

    LEVEL01A h415 (23,3) N
      -> LEVEL01
      -> spawn (22,3,S)

This is the exact same-interface reciprocal of h89.

## Verified h89 return sequence

The complete evidence-backed sequence is:

    LEVEL01 h89
      -> LEVEL01A (22,3,S)
      -> h85 action15 ALLOW
      -> E.9 reciprocal LOW clear
      -> forward S to (23,3,S)
      -> turn twice to N
      -> forward N
      -> h415 action3 -> 0x3CFEE
      -> ordinary transition action2 commit
      -> LEVEL01 (22,3,S)

No target-level search for another portal is required.

## Executable evidence anchors

Added `tools/inspect_h89_reciprocal_return.py`.

It validates exact SHA-256 code-region anchors for:

- h85 wrapper
- default callback core
- h415 action2/3 transition region
- h415 common turn-action continuation
- turn input branches
- turn physical precheck
- turn facing apply routine

Authoritative result:

    PASS reciprocal=True regions=7 errors=0

## Three-level graph validation

Updated:

- `tools/build_three_level_portal_graph.py`
- `tests/test_build_three_level_portal_graph.py`
- `tests/test_inspect_h89_reciprocal_return.py`

A clean HomePC verification copy of the current branch compiled successfully.
The two fixture-free regression modules were executed directly and passed.

Authoritative corpus run:

    PASS edges=12 immediate_return=6/6 unresolved=[] errors=0
     h87  -> L15 return=411 IMMEDIATE_SAME_INTERFACE_RETURN_VERIFIED
     h88  -> L15 return=412 IMMEDIATE_SAME_INTERFACE_RETURN_VERIFIED
     h89  -> L15 return=415 IMMEDIATE_SAME_INTERFACE_RETURN_VERIFIED
     h90  -> L15 return=413 IMMEDIATE_SAME_INTERFACE_RETURN_VERIFIED
     h106 -> L2  return=144 IMMEDIATE_SAME_INTERFACE_RETURN_VERIFIED
     h107 -> L2  return=145 IMMEDIATE_SAME_INTERFACE_RETURN_VERIFIED

## Evidence classification

VERIFIED:

- 12-edge three-level portal graph;
- six LEVEL01 outbound interfaces;
- six same-interface return sequences;
- h89 arrival LOW+HIGH portal state;
- h85 action-15 allow;
- h89 arrival-interface post-open MSP/spatial clearance;
- turn physical precheck at h415 source;
- two-turn S -> N facing reachability;
- h415 action6/8 turn callback success;
- h415 conditional transition entry for actions2/3 + facing N;
- exact h415 L15 -> L1 reciprocal payload.

FALSIFIED:

- any of the six known LEVEL01 outbound portal interfaces is intrinsically
  one-way after its outbound transition has executed;
- h89 requires navigation to a different target-level portal in order to
  return across its source interface.

STATE-QUALIFIED:

- the three E.10 producer-gated LEVEL01 outbound portal enable paths retain
  their already documented producer qualifications;
- runtime actor/MSP changes after the serialized snapshots remain stateful.

OPEN:

- complete ordinary-movement + turn graph across LEVEL01, LEVEL01A and LEVEL02;
- callback/event state mutation closure outside the portal sequences above;
- broader world progression outside these three levels;
- global one-way and softlock verdicts.

## Gate

`three_level_portal_graph = VERIFIED_STATE_QUALIFIED`

`three_level_portal_edge_count = 12`

`level01_outbound_portal_interfaces = 6`

`immediate_same_interface_return = 6/6 VERIFIED`

`portal_interface_one_way_concern = FALSIFIED_FOR_6_OF_6_KNOWN_LEVEL01_OUTBOUND_INTERFACES`

`global_one_way_verdict_authorized = false`

`global_softlock_verdict_authorized = false`

## Next — STONE-K292-E.16

Build the first state-qualified ordinary-movement + turn graph for the
three-level scope.

Reuse the verified translation gates, the newly closed turn gate semantics and
the 12 portal edges. Track callback/event mutations explicitly and report
strongly connected / escape properties only where all required state
dependencies are represented.

Do not promote portal-level reciprocity into a global softlock guarantee.
