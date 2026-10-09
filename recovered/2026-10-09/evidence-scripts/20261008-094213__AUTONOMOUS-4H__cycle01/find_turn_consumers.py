"""Narrow LE relocation-based discovery for the proven turn-intent field.
Instruction contexts remain candidates until an entry/control-flow anchor is verified.
"""
import json,struct
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86_const import X86_OP_MEM
from verify_turn_intent import LE_RAW,LF,EXPECTED_EXE_SHA,ROOT
md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;refs=[]
obj=LF.objects[0]
for page in range(obj['mapsize']):
 for f in LF.parse_fixup_page(obj['mapidx']-1+page):
  if f['target_kind']!=0 or f['target_object']!=3 or f['target_offset']!=0x1bc3f6 or f['type']&15!=7:continue
  for src in f['sources']:
   va=obj['base']+page*LF.page_size+src
   for back in range(1,5):
    raw=bytearray(LE_RAW.read_va(va-back,48));struct.pack_into('<I',raw,back,0x2ac3f6)
    first=next(md.disasm(bytes(raw),va-back),None)
    if first is None or not first.address<=va or va+4>first.address+first.size:continue
    if not any(o.type==X86_OP_MEM and o.mem.disp==0x2ac3f6 for o in first.operands):continue
    rows=[{'va':hex(i.address),'bytes':i.bytes.hex(),'op':i.mnemonic+' '+i.op_str} for i in md.disasm(bytes(raw),va-back)]
    refs.append({'relocation_source':hex(va),'instruction':hex(first.address),'context':rows,'following_operands':'Other relocations not applied; discovery only.'});break
p=ROOT/'turn-intent-consumer-candidates.json'
with p.open('x',encoding='utf-8') as f:json.dump({'source_exe_sha256':EXPECTED_EXE_SHA,'field':'object3+0x1bc3f6','references':refs,'scope':'NARROW_STATIC_DISCOVERY'},f,indent=2)
print('REFERENCES',len(refs))
for r in refs:
 if 0x3c360<=int(r['instruction'],16)<=0x3c4bd or 0x82899<=int(r['instruction'],16)<=0x829d0:continue
 print('CONSUMER',r['instruction']);print('\n'.join(i['va']+' '+i['op'] for i in r['context'][:9]))
