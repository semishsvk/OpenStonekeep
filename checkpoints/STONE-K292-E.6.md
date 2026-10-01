# STONE-K292-E.6 — movement callback state-delta tranche 1

- Date: 2026-10-01
- Status: **PARTIAL PASS — direct movement-state deltas resolved for the six previously observed mutating handlers**
- Knowledge classification: GAME-SPECIFIC
- Scope: actions 2/3/4/5 for handlers 110, 111, 112, 115, 410 and 415

## Result

E.5 proved the serialized initial translation layer but intentionally left
non-default callback state deltas PARTIAL. E.6 begins that closure from the six
movement handlers for which E.2 had already observed mutation/event work.

The main new result is that these effects can now be expressed against exact
serialized cell offsets and coordinates rather than generic "state mutation".

This checkpoint does **not** claim that the remaining movement handlers have no
side effects. `NO_DIRECT_WRITE_OBSERVED` is negative evidence only and is not
`ABSENT_VERIFIED`.

## Cell selector API closure

The common getter at runtime 0x3C14D and setter at 0x3C231 index 14-entry
relocation-sensitive jump tables. Reconstructing those tables closes the
selector -> 21-byte cell-record mapping:

| Selector | Cell field |
| ---: | --- |
| 1 | cell+0x00 byte |
| 2 | cell+0x02 byte |
| 3 | cell+0x00 bit 0 |
| 4 | cell+0x09 word |
| 5 | cell+0x0B word |
| 6 | cell+0x0D s16 |
| 7 | cell+0x0F s16 |
| 8 | cell+0x11 s16 |
| 9 | cell+0x13 s16 |
| 10 | cell+0x01 N directional bit |
| 11 | cell+0x01 W directional bit |
| 12 | cell+0x01 S directional bit |
| 13 | cell+0x01 E directional bit |
| 14 | cell+0x01 raw byte |

This independently agrees with prior K291/K292 evidence for selector 8 and
selectors 10..13, and additionally resolves the previously unnamed word fields
at cell+0x09 and cell+0x0B in the generic cell accessor API.

The accessor coordinate convention is also fixed by executable arithmetic:
EDX selects the row, EBX the column, and the resulting index is multiplied by
21 bytes per cell.

## Handler 110 / 111

Dispatch targets:

- 110 -> 0x5F1DA
- 111 -> 0x5F1D9

Handler 111 enters one instruction earlier (`cwtl`) and then shares the same
movement-action body as 110 for actions 2/3/4/5.

Direct deltas:

- action 3 (forward pre): `cell(row=14,col=8)+0x0B = 1`
- action 5 (backward pre): `cell(row=14,col=8)+0x0B = 2`
- actions 2 and 4: no direct cell write is present in this handler body; indirect
  helper effects are not claimed absent.

Thus forward/backward entry into this callback family explicitly encodes a
different serialized state value before translation.

## Handler 112

Dispatch target: 0x5F1FF.

Movement actions 2/4/5 take the common allow chain with no direct cell write in
the handler body.

Action 3 performs conditional event work:

    if cell(row=14,col=8)+0x09 == 0:
        call 0x6A73A with EAX=4, EDX=4, EBX=4, ECX=10
        call 0x9C984 with EAX=0x231

No direct 0x3C231 cell-setter call occurs on this action-3 branch. The effects
of the event helpers themselves remain PARTIAL rather than being guessed.

## Handler 115

Dispatch target: 0x5F421.

All movement actions 2/3/4/5 share the same conditional delta path:

    if u16[0x170D9A] != 0
       and cell(row=8,col=10)+0x0B == 1:
        cell(row=8,col=10)+0x0B = 2
        call 0x41B44 with EAX=0x1FB7

The handler then delegates to its common continuation. Because actions 3/5 are
pre-movement calls, this state change may occur before ordinary translation.

## Handler 410

Dispatch target: 0x4F862.

All movement actions 2/3/4/5 share:

    if cell(row=16,col=3)+0x09 == 0:
        cell(row=16,col=3)+0x09 = 1
        call 0x34228 with the fixed bundle at 0x4F89A..0x4F8B3
        call 0xA91F3 with EAX=0x1AFC
        call 0xA91F3 with EAX=0x1B0D

For an ordinary move starting from value zero, the pre-action (3 forward or 5
backward) therefore performs the direct cell-state mutation before translation;
the post-action subsequently observes the already changed value.

## Handler 415

Dispatch target: 0x4F983.

Actions 2 and 3 share an additional branch that actions 4 and 5 do not take.
When `u16[0x1BC6AE] == 0`:

    cell(row=23,col=3)+0x09 = 30

and, if either

    cell(23,3)+0x09 <= 10
    OR cell(23,2)+0x09 == 30

then selector 1 writes byte value 0x10 into cell+0x00 for row 23 columns:

    6, 7, 8, 19, 20, 21, 22

The common path used by actions 2/3/4/5 additionally has:

    if u16[0x170D9A] != 0
       and cell(row=23,col=2)+0x0B == 1:
        cell(row=23,col=2)+0x0B = 2
        call 0x41B44 with EAX=0x1B25

Therefore forward pre-action 3 can alter multiple cell records before
translation; backward pre-action 5 only takes the common conditional delta.

## Reproducibility / validator

Added:

- `tools/validate_callback_state_delta_manifest.py`
- `tests/test_validate_callback_state_delta_manifest.py`

The validator requires the authoritative SK.EXE SHA-256:

`5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2`

Before accepting the manifest it reconstructs LE object addressing and checks:

- getter and setter selector tables;
- **13/13** exact executable byte-region SHA-256 anchors covering the accessor
  tables and the six handler mutation/event branches;
- manifest movement-action coverage for actions 2/3/4/5.

Authoritative validation:

    PASS regions=13 handlers=6 errors=0

Synthetic/structural regression: **4 PASS**.

## Evidence classification

VERIFIED:

- selector -> cell-offset mapping for selectors 1..14;
- row/column convention of the common cell getter/setter;
- handler entrypoints listed above;
- the direct cell writes and conditions listed for handlers 110/111, 115, 410
  and 415;
- handler 112 action-3 conditional event-call sequence;
- exact executable byte anchors used by the validator.

PARTIAL:

- semantic meaning/designer names of cell+0x09 and cell+0x0B;
- indirect effects of event/helper calls 0x6A73A, 0x9C984, 0x41B44, 0x34228
  and 0xA91F3;
- side-effect closure for the other movement-candidate handler families.

NOT_OBSERVED, not ABSENT_VERIFIED:

- direct cell writes on handler 110/111 actions 2/4;
- direct cell writes on handler 112 movement actions other than the documented
  action-3 event branch.

## Gate

`serialized_initial_translation_graph = VERIFIED_STATE_QUALIFIED`

`movement_callback_state_delta_tranche_1 = VERIFIED`

`movement_callback_state_delta_semantics = PARTIAL`

`dynamic_state_graph = NOT_AUTHORIZED`

`one_way_verdict_authorized = false`

`softlock_verdict_authorized = false`

## Next — continue STONE-K292-E.6

Trace the remaining movement-handler control-flow families for actions 2/3/4/5
with the now-verified selector API. Classify each family as direct cell write,
indirect/event mutation, or evidence-backed no-direct-write, then resolve the
indirect helper state targets needed to turn E.5 from an initial translation
graph into a multi-step dynamic state graph.
