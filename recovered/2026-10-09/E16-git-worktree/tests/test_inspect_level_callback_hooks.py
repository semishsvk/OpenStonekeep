import importlib.util
from pathlib import Path

TOOL=Path(__file__).resolve().parents[1]/'tools'/'inspect_level_callback_hooks.py'
spec=importlib.util.spec_from_file_location('tool',TOOL)
tool=importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

def test_decode_names_uses_nine_byte_slots():
    b=bytearray(tool.NAME_OFFSET+tool.NAME_WIDTH*tool.LEVEL_COUNT)
    names=[f'l{i:02d}'.encode() for i in range(tool.LEVEL_COUNT)]
    for i,n in enumerate(names):
        b[tool.NAME_OFFSET+i*tool.NAME_WIDTH:tool.NAME_OFFSET+i*tool.NAME_WIDTH+len(n)]=n
    assert tool.decode_names(bytes(b))[1]=='l01'
    assert tool.decode_names(bytes(b))[15]=='l15'

def test_callback_store_scan_is_bounded():
    b=bytearray(0x200); start=0x80
    b[start+0x10:start+0x10+len(tool.CALLBACK_STORE_PATTERN)]=tool.CALLBACK_STORE_PATTERN
    assert tool.find_callback_store(bytes(b),start)==start+0x10
    assert tool.find_callback_store(bytes(b),0,window=0x20)==-1

def test_starter_contract_constants():
    assert tool.STARTER_LEVELS==('level01','level01a')
    assert tool.INIT_OFFSET==0xF10E
    assert tool.NAME_OFFSET==0x5D44
