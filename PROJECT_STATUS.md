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
`width * height * 0x15` bytes into the runtime grid.

### STONE-K291-C — runtime cell chains

Status: **VERIFIED structural**

Four signed 16-bit cell fields are linked-list heads into distinct runtime
record pools:

- `cell+0x0D` → stride `0x2F`, next `+0x18`
- `cell+0x0F` → stride `0x111`, next `+0x3A`
- `cell+0x11` → stride `0x30`, next `+0x10`
- `cell+0x13` → stride `0x66`, next `+0x63`

The four-byte field `cell+0x03..+0x06` is verified as a grouped spatial tuple,
but its directional meaning/order remains OPEN.

### STONE-K291-D — cell-chain semantics

Status: **PARTIAL SEMANTIC PASS**

- `cell+0x0D` → **POJ/object-instance chain VERIFIED**
  - runtime pool `0x19E2E0`, stride `0x2F`, 2000 slots
  - object type resource: `OBJTYPE.DEF`
  - runtime object-type table: 250 × `0x38`
  - binary path generates/loads `.POJ` resources
- `cell+0x0F` → **monster-instance chain VERIFIED**
- `cell+0x11` → **MSP/maze-prop instance chain VERIFIED**
  - runtime/save pool `0x1B5210`, stride `0x30`, 250 slots
  - `record+0` indexes a separate static `0x2E` type table
  - all 19 active LEVEL01 type names map exactly to GROUP01 `.MSP` resources
- `cell+0x13` → 0x66 pool is **STRUCTURAL projectile/effect-like**;
  exact umbrella semantic class remains OPEN.

Read-only inspection tools:
- `tools/inspect_level_save.py`
- `tools/inspect_group.py`

Synthetic parser regression: **4 PASS** locally.

## Current gate

STONE-K291-D remains active. Required before K292 connectivity work can be
trusted:

1. prove the meaning/order of `cell+0x03..+0x06`;
2. map topology/passability bits in `cell+0x02`;
3. finish the semantic classification of the `0x66` pool if needed for
   connectivity/runtime occupancy.

No renderer or connectivity graph should depend on guessed topology semantics.
