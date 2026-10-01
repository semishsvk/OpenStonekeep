# STONE-K292-E.5 — serialized initial-state player translation graph

- Date: 2026-10-01
- Status: **PASS — orientation-aware serialized initial translation layer built**
- Knowledge classification: GAME-SPECIFIC
- Scope: ordinary forward/backward translation attempts in the two authoritative starter saves

## Purpose

K292-E.2 closed the movement-callback return gate for all 59 non-default
movement-source handlers. K292-E.3 and E.4 independently decoded the two
physical precheck layers: MSP/maze-prop state and monster-linked spatial
occupancy.

E.5 composes those evidence layers with the reciprocal low cell+0x02 static
edge model into the first orientation-aware serialized initial-state player
translation graph.

This is deliberately a **translation graph**, not yet a complete dynamic world
state graph. Non-default callbacks can mutate state before/after translation,
so later transitions must consume explicit callback state deltas.

## State and attempt model

Each serialized level cell has four facing states:

    (row, column, facing), facing in {N,W,S,E}

For every in-bounds reciprocal low-static-clear oriented source->destination
edge in direction D, E.5 emits two ordinary movement attempts:

- forward: source facing = D, pre-action 3, post-action 2;
- backward: source facing = opposite(D), pre-action 5, post-action 4.

Physical precheck order is inherited from K292-E.4:

    static-clear candidate
      -> MSP/maze-prop precheck
      -> monster-linked spatial precheck
      -> pre-movement callback
      -> adjacent-cell translation
      -> post-movement callback

A physical block prevents the callback from running. If both physical layers
clear, K292-E.2 guarantees the current starter-corpus callback return gate
allows the ordinary translation for all 59 non-default movement-source
handlers; the default path is also the already traced allow path.

## Outcome vocabulary

Each movement attempt is classified as exactly one of:

- `BLOCKED_MSP`
- `BLOCKED_SPATIAL`
- `BLOCKED_MSP_AND_SPATIAL`
- `TRANSLATION_EXECUTES`

`TRANSLATION_EXECUTES` means the adjacent-cell translation instruction is
reached. It does **not** claim that the complete action leaves all world/player
state unchanged after the post callback.

For non-default callbacks, side-effect semantics remain `PARTIAL`; handlers
110, 111, 112, 115, 410 and 415 already have directly observed mutation/event
work on movement paths. Absence from that list is not interpreted as verified
absence of side effects.

## Authoritative corpus result

### LEVEL01.SAV

SHA-256:
`2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9`

- oriented player states: **3,016**
- reciprocal low-static-clear oriented edges: **1,358**
- ordinary movement attempts represented: **2,716**
- non-default movement-source handlers present: **48**

Forward attempts:

- `TRANSLATION_EXECUTES`: **1,322**
- `BLOCKED_MSP`: **28**
- `BLOCKED_SPATIAL`: **6**
- `BLOCKED_MSP_AND_SPATIAL`: **2**

Backward attempts:

- `TRANSLATION_EXECUTES`: **1,330**
- `BLOCKED_MSP`: **21**
- `BLOCKED_SPATIAL`: **6**
- `BLOCKED_MSP_AND_SPATIAL`: **1**

Additional state-qualified structure:

- oriented static-clear edges whose forward/backward outcome differs: **35**
- undirected static-clear interfaces affected by at least one physical block: **24**
- executing forward translations sourced from non-default callbacks: **108**
- executing backward translations sourced from non-default callbacks: **114**
- executing translations sourced from already observed mutating handler families:
  - forward: **11**
  - backward: **11**

The marginal blocker counts exactly reproduce K292-E.3 and E.4:
forward MSP=30, backward MSP=22, forward spatial=8, backward spatial=7.
The combined graph additionally proves the overlap: 2 forward and 1 backward
attempt are blocked by both physical layers simultaneously.

### LEVEL01A.SAV

SHA-256:
`3d1753ca8a4ca49b3ccf9da0fc15bb08ac242301eff40586049379ceba635dc9`

- oriented player states: **3,016**
- reciprocal low-static-clear oriented edges: **2,038**
- ordinary movement attempts represented: **4,076**
- non-default movement-source handlers present: **14**

Forward attempts:

- `TRANSLATION_EXECUTES`: **2,031**
- `BLOCKED_MSP`: **2**
- `BLOCKED_SPATIAL`: **5**
- `BLOCKED_MSP_AND_SPATIAL`: **0**

Backward attempts:

- `TRANSLATION_EXECUTES`: **2,031**
- `BLOCKED_MSP`: **2**
- `BLOCKED_SPATIAL`: **5**
- `BLOCKED_MSP_AND_SPATIAL`: **0**

Additional state-qualified structure:

- oriented static-clear edges whose forward/backward outcome differs: **12**
- undirected static-clear interfaces affected by at least one physical block: **7**
- executing translations sourced from non-default callbacks:
  - forward: **21**
  - backward: **20**
- executing translations sourced from already observed mutating handler families:
  - forward: **3**
  - backward: **3**

The marginal blocker counts exactly reproduce K292-E.3 and E.4. No MSP/spatial
double-block overlap occurs in this serialized starter snapshot.

## Corpus aggregate

Across both authoritative saves:

- oriented player states represented: **6,032**
- reciprocal low-static-clear oriented edges: **3,396**
- ordinary forward/backward movement attempts: **6,792**
- movement-source handler union: **59/59** from K292-E.2
- forward translations executing: **3,353 / 3,396**
- backward translations executing: **3,361 / 3,396**
- forward/backward outcome-asymmetric oriented edges: **47**
- physically affected undirected interfaces: **31**

The 47 asymmetric oriented edges are **not** promoted to one-way passages.
They are state/mode-qualified physical asymmetries in the serialized initial
snapshot. Turning, callback mutations, later MSP changes and later spatial
occupancy changes are separate transition dimensions.

## Tooling

Added:

- `tools/build_serialized_initial_transition_graph.py`
- `tests/test_build_serialized_initial_transition_graph.py`

The builder independently composes the already verified K292-E.2/E.3/E.4
rules, validates MSP and spatial chains, rejects missing callback-return
evidence for a non-default movement-source handler, and can emit every
orientation-qualified attempt with source/destination state, callback actions,
physical blocker evidence and callback side-effect uncertainty.

Synthetic regression: **4 PASS**.

Authoritative run:

    valid=true
    movement_source_handlers=59
    static_clear_oriented_edges=3396
    movement_attempts=6792
    forward_translation_executes=3353
    backward_translation_executes=3361
    mode_asymmetric_oriented_edges=47

## Evidence classification

VERIFIED for the serialized starter snapshots:

- the orientation-aware forward/backward attempt construction;
- exact composition of low-static, MSP, spatial and callback-return gates;
- the per-save and aggregate counts above;
- physical precheck blocks prevent callback invocation;
- the adjacent-cell translation executes on all physically clear ordinary
  movement attempts in the current callback-return scope.

STATE-QUALIFIED:

- every E.5 physical-clear/block result;
- every forward/backward mode asymmetry count.

PARTIAL:

- state deltas produced by movement callbacks;
- final action-complete world/player state after non-default post callbacks.

OPEN:

- callback mutation manifests for all movement-relevant handlers/actions;
- runtime MSP changes after events;
- runtime monster-spatial changes after actors move;
- turn transitions combined with movement state;
- multi-step reachability under state mutations;
- final one-way and softlock verdicts.

## Gate

`handler_target_resolution = VERIFIED`

`movement_callback_return_semantics = VERIFIED`

`serialized_msp_clearance = VERIFIED_STATE_QUALIFIED`

`serialized_monster_spatial_clearance = VERIFIED_STATE_QUALIFIED`

`serialized_initial_translation_graph = VERIFIED_STATE_QUALIFIED`

`callback_state_delta_semantics = PARTIAL`

`one_way_verdict_authorized = false`

`softlock_verdict_authorized = false`

## Next — STONE-K292-E.6

Freeze explicit movement-callback state-delta manifests for actions 2/3/4/5,
starting with the directly mutating families (110, 111, 112, 115, 410, 415),
then compose callback deltas with MSP/spatial mutations and turn transitions.
Only after that dynamic state graph is coverage-complete should one-way or
softlock analysis be authorized.
