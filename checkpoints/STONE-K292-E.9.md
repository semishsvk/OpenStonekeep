# STONE-K292-E.9 — special portal enable / cancel state machine

- Date: 2026-10-01
- Status: **PASS — portal mechanism VERIFIED; action-15 enable gate is state-qualified**
- Knowledge classification: GAME-SPECIFIC
- Scope: the nine E.8 starter transition interfaces and the engine special-barrier movement path

## Correction to the first E.9 freeze

The first E.9 checkpoint correctly resolved the HIGH-secondary special-barrier
path and the reciprocal LOW clear/restore mechanism, but over-generalized the
common `0x3CFEE` action-15 behavior to every wrapper.

Direct wrapper tracing proves that several transition handlers add an
action-15 precondition **before** delegating to the common family.

The corrected serialized starter result is therefore:

- reciprocal LOW+HIGH transition markers: **9/9**
- action-15 ALLOW in the serialized snapshot: **6/9**
- action-15 BLOCKED in the serialized snapshot: **3/9**

The mechanism itself remains verified. Portal enablement is explicitly
state-qualified.

## Special-barrier detection

Runtime `0x13646` scans from the live player cell in a requested direction.

It loads:

- LOW direction masks: N/W/S/E = `08/02/04/01`
- matching HIGH-secondary masks: `80/20/40/10`

It stops at the first LOW wall, stores:

    cell+0x02 & HIGH_mask -> 0x1BC4E4

and returns the distance to that LOW wall.

The forward input dispatcher diverts to runtime `0x2CE8B` when:

- `0x1BC4E4 != 0`
- wall distance `0x1BC5C2 == 0`
- special state `0x1BC4E2 == 0`

Thus an **immediate LOW+HIGH edge** is processed by the special path before the
ordinary translation primitive tests the LOW bit.

## Reciprocal marker coverage

All nine E.8 transition interfaces carry the marker on both sides:

- source LOW: 9/9
- source matching HIGH: 9/9
- adjacent reciprocal LOW: 9/9
- adjacent reciprocal HIGH: 9/9
- complete reciprocal LOW+HIGH marker: **9/9**

Examples:

- S source `0x47` contains LOW S `0x04` + HIGH S `0x40`
- reciprocal N side `0x8F` contains LOW N `0x08` + HIGH N `0x80`
- N source examples use `0x8B`
- W source example uses `0x2E`

Only the selected direction bits are interpreted here; the complete cell byte
may contain unrelated direction flags.

## Exact LOW mutation masks

Object 3 + `0xFCD5`:

    F7 FD FB FE

These are exactly:

    ~08, ~02, ~04, ~01

Object 3 + `0xFCD9`:

    08 02 04 01

Therefore the special path performs an exact directional LOW clear with
`AND FCD5[dir]`, while the cancel/restore path performs an exact LOW set with
`OR FCD9[dir]`.

Neither operation clears the matching HIGH-secondary marker.

## Wrapper-specific action-15 gates

### LEVEL01

Handler 87, source cell `(2,3)`:

    allow iff cell(2,3)+0x09 != 0

Serialized value:

    0

Result:

    BLOCKED

Handler 88, source cell `(2,25)`:

    allow iff current cell+0x09 != -1

Serialized value:

    1

Result:

    ALLOW

Handlers 89 and 90:

    no extra action-15 wrapper gate

Result:

    ALLOW / ALLOW

Handlers 106 and 107:

    allow iff current cell+0x09 != -1

Serialized values:

    -1 / -1

Result:

    BLOCKED / BLOCKED

LEVEL01 serialized action-15 result:

- ALLOW: handlers **88, 89, 90**
- BLOCKED: handlers **87, 106, 107**

### LEVEL01A

Handlers 411, 412 and 413 delegate action 15 directly to the common transition
family.

Result:

- 411: ALLOW
- 412: ALLOW
- 413: ALLOW

### Aggregate

Starter transition handlers:

- ALLOW: **6**
- BLOCKED: **3**
- total: **9**

The common transition family/default path still returns success after a
wrapper gate passes. E.7 proves the starter per-level global callback in that
path is an exact `RET`.

## State machine

### CLOSED_SPECIAL

The idle portal edge has reciprocal LOW+HIGH markers.

Ordinary translation would reject LOW, but the HIGH scan diverts the immediate
edge to the special movement path.

### ENABLE_GATE — action 15

`0x2CE8B` snapshots live row/column/facing and invokes action 15 on the
current cell handler.

- if the wrapper returns 0: the portal remains CLOSED_SPECIAL;
- if it returns nonzero: the engine enters OPENING.

This is the state dependency missing from the first E.9 freeze.

### OPENING — state 1

After a successful action-15 gate, `0x2CE8B`:

1. reads selector 2 on the source cell;
2. clears exactly the facing LOW bit via `FCD5[facing]`;
3. writes selector 2 back;
4. computes the adjacent cell;
5. clears its exact reciprocal LOW bit;
6. recalculates direction state;
7. sets `0x1BC4E2 = 1`.

The HIGH marker remains set.

### OPEN_ARMED — state 2

After the opening movement/animation phase:

    0x1BC4E2 = 2

and action 16 is invoked.

The LOW edge remains clear on both sides when `0x2CE8B` returns.

### FORWARD COMMIT

On a subsequent forward input, the immediate LOW wall is no longer present, so
the engine follows the ordinary forward path.

For a transition-source handler:

1. physical precheck;
2. action 3;
3. E.8 `A2D76` transition/event preparation;
4. if `0x1BC4E2 == 2`, advance to state 4;
5. ordinary grid translation across the clear edge;
6. action 2;
7. E.8 `A2DC7 -> A2BA6 -> event type 8 -> 0x5DC10` level transfer.

The level-transfer payload itself remains VERIFIED by E.8.

### CANCEL / RECLOSE

Non-forward input branches that encounter state 2 can call `0x2D150`.

That path:

1. invokes action 17;
2. enters state 3;
3. runs close/animation work;
4. ORs the source selector-2 byte with `FCD9[facing]`;
5. ORs the adjacent selector-2 byte with the opposite LOW mask;
6. recalculates directional state;
7. returns the special state to 0;
8. invokes action 18.

The reciprocal LOW closure is therefore restored while HIGH remains present.

## Reproducibility

Updated:

- `tools/inspect_portal_enable_state.py`
- `tests/test_inspect_portal_enable_state.py`

The validator now checks:

- authoritative executable/save SHA-256 values;
- exact LOW clear/set tables;
- **11/11** executable code-region hashes, including all wrapper families that
  affect action 15;
- **9/9** reciprocal LOW+HIGH portal markers;
- wrapper-specific serialized action-15 conditions;
- E.7 starter callback no-op evidence.

Correct serialized result:

    portals=9
    reciprocal_low_high=9
    action15_allow=6
    action15_blocked=3
    errors=0

## Evidence classification

VERIFIED:

- HIGH-secondary immediate-barrier detection;
- exact reciprocal LOW clear masks;
- exact reciprocal LOW restore masks;
- HIGH preservation by those mutations;
- nine reciprocal LOW+HIGH starter transition markers;
- wrapper-specific action-15 predicates;
- OPENING / OPEN_ARMED / CANCEL_RECLOSE control-flow and LOW mutations;
- transition commit path once the action-15 gate has enabled the interface.

STATE-QUALIFIED:

- whether a particular portal can enter OPENING;
- starter snapshot gives 6 ALLOW / 3 BLOCKED.

FALSIFIED:

- all nine E.8 transition handlers unconditionally allow action 15;
- `A2D76` is itself the LOW-edge unlock;
- the transition interfaces are ordinary statically open edges.

OPEN:

- mutations that change the three currently blocked action-15 predicates;
- reciprocal-side ingress semantics for neighboring handlers;
- physical MSP/spatial state after a dynamically enabled edge;
- composition into the complete multi-step world graph;
- final one-way and softlock analysis.

## Gate

`starter_portal_mechanism = VERIFIED`

`starter_transition_portal_markers = 9/9 VERIFIED`

`serialized_action15_allow = 6/9`

`serialized_action15_blocked = 3/9`

`portal_enablement = VERIFIED_STATE_QUALIFIED`

`one_way_verdict_authorized = false`

`softlock_verdict_authorized = false`

## Next — STONE-K292-E.10

Resolve the state producers for the three blocked action-15 gates, especially
handler 87's `cell(2,3)+0x09` dependency and handlers 106/107's `-1`
selector-4 state. Then compose dynamically enabled portal edges with E.3 MSP,
E.4 spatial occupancy and E.8 level-transition payloads.
