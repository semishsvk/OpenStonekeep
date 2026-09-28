# STONE-K291-C — Serialized cell structure and runtime chain heads

- Date: 2026-09-28
- Status: **VERIFIED (structural)**
- Knowledge classification: GAME-SPECIFIC
- Scope: Stonekeep per-level SAV grid and runtime cell references
- Runtime semantic class names: **OPEN**

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

This independently confirms the 21-byte runtime cell stride.

## Verified cell fields

### +0x00 — flags byte

The executable reads `cell[0]` and masks bit `0x10`.

Verified claim: **offset +0x00 is a flags/bitfield byte**.

The exact meaning of bit 0x10 remains OPEN.

### +0x02 — mask/type byte

The executable repeatedly reads `cell[2]` and tests it against direction-/state-dependent masks.

Verified claim: **offset +0x02 is a byte-sized mask/type field used by spatial/gameplay checks**.

Exact individual bit semantics remain OPEN.

### +0x03..+0x06 — four-byte grouped field

The executable copies four consecutive bytes beginning at `cell+0x03` as one grouped unit in spatial processing.

Verified claim: **offsets +0x03..+0x06 form a four-element per-cell vector/tuple**.

HYPOTHESIS only: these may encode four directional face/edge properties. They are **not yet proven** to be N/E/S/W wall IDs.

### +0x0D, +0x0F, +0x11, +0x13 — typed linked-list heads

The executable reads four signed 16-bit values from every cell and processes each through a distinct runtime record pool. `0xFF9C` is used as the no-head/end sentinel; `-1` is also tested as a terminal value.

| Cell offset | Runtime record stride | Next-link offset | Structural result |
|---|---:|---:|---|
| `+0x0D` | `0x2F` | `+0x18` | typed linked-list head |
| `+0x0F` | `0x111` | `+0x3A` | typed linked-list head |
| `+0x11` | `0x30` | `+0x10` | typed linked-list head |
| `+0x13` | `0x66` | `+0x63` | typed linked-list head |

These four fields are therefore **not four neighboring-cell/direction pointers**.

The common engine routine emits category values 0/1/2/3 while merging records from the four pools, proving four distinct record classes.

## LEVEL01 corpus validation

For `LEVEL01.SAV`:

| Head | Active cells | Unique active heads | Range |
|---|---:|---:|---:|
| `+0x0D` | 36 | 36 | 50..213 |
| `+0x0F` | 30 | 30 | 7..50 |
| `+0x11` | 105 | 105 | 0..134 |
| `+0x13` | 0 | 0 | — |

Post-grid parsing also yields a count of 250 records with stride `0x30`, so every observed `+0x11` head (maximum 134) is in-range for that serialized pool. This independently cross-validates the executable linkage.

The `+0x0F` runtime stride `0x111` also matches a known later serialized record class. Its semantic identification as monster/actor data remains STRUCTURAL pending direct proof.

## Corrections / rejected interpretations

- REJECTED: `+0x0D/+0x0F/+0x11/+0x13` are N/E/S/W fields.
- REJECTED: small values in these fields are neighboring cell indexes.
- Do not derive runtime-state deltas by comparing `LEVEL01.SAV` with `LEVEL01A.SAV`; `LEVEL01A` is a distinct level resource, not simply another state of LEVEL01.
- Earlier interpretation of raw routine `0x5C1FB` as a direct movement/topology decoder is not sufficient by itself and must not be used as direction proof.

## Reproduction

Run:

```bash
python tools/inspect_level_save.py /path/to/LEVEL01.SAV --json
python tools/inspect_level_save.py /path/to/LEVEL01A.SAV --json
```

Expected for both: marker 2, version 1.05, 26×29, 754 cells, cell size 21, grid end 0x3DE5.

## Next evidence gate

STONE-K291-D should identify the semantic class of each of the four linked-list pools and prove the meaning/order of the four-byte `+0x03..+0x06` vector before K292 connectivity work relies on it.
