# STONE-K292-E.12 — portal-producer selection source closure

- Date: 2026-10-04
- Status: PASS — both E.10 payload sources are serialized and their engine selection paths are verified
- Knowledge classification: GAME-SPECIFIC
- Scope: E.10 payload ID 0 for handler 87 and payload ID 166 for handlers 106/107

## Result

E.12 binds both required selector-5 payloads to authoritative starter state and
resolves how their POJ records can become active selection at 0x1BC6A8.

Payload ID 166 is a serialized global-list/UI selection and is directly
input-addressable in the starter list state.

Payload ID 0 is a serialized world POJ attached to LEVEL01 cell (18,20) and
uses the verified world render -> hit-test -> interaction selection path.
Concrete play-state visibility and interaction callback success remain
state-qualified.

No original game/save bytes are committed.

## GAMEINFO POJ pool

Authoritative GAMEINFO.SAV:
- SHA-256 eef1dd19f7cb0913a3fe5821aa3bf5906a17b2764e61407279b3bda823d075ca
- POJ pool file offset 0x24FF
- 2000 records
- stride 0x2F

This is the serialized form of runtime POJ pool 0x19E2E0.

## Payload ID 0 — handler 87

POJ record 79:
- ID 0
- row 18, column 20
- previous link -1
- next link 80

LEVEL01 cell (18,20):
- cell+0x0D POJ head = 79
- handler = 0
- selector 4 = 0
- selector 5 = 0

Record 80 backlinks to record 79.

Result:
PRESENT_SERIALIZED + PLACED_IN_LEVEL + CELL_POJ_CHAIN_VERIFIED.

Verified world selection chain:
1. 0x2E210 reads cell+0x0D and walks the 0x2F POJ chain.
2. 0x2E860 computes runtime screen hitbox fields.
3. 0x2E6xx/0x2E7xx append eligible rendered POJ indices to the clickable list.
4. 0x7E140 hit-tests that list.
5. 0x79EBA stores the resulting POJ index in 0x1BC496.
6. 0x7DA60 verifies the candidate against nearby cell+0x0D chains and, on its
   normal interaction path, writes the selected POJ to 0x1BC6A8.

Record 79 ID0 does not match the special ID branches 0x29, 0x98, 0x8C or 0xB7.

Classification:
ID0_SELECTION_MECHANISM = VERIFIED
ID0_WORLD_INTERACTION_REACHABILITY = STATE_QUALIFIED

The qualification is actual play-state visibility / interaction callback
success, not an unknown mechanism or missing payload source.

## Payload ID 166 — handlers 106/107

POJ record 162:
- ID 166
- row/column -1/-1
- previous global-list link 70
- next global-list link 158
- stack/count field +0x1A = 1

Serialized global POJ-list state:
- head 120
- count 16
- active selection -5 = none
- scroll offset 0

Walking record+0x18 from head 120 yields exactly 16 records and terminates at
sentinel -4. Record 162 is zero-based list index 4.

Engine initialization sets visible list slots to 5 at runtime 0xAA783.

The input path around 0x48734 computes:
n = (ui_slot - 1) + scroll_offset

Starter state therefore gives:
UI slot 5 -> n=4 -> record 162.

0x496A0 walks the global list to the nth POJ and 0x4AF32 stores the result in
active selection 0x1BC6A8.

The record+0x1A == 1 branch in 0x4A0BC returns the no-split result; it is not a
selection veto.

Classification:
ID166_GLOBAL_LIST_MEMBERSHIP = VERIFIED
ID166_UI_SLOT = 5/5 VERIFIED
ID166_SELECTION_ROUTE = SERIALIZED_LIST_INPUT_REACHABLE

## Reproducibility

Added:
- tools/inspect_selection_reachability.py
- tests/test_inspect_selection_reachability.py

Authoritative result:
PASS regions=9 errors=0
ID0 record=79 cell=[18,20] head=79 placement=True
  reach=WORLD_RENDER_INTERACTION_STATE_QUALIFIED
ID166 record=162 list_index=4 slot=5/5 reachable=True
  reach=SERIALIZED_LIST_INPUT_REACHABLE

Executable evidence anchors: 9/9 SHA-256 matched.
Synthetic regression: 4 PASS.

## Falsified path

The selector-6 branch around 0x644D0 is not record79 evidence. It requires
POJ +0x0A == -2 and +0x0C == -1. Record79 has -3 and +1.

## Level-2 source boundary

Starter GAME00 contains LEVEL01.SAV and LEVEL01A.SAV, but no LEVEL02.SAV.
Drive-wide searches for LEVEL02 / LEVEL02.SAV found no authoritative starter
level-2 save.

Therefore:
LEVEL2_STARTER_DYNAMIC_STATE = SOURCE_INCOMPLETE

This is not evidence that level 2 has no return path.

## Gate

e10_payload_source_records = 2/2 VERIFIED
id166_selection_source = VERIFIED_INPUT_REACHABLE
id0_selection_mechanism = VERIFIED
id0_selection_reachability = VERIFIED_STATE_QUALIFIED
conditional_portal_graph = VERIFIED_STATE_QUALIFIED
level2_dynamic_continuation = SOURCE_INCOMPLETE
one_way_verdict_authorized = false
softlock_verdict_authorized = false

## Next — STONE-K292-E.13

Trace the missing-save/new-level path for target level 2 and identify the
authoritative base resource that materializes its initial grid/runtime state.
Reconstruct a deterministic initial LEVEL02 state if corpus evidence is
sufficient. Do not infer one-way or softlock behavior from a missing save.
