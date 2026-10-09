"""Original H415 direct-delta prefix + real getter/setter, with actual LE fixups.
Stops before opaque event/default continuation. It proves a state dependency,
NOT the full callback return value, world event, navigation success or softlock freedom.
"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,struct,itertools
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.x86_const import *
from source_manifest import LEImage,EXPECTED_EXE_SHA
from le_fixups import LE
ROOT=Path(__file__).resolve().parent
EXE=Path(r'F:\Remaster Framework\source\Stonekeep\SK.EXE')
B=EXE.read_bytes();assert hashlib.sha256(B).hexdigest()==EXPECTED_EXE_SHA
LE_RAW=LEImage(B);LE_FIX=LE(B)
RANGES=[(0x3c0c9,0x3c2f4),(0x4fc57,0x4fc9b)]
GRID,STACK=0x40000000,0x50008000
CELL=GRID+(23*32+2)*21
GLOBAL=0x260d9a

def w32(u,p,v):u.mem_write(p,struct.pack('<I',v))
def machine():
 u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x10000,0x300000);u.mem_map(GRID,0x10000);u.mem_map(0x50000000,0x10000)
 for a,b in RANGES:u.mem_write(a,LE_RAW.read_va(a,b-a))
 reloc={}
 for obj in LE_FIX.objects:
  for lp in range(obj['mapsize']):
   base=obj['base']+lp*LE_FIX.page_size
   if not any(a<base+LE_FIX.page_size and base<b for a,b in RANGES):continue
   for f in LE_FIX.parse_fixup_page(obj['mapidx']-1+lp):
    for so in f['sources']:
     p=base+so
     if not any(a<=p and p+4<=b for a,b in RANGES):continue
     if f['type']&15!=7 or f['target_kind']!=0 or f['target_offset'] is None:raise ValueError('UNSUPPORTED_EXECUTED_FIXUP')
     dest=LE_FIX.objects[f['target_object']-1]['base']+f['target_offset']
     if p in reloc and reloc[p]!=dest:raise ValueError('AMBIGUOUS_FIXUP')
     reloc[p]=dest;w32(u,p,dest)
 if reloc.get(0x4fc5a)!=GLOBAL or reloc.get(0x4fc92)!=0xf1b25:raise ValueError('GLOBAL_OR_EVENT_FIXUP')
 w32(u,0xfcd0d,GRID)
 u.mem_write(0x2a9df8,struct.pack('<32h',*[32*i for i in range(32)]))
 return u,reloc

def run(global_flag,state,action):
 u,reloc=machine();u.reg_write(UC_X86_REG_ESP,STACK);u.reg_write(UC_X86_REG_ESI,action)
 initial=bytearray((i*17+5)&255 for i in range(32*32*21));struct.pack_into('<H',initial,(23*32+2)*21+11,state)
 u.mem_write(GRID,bytes(initial));u.mem_write(GLOBAL,struct.pack('<H',global_flag))
 writes=[];calls=[];out={'boundary':None,'instructions':0}
 def code(uc,a,n,_):
  out['instructions']+=1
  if a==0x41b44:
   if uc.reg_read(UC_X86_REG_EAX)!=0xf1b25:raise ValueError('EVENT_POINTER_MISMATCH')
   out['boundary']='EVENT_CALL_REQUIRES_SEPARATE_VALIDATION';uc.emu_stop();return
  if a==0x4fc9b:out['boundary']='DEFAULT_CONTINUATION_NOT_EXECUTED';uc.emu_stop();return
  if a in (0x3c14d,0x3c231):
   args=tuple(uc.reg_read(r) for r in [UC_X86_REG_EAX,UC_X86_REG_EDX,UC_X86_REG_EBX])
   if args!=(5,23,2):raise ValueError('CELL_SELECTOR_ARGUMENTS')
   if a==0x3c231 and uc.reg_read(UC_X86_REG_ECX)!=2:raise ValueError('SETTER_VALUE')
   calls.append('get5' if a==0x3c14d else 'set5')
  if not any(x<=a and a+n<=y for x,y in [(0x4fc57,0x4fc9b),(0x3c14d,0x3c1f7),(0x3c231,0x3c2f4)]):raise ValueError('CODE_ESCAPE:'+hex(a))
 def write(uc,access,a,n,v,_):
  if STACK-128<=a and a+n<=STACK:return
  if a==CELL+11 and n==2:writes.append({'address':a,'bytes':n,'value':v&65535});return
  raise ValueError('STATE_WRITE_ESCAPE:'+hex(a))
 u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
 u.emu_start(0x4fc57,0x60000000,timeout=150000,count=1000)
 if out['boundary'] is None:raise ValueError('NO_BOUNDARY')
 expected=bytearray(initial);should_change=global_flag!=0 and state==1
 if should_change:struct.pack_into('<H',expected,(23*32+2)*21+11,2)
 if bytes(u.mem_read(GRID,len(initial)))!=bytes(expected):raise ValueError('STATE_BUFFER_DIFFERENCE')
 if writes!=([{'address':CELL+11,'bytes':2,'value':2}] if should_change else []):raise ValueError('WRITE_TRACE_DIFFERENCE')
 wantcalls=[] if global_flag==0 else ['get5']+(['set5'] if state==1 else [])
 if calls!=wantcalls:raise ValueError('CALL_TRACE_DIFFERENCE')
 if out['boundary']!=('EVENT_CALL_REQUIRES_SEPARATE_VALIDATION' if should_change else 'DEFAULT_CONTINUATION_NOT_EXECUTED'):raise ValueError('BOUNDARY_DIFFERENCE')
 return {'global_flag':global_flag,'selector5_before':state,'action_context':action,'selector5_after':2 if should_change else state,'writes':writes,'helper_trace':calls,**out,'pass':True}

def main():
 tests=[run(g,s,a) for g,s,a in itertools.product((0,1,65535),(0,1,2,65535),(2,3,4,5,6,8))]
 save=Path(r'F:\Remaster Framework\source\Stonekeep\CD\DATA\START\SAVEGAME\GAME00\LEVEL01A.SAV');raw=save.read_bytes()
 savehash=hashlib.sha256(raw).hexdigest();assert savehash=='3d1753ca8a4ca49b3ccf9da0fc15bb08ac242301eff40586049379ceba635dc9'
 rows,cols=struct.unpack_from('<HH',raw,7);pos=11+(23*cols+2)*21
 value=struct.unpack_from('<H',raw,pos+11)[0]
 concrete=[run(g,value,a) for g in (0,1) for a in (6,8)]
 _,reloc=machine()
 result={'schema':'OpenStonekeep.H415DirectDelta.v1','status':'PASS','tests':len(tests)+len(concrete),'cases':tests+concrete,
 'source_exe_sha256':EXPECTED_EXE_SHA,'source_save_sha256':savehash,
 'source_cell':{'row':23,'column':2,'selector':5,'byte_offset':11,'serialized_value':value},
 'rule':'When the relocated 16-bit global is nonzero and selector5 at cell(23,2) equals 1, write exactly 2 to that word before requesting the event/string helper.',
 'address_domains':{'global_object3_offset':'0x170d9a','global_linear':'0x260d9a','grid_pointer_linear':'0xfcd0d','row_offsets_linear':'0x2a9df8','event_object3_offset':'0x1b25','event_linear':'0xf1b25'},
 'relocation_count':len(reloc),'relocations_sha256':hashlib.sha256(json.dumps(reloc,sort_keys=True).encode()).hexdigest(),
 'state_dependency':{'turn_actions':[6,8],'movement_actions':[2,3,4,5],'after_prefix':{'condition_true':'selector5=2, event pending','condition_false':'selector5 unchanged, default continuation pending'}},
 'navigation_gate':'BLOCKED_UNTIL_EVENT_AND_DEFAULT_CONTINUATION_EFFECTS_ACCOUNTED_FOR',
 'claim_limit':'The common prefix is independently validated with real source getter/setter and LE relocations. Neither opaque helper is stubbed as success; execution stops at its boundary.',
 'global_softlock_verdict':False,'game_runtime_executed':False,'created_at_utc':datetime.now(timezone.utc).isoformat()}
 with (ROOT/'callback-verification.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,sort_keys=True)
 print(json.dumps({'status':'PASS','tests':result['tests'],'serialized_selector5':value,'new_dependency':'conditional one-word delta plus explicit pending-event barrier','navigation_gate':result['navigation_gate'],'sha256':hashlib.sha256((ROOT/'callback-verification.json').read_bytes()).hexdigest()}))
if __name__=='__main__':main()
