"""Resolve original LE operand relocations for the chosen callback and helpers."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent;BASE=Path(r'F:\Remaster Framework\work\OpenStonekeep-E16\tools')
with (ROOT/'le_fixups.py').open('xb') as f:f.write((BASE/'resolve_le_handler_dispatch.py').read_bytes())
from le_fixups import LE
from source_manifest import LEImage,EXPECTED_EXE_SHA
b=Path(r'F:\Remaster Framework\source\Stonekeep\SK.EXE').read_bytes();assert hashlib.sha256(b).hexdigest()==EXPECTED_EXE_SHA
le=LE(b);ranges=[(0x4fc57,0x4fca9),(0x3c0c9,0x3c2f4)]
rows=[]
for oi,obj in enumerate(le.objects):
 for lp in range(obj['mapsize']):
  base=obj['base']+lp*le.page_size
  if not any(a<base+le.page_size and base<b for a,b in ranges):continue
  for r in le.parse_fixup_page(obj['mapidx']-1+lp):
   for src in r['sources']:
    p=base+src
    if not any(a<=p<b for a,b in ranges):continue
    target=le.objects[r['target_object']-1]['base']+r['target_offset'] if r['target_kind']==0 and r['target_offset'] is not None else None
    rows.append({'source':hex(p),'type':r['type'],'flags':r['flags'],'target':hex(target) if target is not None else None,'target_object':r['target_object'],'target_offset':r['target_offset']})
report={'objects':le.objects,'relocations':rows,'source_module_sha256':hashlib.sha256((BASE/'resolve_le_handler_dispatch.py').read_bytes()).hexdigest()}
with (ROOT/'relocation-observation.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
print(json.dumps(report,indent=2))
