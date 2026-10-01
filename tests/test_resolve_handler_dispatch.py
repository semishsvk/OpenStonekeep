import importlib.util, struct, sys
from pathlib import Path

TOOL=Path(__file__).resolve().parents[1]/'tools'/'resolve_handler_dispatch.py'
spec=importlib.util.spec_from_file_location('tool',TOOL)
tool=importlib.util.module_from_spec(spec)
sys.modules['tool']=tool
spec.loader.exec_module(tool)

def make_save(path, h=2):
    data=bytearray(struct.pack('<H',2)+b'1.05\0'+struct.pack('<HH',1,1))
    cell=bytearray(0x15)
    struct.pack_into('<h',cell,7,h)
    data+=cell
    path.write_bytes(data)

def make_le(path):
    # Minimal LE with three objects and enough page/fixup data for
    # object3+0xF16A, handler 2 slot -> internal object1+0x120.
    le=0x80
    page_size=0x1000
    pages=18
    objtab=0xC4
    objmap=objtab+3*24
    fixpage=objmap+pages*4
    fixrec=fixpage+(pages+1)*4
    rec=bytes.fromhex('071072010120010000')
    fixmap=[0]*(pages+1)
    target_page=17
    for i in range(target_page+1,pages+1):
        fixmap[i]=len(rec)
    page_data=le+fixrec+len(rec)+0x20
    total=page_data+pages*page_size
    b=bytearray(total)
    b[:2]=b'MZ'
    struct.pack_into('<I',b,0x3c,le)
    b[le:le+2]=b'LE'
    struct.pack_into('<I',b,le+20,pages)
    struct.pack_into('<I',b,le+40,page_size)
    struct.pack_into('<I',b,le+64,objtab)
    struct.pack_into('<I',b,le+68,3)
    struct.pack_into('<I',b,le+72,objmap)
    struct.pack_into('<I',b,le+104,fixpage)
    struct.pack_into('<I',b,le+108,fixrec)
    struct.pack_into('<I',b,le+128,page_data)
    struct.pack_into('<6I',b,le+objtab,0x1000,0x10000,0x2045,1,1,0)
    struct.pack_into('<6I',b,le+objtab+24,0x1000,0xE0000,0x2043,2,1,0)
    struct.pack_into('<6I',b,le+objtab+48,0x10000,0xF0000,0x2043,3,16,0)
    for i in range(pages):
        b[le+objmap+i*4:le+objmap+i*4+4]=bytes([0,0,i+1,0])
    for i,v in enumerate(fixmap):
        struct.pack_into('<I',b,le+fixpage+i*4,v)
    b[le+fixrec:le+fixrec+len(rec)]=rec
    # obj3 offset 0xF172 is zero-based global LE page 17 / physical page 18.
    slot_file=page_data+(18-1)*page_size+0x172
    struct.pack_into('<I',b,slot_file,0x120)
    path.write_bytes(b)

def test_resolves_internal_off32(tmp_path):
    exe=tmp_path/'x.exe'
    sav=tmp_path/'l.sav'
    make_le(exe)
    make_save(sav)
    out=tool.build(exe,[sav])
    e=out['entries']['2']
    assert out['dispatch_resolution']=='PASS'
    assert out['resolved_handler_count']==1
    assert e['target_object']==1
    assert e['target_object_offset']=='0x120'
    assert e['resolved_runtime_target']=='0x10120'
