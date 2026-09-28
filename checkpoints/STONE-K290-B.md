# STONE-K290-B — CD GROUP directory and installed payload transform

- Date: 2026-09-28
- Status: **VERIFIED on GROUP01 and GROUP24**
- Knowledge classification: GAME-SPECIFIC
- Scope: Stonekeep GROUP container storage/provenance

## Verified CD GROUP directory

For both original CD samples tested, a CD GROUP begins with:

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
+0x0E  u32 cumulative_end     // VERIFIED
+0x12  4 bytes metadata       // semantics OPEN
```

Payload interval for entry i:

```text
start[0] = 2 + entry_count * 22
start[i] = cumulative_end[i-1]
end[i]   = cumulative_end[i]
size[i]  = end[i] - start[i]
```

Zero-length logical entries are valid and must be preserved.

The final cumulative end equals `filesize - 4` in both tested GROUPs.

## CD -> installed transform

The installed DATA GROUP is not a separately recompressed payload in the two
samples tested. It is exactly the CD GROUP with the directory prefix removed.

### GROUP01

- CD size: 577,860
- CD SHA-256:
  `7677db711fa51144ba4f88349241e136680d11c8c03a1dbf50b645b69829cb56`
- entry_count: 47
- directory size: `2 + 47*22 = 1,036 = 0x040C`
- installed size: 576,824
- installed SHA-256:
  `808f2786fe794fe6359a2a1fe6a10f44f7115532a98e55246f2939e9082bd39b`
- VERIFIED byte-for-byte:
  `CD_GROUP01[0x040C:] == installed_GROUP01`

### GROUP24

- CD size: 22,314,746
- CD SHA-256:
  `d0bbf68e7e4966fc630560446c14356b9530e602746e87f6d98bd4eb7b58f176`
- entry_count: 1777
- directory size: `2 + 1777*22 = 39,096 = 0x98B8`
- installed size: 22,275,650
- installed SHA-256:
  `1fe4aecfb4b3c4653c5203ae472d9997902268837ebb40d8e4e2327bc5031930`
- VERIFIED byte-for-byte:
  `CD_GROUP24[0x98B8:] == installed_GROUP24`

Result: the previously observed CD-vs-installed size deltas for these groups
are fully explained by directory stripping. This rule is verified 2/2 and
must not yet be generalized to all GROUP01..GROUP87 without additional
sampling.

## OBJTYPE.DEF provenance

MASTER entry #928 is `OBJTYPE.DEF`, with MASTER group id 24.

In CD GROUP24:
- directory entry index: 1770
- stored payload interval: `[0x152D566, 0x1532D57)`
- stored payload size: 22,513 bytes
- stored SHA-256:
  `f49a478b06f868839f7484d0de1fae7a47b87bbc4bc8fed1a131a3c387f3f85c`

The corresponding interval in the installed GROUP24 is shifted down by the
directory size and is byte-identical. The stored payload remains packed; no
uncompressed-size interpretation is asserted here.

## Reproduction

```bash
python tools/inspect_group.py /path/to/CD/DATA/GROUP01 --json
python tools/inspect_group.py /path/to/CD/DATA/GROUP24 --json
```

The inspector intentionally rejects directory-less installed GROUP payloads.
