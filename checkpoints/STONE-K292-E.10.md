# STONE-K292-E.10 — blocked starter portal state producers

- Date: 2026-10-02
- Status: **PASS — selector-4 producer mechanism VERIFIED; producer reachability is runtime-selection-qualified**
- Knowledge classification: GAME-SPECIFIC
- Scope: the three E.9 starter portals whose serialized action-15 gate is initially blocked: handlers 87, 106 and 107

## Result

E.9 reduced the unresolved starter portal set to three LEVEL01 source handlers:

- handler 87 at cell (2,3): selector 4 = 0, action 15 requires selector 4 != 0;
- handler 106 at cell (11,5): selector 4 = -1, action 15 requires selector 4 != -1;
- handler 107 at cell (7,25): selector 4 = -1, action 15 requires selector 4 != -1.

E.10 identifies a common input-reachable current-cell producer for all three
states.

The producer chain is:

    input/command dispatch
      -> 0x6A3DF
      -> read current-cell selector 5
      -> 0x6A433(current cell, selector-5 payload)
      -> runtime selected-record gate
      -> current-cell selector 4 mutation

No original Stonekeep data are committed.

## Serialized payloads

Authoritative LEVEL01.SAV:

| Handler | Cell | Initial selector 4 | Selector 5 payload | Initial action-15 |
| ---: | --- | ---: | ---: | --- |
| 87 | (2,3) | 0 | 0 | BLOCKED |
| 106 | (11,5) | -1 | 166 | BLOCKED |
| 107 | (7,25) | -1 | 166 | BLOCKED |

All three selector-5 values are non-negative, so runtime 0x6A3DF takes the
direct 0x6A433 producer path rather than its negative-selector-5 action-19
fallback.

## Producer mutation

Runtime 0x6A433 reads current-cell selector 4 and writes:

    selector4 = -1  if selector4 == 1
    selector4 = +1  otherwise

Therefore a successful producer invocation transforms the three authoritative
starter states as follows:

- handler 87: 0 -> 1;
- handler 106: -1 -> 1;
- handler 107: -1 -> 1.

After that mutation, action 15 is ALLOW for all three handlers.

A second successful invocation produces 1 -> -1.

This has different portal consequences:

- handler 87 uses the predicate selector4 != 0, therefore after the first
  successful producer invocation both +1 and -1 remain action-15 eligible;
- handlers 106/107 use selector4 != -1, therefore repeated successful
  invocations toggle their action-15 eligibility between ALLOW (+1) and
  BLOCKED (-1).

This is direct evidence of different dynamic portal-state semantics despite the
shared producer.

## Runtime selection gate

0x6A433 does not mutate the cell unconditionally.

After its selection/event step, it reads the runtime selection handle at
0x1BC6A8 and indexes the 0x2F-byte record pool at 0x19E2E0.

The producer proceeds when either:

    s16(selected_record + 0x00) == selector5_payload

or the alternate helper 0x27D8D returns nonzero.

The alternate 0x27D8D path is structurally available only for payloads
0x99..0xAE and requires selected-record type 0xAF plus the matching bit state.

Consequences for the three portals:

- handler 87 payload 0: alternate 0x27D8D range does not apply; the directly
  evidenced gate is selected_record[0] == 0;
- handlers 106/107 payload 166 (0xA6): direct equality can pass, and the
  0x27D8D 0xAF/bitmask alternative is also structurally available.

The exact player-visible object/interaction availability for those runtime
selection states is intentionally not inferred from this static checkpoint.
Producer mechanics are VERIFIED; producer reachability is
STATE_QUALIFIED_RUNTIME_SELECTION.

## Input reachability

0x6A3DF has direct callsites in the main input/command path, including runtime
0x32151, plus a secondary dispatch wrapper at 0x49D17.

E.10 therefore classifies the producer as an input-reachable current-cell
activation path. It does not assign a designer-facing verb/key name without
additional evidence.

## Reciprocal-side hypothesis

The E.9 portal neighbors suggested handlers 85 and 114 as possible reciprocal
unlock producers.

Direct tracing rejects that hypothesis for the missing selector-4 state:

- handler 85 resolves to runtime 0x3D2EA and does not produce selector-4 state
  for the three portal source cells;
- handler 114 resolves to runtime 0x5F3FD; its action-2 special path writes a
  different fixed cell and does not produce the missing selector-4 state.

Thus the missing producer is the shared 0x6A3DF -> 0x6A433 activation path,
not the reciprocal portal-cell handler.

## Corrected false lead

A byte-level search found a hardcoded write:

    cell(2,3) selector4 = 1

at runtime 0x66CA6.

Dispatch and level-initializer mapping prove that code belongs to LEVEL09,
handler 325, not LEVEL01. It is therefore excluded from E.10 evidence for
handler 87.

This prevents an identical coordinate in another level module from being
mistaken for the LEVEL01 producer.

## Reproducibility

Added:

- `tools/inspect_portal_state_producers.py`
- `tests/test_inspect_portal_state_producers.py`

The validator requires:

- SK.EXE SHA-256
  `5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2`
- LEVEL01.SAV SHA-256
  `2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9`

It validates:

- all three source cells and their handler IDs;
- selector-4 / selector-5 starter values;
- LE-resolved dispatch targets for handlers 87/106/107;
- **7/7** executable code-region SHA-256 anchors;
- producer toggle semantics;
- action-15 consequence of one and two successful producer invocations.

Authoritative run:

    PASS portals=3 regions=7 errors=0
    h87  s4=0  payload=0   -> 1  action15=true; second=-1 action15=true
    h106 s4=-1 payload=166 -> 1  action15=true; second=-1 action15=false
    h107 s4=-1 payload=166 -> 1  action15=true; second=-1 action15=false

Synthetic/structural regression: **4 PASS**.

## Evidence classification

VERIFIED:

- 0x6A3DF reads current-cell selector 5 and dispatches non-negative payloads to
  0x6A433;
- 0x6A433 is a direct current-cell selector-4 producer;
- its successful mutation is 1 -> -1, otherwise -> +1;
- the runtime selected-record direct gate;
- the 0x27D8D alternate-gate structural range and 0xAF/bit-state requirement;
- starter selector-4/selector-5 values for handlers 87/106/107;
- one successful producer invocation makes action 15 ALLOW for all three;
- repeated producer success leaves handler 87 enabled but toggles 106/107
  between enabled and blocked;
- reciprocal handlers 85/114 are not the missing direct producer;
- runtime 0x66CA6 is LEVEL09 evidence and not a LEVEL01 producer.

STATE-QUALIFIED:

- availability of a runtime selected record satisfying the producer gate;
- exact player-visible interaction sequence that establishes that selection.

OPEN:

- runtime reachability of each qualifying selection/object state from the
  authoritative starter snapshot;
- composition with MSP and monster-spatial changes after activation;
- complete multi-step world reachability;
- final one-way and softlock verdicts.

## Gate

`starter_portal_enable_producer = VERIFIED`

`blocked_portal_producer_coverage = 3/3`

`portal_producer_reachability = VERIFIED_STATE_QUALIFIED`

`serialized_action15_blocked = 3/9`

`action15_after_successful_producer = 9/9 ALLOW`

`dynamic_portal_state_machine = READY_FOR_CONDITIONAL_COMPOSITION`

`one_way_verdict_authorized = false`

`softlock_verdict_authorized = false`

## Next — STONE-K292-E.11

Compose E.9 portal OPEN/CANCEL/COMMIT states with the E.10 conditional
selector-4 producer, E.3 MSP state, E.4 monster-spatial occupancy and E.8
level-transfer payloads.

Represent producer-gated edges explicitly rather than assuming the runtime
selection predicate is satisfied. Then compute conditional multi-step
reachability without promoting unresolved runtime-selection availability to a
guaranteed path.
