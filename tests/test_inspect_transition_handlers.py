import importlib.util, struct
from pathlib import Path

TOOL=Path(__file__).resolve().parents[1]/'tools'/'inspect_transition_handlers.py'
spec=importlib.util.spec_from_file_location('tool',TOOL)
tool=importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)

def mkcell(h=0,mask=0):
    c=bytearray(tool.CELL_SIZE); c[2]=mask; struct.pack_into('<h',c,7,h); return c

def test_manifest_is_nine_and_unique():
    assert len(tool.TRANSITIONS)==9
    assert len({(x[0],x[1]) for x in tool.TRANSITIONS})==9

def test_transition_edges_are_direction_typed():
    assert {x[4] for x in tool.TRANSITIONS}<={0,1,2,3}
    assert {x[5] for x in tool.TRANSITIONS}=={1,2,15}

def test_reciprocal_closed_south():
    cells=[mkcell() for _ in range(4)]
    cells[0]=mkcell(87,0x04); cells[2]=mkcell(0,0x08)
    t=(1,87,0,0,2,15,3,3,0,0x5F3B9)
    out=tool.check_transition_cell(cells,2,2,t)
    assert out['source_edge_closed'] and out['reciprocal_edge_closed']

def test_hashes_are_full_sha256():
    assert all(len(h)==64 for _,_,h in tool.REGIONS.values())
