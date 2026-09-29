# STONE-K292-A — Static edge consistency validator

- Date: 2026-09-29
- Status: **PASS — VERIFIED on 2 authoritative starter levels**
- Knowledge classification: GAME-SPECIFIC
- Scope: structural validation of serialized static cell-edge topology

## Purpose

K292-A validates only evidence proven by K291-D. It is intentionally **not** a
player movement solver and does not interpret every static-clear adjacency as
walkable.

Validated invariants:

1. N/W/S/E low-nibble static edge bits in `cell+0x02` must agree with the
   corresponding opposite bit of the adjacent cell.
2. Every outer grid boundary must carry its corresponding static barrier bit.
3. `cell+0x01` mutable directional state is reported separately and is not
   collapsed into static topology.
4. `cell+0x03..+0x06` directional tuple activity is reported separately and is
   not interpreted as a barrier without further semantic evidence.

## Corpus validation

Authoritative original CD starter saves:

### LEVEL01.SAV

- SHA-256: `2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9`
- grid: 26 rows × 29 columns = 754 cells
- internal undirected adjacencies: 1,453
- static both-set edges: 774
- static both-clear edges: 679
- static mismatches: **0**
- boundary closure:
  - N: 29/29
  - W: 26/26
  - S: 29/29
  - E: 26/26
- mutable direction bits present: N=0, W=0, S=0, E=0
- result: **PASS**

### LEVEL01A.SAV

- SHA-256: `3d1753ca8a4ca49b3ccf9da0fc15bb08ac242301eff40586049379ceba635dc9`
- grid: 26 rows × 29 columns = 754 cells
- internal undirected adjacencies: 1,453
- static both-set edges: 434
- static both-clear edges: 1,019
- static mismatches: **0**
- boundary closure:
  - N: 29/29
  - W: 26/26
  - S: 29/29
  - E: 26/26
- mutable direction bits present: N=0, W=0, S=0, E=0
- result: **PASS**

The two levels have substantially different topology counts while preserving
exactly the same reciprocity and boundary invariants. This is evidence for a
format invariant rather than a LEVEL01-specific coincidence.

## Tool

`tools/validate_level_topology.py`

Behavior:

- exits 0 only when all supplied saves satisfy static reciprocity and boundary
  closure;
- returns nonzero on static edge mismatch or missing boundary closure;
- supports human-readable and JSON output;
- reports mutable-direction bits as warnings/information, not static failures;
- explicitly emits `movement_model_complete = false`.

Example:

```bash
python tools/validate_level_topology.py LEVEL01.SAV LEVEL01A.SAV
```

## Regression

Synthetic coverage includes:

- valid reciprocal 2×2 topology;
- one-sided static edge corruption;
- outer-boundary hole;
- mutable directional state present without falsely failing static validation.

Combined K291-D + K292-A local regression: **8 PASS**.

## Safety / interpretation gate

K292-A proves static **consistency**, not final navigability.

The validator deliberately does not:

- infer a player path from static-clear edges alone;
- classify `cell+0x00` flag values as floor/void/wall without code evidence;
- interpret the `cell+0x02` high nibble as movement semantics;
- assume mutable `cell+0x01` bits are specifically doors;
- ignore POJ/MSP/monster/effect runtime occupancy.

## Next gate — STONE-K292-B

Classify serialized cell roles/void regions using executable behavior and
corpus invariants before connected-component or softlock analysis. Primary RE
targets:

- semantics of `cell+0x00`, especially bits `0x01`, `0x10`, and `0x80`;
- executable meaning of the reciprocal high-nibble direction bits in
  `cell+0x02`;
- relationship between static-clear edges, cell role, and runtime occupancy.

Only after this classification should K292 build a navigable graph suitable
for one-way/softlock checks.
