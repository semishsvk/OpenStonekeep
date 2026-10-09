import importlib.util, struct
from pathlib import Path

TOOL=Path(__file__).resolve().parents[1]/'tools'/'inspect_msp_clearance.py'
spec=importlib.util.spec_from_file_location('tool',TOOL)
tool=importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

def make_save(path,src_mask=0,dst_mask=0):
    data=bytearray(
        struct.pack('<H',2)+b'1.05\0'+struct.pack('<HH',1,2)
    )
    a=bytearray(0x15)
    b=bytearray(0x15)
    struct.pack_into('<h',a,0x11,0)
    struct.pack_into('<h',b,0x11,1)
    data+=a+b
    data+=bytes(tool.SPATIAL_RECORD_BYTES)
    data+=b'\0\0'
    data+=bytes(tool.SPATIAL_HEAD_BYTES)
    data+=struct.pack('<h',2)
    for mask in (src_mask,dst_mask):
        rec=bytearray(0x30)
        struct.pack_into('<h',rec,0x02,1)
        struct.pack_into('<h',rec,0x10,-100)
        rec[0x18]=mask
        data+=rec
    path.write_bytes(data)

def test_layout_and_chain(tmp_path):
    p=tmp_path/'LEVEL.SAV'
    make_save(p)
    out=tool.inspect(p)
    assert out['serialized_layout']['msp_count']==2
    assert out['serialized_layout']['msp_count_offset']==(
        11+2*0x15+0x12c0+2+0x16c8
    )
    assert out['chain_validation']['invalid_links']==[]
    assert out['chain_validation']['cycles']==[]

def test_directional_mask_blocks_same_interface_both_directions(tmp_path):
    p=tmp_path/'LEVEL.SAV'
    make_save(p,src_mask=0x01,dst_mask=0)
    out=tool.inspect(p)
    assert out['serialized_msp_clearance']['forward_blocked']==2

def test_destination_opposite_mask_blocks_forward(tmp_path):
    p=tmp_path/'LEVEL.SAV'
    make_save(p,src_mask=0,dst_mask=0x02)
    out=tool.inspect(p)
    assert out['serialized_msp_clearance']['forward_blocked']==2

def test_mask_0x10_is_forward_source_gate(tmp_path):
    p=tmp_path/'LEVEL.SAV'
    make_save(p,src_mask=0x10,dst_mask=0)
    out=tool.inspect(p)
    assert out['serialized_msp_clearance']['forward_blocked']==1
