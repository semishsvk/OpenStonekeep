"""Small anchored callback-continuation inspection, with actual internal fixups."""
from pathlib import Path
import hashlib,json,struct
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from source_manifest import LEImage,EXPECTED_EXE_SHA
from le_fixups import LE
ROOT=Path(__file__).resolve().parent
b=Path(r'F:\Remaster Framework\source\Stonekeep\SK.EXE').read_bytes();assert hashlib.sha256(b).hexdigest()==EXPECTED_EXE_SHA
rawle=LEImage(b);le=LE(b);md=Cs(CS_ARCH_X86,CS_MODE_32);out=[]
for start,size in [(0x6a230,0xa5),(0x41b44,0x78),(0x3d4f5,0x38),(0x4f983,0x51)]:
 raw=rawle.read_va(start,size);fixed=bytearray(raw);fixups=[]
 for obj in le.objects:
  for lp in range(obj['mapsize']):
   pb=obj['base']+lp*le.page_size
   if pb>=start+size or pb+le.page_size<=start:continue
   for f in le.parse_fixup_page(obj['mapidx']-1+lp):
    for so in f['sources']:
     a=pb+so
     if start<=a and a+4<=start+size:
      if f['type']&15!=7 or f['target_kind']!=0 or f['target_offset'] is None:raise ValueError('UNSUPPORTED_FIXUP')
      dest=le.objects[f['target_object']-1]['base']+f['target_offset'];struct.pack_into('<I',fixed,a-start,dest)
      fixups.append({'source':hex(a),'target':hex(dest)})
 ins=[{'va':hex(i.address),'bytes':i.bytes.hex(),'op':i.mnemonic+' '+i.op_str} for i in md.disasm(bytes(fixed),start)]
 out.append({'va':hex(start),'raw_sha256':hashlib.sha256(raw).hexdigest(),'relocated_sha256':hashlib.sha256(fixed).hexdigest(),'fixups':fixups,'instructions':ins})
with (ROOT/'continuation-code.json').open('x',encoding='utf-8') as f:json.dump({'exe_sha256':EXPECTED_EXE_SHA,'regions':out},f,indent=2)
for r in out:
 print('REGION',r['va']);print('\n'.join(i['va']+' '+i['op'] for i in r['instructions'][:34]))
