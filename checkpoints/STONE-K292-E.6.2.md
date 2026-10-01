# STONE-K292-E.6.2 — starter-level default callback closure

- Date: 2026-10-01
- Status: **PASS — per-level dynamic default callback resolved for LEVEL01 and LEVEL01A**
- Knowledge classification: GAME-SPECIFIC
- Scope: the dynamic callback slot invoked by runtime 0x3D4F5 through `*[0x1B9DDC]`

## Result

K292-E.6.1 retained `*[0x1B9DDC]` as a concrete unresolved indirect-effect root.
E.6.2 follows the executable's own level-init dispatch and LE relocations and
proves that both authoritative starter levels install a one-byte `RET` entry
in that slot.

This removes the dynamic-callback uncertainty for LEVEL01 and LEVEL01A only.
It does **not** make the complete common callback chain side-effect free:
after the dynamic callback, runtime `0x3D4F5` continues into runtime
`0x3C36A`, which has independent state/event behavior.

## Per-level init selection

The loader sequence at runtime `0x44F2D` is:

    movsx eax, word [0x1BC6A0]
    call *0xF10E(,eax,4)

The call-table displacement is relocation-sensitive. Its LE fixup resolves to:

- internal object 3
- object offset `0xF10E`

Therefore live level ID `0x1BC6A0` indexes the object-3 per-level init table.

This agrees with the already verified MASTER mapping used by the starter data:

- LEVEL01 -> level/resource ID **1**
- LEVEL01A -> level/resource ID **15**

## LEVEL01 — ID 1

Table slot:

    object3 + 0xF10E + 1*4 = object3 + 0xF112

LE fixup:

    OFF32 -> internal object1 + 0x4DD09

Resolved runtime init entry:

    object1 base 0x10000 + 0x4DD09 = 0x5DD09

The init entry writes `0x1B9DDC` through a relocation-sensitive immediate.
That immediate resolves:

    OFF32 -> internal object1 + 0x4E867

Runtime callback target:

    0x5E867

The first instruction at `0x5E867` is exactly:

    C3    ret

Therefore:

`LEVEL01 default dynamic callback = NO_OP_RET`

## LEVEL01A — ID 15

Table slot:

    object3 + 0xF10E + 15*4 = object3 + 0xF14A

LE fixup:

    OFF32 -> internal object1 + 0x3F69A

Resolved runtime init entry:

    0x4F69A

The init entry assigns `0x1B9DDC` through a second LE relocation:

    OFF32 -> internal object1 + 0x3F861

Runtime callback target:

    0x4F861

The first instruction at `0x4F861` is exactly:

    C3    ret

Therefore:

`LEVEL01A default dynamic callback = NO_OP_RET`

## Independent bank-shape corroboration

The two init routines independently register the expected handler banks.

The ID-1 init around `0x5DD09` registers the LEVEL01-family handler population,
including the characteristic 87..116 range together with 2/3/86.

The ID-15 init around `0x4F69A` registers the LEVEL01A-family bank containing
410..419 together with 86.

This is supporting structural evidence; the authoritative selector proof is
the level-indexed init-table call plus LE fixups above.

## Common-chain correction

For these two starter levels, the E.6.1 shorthand:

    movement family
      -> *[0x1B9DDC]
      -> default continuation

can now be refined to:

    movement family
      -> NO_OP_RET
      -> 0x3C36A common continuation

The `NO_OP_RET` result applies only to the dynamic slot. Runtime
`0x3C36A` is **not** a no-op.

Direct static tracing of `0x3C36A` already shows for ordinary movement:

- action 3 writes `word[0x1BC3F6] = +1`;
- action 5 writes `word[0x1BC3F6] = -1`;
- action 2 writes `+1`, resolves the current cell handler, runs helper
  `0x3C4BD`, invokes that handler with **action 1**, then clears
  `0x1BC3F6`;
- action 4 performs the symmetric `-1` path, including current-cell
  **action 1**, then clears the marker;
- actions 2/3/4/5 subsequently reach helper `0x3D35E` when the
  `0x1B9D88` gate is clear.

Since K292-C established actions 2/4 as post-translation callbacks, the
current-cell handler reached from actions 2/4 is the **destination-cell**
handler for the completed ordinary move.

This creates a new evidence requirement: action-1 semantics for reachable
destination handlers.

## Destination action-1 scope in the serialized starter snapshots

Re-evaluating the E.5 physically executable translations gives:

- LEVEL01: 45 non-default destination handler IDs
- LEVEL01A: 14 non-default destination handler IDs
- union: **56 non-default destination handler IDs**

The only members of the 59 movement-source handler universe that are not
observed as post-translation destination handlers in these snapshots are:

`75, 80, 108`

Therefore dynamic action-complete closure for the serialized starter graph
requires action-1 evidence for exactly:

- default handler, plus
- **56 non-default destination handlers**

rather than blindly expanding all 62 non-default IDs.

## Helper observations

`0x3D35E` does not branch on the incoming movement action after entry.
For actions 2/3/4/5 it is one common current-cell/per-level post-processing
path. It can update runtime globals `0x1B9D58` and `0x1B9D5A` and invoke
resource/world helpers, but no movement return-value veto is introduced there.

`0x3C4BD` is reached by post actions 2/4 before destination action 1. It
walks the current cell's selector-8 MSP chain looking for MSP type `0x6C`,
reads record+0x2A, and invokes helpers `0xA4480` and `0x8C3AB`.
Downstream state impact remains PARTIAL and is not guessed.

## Tooling

Added:

- `tools/verify_starter_level_default_callbacks.py`
- `tests/test_verify_starter_level_default_callbacks.py`

The verifier requires the authoritative SK.EXE SHA-256 and follows:

1. loader dispatch bytes;
2. LE fixup of the per-level init-table reference;
3. level-ID table slot fixup;
4. selected init entry;
5. relocation-backed assignment to `0x1B9DDC`;
6. resolved callback entry byte.

Expected authoritative result:

    PASS levels=2 errors=0
    level=1  init=0x5DD09 callback=0x5E867 ret=true
    level=15 init=0x4F69A callback=0x4F861 ret=true

## Evidence classification

VERIFIED:

- the loader indexes object3+0xF10E by live level ID;
- LEVEL01/ID1 selects init 0x5DD09;
- LEVEL01A/ID15 selects init 0x4F69A;
- those init routines install callbacks 0x5E867 and 0x4F861 respectively;
- both callback entries are immediate `RET`;
- `*[0x1B9DDC]` therefore contributes no direct state effect in the two
  authoritative starter levels.

VERIFIED structural consequence:

- post movement actions 2/4 re-enter the destination cell handler with action 1;
- the serialized starter scope contains 56 non-default destination handler IDs.

PARTIAL:

- action-1 state effects of those 56 destination handlers;
- downstream effects of `0x3C4BD`;
- state relevance of `0x3D35E` globals/resource helpers;
- complete action-complete dynamic graph.

## Gate

`movement_callback_effect_surface_coverage = VERIFIED_59_OF_59`

`starter_level_dynamic_default_callback = VERIFIED_NO_OP_RET`

`post_translation_destination_action1 = VERIFIED_PRESENT`

`destination_action1_semantics = OPEN_56_NONDEFAULT_PLUS_DEFAULT`

`dynamic_state_graph = NOT_AUTHORIZED`

`one_way_verdict_authorized = false`

`softlock_verdict_authorized = false`

## Next — STONE-K292-E.6.3

Trace action 1 for the 56 actually reachable non-default destination handlers
plus the default path. Classify exact direct writes, indirect events and
delegation families. In parallel, determine whether `0x3C4BD` can mutate the
MSP directional mask at record+0x18 or monster-spatial state. Only then compose
post-translation state deltas into the multi-step graph.
