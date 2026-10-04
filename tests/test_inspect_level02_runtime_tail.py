import importlib.util
import struct
from pathlib import Path

TOOL=Path(__file__).resolve().parents[1]/"tools"/"inspect_level02_runtime_tail.py"
spec=importlib.util.spec_from_file_location("tool",TOOL)
tool=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(tool)

def synthetic_maz():
    rows,cols=2,2
    out=bytearray(b"ON"+struct.pack("<HH",rows,cols)+bytes(8))
    # block1: one 18-byte record
    out+=struct.pack("<H",1)+bytes(18)
    # block2: type3 with qualifying +8 bytes, then one plain record
    out+=struct.pack("<H",2)
    out+=struct.pack("<5h",3,0,0,0,-99)+bytes(8)
    out+=struct.pack("<5h",4,0,0,0,0)
    # block3: one MSP at (1,1), one attached 16-byte POJ,
    # one nested monster with one 14-byte attached POJ
    out+=struct.pack("<H",1)
    base=[13,1,1,0,0,100,0,1,0,0,0,0,1]
    out+=struct.pack("<13h",*base)+bytes(16)
    out+=struct.pack("<H",1)
    out+=struct.pack("<8h",8,0,0,0,0,0,-37,1)+bytes(14)
    # block4: one monster with two 14-byte POJs; count is word +0x10
    out+=struct.pack("<H",1)
    out+=struct.pack("<9h",8,0,1,0,0,0,0,-1,2)+bytes(28)
    return bytes(out)

def test_variable_tail_consumes_exact_eof():
    b=synthetic_maz()
    p=tool.parse_maz(b)
    assert p["end_offset"]==len(b)
    assert p["block1_count"]==1
    assert p["block2_count"]==2
    assert p["msp_count"]==1
    assert p["standalone_monster_count"]==1
    assert len(p["msp"][0][1])==1
    assert len(p["msp"][0][2])==1
    assert len(p["msp"][0][2][0][1])==1
    assert len(p["monsters"][0][1])==2

def test_block4_count_is_final_word():
    b=synthetic_maz()
    p=tool.parse_maz(b)
    base,_=p["monsters"][0]
    assert struct.unpack("<9h",base)[8]==2

def test_nested_and_standalone_monster_positions():
    p=tool.parse_maz(synthetic_maz())
    nested,standalone=tool.monster_positions(p)
    assert nested==[(1,1,0,0)]
    assert standalone==[(0,1,0)]

def test_msp_signature_ignores_only_coordinates():
    a=struct.pack("<13h",13,7,2,0,0,100,0,1,0,0,0,0,0)
    b=struct.pack("<13h",13,22,25,0,0,100,0,1,0,0,0,0,0)
    c=struct.pack("<13h",13,22,25,1,0,100,0,1,0,0,0,0,0)
    assert tool.msp_signature(a)==tool.msp_signature(b)
    assert tool.msp_signature(a)!=tool.msp_signature(c)
