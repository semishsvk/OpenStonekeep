# STONE-K291-D — Direction model and static cell-edge topology

- Date: 2026-09-29
- Status: **VERIFIED direction/topology pass**
- Knowledge classification: GAME-SPECIFIC
- Scope: Stonekeep level-cell direction order, directional tuple, static edge mask, mutable directional bitfield

## Corpus

Authoritative original CD starter save:

- `START/SAVEGAME/GAME00/LEVEL01.SAV`
  - size: 68,829 bytes
  - SHA-256: `2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9`
- `SK.EXE`
  - SHA-256: `5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2`

No original game files are committed to the repository.

## Verified engine direction order

Object-3 signed 16-bit delta tables are:

```text
column delta @ +0x4E0C = [ 0, -1,  0, +1 ]
row delta    @ +0x4E14 = [-1,  0, +1,  0 ]
```

The engine indexes both tables with its direction value and then indexes the
row-offset table plus column. Therefore:

```text
direction 0 = N  (row-1, column+0)
direction 1 = W  (row+0, column-1)
direction 2 = S  (row+1, column+0)
direction 3 = E  (row+0, column+1)
```

For `LEVEL01.SAV`, the serialized dimensions must therefore be interpreted as
26 rows × 29 columns for row-major cell addressing. This orientation is also
the only orientation that satisfies the static-edge reciprocity invariants
below.

## `cell+0x03..+0x06` — direction-indexed tuple

The executable helper at raw `0x6A8F4` computes the selected cell and returns:

```text
signed_byte cell[0x03 + direction_index]
```

Multiple call-sites pass the live engine direction global directly as the
index, including raw `0x59241→0x59248`, `0x628D1→0x628D8`, and later runtime
paths.

Result:

```text
cell+0x03 = direction 0 = N
cell+0x04 = direction 1 = W
cell+0x05 = direction 2 = S
cell+0x06 = direction 3 = E
```

The tuple's exact value semantics remain OPEN; the **direction/order is
VERIFIED**.

## `cell+0x01` — mutable directional bitfield

The generic cell getter/setter uses selectors 10..13 for masked access to
`cell+0x01`.

The selector table is exactly:

```text
[10, 11, 12, 13]
```

and is indexed by engine direction. The mask table used by those selectors is:

```text
[0x01, 0x02, 0x04, 0x08]
```

The setter can independently set or clear the selected bit. Therefore:

```text
N = 0x01
W = 0x02
S = 0x04
E = 0x08
```

`LEVEL01.SAV` has all of these bits clear in all 754 cells. The bitfield is
therefore a mutable directional state layer, but its exact gameplay umbrella
(e.g. which door/temporary-edge conditions use it) remains OPEN.

## `cell+0x02` — static directional edge/barrier mask

The engine direction-mask table begins:

```text
[0x08, 0x02, 0x04, 0x01]
```

and is indexed by the same N,W,S,E direction index. Directional scan code tests
this mask against `cell+0x02`; a set bit terminates the scan while a clear bit
allows the scan to advance to the adjacent cell using the verified direction
delta tables.

Result:

```text
N = 0x08
W = 0x02
S = 0x04
E = 0x01
```

This identifies the low nibble as a **static directional edge/barrier mask**.
It is not yet claimed to be a complete player-walkability model.

### LEVEL01 corpus invariants

Using 26 rows × 29 columns:

- N/S internal adjacency pairs: 725
- W/E internal adjacency pairs: 728
- **0 one-sided mismatches** across all 1,453 undirected internal adjacencies
- static edge-mask reciprocity: **100%** in all four directions
- north boundary: 29/29 N bits set
- south boundary: 29/29 S bits set
- west boundary: 26/26 W bits set
- east boundary: 26/26 E bits set

Undirected internal edges:

- both sides static-bit set: 774
- both sides static-bit clear: 679
- mismatched: 0

The alternative 29×26 orientation fails the corresponding reciprocity test;
the 26-row × 29-column orientation is therefore independently corroborated by
the corpus.

## High-nibble observation

In `LEVEL01.SAV`, high-nibble bit pairs also show perfect directional
reciprocity under masks N=0x80, W=0x20, S=0x40, E=0x10. Unlike the low nibble,
this has not yet been tied to an executable semantic table, so it remains
**STRUCTURAL / OPEN** and must not be used as a movement rule yet.

## Connectivity implication

A graph made from every serialized cell with `cell+0x02` low-nibble bit clear
as an edge produces many components because the serialized grid also contains
boundary/void/non-walkable cells. Therefore:

- K292 may now validate **static edge reciprocity and boundary integrity**.
- K292 must **not** equate the static edge mask alone with final player
  walkability.
- Final movement connectivity must combine static topology with dynamic
  directional state and relevant runtime/object semantics.

## Tooling

`tools/inspect_level_save.py` now reports:

- row/column dimensions;
- verified N,W,S,E direction order;
- static and mutable direction masks;
- per-direction reciprocity/boundary statistics;
- undirected static-edge set/clear/mismatch totals;
- existing typed cell-chain statistics.

Synthetic tests cover reciprocal 2×2 topology, mismatch detection, boundary
closure, chain metadata, and truncated-grid rejection.

## Gate

**STONE-K291-D direction/topology gate: PASS.**

The exact umbrella semantic of the `0x66` chain remains OPEN, but it is no
longer a blocker for K292-A static-edge consistency validation. It remains a
blocker only for any later runtime occupancy/movement model that needs it.
