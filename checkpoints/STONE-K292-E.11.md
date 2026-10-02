# STONE-K292-E.11 — conditional multi-step starter portal graph

- Date: 2026-10-02
- Status: **PASS — all nine portal transitions reach commit after their required enable state**
- Knowledge classification: GAME-SPECIFIC
- Scope: compose E.3/E.4/E.8/E.9/E.10 for the nine starter portal interfaces

## Result

E.11 composes the previously independent portal evidence layers:

1. E.9 special LOW+HIGH portal detection and reciprocal LOW opening;
2. E.10 selector-4 producer for the three initially blocked action-15 gates;
3. E.3 MSP/maze-prop physical precheck;
4. E.4 monster-linked spatial occupancy precheck;
5. E.8 action-2 level-transition commit payload.

The key result is that **all 9/9 portal interfaces are physically clear after
the verified E.9 reciprocal LOW clear** in the authoritative serialized
starter snapshots.

Therefore the starter portal set divides into:

- **6 direct-enable portals** — serialized action 15 already ALLOW;
- **3 producer-conditional portals** — a successful E.10
  runtime-selection-qualified producer must first make action 15 ALLOW.

After that required enable state, **9/9 reach the E.8 transition commit path**.

## Post-open physical clearance

E.9 mutates only the reciprocal LOW direction bits. MSP and monster-spatial
state are independent physical layers, so E.11 evaluates the already verified
E.3/E.4 rules on each portal interface while treating the LOW edge as open.

Authoritative result for all nine portals:

- source MSP mask relevant to the portal move: 0;
- destination MSP mask relevant to the portal move: 0;
- source blocking spatial categories: none;
- destination blocking spatial categories: none;
- MSP blocked after LOW clear: **0/9**;
- monster-spatial blocked after LOW clear: **0/9**;
- physical-clear after LOW clear: **9/9**.

No second physical blocker is hidden behind the initially closed special edge
in the serialized starter state.

## Enable classes

### Direct action-15 enable

Six portals require no E.10 selector-4 producer in the serialized snapshot:

- LEVEL01 handler 88;
- LEVEL01 handlers 89 and 90;
- LEVEL01A handlers 411, 412 and 413.

For these interfaces the evidenced sequence is:

    CLOSED_SPECIAL
      -> action15 ALLOW
      -> OPENING
      -> reciprocal LOW clear
      -> OPEN_ARMED
      -> next forward physical precheck CLEAR
      -> action3
      -> ordinary translation
      -> action2
      -> E.8 level transfer

### E.10 producer-conditional enable

Three LEVEL01 portals begin with action 15 blocked:

- handler 87;
- handler 106;
- handler 107.

Their evidenced conditional sequence is:

    CLOSED_SPECIAL_ACTION15_BLOCKED
      -> E.10 runtime-selection gate
      -> successful 0x6A3DF -> 0x6A433 producer
      -> selector4 = +1
      -> action15 ALLOW
      -> OPENING
      -> reciprocal LOW clear
      -> OPEN_ARMED
      -> next forward physical precheck CLEAR
      -> action3
      -> ordinary translation
      -> action2
      -> E.8 level transfer

The transition after producer success is verified. Whether the required
runtime selected-record condition is reachable in a particular play state
remains explicit state-qualified evidence rather than an assumed path.

## Level-transition edges

The nine conditional graph edges are distributed as:

- LEVEL01 -> LEVEL01A: **4**
- LEVEL01A -> LEVEL01: **3**
- LEVEL01 -> level 2: **2**

This count is descriptive only.

The asymmetry between four 1->15 transition handlers and three 15->1
transition handlers is **not** promoted to a one-way-world verdict. Other
stateful paths, different source cells and the incomplete level-2 continuation
remain outside this checkpoint.

## State semantics

For each portal E.11 retains:

- source level / handler / cell / facing gate;
- target level and staged target row/column/facing from E.8;
- serialized action-15 result from E.9;
- whether E.10 producer success is required;
- MSP and spatial evidence after LOW clear;
- complete state path to transition commit;
- uncertainty on the E.10 runtime selection predicate where applicable.

The graph therefore represents conditional transitions rather than flattening
producer-dependent portals into guaranteed edges.

## Tooling

Added:

- `tools/build_conditional_portal_graph.py`
- `tests/test_build_conditional_portal_graph.py`

The builder re-runs E.9 and E.10 validation, reconstructs the serialized MSP
and monster-spatial state through the existing verified readers, evaluates
each portal after reciprocal LOW clear and fails closed if:

- an E.10 producer is missing for an initially blocked portal;
- MSP/spatial chain validation fails;
- any portal remains physically blocked after opening;
- any portal cannot reach transition commit after its required enable state.

Authoritative composition result:

    portals=9
    direct_enable=6
    producer_conditional=3
    physical_clear_after_open=9
    transition_commit_reached_after_required_enable=9
    errors=0

Synthetic composition coverage includes direct-enable, producer-conditional,
missing-producer and post-open physical-block fail-closed cases.

## Evidence classification

VERIFIED for the serialized starter physical state:

- post-open MSP clearance for 9/9 portal interfaces;
- post-open monster-spatial clearance for 9/9 portal interfaces;
- six direct action-15 enable paths;
- three E.10 producer-dependent action-15 paths;
- transition commit after the required enable state for 9/9 portals;
- transition distribution 1->15 x4, 15->1 x3, 1->2 x2.

STATE-QUALIFIED:

- the three E.10 runtime selected-record producer gates;
- all portal transitions after runtime MSP/spatial state has changed from the
  serialized snapshot.

OPEN:

- actual reachability of qualifying selected-record states for E.10 payloads
  0 and 166;
- level-2 continuation/return transition state in the current starter corpus;
- other runtime mutations after actors or MSP records move/change;
- complete world-level multi-step reachability;
- final one-way and softlock verdicts.

## Gate

`starter_portal_mechanism = VERIFIED`

`starter_portal_post_open_physical_clearance = 9/9 VERIFIED_STATE_QUALIFIED`

`starter_portal_direct_enable = 6/9`

`starter_portal_producer_conditional = 3/9`

`starter_portal_commit_after_required_enable = 9/9`

`conditional_portal_graph = VERIFIED_STATE_QUALIFIED`

`one_way_verdict_authorized = false`

`softlock_verdict_authorized = false`

## Next — STONE-K292-E.12

Resolve runtime-selection reachability for the E.10 payloads:

- handler 87 payload 0;
- handlers 106/107 payload 166.

Trace how 0x1BC6A8 is populated by the input/selection pipeline and bind the
qualifying 0x2F-byte selected-record states to authoritative starter runtime or
serialized object evidence where possible.

In parallel, locate the level-2 starter/initial state needed to continue the
two verified LEVEL01 -> level2 transition edges before attempting any
world-level one-way or softlock analysis.
