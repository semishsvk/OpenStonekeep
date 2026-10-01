import importlib.util
from pathlib import Path
TOOL=Path(__file__).resolve().parents[1]/'tools'/'validate_handler_action_evidence.py'
spec=importlib.util.spec_from_file_location('tool',TOOL); tool=importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)

def resolved(ids):
    return {'exe_sha256':tool.EXPECTED_EXE_SHA,
            'saves':[{'sha256':x} for x in tool.EXPECTED_SAVE_SHAS],
            'movement_candidate_source_handler_ids':ids}

def test_evidence_groups_are_unique():
    flat=[h for ids in tool.EVIDENCE_GROUPS.values() for h in ids]
    assert len(flat)==59 and len(set(flat))==59

def test_exact_coverage_passes():
    flat=sorted(h for ids in tool.EVIDENCE_GROUPS.values() for h in ids)
    out=tool.validate(resolved(flat))
    assert out['pass'] and out['action_cells']==236
    assert out['forward_pre_return0_handlers']==0
    assert out['backward_pre_return0_handlers']==0

def test_missing_handler_fails():
    flat=sorted(h for ids in tool.EVIDENCE_GROUPS.values() for h in ids)
    out=tool.validate(resolved(flat+[999]))
    assert not out['pass'] and any('missing' in e for e in out['errors'])
