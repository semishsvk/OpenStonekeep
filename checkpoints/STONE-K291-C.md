# STONE-K291-C — Serialized cell structure and runtime chain heads

- Date: 2026-09-28
- Status: **VERIFIED (structural, with verified monster-chain semantics)**
- Knowledge classification: GAME-SPECIFIC
- Scope: Stonekeep per-level SAV grid and runtime cell references

## Corpus

Authoritative original CD starter save corpus:

- `START/SAVEGAME/GAME00/LEVEL01.SAV`
  - size: 68,829 bytes
  - SHA-256: `2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9`
- `START/SAVEGAME/GAME00/LEVEL01A.SAV`
  - size: 66,901 bytes
  - SHA-256: `3d1753ca8a4ca49b3ccf9da0fc15bb08ac242301eff40586049379ceba635dc9`
- `SK.EXE`
  - SHA-256: `5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2`

## Verified save-grid layout

Both starter level saves decode as:

```text
+0x00  u16 format marker = 2
+0x02  char version[5] = "1.05\0"
+0x07  u16 width  = 26
+0x09  u16 height = 29
+0x0B  Cell cells[width * height]
```

`Cell` serialized size is exactly `0x15` (21) bytes.

For both files:

- width × height = 26 × 29 = 754 cells
- grid size = 754 × 21 = 15,834 bytes
- grid range = `[0x000B, 0x3DE5)`

The executable independently computes runtime cell addresses as:

```text
row_offset = row_table[y]
cell_index = row_offset + x
cell_ptr   = grid_base + cell_index * 0x15
```

The level loader around raw file offset `0x8B9B6` reads the marker/version,
dimensions, computes `width * height * 0x15`, and reads that exact byte count
into the runtime grid. This independently verifies the serialized/runtime
21-byte cell stride.

## Verified cell fields

### +0x00 — flags byte

The executable reads `cell[0]` and masks bit `0x10`.

Verified claim: **offset +0x00 is a flags/bitfield byte**.

The exact meaning of bit 0x10 remains OPEN.

### +0x02 — mask/type byte

The executable repeatedly reads `cell[2]` and tests it against
direction-/state-dependent masks.

Verified claim: **offset +0x02 is a byte-sized mask/type field used by
spatial/gameplay checks**.

Exact individual bit semantics remain OPEN.

### +0x03..+0x06 — four-byte grouped field

The executable copies four consecutive bytes beginning at `cell+0x03` as one
grouped unit in spatial processing.

Verified claim: **offsets +0x03..+0x06 form a four-element per-cell
vector/tuple**.

HYPOTHESIS only: these may encode four directional face/edge properties. They
are **not yet proven** to be N/E/S/W wall IDs and their ordering remains OPEN.

### +0x0D, +0x0F, +0x11, +0x13 — typed linked-list heads

The executable reads four signed 16-bit values from every cell and processes
each through a distinct runtime record pool. `0xFF9C` (-100) is used as the
no-head/end sentinel; `-1` is also tested as a terminal value.

| Cell offset | Runtime record stride | Next-link offset | Result |
|---|---:|---:|---|
| `+0x0D` | `0x2F` | `+0x18` | typed linked-list head; semantic class OPEN |
| `+0x0F` | `0x111` | `+0x3A` | **monster-instance linked-list head — VERIFIED** |
| `+0x11` | `0x30` | `+0x10` | serialized/runtime 0x30-pool head — VERIFIED structurally; semantic class OPEN |
| `+0x13` | `0x66` | `+0x63` | typed linked-list head; semantic class OPEN |

These four fields are therefore **not four neighboring-cell/direction
pointers**.

The common engine routine emits category values 0/1/2/3 while merging records
from the four pools, proving four distinct record classes.

## +0x0F monster-chain proof

The semantic identification of `cell+0x0F` is end-to-end and does not rely
only on a matching stride:

1. Cell traversal follows `cell+0x0F` through runtime pool base
   `0x1971F8`.
2. Each runtime record has stride `0x111`; its next-link is read at
   record `+0x3A`.
3. The level loader iterates exactly 96 slots (`0x60`) and reads each
   `0x111` record directly into this same pool.
4. Per-record attached data is loaded through an allocation/read site whose
   object-3 string at offset `+0x1F99` is exactly
   `"Monster L-Variables"`.
5. Related executable labels include `"Monster Script"`,
   `"Monster G-Variables"`, and `"Monster Data"`.
6. A 50-entry table with runtime stride `0x52` is used as the monster type
   definition table; the `0x111` records reference this type information.

Result: **`cell+0x0F` is the per-cell head of the monster-instance chain.**

## +0x11 serialized-pool proof

The level loader reads a `u16 count`, then reads exactly
`count * 0x30` bytes from the save into runtime pool base `0x1B5210`.
Cell traversal follows `cell+0x11` through this same base using stride
`0x30` and next-link offset `+0x10`.

For `LEVEL01.SAV` the serialized count is 250. All observed active
`cell+0x11` heads are 0..134, therefore all are in-range.

Result: **`cell+0x11` is a head into the save-serialized variable-count
0x30 record pool.** Its semantic class name remains OPEN.

## LEVEL01 corpus validation

For `LEVEL01.SAV`:

| Head | Active cells | Unique active heads | Range |
|---|---:|---:|---:|
| `+0x0D` | 36 | 36 | 50..213 |
| `+0x0F` | 30 | 30 | 7..50 |
| `+0x11` | 105 | 105 | 0..134 |
| `+0x13` | 0 | 0 | — |

The starter save has no active `+0x13` head, so that pool's cell-level
semantics cannot be inferred from this save alone.

## Corrections / rejected interpretations

- REJECTED: `+0x0D/+0x0F/+0x11/+0x13` are N/E/S/W fields.
- REJECTED: small values in these fields are neighboring cell indexes.
- Do not derive runtime-state deltas by comparing `LEVEL01.SAV` with
  `LEVEL01A.SAV`; `LEVEL01A` is a distinct level resource, not simply
  another state of LEVEL01.
- The old blanket interpretation of the raw `0x5C1FB` area as unrelated
  text/formatting code is superseded by wider disassembly: the surrounding
  `0x5C110` routine performs grid/spatial processing. This still does **not**
  prove a direction order for `+0x03..+0x06`.

## Reproduction

Run:

```bash
python tools/inspect_level_save.py /path/to/LEVEL01.SAV --json
python tools/inspect_level_save.py /path/to/LEVEL01A.SAV --json
```

Expected for both: marker 2, version 1.05, 26×29, 754 cells, cell size 21,
grid end 0x3DE5.

## Next evidence gate

STONE-K291-D should:

1. identify the semantic class of the `0x2F`, `0x30`, and `0x66` pools;
2. prove the meaning and ordering of the four-byte `+0x03..+0x06` tuple;
3. identify the relevant bits in `+0x02` used for passability/topology.

K292 connectivity work must not depend on guessed direction semantics.
