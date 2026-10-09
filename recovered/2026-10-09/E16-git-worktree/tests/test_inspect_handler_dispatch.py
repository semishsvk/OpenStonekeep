import importlib.util, struct
from pathlib import Path
TOOL=Path(__file__).resolve().parents[1]/'tools'/'inspect_handler_dispatch.py'
spec=importlib.util.spec_from_file_location('tool',TOOL); tool=importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)

def make_save(path):
    data=bytearray(struct.pack('<H',2)+b'1.05\\0'+struct.pack('<HH',1,2))
    for h in (0,13):
        cell=bytearray(0x15); struct.pack_into('<h',cell,7,h); data+=cell
    path.write_bytes(data)

def test_inventory(tmp_path):
    save=tmp_path/'LEVEL.SAV'; make_save(save)
    dis=tmp_path/'d.txt'; dis.write_text('    f16a: 11 22 33 44\\n    f19e: aa bb cc dd\\n')
    assert tool.handler_ids(save)==(1,2,[13])
    out=tool.build([save],dis)
    assert out['entries']['13']['raw_entry']=='aabbccdd'
    assert out['dispatch_resolution']=='RELOCATION_REQUIRED'

def test_missing_bytes(tmp_path):
    save=tmp_path/'LEVEL.SAV'; make_save(save); dis=tmp_path/'d.txt'; dis.write_text('')
    assert tool.build([save],dis)['entries']['13']['raw_entry'] is None