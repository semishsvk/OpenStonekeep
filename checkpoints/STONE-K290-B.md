# STONE-K290-B — CD GROUP directory and installed payload transform

- Date: 2026-09-28
- Corrected: 2026-10-04
- Status: **VERIFIED on GROUP01, GROUP02 and GROUP24; directory offset semantics corrected**
- Knowledge classification: GAME-SPECIFIC
- Scope: Stonekeep GROUP container storage/provenance

## Correction note

The original K290-B interpretation labeled directory entry `+0x0E u32` as
the cumulative **end** of the same entry's payload.

E.13 direct inspection of `LEVEL01.MAZ`, `LEVEL02.MAZ` and
`OBJTYPE.DEF`, plus entry-0 / sentinel invariants in three independent
GROUPs, falsifies that off-by-one interpretation.

The field is the absolute **start offset of the entry named by that same
directory record**.

This correction changes named-resource intervals, but does **not** invalidate
the independently verified CD -> installed directory-strip transform.

## Verified CD GROUP directory

A CD GROUP begins with:

```text
u16 entry_count
entry_count × 22-byte directory entry
payload area
4 trailing bytes
```

A directory entry has:

```text
+0x00  char name[12]
+0x0C  2 bytes metadata       // semantics OPEN
+0x0E  u32 payload_start      // VERIFIED
+0x12  4 bytes metadata       // semantics OPEN
```

Payload interval for entry i:

```text
start[i] = payload_start[i]
end[i]   = payload_start[i+1]              // if a next entry exists
end[last]= filesize - 4
size[i]  = end[i] - start[i]
```

Duplicate adjacent start offsets represent valid zero-length resources.

Corpus invariants:

- GROUP01: entry count 47, directory end 0x040C, entry0 start 0x040C.
- GROUP02: entry count 58, directory end 0x04FE, entry0 start 0x04FE.
- GROUP24: entry count 1777, directory end 0x98B8, entry0 start 0x98B8.
- all three real GROUPs contain a final `!SENTINEL!` entry whose start equals
  `filesize - 4`, yielding a zero-length sentinel payload.

## CD -> installed transform

For GROUP01, GROUP02 and GROUP24 the installed DATA GROUP is exactly the CD
GROUP with the directory prefix removed. Payload bytes and the four-byte
trailer are otherwise byte-identical.

### GROUP01

- CD size: 577,860
- CD SHA-256:
  `7677db711fa51144ba4f88349241e136680d11c8c03a1dbf50b645b69829cb56`
- entry_count: 47
- directory size: 1,036 = 0x040C
- installed size: 576,824
- installed SHA-256:
  `808f2786fe794fe6359a2a1fe6a10f44f7115532a98e55246f2939e9082bd39b`
- VERIFIED:
  `CD_GROUP01[0x040C:] == installed_GROUP01`

### GROUP02

- CD size: 524,847
- entry_count: 58
- directory size: 1,278 = 0x04FE
- installed size: 523,569
- installed SHA-256:
  `b890250635adec26ef0dd04ccb209f91e40e6e2a304416a831d6d969e6d858c3`
- VERIFIED:
  `CD_GROUP02[0x04FE:] == installed_GROUP02`

### GROUP24

- CD size: 22,314,746
- CD SHA-256:
  `d0bbf68e7e4966fc630560446c14356b9530e602746e87f6d98bd4eb7b58f176`
- entry_count: 1777
- directory size: 39,096 = 0x98B8
- installed size: 22,275,650
- installed SHA-256:
  `1fe4aecfb4b3c4653c5203ae472d9997902268837ebb40d8e4e2327bc5031930`
- VERIFIED:
  `CD_GROUP24[0x98B8:] == installed_GROUP24`

The directory-strip transform is therefore verified 3/3 sampled GROUPs.

## Named-resource provenance examples

### LEVEL01.MAZ

GROUP01 directory entry 23:

- payload interval: `[0x50C77, 0x531CF)`
- payload size: 9,560 bytes
- SHA-256:
  `58bb761f67a6660b704cb126822e252e76d0a64bb56765b665ff540793d8daa3`
- first bytes: `4F 4E 1A 00 1D 00 ...` = marker `ON`, dimensions 26 × 29.

### LEVEL02.MAZ

GROUP02 directory entry 26:

- payload interval: `[0x4257C, 0x444F8)`
- payload size: 8,060 bytes
- SHA-256:
  `2255a617c1470bc388fa33667944d9df7dac350b2f0a5943a95fc719ae475b84`
- first bytes: `4F 4E 1E 00 1B 00 ...` = marker `ON`, dimensions 30 × 27.

This directly explains the E.13 new-level loader input for level 2.

### OBJTYPE.DEF

MASTER entry #928 names `OBJTYPE.DEF` and maps it to GROUP24.

Corrected GROUP24 directory entry 1770:

- payload interval: `[0x1532D57, 0x1536407)`
- payload size: 14,000 bytes
- SHA-256:
  `4341849062262a889366ece2705143303789ff106af461f0e1f61560d1b28861`

The previously recorded 22,513-byte interval
`[0x152D566,0x1532D57)` belongs to the preceding directory entry and is
explicitly **FALSIFIED** as the `OBJTYPE.DEF` payload.

## Tooling

`tools/inspect_group.py` now exposes:

- own-entry `payload_start`;
- next-entry-derived `payload_end`;
- `payload_size`;
- installed offsets after directory stripping.

`tests/test_inspect_group.py` constructs synthetic GROUPs using the corrected
start-offset semantics and preserves zero-length-entry coverage.

## Evidence classification

VERIFIED:

- 22-byte CD GROUP directory records;
- entry `+0x0E` = own payload absolute start;
- interval = current start to next start;
- duplicate starts = zero-length resource;
- final real `!SENTINEL!` starts at `filesize-4`;
- CD -> installed directory-strip transform for GROUP01/GROUP02/GROUP24;
- corrected LEVEL01.MAZ, LEVEL02.MAZ and OBJTYPE.DEF intervals above.

FALSIFIED:

- `+0x0E` is the cumulative end of the same named entry;
- old OBJTYPE.DEF 22,513-byte interval.

OPEN:

- semantics of the other six directory metadata bytes;
- transform generalization to every GROUP without direct validation.

## Reproduction

```bash
python tools/inspect_group.py /path/to/CD/DATA/GROUP01 --json
python tools/inspect_group.py /path/to/CD/DATA/GROUP02 --json
python tools/inspect_group.py /path/to/CD/DATA/GROUP24 --json
```
