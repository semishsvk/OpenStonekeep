import importlib.util, sys
from pathlib import Path

TOOL=Path(__file__).resolve().parents[1]/'tools'/'validate_destination_action1_manifest.py'
sys.path.insert(0,str(TOOL.parent))
spec=importlib.util.spec_from_file_location('tool',TOOL)
tool=importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

def test_exact_destination_scope():
    assert len(tool.DESTINATION_HANDLER_IDS)==56
    assert {75,80,108}.isdisjoint(tool.DESTINATION_HANDLER_IDS)

def test_families_are_disjoint_and_complete():
    groups=[set(v) for v in tool.FAMILIES.values()]
    assert all(not (groups[i]&groups[j]) for i in range(len(groups)) for j in range(i+1,len(groups)))
    assert set().union(*groups)==tool.DESTINATION_HANDLER_IDS

def test_direct_write_set():
    assert set(tool.DIRECT_WRITES)=={86,91,96,105,112,115,410,415}
    assert len(tool.DIRECT_WRITES)==8

def test_h86_is_current_destination_not_fixed_7_8():
    w=tool.DIRECT_WRITES[86]['writes'][0]
    assert w['cell']=='current_destination'
    assert w['selector']==4 and w['from']==0 and w['to']==1

def test_h105_preserves_col18_into_shared_setter_tail():
    w=tool.DIRECT_WRITES[105]['writes'][0]
    assert (w['row'],w['col'],w['selector'],w['to'])==(7,18,4,1)

def test_action1_anchor_inventory():
    assert len(tool.REGIONS)==18
    assert len({(va,n) for va,n,_ in tool.REGIONS.values()})==18
