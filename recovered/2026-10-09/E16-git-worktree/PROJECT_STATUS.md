# Project Status

- Project: OpenStonekeep
- Game: Stonekeep
- Lifecycle: **INCUBATION / ACTIVE RESEARCH**
- Priority: LOW
- Source corpus: **IDENTIFIED; original CD corpus in Google Drive is authoritative**
- Checkpoints: `STONE-K###`
- Full engine development: NOT AUTHORIZED
- Cross-project writes: FORBIDDEN
- Framework promotion: EVIDENCE-GATED
- Initialized: 2026-09-26

## Current evidence baseline

### STONE-K290 — world-data discovery

Status: **STRUCTURAL PASS**

- `MASTER` deterministic format identified: 2309 × 20-byte resource records.
- `MASTER.metadata[6]` → GROUP ID is VERIFIED.
- 22 `LEVEL*.MAZ` logical resources identified across GROUP01..GROUP21.
- GROUP directory parsing deterministically enumerates named resources and
  cumulative payload ranges.
- Some logical resources, including several `.MAZ` entries, legitimately
  have zero local payload; GROUP is not a simple filename→blob archive.

### STONE-K290-B — GROUP storage transform

Status: **VERIFIED 2/2**

Original CD GROUP01 and GROUP24 use:
- `u16 count`
- `count × 22-byte directory`
- payload area
- 4-byte trailer

Entry `+0x0E u32` is the cumulative payload end. Zero-length entries are
valid.

For both samples the installed GROUP equals the CD GROUP payload area
byte-for-byte after stripping exactly `2 + count*22` directory bytes:
- GROUP01: strip `0x040C`
- GROUP24: strip `0x98B8`

A deterministic read-only parser is in `tools/inspect_group.py`.

### STONE-K291-A — serialized level grid

Status: **VERIFIED**

Original CD starter saves `LEVEL01.SAV` and `LEVEL01A.SAV` independently
confirm:

- format marker = 2
- version = 1.05
- dimensions = 26 × 29
- 754 cells
- serialized/runtime cell stride = 21 bytes (`0x15`)
- grid range = `[0x0B, 0x3DE5)`

The executable level loader independently reads exactly
`dimension_A * dimension_B * 0x15` bytes into the runtime grid.

K291-D establishes the runtime/grid orientation for LEVEL01 as **26 rows × 29
columns**.

### STONE-K291-C — runtime cell chains

Status: **VERIFIED structural**

Four signed 16-bit cell fields are linked-list heads into distinct runtime
record pools:

- `cell+0x0D` → stride `0x2F`, next `+0x18`
- `cell+0x0F` → stride `0x111`, next `+0x3A`
- `cell+0x11` → stride `0x30`, next `+0x10`
- `cell+0x13` → stride `0x66`, next `+0x63`

### STONE-K291-D — cell semantics + direction/topology

Status: **VERIFIED DIRECTION/TOPOLOGY PASS; semantic tail partial**

Verified chain semantics:

- `cell+0x0D` → **POJ/object-instance chain**
  - runtime pool `0x19E2E0`, stride `0x2F`, 2000 slots
  - object type resource: `OBJTYPE.DEF`
  - runtime object-type table: 250 × `0x38`
  - binary path generates/loads `.POJ` resources
- `cell+0x0F` → **monster-instance chain**
- `cell+0x11` → **MSP/maze-prop instance chain**
  - runtime/save pool `0x1B5210`, stride `0x30`, 250 slots
  - `record+0` indexes a separate static `0x2E` type table
  - all 19 active LEVEL01 type names map exactly to GROUP01 `.MSP` resources
- `cell+0x13` → `0x66` pool remains **STRUCTURAL projectile/effect-like**;
  exact umbrella semantic class is OPEN.

Verified direction/topology model:

- engine direction order: `0=N, 1=W, 2=S, 3=E`
- direction deltas: N `(-1,0)`, W `(0,-1)`, S `(+1,0)`, E `(0,+1)` in
  `(row,column)` space
- `cell+0x03..+0x06` is direction-indexed in **N,W,S,E** order
- `cell+0x01` is a mutable directional bitfield with masks
  `N=0x01, W=0x02, S=0x04, E=0x08`
- `cell+0x02` low nibble is a static directional edge/barrier mask with masks
  `N=0x08, W=0x02, S=0x04, E=0x01`

LEVEL01 static-edge corpus validation at 26 rows × 29 columns:

- 1,453 undirected internal cell adjacencies
- 774 with both static bits set
- 679 with both static bits clear
- **0 mismatches**
- **100% directional reciprocity**
- all four outer boundaries are fully closed by the corresponding static bit

This static mask is not yet claimed to be the complete player-walkability
model. Dynamic directional state plus relevant runtime/object semantics must be
layered on top.

Read-only inspection tools:
- `tools/inspect_level_save.py`
- `tools/inspect_group.py`

Synthetic `inspect_level_save` regression: **4 PASS**.

## Current gate

**STONE-K291-D direction/topology gate: PASS.**

`cell+0x13` / `0x66` semantic naming remains OPEN but no longer blocks a
structural static-edge validator.

### STONE-K292-A — static edge consistency validator

Status: **PASS — VERIFIED on 2 authoritative starter levels**

`tools/validate_level_topology.py` validates only the evidence-backed static
topology layer:

- reciprocal N/W/S/E low-nibble `cell+0x02` edges;
- complete outer-boundary closure;
- mutable `cell+0x01` direction state reported separately;
- directional `cell+0x03..+0x06` activity reported separately.

Authoritative corpus results:

- `LEVEL01.SAV`: set=774, clear=679, mismatch=0, boundary 29/26/29/26 PASS
- `LEVEL01A.SAV`: set=434, clear=1019, mismatch=0, boundary 29/26/29/26 PASS
- mutable directional bits: zero in both starter saves

Combined synthetic K291-D + K292-A regression: **8 PASS**.

K292-A explicitly does **not** claim that every static-clear adjacency is
player-walkable.

### STONE-K292-B — cell-region + actor-clearance classification

Status: **PASS — VERIFIED actor-clearance layering; player movement remains gated**

Three evidence layers are now separated:

- cell+0x00 bit 0x10 — static actor-clearance / region gate. It participates
  in the executable monster-clearance test and gates interior BMAP bit-0x01
  initialization.
- cell+0x00 bit 0x80 — runtime-mutable actor-clearance blocker. Independent
  executable paths set it with OR 0x80 and clear it with AND 0x7F.
- cell+0x02 high directional bits — secondary actor-clearance blocker layer:
  N=0x80, W=0x20, S=0x40, E=0x10. Monster clearance tests combined masks
  0x88/0x22/0x44/0x11.

Corpus results:
- LEVEL01.SAV: bit10=381, bit80=15, interior !bit10=321,
  bit10-boundary sealed=591/591, high-without-low=0/60.
- LEVEL01A.SAV: bit10=577, bit80=0, interior !bit10=125,
  bit10-boundary sealed=251/251, high-without-low=0/26.

The exact designer-facing meaning of bit 0x10, the high-bit subtype, and BMAP
bit 0x01 remains OPEN. K292-B does not label cells floor/void/player-walkable.

Read-only classifier:
- tools/classify_level_cells.py
- tests/test_classify_level_cells.py
- checkpoints/STONE-K292-B.md

### STONE-K292-C — player translation clearance + event layer

Status: **PASS — VERIFIED ordinary player translation call-chain**

Player translation is now separated into evidence-typed layers:

- direct forward/backward primitive: low cell+0x02 static edge mask;
- runtime physical precheck: cell+0x11 MSP/maze-prop directional clearance;
- runtime occupancy precheck: monster-linked 0x0C spatial index;
- script/event layer: signed cell+0x07 handler index -> per-cell callback.

The ordinary direct translation path does not directly read cell0 bit0x10,
cell0 bit0x80, high cell+0x02, or cell+0x01 selectors 10..13. Those layers
remain actor-specific, state-tracking, or indirectly script-consumable.

Starter corpus event handlers:
- LEVEL01.SAV: 81 non-default cells, 52 unique IDs, range 0..116.
- LEVEL01A.SAV: 18 non-default cells, 16 unique IDs, range 0..419.

The main input path tests the per-cell callback before translation, so static
clearance alone is insufficient for final one-way/softlock conclusions.

Read-only evidence:
- checkpoints/STONE-K292-C.md
- tools/inspect_level_save.py exposes cell+0x07 handler metadata
- synthetic handler regression added to tests/test_inspect_level_save.py

### STONE-K292-D — evidence-typed player edge graph

Status: **PASS — candidate graph constructed; softlock verdict remains gated**

`tools/build_navigation_evidence.py` now classifies every in-bounds directed player edge as:

- `STATIC_BLOCKED` — verified low `cell+0x02` player barrier set;
- `STATIC_CLEAR_RUNTIME_GATED` — low static edge clear, default source handler, but MSP/monster runtime prechecks unresolved;
- `SCRIPTED` — low static edge clear and non-default source `cell+0x07` pre-movement handler.

Actor-specific monster blockers (`cell0 0x10/0x80` and high `cell+0x02`) are reported but do not suppress player candidate edges.

Authoritative starter results:

- LEVEL01.SAV:
  - static blocked/clear/mismatch = 774/679/0
  - directed = 1548 STATIC_BLOCKED, 1231 RUNTIME_GATED, 127 SCRIPTED
  - 71 static-clear pairs have source-handler asymmetry
  - candidate static components = 153; largest 138
- LEVEL01A.SAV:
  - static blocked/clear/mismatch = 434/1019/0
  - directed = 868 STATIC_BLOCKED, 2016 RUNTIME_GATED, 22 SCRIPTED
  - 22 static-clear pairs have source-handler asymmetry
  - candidate static components = 131; largest 469

These asymmetries are candidates only. `one_way_verdict_authorized=false` and `softlock_verdict_authorized=false`.

Read-only evidence:
- `tools/build_navigation_evidence.py`
- `tests/test_build_navigation_evidence.py` — 4 PASS
- `checkpoints/STONE-K292-D.md`

### Next authorized work — STONE-K292-E

Resolve candidate scripted/runtime edges into state-qualified transitions:

1. enumerate non-default handler IDs on static-clear candidate edges;
2. map handler IDs to function pointers;
3. classify movement actions 2/3/4/5 as allow/veto/state mutation;
4. resolve MSP directional masks and monster spatial categories for the same edges;
5. build the first state-qualified player transition graph;
6. only then authorize CRITICAL one-way/softlock validation.

Framework candidate: NavigationEvidence / NavigationIR with directed edges, actor policy, static/runtime/script evidence and unresolved-state reasons. Cross-game promotion remains gated.

### STONE-K292-E — relocation-aware handler dispatch gate

Status: **PARTIAL PASS — handler inventory verified; final target/action semantics remain gated**

K292-E corrects the representation of cell+0x07 dispatch targets. The executable getter at virtual 0x6C5CC indexes a 4-byte dispatch table at virtual 0xF16A and installs the selected entry as an indirect-call target. Because the executable is LE, raw on-disk bytes are relocation-sensitive and are not promoted to final linear function addresses.

Candidate source-handler IDs on static-clear edges form a union of 62 IDs across LEVEL01.SAV and LEVEL01A.SAV. The new `tools/inspect_handler_dispatch.py` inventories these IDs and records raw table-slot evidence without guessing resolved targets.

Current gate:
- handler target resolution: **BLOCKED_ON_LE_RELOCATION**
- movement action classification: **NOT_AUTHORIZED**
- one-way verdict: **NOT AUTHORIZED**
- softlock verdict: **NOT AUTHORIZED**

Synthetic handler-dispatch regression: **2 PASS**.

### Next authorized work — STONE-K292-E.1

Resolve the LE relocation/fixup records affecting the dispatch table at virtual 0xF16A; reconstruct final indirect targets; trace movement selectors 2/3/4/5; classify only directly evidenced allow/veto/state mutations; then feed resolved outcomes into the state-qualified player transition graph.

Framework candidate: NavigationIR should represent dispatch references with executable format, virtual address, raw entry, relocation state, resolved target and resolution evidence.