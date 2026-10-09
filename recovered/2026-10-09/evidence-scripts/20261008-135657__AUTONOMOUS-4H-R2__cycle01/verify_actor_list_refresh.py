"""Original distance-qualified active/inactive list refresh, with stable identities.
The pure activation path executes fully. Eviction stops before its real external
helper after preserving the original partial bookkeeping changes.
"""
from datetime import datetime,timezone
from itertools import product
import hashlib,json,struct
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.x86_const import *
from verify_turn_intent import create,STACK,STOP,ROOT,EXPECTED_EXE_SHA
from verify_ordinary_turn_envelope import add_ranges
ACTOR,STRIDE=0x2871f8,0x111
ACTIVE_LIST,DORMANT_LIST,INDEX=0x24893c,0x248a0c,0x248adc
ACOUNT,DCOUNT=0xf540c,0xf5408

def s16(v):return v if v<32768 else v-65536

def run(active,dormant,entities,player=(16,16)):
 allids=active+dormant
 if len(allids)>104 or len(allids)!=len(set(allids)) or any(not 0<=i<104 for i in allids):raise ValueError('LIST_IDENTITY_INVARIANT')
 u,_=create();add_ranges(u,[(0x75e50,0x76023)])
 actors=bytearray((i*13+7)&255 for i in range(104*STRIDE))
 for identity,(kind,row,col,state,radius) in entities.items():
  for o,v in [(0,kind),(0x10,row),(0x12,col),(0x3e,state),(0xd1,radius)]:struct.pack_into('<H',actors,identity*STRIDE+o,v&65535)
 lists=bytearray(b'\xa5'*416)
 for base,ids in [(0,active),(208,dormant)]:
  for i,item in enumerate(ids):struct.pack_into('<H',lists,base+2*i,item)
 u.mem_write(ACTOR,bytes(actors));u.mem_write(ACTIVE_LIST,bytes(lists))
 for p,v in [(ACOUNT,len(active)),(DCOUNT,len(dormant)),(INDEX,77)]:u.mem_write(p,struct.pack('<I',v))
 for p,v in [(0x2ac698,player[0]),(0x2ac69a,player[1])]:u.mem_write(p,struct.pack('<H',v&65535))
 u.reg_write(UC_X86_REG_ESP,STACK);u.mem_write(STACK,struct.pack('<I',STOP))
 writes=[];state={'boundary':None,'instructions':0}
 def code(uc,a,size,_):
  state['instructions']+=1
  if a==STOP:state['boundary']='REFRESH_RETURNED';uc.emu_stop();return
  if a==0x948c6:state['boundary']='EVICTION_HELPER_PENDING';state['pending_entity']=uc.reg_read(UC_X86_REG_EAX);uc.emu_stop();return
  if not 0x75e50<=a or a+size>0x76023:raise ValueError('REFRESH_CODE_ESCAPE')
 def write(uc,access,a,size,v,_):
  if STACK-64<=a and a+size<=STACK:return
  if ACTIVE_LIST<=a and a+size<=DORMANT_LIST+208 and size==2 or a in (ACOUNT,DCOUNT,INDEX) and size==4:writes.append((a,size,v&((1<<(size*8))-1)));return
  raise ValueError('REFRESH_WRITE_ESCAPE:'+hex(a))
 u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
 u.emu_start(0x75e50,STOP+1,timeout=200000,count=25000)
 expected=bytearray(lists);globals={ACOUNT:len(active),DCOUNT:len(dormant),INDEX:77};ew=[];pending=None
 def wlist(base,i,value):struct.pack_into('<H',expected,base-ACTIVE_LIST+2*i,value);ew.append((base+2*i,2,value))
 def readlist(base,i):return struct.unpack_from('<H',expected,base-ACTIVE_LIST+2*i)[0]
 def wg(p,value):value&=0xffffffff;globals[p]=value;ew.append((p,4,value))
 def distance(e):return abs(e[1]-player[0])+abs(e[2]-player[1])
 for i in range(len(active)):
  identity=readlist(ACTIVE_LIST,i);entity=entities[identity];kind,row,col,st,radius=entity
  wg(INDEX,i)
  keep=kind>=0 and st!=-37 and radius!=-1 and (radius==-58 or distance(entity)<=radius)
  if not keep:
   last=readlist(ACTIVE_LIST,globals[ACOUNT]-1)
   wlist(DORMANT_LIST,globals[DCOUNT],identity);wg(INDEX,i-1);wg(ACOUNT,globals[ACOUNT]-1);wg(DCOUNT,globals[DCOUNT]+1);wlist(ACTIVE_LIST,i,last)
   pending=identity;break
 if pending is None:
  i=0;remaining=len(dormant)
  while i<remaining:
   identity=readlist(DORMANT_LIST,i);entity=entities[identity];kind,row,col,st,radius=entity
   wg(INDEX,i)
   admit=kind>=0 and st!=-37 and (radius==-58 or distance(entity)<=radius)
   if admit:
    last_initial=readlist(DORMANT_LIST,remaining-1);remaining-=1
    wlist(DORMANT_LIST,i,last_initial);wg(DCOUNT,globals[DCOUNT]-1)
    last_total=readlist(DORMANT_LIST,globals[DCOUNT]);wlist(DORMANT_LIST,remaining,last_total)
    wg(ACOUNT,globals[ACOUNT]+1);wlist(ACTIVE_LIST,globals[ACOUNT]-1,identity)
   else:i+=1
  wg(INDEX,i)
 boundary='EVICTION_HELPER_PENDING' if pending is not None else 'REFRESH_RETURNED'
 if state['boundary']!=boundary or writes!=ew or bytes(u.mem_read(ACTIVE_LIST,len(lists)))!=bytes(expected):
  failure={'status':'FAIL','active':active,'dormant':dormant,'entities':entities,'boundary':state,'expected_boundary':boundary,'writes':writes,'expected_writes':ew}
  p=ROOT/'actor-refresh-counterexample.json'
  if not p.exists():p.write_text(json.dumps(failure,indent=2),encoding='utf-8')
  raise ValueError('LIST_REFRESH_OR_WRITE_SEQUENCE_DIFFERENCE')
 if any(int.from_bytes(u.mem_read(p,4),'little')!=v for p,v in globals.items()) or bytes(u.mem_read(ACTOR,len(actors)))!=bytes(actors):raise ValueError('ENTITY_OR_COUNTER_DIFFERENCE')
 if pending is not None and state.get('pending_entity')!=pending:raise ValueError('PENDING_HELPER_IDENTITY')
 final_active=[readlist(ACTIVE_LIST,i) for i in range(globals[ACOUNT])];final_dormant=[readlist(DORMANT_LIST,i) for i in range(globals[DCOUNT])]
 if sorted(final_active+final_dormant)!=sorted(allids):raise ValueError('IDENTITY_POPULATION_NOT_PRESERVED')
 return {'active_before':active,'dormant_before':dormant,'active_after':final_active,'dormant_after':final_dormant,'pending_eviction':pending,
  'boundary':boundary,'state_trace_sha256':hashlib.sha256(json.dumps(writes).encode()).hexdigest(),'nonstack_writes':len(writes),'instructions':state['instructions'],'pass':True}

def main():
 cases=[]
 for ac,radius,distance,special in product((0,2),(-58,-1,0,1,5,7),(0,1,5,7),('none','identity-negative','state-disabled')):
  active=list(range(ac));dormant=[2,3,4,5];entities={i:(i,16,16,0,-58) for i in active}
  for j,item in enumerate(dormant):entities[item]=(item,16+distance+(j&1),16,0,radius)
  if special=='identity-negative':v=list(entities[2]);v[0]=-1;entities[2]=tuple(v)
  elif special=='state-disabled':v=list(entities[2]);v[3]=-37;entities[2]=tuple(v)
  c=run(active,dormant,entities);c.update(radius=radius,manhattan_axis_distance=distance,special=special);cases.append(c)
 for ids,active in [(list(range(104)),False),(list(range(104)),True),([],False)]:
  cases.append(run(ids if active else [],[] if active else ids,{i:(i,16,16,0,-58) for i in ids}))
 for bad in [(-1,16,16,0,-58),(1,16,16,-37,-58),(1,16,16,0,-1),(1,31,31,0,3)]:cases.append(run([0,1],[2],{0:(0,16,16,0,-58),1:bad,2:(2,16,16,0,5)}))
 result={'schema':'OpenStonekeep.ActiveInactiveRefresh.v1','status':'PASS','tests':len(cases),'cases':cases,'source_exe_sha256':EXPECTED_EXE_SHA,
  'function':'0x75e50..0x76022','rule':'Refresh two identity lists by source signed fields and Manhattan distance; radius -58 bypasses distance. Activation uses swap-removal, appending to active. Deactivation transfers list bookkeeping before calling its external helper.',
  'semantic_distinction':'Inactive entries selected for this pass are the entry-time snapshot; newly evicted entries are not silently treated as newly active in the same scan.',
  'negative_boundary':'An invalid/disabled/out-of-range active entry leaves observed list changes and stops before 0x948c6. No helper effect or automatic rollback is fabricated.',
  'identity_invariants':'Valid unique disjoint lists with combined population<=104; runtime list validity is a prerequisite, not inferred from these fixtures.',
  'game_runtime_executed':False,'full_actor_lifecycle_verified':False,'fidelity_verified':False,
  'next':'Compose active-list changes with actor action helpers only when those helper contracts are discharged.',
  'created_at_utc':datetime.now(timezone.utc).isoformat()}
 p=ROOT/'actor-refresh-verification.json'
 with p.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,sort_keys=True)
 print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2));print('SHA256',hashlib.sha256(p.read_bytes()).hexdigest())
if __name__=='__main__':main()
