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
- GROUP directory parsing is sufficiently understood to deterministically
  enumerate named resources and cumulative payload ranges.
- Some logical resources, including several `.MAZ` entries, legitimately have
  zero local payload, so GROUP must not be treated as a simple filename→blob
  archive.

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

- `cell+0x0D` → stride `0x2F`, semantic class OPEN
- `cell+0x0F` → stride `0x111`, **monster-instance chain VERIFIED**
- `cell+0x11` → stride `0x30`, direct save/runtime pool linkage VERIFIED,
  semantic class OPEN
- `cell+0x13` → stride `0x66`, semantic class OPEN

The four-byte field `cell+0x03..+0x06` is verified as a grouped spatial tuple,
but its directional meaning/order is still OPEN.

## Current gate

STONE-K291-D is active. Required before K292 connectivity work can be trusted:

1. identify the remaining `0x2F`, `0x30`, and `0x66` pool semantics;
2. prove the meaning/order of `cell+0x03..+0x06`;
3. map the relevant topology/passability bits in `cell+0x02`.

No renderer or full runtime work should depend on guessed topology semantics.
