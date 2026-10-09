"""Source callback acceptance to turn entry for ordinary starter-level cells.
Real ordinary callback/getter/preparation helpers execute. Resource disposal,
effect callbacks, and the turn animation itself remain explicit stop boundaries.
"""
from datetime import datetime,timezone
from collections import Counter
import hashlib,json,struct,itertools
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.x86_const import *
from verify_turn_intent import create,STACK,INTENT,CALLBACK,SUPPRESS,EXPECTED_EXE_SHA,ROOT
from verify_ordinary_turn_envelope import add_ranges,data_for,LEVELS
GRID=0x50000000;MEMBASE=0x2ac4cc;MEMSIZE=0x110
CLEAR=(0x2ac4e0,0x2ac4de,0x2ac4d0,0x2ac4cc)

def run(level,action,resources,actor_state,post_result=None):
 pair,regionbase,regions,regionbytes=data_for(level);u,_=create()
 ranges=[(0x31926,0x31958),(0x3197b,0x319c2),(0x84904,0x84937),(0x7a25e,0x7a289),
  (0x3c0c9,0x3c1f7),(0x3d35e,0x3d454),(0xfe9ae,0xfe9ae+88),(0xff0b2,0xff0b2+88),(regionbase,regionbase+len(regionbytes)),(LEVELS[level][1],LEVELS[level][1]+1)]
 add_ranges(u,ranges);u.mem_map(GRID,0x8000);grid=bytes(32*32*21);u.mem_write(GRID,grid)
 initial=bytearray(b'\xa5'*MEMSIZE);struct.pack_into('<H',initial,0x2ac4d6-MEMBASE,resources);u.mem_write(MEMBASE,bytes(initial))
 for p,v in [(0xfcd0d,GRID),(SUPPRESS,0),(CALLBACK,LEVELS[level][1]),(0x2a9df4,0x3d4f5)]:u.mem_write(p,struct.pack('<I',v))
 for p,v in [(0x2ac698,0),(0x2ac69a,0),(0x2ac6a0,level),(0x2ac6b4,actor_state),(INTENT,77)]:u.mem_write(p,struct.pack('<h',v))
 u.mem_write(0x2a9df8,struct.pack('<32h',*[i*32 for i in range(32)]));u.mem_write(0x2a9d58,struct.pack('<hh',*pair))
 u.reg_write(UC_X86_REG_ESP,STACK);state={'boundary':None,'instructions':0};calls=[];writes=[]
 start=(0x31926 if action==6 else 0x3197b) if post_result is None else (0x31931 if action==6 else 0x31986)
 if post_result is not None:u.reg_write(UC_X86_REG_EAX,post_result)
 def code(uc,a,n,_):
  state['instructions']+=1
  if a in (0x317ab,0x3198b):state['boundary']='CALLBACK_REJECTED_TURN';uc.emu_stop();return
  if a==0x84937:state['boundary']='RESOURCE_DISPOSAL_PENDING';uc.emu_stop();return
  if a==0x82899:state['boundary']='TURN_ENTRY_PENDING';state['turn_argument']=uc.reg_read(UC_X86_REG_EAX);uc.emu_stop();return
  if a in (0x3d4f5,LEVELS[level][1],0x3c36a,0x3d35e,0x3c14d,0x84904,0x7a25e):calls.append(hex(a))
  allowed=ranges+[(0x3d4f5,0x3d502),(0x3c36a,0x3c4bd)]
  if not any(lo<=a and a+n<=hi for lo,hi in allowed):raise ValueError('ADMISSION_CODE_ESCAPE:'+hex(a))
 def write(uc,access,a,n,v,_):
  if STACK-160<=a and a+n<=STACK:return
  if a==INTENT and n==2:writes.append((a,v&65535));return
  if a in CLEAR+(0x2ac5c0,0x2ac5be,0x2ac5d8) and n==2:writes.append((a,v&65535));return
  raise ValueError('ADMISSION_STATE_ESCAPE:'+hex(a))
 u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
 u.emu_start(start,0x4000f000,timeout=200000,count=2000)
 accepted=post_result is None or post_result&65535!=0
 expected=bytearray(initial);ew=[]
 if post_result is None:ew.append((INTENT,2 if action==6 else 65534))
 if accepted:
  for p in CLEAR:struct.pack_into('<H',expected,p-MEMBASE,65535);ew.append((p,65535))
  if not resources and actor_state!=-5:
   for p,v in [(0x2ac5c0,2),(0x2ac5be,1),(0x2ac5d8,2)]:struct.pack_into('<H',expected,p-MEMBASE,v);ew.append((p,v))
 boundary='CALLBACK_REJECTED_TURN' if not accepted else 'RESOURCE_DISPOSAL_PENDING' if resources else 'TURN_ENTRY_PENDING'
 if state['boundary']!=boundary or bytes(u.mem_read(MEMBASE,MEMSIZE))!=bytes(expected) or writes!=ew:raise ValueError('ADMISSION_MODEL_OR_TRACE')
 if boundary=='TURN_ENTRY_PENDING' and state['turn_argument']!=(2 if action==6 else 0xfffffffe):raise ValueError('TURN_DIRECTION_ARGUMENT')
 if bytes(u.mem_read(GRID,len(grid)))!=grid:raise ValueError('SOURCE_GRID_CHANGED')
 return {'level':level,'callback_action':action,'post_callback_result_override':post_result,'resource_disposal_needed':resources,'actor_state':actor_state,
  'boundary':boundary,'turn_argument':state.get('turn_argument'),'source_calls':calls,'writes':writes,'instructions':state['instructions'],'pass':True}

def main():
 cases=[run(l,a,r,s) for l,a,r,s in itertools.product(LEVELS,(6,8),(0,1),(-5,0))]
 cases +=[run(1,a,0,-5,result) for a,result in itertools.product((6,8),(0,1,65535,65536,65537,0xffffffff))]
 result={'schema':'OpenStonekeep.CallbackToTurnAdmission.v1','status':'PASS','tests':len(cases),'cases':cases,'source_exe_sha256':EXPECTED_EXE_SHA,
  'rule':'Source callback AX!=0 admits pre-turn preparation. With no resource disposal pending, action6 passes +2 and action8 passes -2 into the actual turn function; callback AX==0 does not enter it.',
  'closed_chain':'ordinary level RET callback -> verified intent/environment stage -> source preparation helpers -> original turn entry boundary',
  'state_side_effects':'Four preparation words become -1; actor-state !=-5 enables the source 2/1/2 preparation fields.',
  'domain':'Ordinary starter-level callbacks with source tables and cached environment ids. H415 event-specific branch is not substituted by this ordinary callback.',
  'negative_obligation':'Nonzero resource-disposal flag stops before its helper, and high bits of callback EAX cannot turn a zero AX into acceptance.',
  'game_runtime_executed':False,'turn_animation_executed':False,'fidelity_verified':False,
  'next':'Keep H415 event, resource disposal and animation obligations explicit when composing the complete bounded state graph.',
  'created_at_utc':datetime.now(timezone.utc).isoformat()}
 p=ROOT/'turn-admission-verification.json'
 with p.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,sort_keys=True)
 print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2));print('SHA256',hashlib.sha256(p.read_bytes()).hexdigest())
if __name__=='__main__':main()
