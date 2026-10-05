# STONE-K292-E.13 — LEVEL02 base-state and reciprocal transition closure

- Date: 2026-10-04
- Status: **PASS — authentic LEVEL02 base grid, initializer handler map and both return transitions VERIFIED**
- Knowledge classification: GAME-SPECIFIC
- Scope: new-level materialization for target level 2 when no LEVEL02.SAV exists

## Result

The missing starter `LEVEL02.SAV` is no longer a source blocker for static
initial-level reconstruction.

The executable explicitly implements:

```text
savegame\<level>.SAV
  if present -> load serialized runtime state
  else       -> open <level>.MAZ -> 0x6D86F initial-level materializer
```

For level index 2, the executable name table is `level02` and the
relocation-resolved level initializer is runtime `0x5F68A`.

The authoritative base resource is present in the read-only CD corpus.

## MASTER -> GROUP02 provenance

Authoritative MASTER:

- SHA-256:
  `d29db8dd09ec20ed0eadbb3187924e1d83b766481051da42c3ac5a49f703e350`
- entry count: 2309
- entry #811: `LEVEL02.MAZ`
- group ID: **2**

K290-B was corrected during E.13: GROUP directory `+0x0E` is the start
offset of the resource named by the same entry, not the cumulative end of that
entry.

Authoritative GROUP02:

- SHA-256:
  `ae4fadcddfb3f722330cbcda1362e8ed4b77a1642de5b20aa4f668151fbea425`
- entry count: 58
- directory end: 0x04FE
- `LEVEL02.MAZ` directory entry: 26
- payload interval: **[0x4257C, 0x444F8)**
- payload size: **8,060 bytes**
- payload SHA-256:
  `2255a617c1470bc388fa33667944d9df7dac350b2f0a5943a95fc719ae475b84`

The first bytes are:

```text
4F 4E 1E 00 1B 00 ...
 O  N  30     27
```

## Generic MAZ grid materialization

Runtime `0x6D86F` reads:

1. marker `ON`;
2. signed/word row count;
3. signed/word column count;
4. `rows * columns` bytes used to initialize cell selector 2 / `cell+0x02`;
5. a second `rows * columns` byte plane used by the generic cell
   initialization path;
6. typed variable records that build POJ/MSP/monster/effect runtime state.

For LEVEL02:

- rows: **30**
- columns: **27**
- cells: **810**

The first two grid planes are therefore directly reconstructable from the base
resource without running the original game.

The typed tail begins after the two grid planes and remains an explicit E.14
scope item for full MSP / monster-spatial reconstruction.

## Level-2 initializer handler map

On the no-save path, initializer `0x5F68A` invokes the same verified cell
handler setter `0x3DFBA(handler,row,column)` used by LEVEL01.

E.13 freezes:

- sequential handler writes: **54**
- final non-default handler cells: **52**
- unique handler IDs written: **37**

Two cells are intentionally overwritten later in the initializer, so write
count and final non-default cell count differ.

The complete ordered assignment manifest is in
`tools/inspect_level02_initial_state.py`.

## Two level-2 return transitions

Only two level-2 handler entrypoints in this initializer bind to the verified
E.8/E.9 transition common family.

### Handler 144

Initializer assignment:

```text
handler 144 -> LEVEL02 cell (6,2)
```

Dispatch:

```text
144 -> runtime 0x6005F
```

Transition wrapper payload:

```text
source level = 2
target level = 1
target spawn = (row=10, col=5, facing=S/2)
source direction gate = S/2
```

LEVEL02.MAZ static edge bytes:

- source (6,2): `cell+0x02 = 0x47`
- adjacent (7,2): `cell+0x02 = 0x8F`

Thus the S/N interface has reciprocal LOW+HIGH special-portal markers.

This adjacent cell is exactly the incoming spawn from LEVEL01 handler 106:

```text
LEVEL01 h106 -> LEVEL02 spawn (7,2,N)
```

The return target is correspondingly on the opposite side of the LEVEL01
portal:

```text
LEVEL02 h144 -> LEVEL01 spawn (10,5,S)
```

LEVEL01 h106 itself is at (11,5) with N gate.

### Handler 145

Initializer assignment:

```text
handler 145 -> LEVEL02 cell (2,17)
```

Dispatch:

```text
145 -> runtime 0x60080
```

Transition wrapper payload:

```text
source level = 2
target level = 1
target spawn = (row=7, col=24, facing=E/3)
source direction gate = E/3
```

LEVEL02.MAZ:

- source (2,17): `cell+0x02 = 0x1D`
- adjacent (2,18): `cell+0x02 = 0x2F`

The E/W interface again has reciprocal LOW+HIGH special markers.

Adjacent (2,18) is exactly the incoming spawn from LEVEL01 handler 107:

```text
LEVEL01 h107 -> LEVEL02 spawn (2,18,W)
```

The return target lands immediately across the reciprocal LEVEL01 interface:

```text
LEVEL02 h145 -> LEVEL01 spawn (7,24,E)
```

LEVEL01 h107 is at (7,25) with W gate.

## Portal enable semantics

Handlers 144 and 145 enter the common transition family directly rather than
using the extra selector-4 action-15 wrapper predicates present on LEVEL01
handlers 87/106/107.

Under the already VERIFIED E.9 common-family semantics, their action-15 class
is therefore:

`DIRECT_COMMON_FAMILY_ALLOW`

Their reciprocal LOW+HIGH marker state is independently verified from the
LEVEL02.MAZ cell+0x02 plane.

E.13 does **not** yet claim post-open physical passage because initial MSP and
monster-spatial runtime pools from the typed MAZ tail are not yet reconstructed.

## Reproducibility

Added:

- `tools/inspect_level02_initial_state.py`
- `tests/test_inspect_level02_initial_state.py`

Corrected in the same iteration:

- `tools/inspect_group.py`
- `tests/test_inspect_group.py`
- `checkpoints/STONE-K290-B.md`

Authoritative E.13 run:

```text
PASS level02=30x27 handler_writes=54 return_transitions=2 regions=5 errors=0
 h144 [6,2] S -> L1 [10,5,2] marker=True
 h145 [2,17] E -> L1 [7,24,3] marker=True
```

Executable code anchors: **5/5 SHA-256 matched**.

## Evidence classification

VERIFIED:

- no-save -> MAZ fallback in the level loader;
- MASTER entry #811 -> LEVEL02.MAZ -> GROUP02;
- corrected GROUP02 resource interval;
- LEVEL02.MAZ marker/hash/dimensions;
- generic first two MAZ grid planes;
- level index 2 name and initializer;
- 54 initializer handler writes / 52 final non-default handler cells;
- h144/h145 LE dispatch targets;
- h144/h145 target level and spawn payloads;
- reciprocal LOW+HIGH portal markers for both level-2 return interfaces;
- geometric/state reciprocity with the two LEVEL01 -> level2 arrivals.

OPEN / E.14:

- typed MAZ tail -> complete initial MSP pool;
- typed MAZ tail -> monster instances and monster-spatial occupancy grid;
- post-open physical precheck for h144/h145;
- full ordinary-movement graph inside LEVEL02;
- world-level one-way / softlock verdict.

## Gate

`level02_base_resource = VERIFIED`

`level02_base_grid = 30x27 VERIFIED`

`level02_initial_handler_map = VERIFIED`

`level02_return_transition_count = 2 VERIFIED`

`level01_to_level02_transition_pairing = 2/2 RECIPROCAL_PAYLOAD_VERIFIED`

`level02_special_portal_markers = 2/2 VERIFIED`

`level02_post_open_physical_clearance = OPEN_E14`

`one_way_verdict_authorized = false`

`softlock_verdict_authorized = false`

## Next — STONE-K292-E.14

Decode the typed LEVEL02.MAZ tail far enough to materialize the initial MSP and
monster-spatial state used by the already VERIFIED player prechecks.

Evaluate h144/h145 after the E.9 reciprocal LOW clear and then build the first
three-level conditional transition graph for LEVEL01 / LEVEL01A / LEVEL02.
