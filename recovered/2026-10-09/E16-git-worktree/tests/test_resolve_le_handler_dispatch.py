import importlib.util, struct
from pathlib import Path
TOOL=Path(__file__).resolve().parents[1]/'tools'/'resolve_le_handler_dispatch.py'
spec=importlib.util.spec_from_file_location('tool',TOOL); tool=importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)

def make_save(path):
    data=bytearray(struct.pack('<H',2)+b'1.05\0'+struct.pack('<HH',1,2))
    a=bytearray(0x15); struct.pack_into('<h',a,7,13); a[2]=0x0A
    b=bytearray(0x15); b[2]=0x0F
    data += a+b; path.write_bytes(data)

def test_save_scope(tmp_path):
    p=tmp_path/'LEVEL.SAV'; make_save(p)
    out=tool.read_save(p)
    assert out['nondefault_handler_ids']==[13]
    assert out['movement_candidate_source_handler_ids']==[13]

def test_fixup_page_parser_shape():
    rec=bytes.fromhex('0710720101e0a20500')
    le=object.__new__(tool.LE)
    le.data=rec; le.le=0; le.fixrec=0; le.fixmap=[0,len(rec)]
    out=le.parse_fixup_page(0)
    assert out==[{'record_file_offset':0,'type':7,'flags':0x10,'sources':[0x172],
                 'target_kind':0,'target_object':1,'target_offset':0x5A2E0}]
