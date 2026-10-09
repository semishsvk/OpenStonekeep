import importlib.util
from pathlib import Path
import struct

TOOL = Path(__file__).resolve().parents[1] / "tools" / "inspect_selection_reachability.py"
spec = importlib.util.spec_from_file_location("tool", TOOL)
tool = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(tool)

def test_global_list_walk():
    b=bytearray(tool.POJ_OFFSET+tool.POJ_COUNT*tool.POJ_STRIDE+16)
    for idx,nxt in ((3,7),(7,-4)):
        struct.pack_into("<h",b,tool.POJ_OFFSET+idx*tool.POJ_STRIDE+0x18,nxt)
    chain,end=tool.walk_global_list(bytes(b),3,2)
    assert chain==[3,7]
    assert end==-4

def test_global_list_count_mismatch_fails():
    b=bytearray(tool.POJ_OFFSET+tool.POJ_COUNT*tool.POJ_STRIDE+16)
    struct.pack_into("<h",b,tool.POJ_OFFSET+3*tool.POJ_STRIDE+0x18,-4)
    try:
        tool.walk_global_list(bytes(b),3,2)
    except ValueError as e:
        assert "count mismatch" in str(e)
    else:
        raise AssertionError("expected count mismatch")

def test_poj_record_bounds():
    b=bytes(tool.POJ_OFFSET+tool.POJ_COUNT*tool.POJ_STRIDE)
    assert len(tool.poj_record(b,0))==tool.POJ_STRIDE
    assert len(tool.poj_record(b,tool.POJ_COUNT-1))==tool.POJ_STRIDE
    try:
        tool.poj_record(b,tool.POJ_COUNT)
    except ValueError:
        pass
    else:
        raise AssertionError("expected out-of-range POJ index")

def test_level_cell_parser():
    rows,cols=2,3
    b=bytearray(11+rows*cols*tool.CELL_SIZE)
    struct.pack_into("<HH",b,7,rows,cols)
    r,c,cells=tool.parse_level_cells(bytes(b))
    assert (r,c,len(cells))==(2,3,6)
