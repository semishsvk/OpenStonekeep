# STONE-K292-E — handler dispatch resolution gate

- Date: 2026-09-30
- Status: PARTIAL PASS — handler inventory verified; final target/action semantics remain gated
- Knowledge classification: GAME-SPECIFIC

## Key correction

K292-E confirms that cell+0x07 is an index into a relocation-sensitive 4-byte dispatch table, not a bare linear function address.

The executable getter at virtual 0x6C5CC reads the signed cell handler ID, indexes the dispatch table at virtual 0xF16A, writes the selected 4-byte entry to a caller-supplied target slot, and callers subsequently invoke that slot indirectly.

Because this is an LE executable, raw on-disk bytes are not promoted to final runtime targets. A direct handler_id -> address table derived without LE fixups would be false evidence.

## Authoritative starter corpus

LEVEL01.SAV candidate source-handler IDs:

2, 3, 13, 14, 15, 16, 21, 22, 23, 24, 43, 60, 75, 76, 77, 78, 79, 80, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 115, 116

LEVEL01A.SAV candidate source-handler IDs:

13, 23, 42, 86, 410, 411, 412, 413, 414, 415, 416, 417, 418, 419

Union: 62 relevant IDs.

## Movement-path consequence

K292-C already established that the per-cell handler is reached before ordinary translation. Forward and backward movement use selectors 3 and 5 in the ordinary input path.

Selectors 2/3/4/5 must not yet be interpreted as universal handler allow/veto codes. They must be traced through the resolved dispatch targets.

## Tooling

Added tools/inspect_handler_dispatch.py and tests/test_inspect_handler_dispatch.py.

The tool inventories IDs, records dispatch-table slots and raw disassembly bytes, and explicitly stops at RELOCATION_REQUIRED.

Synthetic regression: 2 PASS.

## Current gate

handler_target_resolution = BLOCKED_ON_LE_RELOCATION
movement_action_classification = NOT_AUTHORIZED
one_way_verdict_authorized = false
softlock_verdict_authorized = false

## Next step — STONE-K292-E.1

Resolve the LE relocation/fixup records affecting the dispatch table at 0xF16A; reconstruct final targets; trace selectors 2/3/4/5; classify only directly evidenced allow/veto/state mutations; then feed resolved outcomes into the state-qualified transition graph.

Framework improvement: NavigationIR should carry a DispatchRef with format, virtual_address, raw_entry, relocation_state, resolved_target and resolution_evidence rather than a bare handler address.