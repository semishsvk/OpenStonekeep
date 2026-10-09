"""Targeted original-cell helper excerpts, no execution or source mutation."""
from pathlib import Path
import hashlib,json
from source_manifest import LEImage,EXPECTED_EXE_SHA
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
ROOT=Path(__file__).resolve().parent
source=Path(r'F:\Remaster Framework\source\Stonekeep\SK.EXE');b=source.read_bytes()
assert hashlib.sha256(b).hexdigest()==EXPECTED_EXE_SHA
le=LEImage(b);md=Cs(CS_ARCH_X86,CS_MODE_32);rows=[]
for start,length in [(0x3c14d,0xa0),(0x3c231,0xc8),(0x4f983,0x72)]:
 raw=le.read_va(start,length)
 ins=[{'va':hex(i.address),'op':i.mnemonic+' '+i.op_str,'bytes':i.bytes.hex()} for i in md.disasm(raw,start)]
 rows.append({'va':hex(start),'raw_sha256':hashlib.sha256(raw).hexdigest(),'instructions':ins})
with (ROOT/'helper-code.json').open('x',encoding='utf-8') as f:json.dump({'source_sha256':EXPECTED_EXE_SHA,'regions':rows},f,indent=2)
for r in rows[:2]:
 print('FUNCTION',r['va']);print('\n'.join(i['va']+' '+i['op'] for i in r['instructions']))
