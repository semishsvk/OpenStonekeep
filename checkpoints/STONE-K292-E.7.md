# STONE-K292-E.7 — starter-level global callback closure

- Date: 2026-10-01
- Status: **PASS — starter global movement callback side effect is ABSENT_VERIFIED**
- Knowledge classification: GAME-SPECIFIC
- Scope: per-level callback stored at runtime global `0x1B9DDC` for `level01` and `level01a`

## Purpose

K292-E.6 expanded movement-callback side-effect tracing across all 59 movement
source handlers. Several common families delegate to a per-level global
callback at `0x1B9DDC`. Until that callback was resolved, those paths retained
an opaque indirect-effect dependency.

E.7 resolves the per-level callback from the executable's own LE relocation
metadata and level initializer table.

## Authoritative executable

`SK.EXE`:

- SHA-256: `5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2`
- MZ + LE
- level-name table: object 3 + `0x5D44`
- fixed level-name width: 9 bytes
- level-init dispatch table: object 3 + `0xF10E`
- level-init count represented by the paired tables: 22
- level index used by the loader: live current-level value `0x1BC6A0`

Raw init-table dwords and raw callback immediates are not treated as runtime
addresses. E.7 requires matching `OFF32 -> internal object` LE fixups.

## Level-index alignment

The 9-byte name table and init table share the same index ordering. Relevant
starter entries are:

- index 1: `level01`
- index 15: `level01a`

The full executable table contains 22 named slots. `level00` has a null init
entry; 21 level initializers are relocation-resolved.

## LEVEL01

Index 1 resolves to initializer runtime address:

`0x5DD09`

The initializer writes a relocation-sensitive raw callback value to
`0x1B9DDC`. Its LE fixup resolves the callback to:

`0x5E867`

The first opcode at that runtime target is exactly `C3` = `RET`.

Therefore, for the authoritative LEVEL01 starter module, the per-level global
callback itself has **no executed body beyond immediate return**.

## LEVEL01A

Index 15 resolves to initializer runtime address:

`0x4F69A`

Its callback write resolves through LE relocation to:

`0x4F861`

The first opcode is again exactly `C3` = `RET`.

Therefore, for the authoritative LEVEL01A starter module, the per-level global
callback itself also has **no executed body beyond immediate return**.

## Corpus-wide context

Across the 21 initialized level entries:

- callback entrypoints beginning with `RET`: 19
- non-RET callback entrypoints: 2

This checkpoint does not generalize starter no-op semantics to those two other
level modules.

## E.6 support closure

The current `validate_callback_state_delta_manifest.py` now covers all
**59/59** movement-source handlers across three tranches. Its 56 executable
code-region SHA-256 anchors were independently checked against the authoritative
SK.EXE during E.7 preparation: **56/56 matched**.

That does not make every helper semantically closed. It does remove the
`0x1B9DDC` indirect callback as an unresolved side-effect source for LEVEL01
and LEVEL01A.

## Tooling

Added:

- `tools/inspect_level_callback_hooks.py`
- `tests/test_inspect_level_callback_hooks.py`

Authoritative run:

    PASS levels=22 initialized=21 ret=19 nonret=2 errors=0
    level01  0x5dd09 0x5e867 RET=True
    level01a 0x4f69a 0x4f861 RET=True

Synthetic regression: **3 PASS**.

## Evidence classification

VERIFIED:

- level-name and level-init table alignment;
- index 1 = `level01`;
- index 15 = `level01a`;
- LE relocation of both starter init entries;
- LE relocation of both writes to `0x1B9DDC`;
- LEVEL01 callback target `0x5E867` begins with `RET`;
- LEVEL01A callback target `0x4F861` begins with `RET`.

ABSENT_VERIFIED, starter levels only:

- side effects executed inside the per-level `0x1B9DDC` callback body.

PARTIAL / OPEN:

- explicit semantics of the remaining non-callback helper/event paths in the
  59-handler movement manifest;
- portal/level-transition payloads;
- portal unlock state mutation;
- multi-step dynamic state graph.

## Gate

`movement_callback_return_semantics = VERIFIED`

`movement_callback_manifest_coverage = 59/59`

`starter_level_global_callback = VERIFIED_NOOP`

`starter_level_global_callback_side_effect = ABSENT_VERIFIED`

`dynamic_state_graph = NOT_AUTHORIZED`

`one_way_verdict_authorized = false`

`softlock_verdict_authorized = false`

## Next — STONE-K292-E.8

Freeze explicit level-transition payload semantics for the movement handlers
that delegate through the 0x3CFEE -> 0xA2DC7 -> 0xA2BA6 family, including
target level and staged player row/column/facing. Keep portal unlock semantics
separate until the mutation that makes the initially closed low-static edge
passable is directly evidenced.
