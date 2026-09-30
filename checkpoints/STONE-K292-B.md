# STONE-K292-B — Cell-region and actor-clearance classification

- Date: 2026-09-30
- Status: **PASS — VERIFIED actor-clearance layering; player movement remains gated**
- Knowledge classification: GAME-SPECIFIC

## Purpose

K292-B separates cell-region, directional blocker, mutable state, and runtime
occupancy evidence. It deliberately does not rename those fields into
designer-facing concepts such as floor, void, door, or player-walkable unless
the executable proves that semantic.

## Executable evidence

### cell+0x00 bit 0x10

A helper near 0x6A6FE reads cell selector 1 (cell+0x00) and returns value &
0x10.

The BMAP initialization path near 0x480BF iterates interior cells only. When
bit 0x10 is clear it reads cell+0x00, ORs 0x01, and writes the byte back.

Therefore:
- bit 0x10 is a VERIFIED gate for interior BMAP initialization;
- bit 0x01 is VERIFIED BMAP-linked, but its exact meaning is OPEN.

The monster-direction clearance routine near 0x693D9 independently tests
cell+0x00 & 0x90 for both the current and candidate neighboring cell.
Therefore bit 0x10 also participates directly in actor clearance.

K292-B conservatively names 0x10 a static actor-clearance / region gate. It is
not yet named void or solid.

### cell+0x00 bit 0x80

The same monster-direction clearance routine includes 0x80 in its 0x90 test.

Independent mutation paths prove runtime state:
- near 0x9CD47: read cell+0x00, OR 0x80, write it back;
- near 0x6BD8C: read cell+0x00, AND 0x7F, write it back.

Therefore 0x80 is a VERIFIED runtime-mutable actor-clearance blocker.

### cell+0x02 high directional bits

The executable monster-clearance path uses combined direction masks:
- N = 0x88
- W = 0x22
- S = 0x44
- E = 0x11

These decompose into the already VERIFIED low static-edge layer plus a second
high directional bit:
- N low 0x08 + high 0x80
- W low 0x02 + high 0x20
- S low 0x04 + high 0x40
- E low 0x01 + high 0x10

The high nibble is therefore a VERIFIED secondary directional
actor-clearance blocker layer. Its exact subtype meaning remains OPEN.

## Authoritative corpus validation

LEVEL01.SAV
- SHA-256: 2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9
- grid 26 x 29
- cell0 bit10: 381 cells
- cell0 bit80: 15 cells
- interior !bit10 actor-region candidates: 321
- bit10 partition crossings: 591
- reciprocal static barriers across those crossings: 591/591
- violations: 0
- high direction bits: N=19, W=11, S=19, E=11
- high without matching low bit: 0/60
- BMAP-linked bit01 already set in 100/321 candidate cells; initialization
  would set the remaining 221

LEVEL01A.SAV
- SHA-256: 3d1753ca8a4ca49b3ccf9da0fc15bb08ac242301eff40586049379ceba635dc9
- grid 26 x 29
- cell0 bit10: 577 cells
- cell0 bit80: 0 cells
- interior !bit10 actor-region candidates: 125
- bit10 partition crossings: 251
- reciprocal static barriers across those crossings: 251/251
- violations: 0
- high direction bits: N=8, W=5, S=8, E=5
- high without matching low bit: 0/26
- BMAP-linked bit01 already set in 64/125 candidate cells; initialization
  would set the remaining 61

The full sealing of the bit10 partition in two substantially different starter
states is strong STRUCTURAL evidence for a static actor-space region boundary.

## Evidence classification

VERIFIED:
- cell0 bit10 participates in monster actor clearance;
- cell0 bit10 gates interior BMAP bit01 initialization;
- cell0 bit80 participates in actor clearance and is runtime mutable;
- cell2 high direction bits participate in monster directional clearance;
- high masks are N=0x80, W=0x20, S=0x40, E=0x10.

STRUCTURAL:
- interior !bit10 is a useful static actor-region candidate;
- all observed bit10/non-bit10 boundaries are statically sealed in both saves;
- every observed high direction bit also has its matching low static bit.

OPEN:
- designer-facing meaning of bit10;
- exact high-bit subtype;
- exact BMAP bit01 meaning;
- final player movement/passability rule;
- interaction with cell+0x01 mutable direction state;
- softlock/one-way graph semantics.

## Tooling

Added:
- tools/classify_level_cells.py
- tests/test_classify_level_cells.py

The classifier explicitly reports player_movement_model_complete=false and
softlock_analysis_authorized=false. No original game/save data is committed.

Synthetic classifier regression covers sealed and invalid bit10 boundaries,
bit80 separation, and high-without-low reporting.

## K292-C gate

Before player navigation or CRITICAL softlock analysis:
1. locate and prove the player movement/transition clearance routine;
2. map consumers and mutators of cell+0x01 mutable directional bits;
3. compare player rules with the verified monster actor-clearance model;
4. keep static region, low static edge, high secondary blocker, mutable edge
   state, and POJ/MSP/monster/0x66 occupancy as separate evidence layers;
5. only then derive separate actor-clearance and player-navigation graphs.

## Framework candidate

Stonekeep supports a candidate general NavigationEvidence / NavigationIR model
with static region flags, static edge barriers, secondary directional blocker
subtypes, mutable edge state, runtime occupancy, and actor-specific clearance
policy.

This is a promotion candidate only. Cross-project framework promotion remains
evidence-gated and should wait for validation in at least one additional game.
