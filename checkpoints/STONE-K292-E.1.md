# STONE-K292-E.1 — LE relocation closure for cell-handler dispatch

- Date: 2026-10-01
- Status: **PASS — dispatch targets deterministically resolved**
- Knowledge classification: GAME-SPECIFIC
- Scope: LE relocation/fixup resolution for cell+0x07 handler dispatch

## Purpose

K292-E stopped at RELOCATION_REQUIRED because the four-byte entries selected
by cell+0x07 are loader-relocated LE data. Raw on-disk values must not be
promoted to final runtime addresses.

K292-E.1 resolves that gate from the executable's own LE object/page/fixup
metadata. No original Stonekeep bytes are committed.

## Authoritative executable

SK.EXE:

- size: 1,203,449 bytes
- SHA-256: 5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2
- container: MZ + LE
- LE pages: 232
- page size: 0x1000
- objects: 3
- object 1: runtime base 0x10000, size 0xC3DC9, mapped pages 1..196
- object 3: runtime base 0xF0000, size 0x1C5D30, mapped pages 197..232

## Dispatch relocation

The handler getter indexes a four-byte table at object 3 + 0xF16A. This
location falls on LE logical page 212 at page offset 0x16A.

Every relevant dispatch slot has exactly one LE fixup with:

- source type: OFF32 (0x07)
- target kind: INTERNAL
- target object: 1
- target offset width: 32 bit

The final runtime address is therefore object1.runtime_base +
target_object_offset. Treating the raw four-byte slot as an already-final
linear pointer is falsified.

## Starter-save inventories

Authoritative saves:

- LEVEL01.SAV SHA-256:
  2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9
- LEVEL01A.SAV SHA-256:
  3d1753ca8a4ca49b3ccf9da0fc15bb08ac242301eff40586049379ceba635dc9

Across both saves:

- all non-default cell+0x07 handler IDs: **62**
- slots with exactly one matching LE fixup: **62/62**
- resolved object-1 targets: **62**
- unique resolved targets: **62**
- missing or ambiguous relevant slots: **0**

## K292-E scope correction

K292-E conflated two counts. The correct sets are:

- **62** = all non-default handler IDs present in the two saves;
- **59** = non-default handlers that are the source of at least one in-bounds
  low-static-clear candidate player edge.

The three resolved non-default IDs outside the current movement-source set are
41, 85 and 114.

## Tooling

Added:

- tools/resolve_le_handler_dispatch.py
- tests/test_resolve_le_handler_dispatch.py

The resolver parses the MZ/LE headers, object records, LE page map, fixup page
table and variable-length fixup records; inventories save handlers; derives
the movement-source subset; and resolves each slot to target object,
object-relative offset, runtime linear address and backing file offset.

Authoritative run:

    all_nondefault=62
    movement_candidates=59
    resolved=62
    unique_targets=62
    errors=0

Synthetic regression: **2 PASS**.

## Evidence classification

VERIFIED:

- cell+0x07 dispatch entries are LE relocation-sensitive;
- dispatch table location is object 3 + 0xF16A;
- all 62 non-default starter-save slots resolve uniquely;
- every relevant slot resolves through an internal object-1 OFF32 fixup;
- current movement-candidate source set contains 59 IDs.

FALSIFIED:

- raw dispatch bytes are final linear function addresses;
- 62 is the movement-candidate source-handler count for the starter saves.

## Action-trace status

Static tracing during E.1 has found no pre-movement veto for action 3
(forward pre) or action 5 (backward pre) in the 59 candidate handlers examined.
Several handlers perform state mutations before delegating to an allow-returning
path, so ALLOW must not be interpreted as NO_SIDE_EFFECT.

This action-level claim remains separate from the relocation proof until a
coverage-complete 59-ID action evidence manifest is frozen.

## Gate

handler_target_resolution = VERIFIED

movement_candidate_source_handler_count = 59

movement_action_classification = IN_PROGRESS

one_way_verdict_authorized = false

softlock_verdict_authorized = false

## Next — STONE-K292-E.2

Freeze coverage-complete evidence for actions 2/3/4/5 across all 59 movement
source handlers, distinguishing allow, veto, state mutation, event/transition
side effect and unresolved behavior. Runtime MSP/maze-prop and monster spatial
occupancy remain independent movement gates even if the handler pre-action
layer proves allow-only.
