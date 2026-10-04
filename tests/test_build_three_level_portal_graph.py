import importlib.util
from pathlib import Path

TOOL=Path(__file__).resolve().parents[1]/"tools"/"build_three_level_portal_graph.py"
spec=importlib.util.spec_from_file_location("tool",TOOL)
tool=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(tool)

def edge(h,sl,src,d,tl,tgt,reach="DIRECT_ENABLE_INITIAL_STATE"):
    return {
        "source_level":sl,"handler_id":h,"source":list(src),"direction":d,
        "target_level":tl,"target_spawn":list(tgt),
        "outgoing_reachability":reach,
        "physical_clear_after_open":True,"transition_commit":True,
    }

def test_immediate_reciprocal_geometry():
    a=edge(106,1,(11,5),"N",2,(7,2,0),"INPUT_REACHABLE_CONDITIONAL")
    b=edge(144,2,(6,2),"S",1,(10,5,2))
    assert tool.immediate_reciprocal(a,b)
    assert tool.immediate_reciprocal(b,a)

def test_nonmatching_interface_is_not_reciprocal():
    a=edge(89,1,(23,3),"N",15,(22,3,2))
    b=edge(413,15,(23,25),"N",1,(22,25,2))
    assert not tool.immediate_reciprocal(a,b)

def test_expected_pair_geometry_all_five():
    pairs=[
        (edge(87,1,(2,3),"S",15,(3,3,0)),edge(411,15,(2,3),"S",1,(3,3,0))),
        (edge(88,1,(2,25),"S",15,(3,25,0)),edge(412,15,(2,25),"S",1,(3,25,0))),
        (edge(90,1,(23,25),"N",15,(22,25,2)),edge(413,15,(23,25),"N",1,(22,25,2))),
        (edge(106,1,(11,5),"N",2,(7,2,0)),edge(144,2,(6,2),"S",1,(10,5,2))),
        (edge(107,1,(7,25),"W",2,(2,18,1)),edge(145,2,(2,17),"E",1,(7,24,3))),
    ]
    for a,b in pairs:
        assert tool.immediate_reciprocal(a,b)

def test_h89_expected_missing_same_interface_partner():
    a=edge(89,1,(23,3),"N",15,(22,3,2))
    candidates=[
        edge(411,15,(2,3),"S",1,(3,3,0)),
        edge(412,15,(2,25),"S",1,(3,25,0)),
        edge(413,15,(23,25),"N",1,(22,25,2)),
    ]
    assert not any(tool.immediate_reciprocal(a,b) for b in candidates)
