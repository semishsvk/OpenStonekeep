# STONE-K291-D — Object and maze-prop cell-chain semantics

- Date: 2026-09-28
- Status: **PARTIAL SEMANTIC PASS**
- Knowledge classification: GAME-SPECIFIC
- Scope: Stonekeep 21-byte runtime/save cell records and linked runtime pools

## Result

Two previously unknown cell chains now have end-to-end semantic identities:

| Cell head | Pool | Next | Semantic class | Evidence |
|---|---:|---:|---|---|
| `+0x0D` | `0x2F` | `+0x18` | POJ/object instance | **VERIFIED** |
| `+0x0F` | `0x111` | `+0x3A` | monster instance | **VERIFIED** (K291-C) |
| `+0x11` | `0x30` | `+0x10` | MSP/maze-prop instance | **VERIFIED** |
| `+0x13` | `0x66` | `+0x63` | transient projectile/effect-like record | **STRUCTURAL; exact class OPEN** |

## +0x0D — POJ/object-instance chain

Runtime pool:
- base `0x19E2E0`
- stride `0x2F`
- capacity 2000 (`0x7D0`)
- next-link `record+0x18`

The executable initializes all 2000 slots, using -100 (`0xFF9C`) in the
link fields and -1 as the free type marker.

The same initialization path contains exact object-3 strings:
- `Object type table`
- `OBJTYPE.DEF`
- `.POJ`
- `RESERVED.POJ`

For a 0x2F instance, code at raw `0xAC630` reads record field `+0x00`,
uses it as an object type, obtains the object resource name, and code at
`0xAC5B0` appends `.POJ` before invoking the resource loaders.

Result: **cell+0x0D is the head of the POJ/object-instance linked list.**

### OBJTYPE runtime table

The loader allocates exactly `0x36B0 = 14,000` bytes for `OBJTYPE.DEF`.
Accessor `0xAD3CC` computes:

```text
type_index * 7 * 8 = type_index * 56 = type_index * 0x38
```

and adds runtime pointer `0x1BA170`.

Therefore the runtime object-type table contains:
- 250 entries
- 56 bytes (`0x38`) per entry.

This corrects an earlier tentative association with the unrelated 0x2E
static table used by the 0x30 pool.

## +0x11 — MSP/maze-prop instance chain

Runtime/save pool:
- base `0x1B5210`
- stride `0x30`
- capacity / LEVEL01 serialized count: 250
- next-link `record+0x10`
- type id: signed u16 at `record+0x00`

The type id indexes a separate static table at object-3 offset `0x11E24`
with stride `0x2E`. That table embeds resource base names.

For all 135 active 0x30 records in original `LEVEL01.SAV`, 19 type IDs are
used. Their decoded names are:

```text
FORGE, FORGEFIR, BARREL, RUBBLE1, SACKOGRN, BED, PLATE, FIREPIT,
CAMPFIRE, SMCHAIR, SMTABLE, D1STDN, D1STUP, CHEST1, BONES,
DEDGOB, DEDANT, DTBL, SCRLCASE
```

Every one of these 19 names has an exact corresponding `<name>.MSP`
resource in MASTER assigned to GROUP01.

Examples:
- type 0 -> `FORGE` -> `FORGE.MSP`
- type 1 -> `FORGEFIR` -> `FORGEFIR.MSP`
- type 2 -> `BARREL` -> `BARREL.MSP`
- type 34 -> `BONES` -> `BONES.MSP`
- type 71 -> `DEDGOB` -> `DEDGOB.MSP`
- type 77 -> `DEDANT` -> `DEDANT.MSP`
- type 105 -> `DTBL` -> `DTBL.MSP`
- type 106 -> `SCRLCASE` -> `SCRLCASE.MSP`

All 135 active 0x30 records are reachable from the 105 active `cell+0x11`
heads in LEVEL01.

Result: **cell+0x11 is the per-cell MSP/maze-prop instance chain.**

## +0x13 — 0x66 pool

The executable initializes exactly 64 (`0x40`) records of stride `0x66`.
Each record can reference a POJ/object instance through `record+0x02` and
contains spatial/motion state including fields around `+0x23..+0x3F`.
The pool contains internal record kinds and is heavily used by transient
simulation code.

Processing of these records reaches the exact diagnostic string:

`MISSILE HITTING SFX NOT IN TABLE`

and creation/update paths populate direction/velocity-like fields and object
type dependent data.

This is strong evidence that at least part of the pool represents projectile
or spell/effect runtime actors. Because the pool has several internal record
kinds and the starter LEVEL01 save has no active `cell+0x13` head, the
semantic name for the entire 0x66 class remains OPEN.

## Remaining K291-D gates

Still OPEN before K292:
1. exact meaning and direction order of `cell+0x03..+0x06`;
2. exact passability/topology bit meanings in `cell+0x02`;
3. exact umbrella semantic name for the 0x66 pool.

No connectivity graph may rely on guessed direction ordering.
