import importlib.util
from pathlib import Path
TOOL=Path(__file__).resolve().parents[1]/'tools'/'validate_callback_state_delta_manifest.py'
spec=importlib.util.spec_from_file_location('tool',TOOL); tool=importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)

def resolved_actions(h):
    x=tool.HANDLERS[h]
    if 'movement_behavior_alias' in x: return resolved_actions(x['movement_behavior_alias'])
    return set(x['actions'])

def test_six_handlers_cover_all_movement_actions():
    assert set(tool.HANDLERS)=={110,111,112,115,410,415}
    for h in tool.HANDLERS: assert resolved_actions(h)=={2,3,4,5}

def test_selector_map_closes_serialized_cell_fields():
    assert tool.SELECTOR_MAP[4]['offset']==0x09
    assert tool.SELECTOR_MAP[5]['offset']==0x0B
    assert tool.SELECTOR_MAP[8]['offset']==0x11
    assert [tool.SELECTOR_MAP[x]['offset'] for x in (10,11,12,13)]==[1,1,1,1]

def test_mutating_manifest_preserves_negative_evidence_boundary():
    assert tool.HANDLERS[110]['actions'][2]['class']=='NO_DIRECT_WRITE_OBSERVED'
    assert 'NO_DIRECT_WRITE_OBSERVED' in tool.NEGATIVE_EVIDENCE_POLICY
    assert 'ABSENT_VERIFIED' in tool.NEGATIVE_EVIDENCE_POLICY

def test_region_anchors_are_unique():
    spans=[(va,n) for va,n,_ in tool.REGIONS.values()]
    assert len(tool.REGIONS)>=10
    assert len(set(spans))==len(spans)


def resolve_t2(h):
    x=tool.TRANCHE2_HANDLERS[h]
    if 'alias_action_semantics' in x:
        return resolve_t2(x['alias_action_semantics'])
    return x['actions']

def test_tranche2_adds_twenty_handlers_with_all_movement_actions():
    assert len(tool.TRANCHE2_HANDLERS)==20
    assert set(tool.HANDLERS).isdisjoint(tool.TRANCHE2_HANDLERS)
    for h in tool.TRANCHE2_HANDLERS:
        assert set(resolve_t2(h))=={2,3,4,5}

def test_handler91_and_116_have_direct_state_deltas():
    assert tool.TRANCHE2_HANDLERS[91]['actions'][3]['writes'][0]=={'row':5,'col':9,'selector':4,'from':1,'to':2}
    assert tool.TRANCHE2_HANDLERS[116]['actions'][5]['writes'][0]=={'row':8,'col':10,'selector':5,'from':1,'to':2}

def test_all_region_anchors_are_unique():
    spans=[(va,n) for va,n,_ in tool.ALL_REGIONS.values()]
    assert len(tool.ALL_REGIONS)==30
    assert len(set(spans))==len(spans)
