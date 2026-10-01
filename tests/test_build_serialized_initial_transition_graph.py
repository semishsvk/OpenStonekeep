import importlib.util, struct
from pathlib import Path
TOOL=Path(__file__).resolve().parents[1]/'tools'/'build_serialized_initial_transition_graph.py'
spec=importlib.util.spec_from_file_location('tool',TOOL); tool=importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)

def make_save(path, msp0=0, msp1=0, cat0=None, cat1=None, handler0=0):
    data=bytearray(struct.pack('<H',2)+b'1.05\0'+struct.pack('<HH',1,2))
    cells=[]
    for idx,h in enumerate((handler0,0)):
        c=bytearray(tool.CELL_SIZE)
        struct.pack_into('<h',c,0x07,h)
        struct.pack_into('<h',c,0x11,idx)
        cells.append(c); data+=c
    records=[bytearray(tool.SPATIAL_RECORD_SIZE) for _ in range(tool.SPATIAL_RECORD_COUNT)]
    for r in records: struct.pack_into('<h',r,0x0A,-1)
    heads=[-1]*tool.SPATIAL_HEAD_COUNT
    ri=0
    for col,cat in ((0,cat0),(1,cat1)):
        if cat is None: continue
        r=records[ri]
        struct.pack_into('<h',r,0x02,col); struct.pack_into('<h',r,0x04,0)
        struct.pack_into('<h',r,0x06,cat); heads[col]=ri; ri+=1
    for r in records: data+=r
    data+=struct.pack('<h',ri)
    data+=struct.pack('<'+'h'*len(heads),*heads)
    data+=struct.pack('<h',2)
    for mask in (msp0,msp1):
        r=bytearray(tool.MSP_RECORD_SIZE)
        struct.pack_into('<h',r,0x02,1); struct.pack_into('<h',r,0x10,-100); r[0x18]=mask
        data+=r
    path.write_bytes(data)

def test_all_clear_two_oriented_edges(tmp_path):
    p=tmp_path/'L.SAV'; make_save(p)
    out=tool.build(p)
    assert out['validation']['pass']
    assert out['static_clear_oriented_edge_count']==2
    assert out['movement_attempt_count']==4
    assert out['transition_counts']['forward']=={'TRANSLATION_EXECUTES':2}
    assert out['transition_counts']['backward']=={'TRANSLATION_EXECUTES':2}
    assert out['mode_asymmetric_oriented_edge_count']==0
    assert out['physical_affected_undirected_interface_count']==0

def test_combined_msp_and_spatial_reason(tmp_path):
    p=tmp_path/'L.SAV'; make_save(p,msp0=0x01,cat0=0x27)
    out=tool.build(p,True)
    east_forward=[a for a in out['attempts'] if a['direction']=='E' and a['mode']=='forward'][0]
    assert east_forward['msp_blocked'] and east_forward['spatial_blocked']
    assert east_forward['outcome']=='BLOCKED_MSP_AND_SPATIAL'
    assert not east_forward['callback_invoked']
    assert out['physical_affected_undirected_interface_count']==1

def test_nondefault_allow_and_side_effect_uncertainty(tmp_path):
    p=tmp_path/'L.SAV'; make_save(p,handler0=110)
    out=tool.build(p,True)
    east_forward=[a for a in out['attempts'] if a['direction']=='E' and a['mode']=='forward'][0]
    assert east_forward['callback_return_gate']=='ALLOW_VERIFIED'
    assert east_forward['outcome']=='TRANSLATION_EXECUTES'
    assert east_forward['callback_invoked']
    assert east_forward['callback_side_effect_semantics']=='OBSERVED_MUTATION_POSSIBLE'
    assert east_forward['action_complete_state_semantics']=='POST_CALLBACK_STATE_DELTA_PARTIAL'

def test_unknown_nondefault_handler_fails_validation(tmp_path):
    p=tmp_path/'L.SAV'; make_save(p,handler0=999)
    out=tool.build(p)
    assert not out['validation']['pass']
    assert out['callback_evidence_missing_handlers']==[999]
