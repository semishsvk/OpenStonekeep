import importlib.util, struct
from pathlib import Path

TOOL=Path(__file__).resolve().parents[1]/'tools'/'inspect_monster_spatial_clearance.py'
spec=importlib.util.spec_from_file_location('tool',TOOL)
tool=importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

def make_save(path,src_cat=None,dst_cat=None):
    data=bytearray(
        struct.pack('<H',2)+b'1.05\0'+struct.pack('<HH',1,2)
    )
    data+=bytes(2*0x15)

    records=[bytearray(0x0c) for _ in range(400)]
    for rec in records:
        struct.pack_into('<h',rec,0x0a,-1)

    heads=[-1]*(54*54)
    next_index=0
    for col,category in ((0,src_cat),(1,dst_cat)):
        if category is None:
            continue
        rec=records[next_index]
        struct.pack_into('<h',rec,0x00,7)
        struct.pack_into('<h',rec,0x02,col)
        struct.pack_into('<h',rec,0x04,0)
        struct.pack_into('<h',rec,0x06,category)
        heads[col]=next_index
        next_index+=1

    for rec in records:
        data+=rec
    data+=struct.pack('<h',next_index if next_index<400 else -1)
    data+=struct.pack('<'+'h'*len(heads),*heads)
    path.write_bytes(data)

def test_layout_and_coordinates(tmp_path):
    p=tmp_path/'LEVEL.SAV'
    make_save(p,src_cat=0x27)
    out=tool.inspect(p)
    v=out['chain_validation']
    assert out['serialized_layout']['record_count']==400
    assert out['serialized_layout']['head_rows']==54
    assert v['invalid_links']==[]
    assert v['cycles']==[]
    assert v['record_coordinate_mismatches']==[]

def test_forward_current_category_blocks(tmp_path):
    p=tmp_path/'LEVEL.SAV'
    make_save(p,src_cat=0x27)
    out=tool.inspect(p)
    assert out['serialized_spatial_clearance']['forward_blocked']==1

def test_forward_destination_category_blocks(tmp_path):
    p=tmp_path/'LEVEL.SAV'
    make_save(p,dst_cat=0x43)
    out=tool.inspect(p)
    assert out['serialized_spatial_clearance']['forward_blocked']==1

def test_backward_destination_family_blocks(tmp_path):
    p=tmp_path/'LEVEL.SAV'
    make_save(p,dst_cat=0x37)
    out=tool.inspect(p)
    assert out['serialized_spatial_clearance']['backward_blocked']==1
