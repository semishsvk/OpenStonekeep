"""Bounded LE code/data discovery with internal OFF32 relocation evidence.
Does not execute the game or establish semantics merely from decoded instructions.
"""
from pathlib import Path
import argparse,hashlib,json,struct
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from source_manifest import LEImage,EXPECTED_EXE_SHA
from le_fixups import LE
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('va',type=lambda s:int(s,0));p.add_argument('size',type=lambda s:int(s,0));a=p.parse_args()
if not 1<=a.size<=2048:raise ValueError('BYTE_BUDGET')
source=Path(r'F:\Remaster Framework\source\Stonekeep\SK.EXE');b=source.read_bytes();assert hashlib.sha256(b).hexdigest()==EXPECTED_EXE_SHA
le=LE(b);raw=LEImage(b).read_va(a.va,a.size);fixed=bytearray(raw);relocs=[]
for obj in le.objects:
 for lp in range(obj['mapsize']):
  base=obj['base']+lp*le.page_size
  if base>=a.va+a.size or base+le.page_size<=a.va:continue
  for f in le.parse_fixup_page(obj['mapidx']-1+lp):
   for off in f['sources']:
    pos=base+off
    if a.va<=pos and pos+4<=a.va+a.size:
     if f['type']&15!=7 or f['target_kind']!=0 or f['target_offset'] is None:raise ValueError('UNSUPPORTED_FIXUP')
     dest=le.objects[f['target_object']-1]['base']+f['target_offset'];struct.pack_into('<I',fixed,pos-a.va,dest)
     relocs.append({'source':hex(pos),'target':hex(dest)})
rows=[{'va':hex(i.address),'bytes':i.bytes.hex(),'op':i.mnemonic+' '+i.op_str} for i in Cs(CS_ARCH_X86,CS_MODE_32).disasm(bytes(fixed),a.va)]
out=ROOT/f'lecode_{a.va:x}_{a.size:x}.json'
with out.open('x',encoding='utf-8') as f:json.dump({'source_sha256':EXPECTED_EXE_SHA,'raw_sha256':hashlib.sha256(raw).hexdigest(),'raw_hex':raw.hex(),'relocations':relocs,'instructions':rows,'semantics':'NOT_VERIFIED_BY_DISASSEMBLY_ALONE'},f,indent=2)
print('EVIDENCE',out,hashlib.sha256(out.read_bytes()).hexdigest())
for i in rows:print(i['va'],i['op'])
