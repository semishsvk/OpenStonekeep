"""Original preparation through the first animation-frame request under explicit
quiet/audio states. All executed helpers are real source code; nonquiet effects
remain stop boundaries. This is not the seven-frame turn or a gameplay replay.
"""
from datetime import datetime,timezone
import json,hashlib,struct,itertools
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.x86_const import *
from verify_turn_intent import create,STACK,INTENT,EXPECTED_EXE_SHA,ROOT
from verify_ordinary_turn_envelope import add_ranges
PREP,GATE=0x2ac46c,0x260d9a;AUDIOSTATE=0x2aa4d3;HANDLE1,HANDLE2=0x25ffca,0x25ffc8

def run(turn,audiostate,handle1,handle2,oldgate):
 u,_=create();ranges=[(0x828da,0x829a7),(0x9c8b5,0x9c920),(0x7da40,0x7da5a)];add_ranges(u,ranges)
 u.reg_write(UC_X86_REG_ESP,STACK);u.reg_write(UC_X86_REG_EBX,turn&0xffffffff)
 for p,v in [(PREP,44),(GATE,oldgate),(AUDIOSTATE,audiostate),(HANDLE1,handle1),(HANDLE2,handle2),(INTENT,77),(0x2ac47a,11),(0x2ac47c,22)]:u.mem_write(p,struct.pack('<H',v&65535))
 state={'end':None,'instructions':0};writes=[]
 def code(uc,a,n,_):
  state['instructions']+=1
  if a in (0x7fca2,0x9c7af,0x390e0):
   state['end']={0x7fca2:'HANDLE_EFFECT_PENDING',0x9c7af:'NEW_EFFECT_LOOKUP_PENDING',0x390e0:'FIRST_ANIMATION_FRAME_PENDING'}[a]
   state['eax']=uc.reg_read(UC_X86_REG_EAX);state['edx']=uc.reg_read(UC_X86_REG_EDX);uc.emu_stop();return
  if not any(lo<=a and a+n<=hi for lo,hi in ranges):raise ValueError('FIRST_FRAME_CODE_ESCAPE')
 def write(uc,access,a,n,v,_):
  if STACK-64<=a and a+n<=STACK:return
  if n==2 and a in (PREP,GATE,INTENT,0x2ac47a,0x2ac47c):writes.append((a,v&65535));return
  raise ValueError('FIRST_FRAME_STATE_ESCAPE:'+hex(a))
 u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
 u.emu_start(0x828da,0x4000f000,timeout=150000,count=250)
 expected=[(PREP,1),(GATE,0)]
 if handle1 or handle2:
  boundary='HANDLE_EFFECT_PENDING';argument=handle1 or handle2
 elif audiostate!=1:boundary='NEW_EFFECT_LOOKUP_PENDING';argument=1
 else:
  boundary='FIRST_ANIMATION_FRAME_PENDING';argument=6 if turn==-2 else 0
  expected +=[(INTENT,65534 if turn==-2 else 2),(0x2ac47a,1),(0x2ac47c,0)]
 if state['end']!=boundary or writes!=expected or state['eax']!=argument:raise ValueError('FIRST_FRAME_TRACE_OR_STATE_MISMATCH')
 if boundary=='FIRST_ANIMATION_FRAME_PENDING' and state['edx']!=1:raise ValueError('ANIMATION_PARAMETER')
 return {'turn':turn,'audio_state':audiostate,'old_handles':[handle1,handle2],'old_h415_gate':oldgate,'boundary':boundary,'forwarded_value':argument,'write_trace':writes,'instructions':state['instructions'],'pass':True}

def main():
 cases=[run(t,a,h1,h2,g) for t,a,(h1,h2),g in itertools.product((-2,2),(0,1,65535),((0,0),(1,0),(0,2),(3,4)),(0,1,65535))]
 result={'schema':'OpenStonekeep.TurnFirstFrameGate.v1','status':'PASS','tests':len(cases),'cases':cases,'source_exe_sha256':EXPECTED_EXE_SHA,
  'rule':'Preparation clears the H415 global before examining existing effect handles. With both handles zero and state word==1 the real helper returns, and turn -2 requests frame6 while +2 requests frame0; both pass parameter1.',
  'first_frame_flags':'The original helper0x7da40 writes control words1 and0 before the frame routine.',
  'negative_obligations':'Any existing handle stops before its effect helper; state word!=1 stops before effect lookup. Neither boundary is treated as success.',
  'scope':'Preparation-to-first-frame under declared state, no original sound/game I/O and no animation body executed.',
  'semantic_labels':'Audio/effect naming is contextual; exact addresses and branch values are the authority, not a claim of a complete sound subsystem.',
  'game_runtime_executed':False,'full_turn_verified':False,'next':'Validate the frame routine/state delta and event-pump obligations before joining preparation to orientation commit.',
  'created_at_utc':datetime.now(timezone.utc).isoformat()}
 out=ROOT/'turn-first-frame-verification.json'
 with out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,sort_keys=True)
 print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2));print('SHA256',hashlib.sha256(out.read_bytes()).hexdigest())
if __name__=='__main__':main()
