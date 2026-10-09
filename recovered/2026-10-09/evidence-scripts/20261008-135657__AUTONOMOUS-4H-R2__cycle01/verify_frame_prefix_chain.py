"""Original turn frame -> world tick -> 64-object tick -> renderer boundary.
Known helper code executes, never a fabricated success stub. Explicit actor-list,
phase and event states constrain the domain; unknown actor/event helpers stop.
"""
from datetime import datetime,timezone
from itertools import product
import json,struct,hashlib
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.x86_const import *
from verify_turn_intent import create,STACK,EXPECTED_EXE_SHA,ROOT
from verify_ordinary_turn_envelope import add_ranges
from verify_object_frame_tick import model as object_model,build as object_build,BASE as OBJECTS,STRIDE as OSTRIDE,COUNT as OCOUNT
ACTORS,ASTRIDE=0x2871f8,0x111
FRAME,COUNTER,PERIOD,PHASE,ORIENT,HEADING=0x2ac448,0x2ac45e,0x2ac44e,0x2ac452,0x2ac40a,0x2ac6ae
WORLD_COUNT,WORLD_PHASE,ACTIVE,DORMANT,INDEX=0xf5404,0xf5410,0xf540c,0xf5408,0x248adc
MESSAGE,MESSAGE_BLOCK=0x2ac714,0x2ac52c
RANGES=[(0x390e0,0x39151),(0x76be0,0x76d0d),(0x75e50,0x76023),(0x77520,0x775a0),(0x6fd90,0x6fdfa)]


def run(frame,worldphase,n,timer,countdown,orient,event=0,eventblock=0,mode=1,tickcount=0xffffffff):
 if frame not in (0,6) or worldphase not in range(6) or n not in (0,2) or not 0<=timer<=15:raise ValueError('DOMAIN')
 u,_=create();add_ranges(u,RANGES)
 expected={};writes=[];want=[]
 def init(address,data):u.mem_write(address,data);expected.update({address+i:v for i,v in enumerate(data)})
 def winit(address,value,size=2):init(address,(value&((1<<(size*8))-1)).to_bytes(size,'little'))
 def store(address,value,size=2):
  value&=(1<<(size*8))-1;data=value.to_bytes(size,'little');expected.update({address+i:v for i,v in enumerate(data)});want.append((address,size,value))
 actors=bytearray((i*11+3)&255 for i in range(ASTRIDE*3))
 for i in range(n):
  for off,value in [(0,i),(0x10,23),(0x12,2),(0x3e,0),(0xd1,65536-58),(0xff,mode),(0x10b,0xab00|timer)]:struct.pack_into('<H',actors,i*ASTRIDE+off,value)
 init(ACTORS,bytes(actors))
 obj=object_build([(0,1,7,1,3,65535),(2,1,0,1,1,7),(0,0,0,9,2,0)]);init(OBJECTS,obj)
 init(0x24893c,struct.pack('<2H',0,1))
 for a,v,size in [(FRAME,99,2),(COUNTER,countdown,2),(PERIOD,3,2),(PHASE,65535,2),(ORIENT,orient,2),(HEADING,2,2),
  (WORLD_COUNT,tickcount,4),(WORLD_PHASE,worldphase,4),(ACTIVE,n,4),(DORMANT,0,4),(INDEX,77,4),(MESSAGE,event,1),(MESSAGE_BLOCK,eventblock,2),
  (0x2ac698,23,2),(0x2ac69a,2,2),(0x2aa158,0x12345678,4)]:winit(a,v,size)
 before=dict(expected);u.reg_write(UC_X86_REG_ESP,STACK);u.reg_write(UC_X86_REG_EAX,frame);u.reg_write(UC_X86_REG_EDX,1)
 state={'end':None,'instructions':0};trace=[]
 boundaries={0x2db10:'RENDER_ORIENTATION_HELPER_PENDING',0x772c0:'ACTOR_STAGE1_PENDING',0x76d10:'ACTOR_STAGE2_PENDING',0x948c6:'ACTOR_DEACTIVATION_PENDING',0x94622:'WORLD_EVENT_PENDING'}
 def code(uc,a,size,_):
  state['instructions']+=1
  if a in boundaries:state['end']=boundaries[a];state['eax']=uc.reg_read(UC_X86_REG_EAX);uc.emu_stop();return
  if a in (0x76be0,0x75e50,0x77520,0x6fd90):trace.append(hex(a))
  if not any(lo<=a and a+size<=hi for lo,hi in RANGES):raise ValueError('FRAME_PREFIX_CODE_ESCAPE:'+hex(a))
 def write(uc,access,a,size,value,_):
  if STACK-192<=a and a+size<=STACK:return
  if all(a+i in expected for i in range(size)):writes.append((a,size,value&((1<<(size*8))-1)));return
  raise ValueError('FRAME_PREFIX_STATE_ESCAPE:'+hex(a))
 u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
 u.emu_start(0x390e0,0x4000f000,timeout=250000,count=6500)
 store(FRAME,frame+1);store(WORLD_COUNT,tickcount+1,4);expected_trace=['0x76be0']
 if worldphase==0:
  expected_trace.append('0x75e50')
  for i in range(n):store(INDEX,i,4)
  store(INDEX,0,4)
 store(WORLD_PHASE,(worldphase+1)%6,4);store(INDEX,0 if worldphase==0 else 77,4)
 expected_trace.append('0x77520');boundary=None
 current=[0xab00|timer]*n
 for passid in range(2):
  for i in range(n):
   store(INDEX,i,4)
   if mode:
    value=current[i];store(ACTORS+i*ASTRIDE+0x10b,value&0xfff0)
    if value&15:
     current[i]=(value&0xfff0)|((value&15)-1);store(ACTORS+i*ASTRIDE+0x10b,current[i]);continue
   boundary='ACTOR_STAGE1_PENDING' if passid==0 else 'ACTOR_STAGE2_PENDING';break
  if boundary:break
  store(INDEX,n,4)
 if boundary is None:
  if event and eventblock==0:boundary='WORLD_EVENT_PENDING'
  else:
   c=(countdown-1)&65535;store(COUNTER,c)
   if c>=32768 or c==0:store(COUNTER,3);store(PHASE,0)
   expected_trace.append('0x6fd90');after,ot=object_model(obj)
   for a,size,value in ot:store(a,value,size)
   store(0x2aa158,frame-7 if orient==-2 else frame+1,4)
   boundary='RENDER_ORIENTATION_HELPER_PENDING'
 if state['end']!=boundary or trace!=expected_trace or writes!=want:
  bad={'status':'FAIL','inputs':[frame,worldphase,n,timer,countdown,orient,event,eventblock,mode],
   'boundary':state['end'],'expected_boundary':boundary,'trace':trace,'expected_trace':expected_trace,'writes':writes,'expected_writes':want}
  p=ROOT/'frame-prefix-counterexample.json'
  if not p.exists():p.write_text(json.dumps(bad,indent=2),encoding='utf-8')
  raise ValueError('FRAME_PREFIX_MODEL_OR_TRACE_MISMATCH')
 for start,length in [(ACTORS,len(actors)),(OBJECTS,len(obj))]+[(a,size) for a,_,size in [(FRAME,0,2),(COUNTER,0,2),(PERIOD,0,2),(PHASE,0,2),(WORLD_COUNT,0,4),(WORLD_PHASE,0,4),(INDEX,0,4),(0x2aa158,0,4)]]:
  if bytes(u.mem_read(start,length))!=bytes(expected[start+i] for i in range(length)):raise ValueError('FRAME_PREFIX_BYTES')
 return {'frame':frame,'worldphase':worldphase,'active_actors':n,'actor_timer_nibble':timer,'countdown':countdown,'turn_mode':orient,
  'event':event,'event_blocked':eventblock,'actor_mode':mode,'boundary':boundary,'calls':trace,'nonstack_write_count':len(writes),
  'state_delta_sha256':hashlib.sha256(json.dumps(writes).encode()).hexdigest(),'instructions':state['instructions'],'pass':True}

def main():
 cases=[run(f,p,n,t,c,o) for f,p,n,t,c,o in product((0,6),(0,1,5),(0,2),(2,15),(0,1,2,32768),(-2,2))]
 for p,t,event,blocked,mode in [(1,1,0,0,1),(0,0,0,0,1),(1,5,0,0,0),(1,5,1,0,1),(1,5,1,1,1)]:cases.append(run(0,p,2,t,1,2,event,blocked,mode))
 result={'schema':'OpenStonekeep.FramePrefixStateChain.v1','status':'PASS','tests':len(cases),'cases':cases,'source_exe_sha256':EXPECTED_EXE_SHA,
  'closed_chain':'Original frame request -> original world/update and active-list refresh in retained-list domain -> original object tick -> renderer/orientation helper boundary.',
  'new_observation':'Actor timer low nibble is processed twice per completed world-update stage, while object countdowns are processed once. Replacing a whole frame by a heading change loses both state transitions.',
  'cycle_fields':'World counter increments modulo32bits; phase wraps at6. Frame countdown is signed16 after decrement and may reload/advance its own phase.',
  'explicit_domain':'Zero inactive actors; active actor identities valid and retained by original refresh predicate; two actor timer-only paths or precise negative helper stops.',
  'negative_barriers':['Actor stage1/stage2 helper','Actor deactivation helper','World message/event helper','Next render/orientation helper'],
  'game_runtime_executed':False,'full_frame_verified':False,'full_turn_verified':False,'created_at_utc':datetime.now(timezone.utc).isoformat()}
 p=ROOT/'frame-prefix-chain-verification.json'
 with p.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,sort_keys=True)
 print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2));print('SHA256',hashlib.sha256(p.read_bytes()).hexdigest())
if __name__=='__main__':main()
