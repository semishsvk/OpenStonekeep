# STONE-K292-E.9 — special portal enable / cancel state machine

- Date: 2026-10-01
- Status: **PASS — starter transition-family portal enable/cancel semantics VERIFIED**
- Knowledge classification: GAME-SPECIFIC
- Scope: the nine E.8 starter transition interfaces and the engine special-barrier movement path

## Result

E.8 proved that all nine starter level-transition interfaces are serialized as
reciprocally LOW-static-closed edges, which appeared incompatible with the
ordinary translation primitive.

E.9 resolves that apparent contradiction.

The engine has a separate movement path for an **immediate LOW barrier carrying
the matching HIGH-secondary direction bit**. That path calls the current cell
handler with action 15, temporarily clears the reciprocal LOW edge through the
generic selector-2 API, runs its movement/animation phase, and leaves the edge
in an armed open state. A subsequent forward input then follows the ordinary
movement path and reaches the already VERIFIED E.8 action-3/action-2
level-transition logic.

A cancellation path calls actions 17/18 and restores the reciprocal LOW edge.

The HIGH-secondary bit is preserved throughout this open/reclose cycle. For
this state machine it is therefore an evidence-backed special-barrier marker,
while the LOW bit carries the current ordinary-translation closed/open state.

## Direction mask tables

The special path uses relocation-sensitive data in object 3.

At object 3 + `0xFCD5`:

    F7 FD FB FE

These are exactly the bytewise complements of the verified LOW masks:

    N W S E = 08 02 04 01

At object 3 + `0xFCD9`:

    08 02 04 01

Therefore:

- `AND FCD5[direction]` clears exactly the selected LOW edge bit;
- `OR FCD9[direction]` restores exactly the selected LOW edge bit.

No HIGH-secondary bit is changed by either operation.

## Special-barrier detection

Runtime `0x13646` scans from the live player cell in a requested direction.

It:

1. loads the LOW direction mask from the verified LOW table;
2. loads the matching HIGH-secondary direction mask;
3. scans at most five cells;
4. reads selector 2 / `cell+0x02`;
5. stops at the first LOW wall;
6. stores `cell+0x02 & HIGH_mask` into `0x1BC4E4`;
7. returns the distance to that LOW wall.

The forward input dispatcher uses this result:

- `0x1BC4E4 != 0`;
- wall distance `0x1BC5C2 == 0`;
- special movement state `0x1BC4E2 == 0`;

to divert from the ordinary physical-precheck path into runtime `0x2CE8B`.

Thus an immediate LOW+HIGH barrier is handled by the special state machine
before the ordinary forward translation primitive sees the closed LOW edge.

## Starter portal marker coverage

All nine E.8 transition interfaces have the matching special marker on **both**
sides in the authoritative serialized saves:

- source LOW bit set: 9/9
- source matching HIGH bit set: 9/9
- adjacent reciprocal LOW bit set: 9/9
- adjacent reciprocal HIGH bit set: 9/9
- complete reciprocal LOW+HIGH special marker: **9/9**

Examples:

- S-facing portal source: `cell+0x02 = 0x47` -> LOW S `0x04` + HIGH S `0x40`;
- reciprocal north side: `0x8F` -> LOW N `0x08` + HIGH N `0x80`;
- N-facing source: `0x8B`;
- W-facing source: `0x2E`.

The exact byte contains unrelated direction bits as well; only the selected
direction pair is claimed here.

## State machine

### 0 — CLOSED_SPECIAL

Serialized / idle portal state:

- source and reciprocal adjacent edge have LOW + matching HIGH bits;
- ordinary translation would reject the LOW bit;
- HIGH scan identifies the immediate edge as special.

Forward input diverts to `0x2CE8B`.

### action 15 — ENABLE gate

`0x2CE8B` snapshots live row/column/facing and invokes the current cell
handler with action 15.

The E.8 transition family at `0x3CFEE` only specializes actions 2, 3 and 31.
Actions 15, 16, 17 and 18 fall through to `0x3D4F5`.

For LEVEL01 and LEVEL01A, E.7 proved the per-level callback used by
`0x3D4F5` is an exact `RET`; the default callback path returns 1.

Therefore action 15 is **ALLOW_VERIFIED** for all nine starter transition
handlers.

### 1 — OPENING

After action 15 succeeds, `0x2CE8B`:

- reads selector 2 at the source cell;
- ANDs with `FCD5[facing]`;
- writes selector 2 back;
- computes the adjacent cell;
- ANDs its selector 2 with `FCD5[opposite(facing)]`;
- writes it back.

This clears the reciprocal LOW edge on both sides while preserving HIGH.

It recalculates directional state and sets:

    0x1BC4E2 = 1

while the special movement/animation sequence executes.

### 2 — OPEN_ARMED

At the end of the opening sequence:

    0x1BC4E2 = 2

and action 16 is invoked.

The source/adjacent LOW bits remain clear at return from `0x2CE8B`.
HIGH markers remain set.

Because the immediate LOW wall has been cleared, the next forward input no
longer satisfies the immediate LOW+HIGH diversion condition for this
interface, and proceeds through the ordinary forward path.

### FORWARD COMMIT

On the next forward attempt:

1. ordinary physical precheck executes;
2. action 3 executes;
3. for the transition family action 3 invokes the E.8 `A2D76` pre-transition
   event path;
4. when `0x1BC4E2 == 2`, the input path advances it to state 4;
5. ordinary forward translation executes through the now-clear LOW edge;
6. action 2 executes;
7. action 2 invokes E.8 `A2DC7 -> A2BA6`;
8. the staged destination/player transform and event-type-8 level transfer are
   committed as VERIFIED in E.8.

Thus the transition is a multi-input, state-qualified path rather than a
single traversal of a statically open graph edge.

### CANCEL / RECLOSE

Several non-forward input branches detect:

    0x1BC4E2 == 2

and call runtime `0x2D150`.

This path:

1. invokes action 17;
2. enters special state 3;
3. runs its close/animation sequence;
4. reads selector 2 on the stored source cell and ORs
   `FCD9[facing]`;
5. reads selector 2 on the adjacent cell and ORs
   `FCD9[opposite(facing)]`;
6. writes both fields back;
7. recalculates directional state;
8. resets `0x1BC4E2 = 0`;
9. invokes action 18.

Actions 17 and 18 use the same VERIFIED starter default-allow path as action
15.

The cancellation path therefore restores the reciprocal LOW closure while
leaving the HIGH special marker intact.

## Why E.5 was correct

E.5 classified the serialized initial portals as blocked because the ordinary
translation primitive directly tests LOW `cell+0x02`.

That remains correct for the serialized idle snapshot.

E.9 adds the missing state transition:

    CLOSED_SPECIAL
      -> special action15 enable
      -> OPEN_ARMED
      -> ordinary translation
      -> action2 level transition

or:

    CLOSED_SPECIAL
      -> special action15 enable
      -> OPEN_ARMED
      -> cancel/action17
      -> CLOSED_SPECIAL

Static graph evidence was not wrong; it was incomplete without the
HIGH-secondary special movement state.

## Reproducibility

Added:

- `tools/inspect_portal_enable_state.py`
- `tests/test_inspect_portal_enable_state.py`

The validator requires the authoritative SK.EXE and starter-save hashes,
reuses the E.8 transition inventory and E.7 level-hook proof, and validates:

- exact object-3 clear mask table;
- exact object-3 set mask table;
- **6/6** executable state-machine region SHA-256 anchors;
- **9/9** reciprocal LOW+HIGH portal markers;
- starter per-level callback targets remain exact `RET`.

Authoritative evidence rerun:

    PASS exe_hash=1 masks=2 region_anchors=6 portal_markers=9
    actions_15_18=E7_default_allow

Synthetic/structural regression logic: **4/4 PASS**.

## Evidence classification

VERIFIED for the nine starter transition interfaces:

- LOW+HIGH special-barrier detection;
- reciprocal LOW clear masks;
- reciprocal LOW restore masks;
- HIGH marker preservation by the clear/restore operations;
- action-15 allow gate;
- open state progression to `0x1BC4E2 == 2`;
- next-forward ordinary translation path;
- action-3/action-2 transition commit chain from E.8;
- action-17 cancel/reclose path;
- reciprocal LOW closure restoration;
- action-18 completion path.

STATE-QUALIFIED:

- portal traversability depends on the special movement state, not only the
  serialized cell byte.

FALSIFIED:

- E.8 action-3 helper `A2D76` is itself the LOW-edge unlock;
- the nine starter transition interfaces are ordinary statically open edges.

OPEN:

- composition of this portal state machine into the complete multi-step
  orientation/player-state graph;
- interactions with live MSP/spatial occupancy changes while the portal is
  armed;
- complete turn-state integration;
- final one-way and softlock analysis.

## Gate

`starter_portal_enable_state_machine = VERIFIED`

`starter_transition_portal_markers = 9/9 VERIFIED`

`portal_low_clear_restore = VERIFIED`

`portal_transition_commit = VERIFIED`

`portal_dynamic_graph_layer = READY_TO_COMPOSE`

`one_way_verdict_authorized = false`

`softlock_verdict_authorized = false`

## Next — STONE-K292-E.10

Compose the E.9 CLOSED_SPECIAL -> OPEN_ARMED -> COMMIT/CANCEL states with E.5
orientation-aware translation, E.3 MSP clearance and E.4 monster-spatial
occupancy. Preserve dynamic occupancy/state uncertainty explicitly. Only then
begin state-qualified reachability and candidate one-way analysis.
