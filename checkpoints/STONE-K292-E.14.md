# STONE-K292-E.14 — LEVEL02 typed MAZ tail and post-open physical clearance

- Date: 2026-10-04
- Status: **PASS — typed MAZ tail framing VERIFIED; both LEVEL02 return portals physically clear after LOW opening**
- Knowledge classification: GAME-SPECIFIC

## Result

E.14 decodes the variable-length MAZ tail through exact EOF on both authoritative LEVEL01.MAZ and LEVEL02.MAZ, using LEVEL01.MAZ -> LEVEL01.SAV as an independent runtime oracle before applying the same contracts to LEVEL02.

Both LEVEL02 return portals are physically clear after the E.9 reciprocal LOW clear:

- h144 (6,2) S -> (7,2): MSP clear; initial monster-spatial clear.
- h145 (2,17) E -> (2,18): MSP clear; initial monster-spatial clear.

## Typed MAZ tail framing

After marker/dimensions and the two rows*columns grid planes:

1. Block 1: u16 count + count x 18-byte records.
2. Block 2: u16 count + 10-byte base records; type 3 consumes an additional 8 bytes when word4 >= 0 or word4 == -99.
3. Block 3: u16 MSP count; each MSP has a 26-byte base, word12 x 16-byte attached POJ records, then u16 nested-monster count. Each nested monster has a 16-byte base and word7 x 14-byte attached POJ records.
4. Block 4: u16 standalone-monster count; each has an 18-byte base and word8 (+0x10) x 14-byte attached POJ records.

Counts:

- LEVEL01: block1=47, block2=131, MSP=122, nested monsters=7, standalone monsters=44.
- LEVEL02: block1=29, block2=71, MSP=93, nested monsters=4, standalone monsters=57.

Exact EOF invariant:

- LEVEL01: 9560 / 9560 bytes consumed.
- LEVEL02: 8060 / 8060 bytes consumed.
- trailing undecoded bytes: 0 / 0.

Executable evidence proves nested monsters inherit the parent MSP row/column at 0x6E4C1/0x6E4C9. Standalone monster base words +0x02/+0x04 are passed as row/column to spatial placement routine 0x76980.

## LEVEL01 runtime oracle

Authoritative LEVEL01.MAZ SHA-256: 58bb761f67a6660b704cb126822e252e76d0a64bb56765b665ff540793d8daa3.
Authoritative LEVEL01.SAV SHA-256: 2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9.

For all first 122/122 MAZ MSP records, type, row, column and the two directly copied positional fields match the independently serialized runtime MSP pool. Identity mismatches: 0.

LEVEL01 contains four type-13 MSP records at (3,3), (3,25), (22,3), (22,25). They share an identical non-coordinate initialization signature and all four serialized runtime movement-mask bytes +0x18 are 0.

LEVEL02 contains the same non-coordinate type-13 signature at (7,2) and (2,18), the two LEVEL01->LEVEL02 arrival cells. Their initial movement mask is therefore 0 under the same generic materializer and global MSP type system.

## Portal h144

- source (6,2): no MSP instance.
- adjacent (7,2): exactly one type-13 MSP, oracle movement mask 0.
- nested monsters at source/adjacent: 0.
- standalone monsters at source/adjacent: 0.
- post-open MSP blocked: false.
- initial monster-spatial blocked: false.
- result: PHYSICAL_CLEAR_AFTER_LOW_OPEN.

## Portal h145

- source (2,17): no MSP instance.
- adjacent (2,18): exactly one type-13 MSP, oracle movement mask 0.
- nested monsters at source/adjacent: 0.
- standalone monsters at source/adjacent: 0.
- post-open MSP blocked: false.
- initial monster-spatial blocked: false.
- result: PHYSICAL_CLEAR_AFTER_LOW_OPEN.

## Executable anchors

E.14 validates exact SHA-256 anchors for:

- 0x6E220 +0x770 — typed-tail MSP/nested-monster block.
- 0x6E990 +0x184 — standalone-monster block.
- 0x76980 +0x100 — monster spatial placement.
- 0x11B40 +0x100 — MSP allocation.

All 4/4 match the authoritative SK.EXE.

## Reproducibility

Added tools/inspect_level02_runtime_tail.py and tests/test_inspect_level02_runtime_tail.py.

Authoritative result:

PASS msp=93 nested_monsters=4 standalone_monsters=57 portal_clear=2/2 regions=4 errors=0

## Gate

level02_typed_maz_framing = VERIFIED
level01_maz_save_msp_oracle = 122/122 VERIFIED
level02_return_portal_msp_clear = 2/2 VERIFIED_INITIAL_STATE
level02_return_portal_spatial_clear = 2/2 VERIFIED_INITIAL_STATE
level02_return_portal_physical_clear_after_open = 2/2 VERIFIED_INITIAL_STATE
three_level_transition_graph = READY
one_way_verdict_authorized = false
softlock_verdict_authorized = false

## Next — STONE-K292-E.15

Compose LEVEL01/LEVEL01A conditional portals with the two LEVEL02 direct-enable return transitions. Classify only the now-closed portal pairs; do not generalize to global softlock safety without the full LEVEL02 ordinary-movement graph.