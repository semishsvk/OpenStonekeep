"""New Stonekeep ordinary-action -> turn-intent contract, with original LE fixups.
The starter level callback is the pinned original RET entry. If downstream work
is not suppressed, stop before the opaque action helper; never stub it as success.
"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,struct,itertools
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.x86_const import *
from source_manifest import LEImage,EXPECTED_EXE_SHA
from le_fixups import LE
ROOT=Path(__file__).resolve().parent
EXE=Path(r'F:\Remaster Framework\source\Stonekeep\SK.EXE');RAW=EXE.read_bytes()
assert hashlib.sha256(RAW).hexdigest()==EXPECTED_EXE_SHA
LE_RAW=LEImage(RAW);LF=LE(RAW);STACK=0x40008000;STOP=0x4000f000
RANGES=[(0x3d4f5,0x3d502),(0x3c36a,0x3c4bd),(0x4f861,0x4f862),(0x5e867,0x5e868)]
INTENT,SUPPRESS,CALLBACK=0x2ac3f6,0x2a9d88,0x2a9ddc

def create():
 u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x10000,0x300000);u.mem_map(0x40000000,0x10000)
 for a,b in RANGES:u.mem_write(a,LE_RAW.read_va(a,b-a))
 fixes={}
 for obj in LF.objects:
  for page in range(obj['mapsize']):
   pb=obj['base']+page*LF.page_size
   if not any(a<pb+LF.page_size and pb<b for a,b in RANGES):continue
   for f in LF.parse_fixup_page(obj['mapidx']-1+page):
    for so in f['sources']:
     p=pb+so
     if not any(a<=p and p+4<=b for a,b in RANGES):continue
     if f['type']&15!=7 or f['target_kind']!=0 or f['target_offset'] is None:raise ValueError('UNSUPPORTED_RELOCATION')
     target=LF.objects[f['target_object']-1]['base']+f['target_offset']
     fixes[p]=target;u.mem_write(p,struct.pack('<I',target))
 if fixes.get(0x3d4f8)!=CALLBACK:raise ValueError('CALLBACK_POINTER_NOT_RELOCATED')
 assert LE_RAW.read_va(0x4f861,1)==LE_RAW.read_va(0x5e867,1)==b'\xc3'
 return u,fixes

def run(action,initial,suppress,callback):
 u,fixes=create();u.mem_write(INTENT-4,b'\xa5'*10);u.mem_write(INTENT,struct.pack('<h',initial))
 u.mem_write(SUPPRESS,struct.pack('<I',suppress));u.mem_write(CALLBACK,struct.pack('<I',callback))
 u.mem_write(STACK,struct.pack('<I',STOP));u.reg_write(UC_X86_REG_ESP,STACK);u.reg_write(UC_X86_REG_EAX,action)
 writes=[];calls=[];state={'end':None,'instructions':0}
 def code(uc,a,n,_):
  state['instructions']+=1
  if a==STOP:state['end']='RETURNED_WITH_DOWNSTREAM_SUPPRESSED';uc.emu_stop();return
  if a==0x3d35e:state['end']='DOWNSTREAM_ACTION_PENDING';uc.emu_stop();return
  if a==callback:calls.append('ORIGINAL_LEVEL_CALLBACK_RET')
  if not any(lo<=a and a+n<=hi for lo,hi in RANGES):raise ValueError('CODE_ESCAPE:'+hex(a))
 def write(uc,access,a,n,value,_):
  if STACK-64<=a and a+n<=STACK:return
  if a==INTENT and n==2:writes.append((a,n,value&65535));return
  raise ValueError('UNDECLARED_STATE_WRITE:'+hex(a))
 u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
 u.emu_start(0x3d4f5,STOP+1,timeout=150000,count=160)
 expected=2 if action==6 else -2
 if struct.unpack('<h',u.mem_read(INTENT,2))[0]!=expected:raise ValueError('TURN_INTENT_VALUE')
 if writes!=[(INTENT,2,expected&65535)] or calls!=['ORIGINAL_LEVEL_CALLBACK_RET']:raise ValueError('TURN_TRACE_MISMATCH')
 if bytes(u.mem_read(INTENT-4,4))!=b'\xa5'*4 or bytes(u.mem_read(INTENT+2,4))!=b'\xa5'*4:raise ValueError('INTENT_NEIGHBOR_MUTATED')
 end='RETURNED_WITH_DOWNSTREAM_SUPPRESSED' if suppress else 'DOWNSTREAM_ACTION_PENDING'
 if state['end']!=end:raise ValueError('DOWNSTREAM_GATE')
 if suppress and u.reg_read(UC_X86_REG_EAX)!=1:raise ValueError('RETURN_VALUE')
 return {'action':action,'initial_intent':initial,'downstream_suppression':suppress,'source_level_callback':hex(callback),
  'intent_after':expected,'boundary':state['end'],'instruction_count':state['instructions'],'trace':calls,'pass':True}

def main():
 cases=[run(a,i,s,c) for a,i,s,c in itertools.product((6,8),(-32768,-2,0,1,2,32767),(0,1,0xffffffff),(0x4f861,0x5e867))]
 _,fixes=create()
 result={'schema':'OpenStonekeep.TurnIntentMechanism.v1','status':'PASS','tests':len(cases),'cases':cases,
  'source_exe_sha256':EXPECTED_EXE_SHA,'relocations_sha256':hashlib.sha256(json.dumps(fixes,sort_keys=True).encode()).hexdigest(),
  'rule':'Ordinary action dispatcher calls the source level RET callback, then action6 writes signed turn-intent +2 and action8 writes -2. If the suppression global is zero the downstream action helper remains pending.',
  'state_fields':{'turn_intent_linear':hex(INTENT),'downstream_suppression_linear':hex(SUPPRESS),'level_callback_linear':hex(CALLBACK)},
  'chain':'0x3d4f5 -> pinned level callback -> 0x3c36a -> intent store -> optional 0x3d35e',
  'scope':'Independent ordinary turn-intent stage, NOT proof that H415 event/common continuation succeeds.',
  'closed_dependency':'Action6/8 -> signed turn intent; original write size, address, boundaries and return tested.',
  'remaining':['Downstream action helper, orientation animation loops and interaction with H415 pending event.',
    'Actual runtime callback selection/state and complete navigation/softlock proof.'],
  'native_game_executed':False,'navigation_success_proven':False,'created_at_utc':datetime.now(timezone.utc).isoformat()}
 with (ROOT/'turn-intent-verification.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,sort_keys=True)
 print(json.dumps({'status':'PASS','tests':len(cases),'rule':result['rule'],'sha256':hashlib.sha256((ROOT/'turn-intent-verification.json').read_bytes()).hexdigest()}))
if __name__=='__main__':main()
