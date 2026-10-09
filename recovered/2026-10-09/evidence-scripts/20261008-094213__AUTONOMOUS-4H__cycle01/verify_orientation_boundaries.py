"""Original turn preparation and orientation commit as separate bounded stages.
The animation/event helpers between them remain explicit proof obligations.
No helper is replaced by success and no full turn/replay verdict is fabricated.
"""
from datetime import datetime,timezone
import hashlib,json,struct,itertools
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.x86_const import *
from verify_turn_intent import create,STACK,INTENT,EXPECTED_EXE_SHA,ROOT
from verify_ordinary_turn_envelope import add_ranges
GATE=0x260d9a;PREPARED=0x2ac46c;HEADING=0x2ac6ae

def invoke(start,end,write_allowed,init):
 u,_=create();add_ranges(u,[(0x828da,0x829ae)])
 u.reg_write(UC_X86_REG_ESP,STACK);init(u);state={'done':False};writes=[]
 def code(uc,a,n,_):
  if a==end:state['done']=True;uc.emu_stop();return
  if not 0x828da<=a or a+n>0x829ae:raise ValueError('TURN_BOUNDARY_CODE_ESCAPE:'+hex(a))
 def write(uc,access,a,n,v,_):
  if (a,n) not in write_allowed:raise ValueError('UNDECLARED_TURN_WRITE:'+hex(a))
  writes.append((a,n,v&((1<<(8*n))-1)))
 u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
 u.emu_start(start,0x4000f000,timeout=100000,count=100)
 if not state['done']:raise ValueError('TURN_STAGE_DID_NOT_REACH_BOUNDARY')
 return u,writes

def preparation(initial_gate,initial_prepared):
 def init(u):
  u.mem_write(GATE,struct.pack('<H',initial_gate));u.mem_write(PREPARED,struct.pack('<H',initial_prepared))
 u,writes=invoke(0x828da,0x9c8b5,{(GATE,2),(PREPARED,2)},init)
 if writes!=[(PREPARED,2,1),(GATE,2,0)] or bytes(u.mem_read(GATE,2))!=b'\0\0':raise ValueError('PREPARATION_TRACE')
 return {'initial_h415_gate':initial_gate,'initial_prepared':initial_prepared,'writes':writes,'pending_helper':'0x9c8b5','pass':True}

def branch(turn_argument):
 # Entry after the unexecuted helper returns; cx==0 is required by the previous source initialization.
 u,_=create();add_ranges(u,[(0x828f2,0x829a7)]);u.reg_write(UC_X86_REG_ESP,STACK);u.reg_write(UC_X86_REG_EBX,turn_argument&0xffffffff);u.reg_write(UC_X86_REG_ECX,0)
 state={'boundary':None};writes=[];stop={0x7da40,0x82908}
 def code(uc,a,n,_):
  if a in stop:state['boundary']=a;uc.emu_stop();return
  if not any(lo<=a and a+n<=hi for lo,hi in [(0x828f2,0x82908),(0x8294c,0x82993)]):raise ValueError('BRANCH_HELPER_NOT_ALLOWED:'+hex(a))
 def write(uc,access,a,n,v,_):
  if STACK-4<=a and a+n<=STACK:return
  if a!=INTENT or n!=2:raise ValueError('BRANCH_STATE_ESCAPE')
  writes.append((a,n,v&65535))
 u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
 u.emu_start(0x828f2,0x4000f000,timeout=100000,count=50)
 negative=(turn_argument&65535)==65534
 if writes!=[(INTENT,2,65534 if negative else 2)] or state['boundary']!=(0x82908 if negative else 0x7da40):raise ValueError('TURN_BRANCH')
 return {'input_argument':turn_argument,'intent':-2 if negative else 2,'boundary':hex(state['boundary']),'animation_loop_not_executed':True,'pass':True}

def commit(heading,negative):
 def init(u):u.mem_write(HEADING-2,b'\xa5\xa5'+struct.pack('<h',heading)+b'\xa5\xa5')
 u,writes=invoke(0x82940 if negative else 0x82993,0x829ae,{(HEADING,2)},init)
 expected=(heading+(3 if negative else 1))%4
 if writes!=[(HEADING,2,expected)] or struct.unpack('<h',u.mem_read(HEADING,2))[0]!=expected:raise ValueError('HEADING_TRANSFORM')
 if bytes(u.mem_read(HEADING-2,2))!=b'\xa5\xa5' or bytes(u.mem_read(HEADING+2,2))!=b'\xa5\xa5':raise ValueError('HEADING_NEIGHBOR_CHANGED')
 return {'heading_before':heading,'turn_intent':-2 if negative else 2,'heading_after':expected,'pending_helper':'0x77b50','pass':True}

def main():
 prep=[preparation(g,p) for g,p in itertools.product((0,1,65535),(0,1,65535))]
 branches=[branch(a) for a in (-2,2,0,1,-1,65534)]
 commits=[commit(h,n) for h,n in itertools.product(range(4),(False,True))]
 graph={'schema':'OpenStonekeep.ConditionalTurnStages.v1','source_exe_sha256':EXPECTED_EXE_SHA,
  'preparation':{'prepared':1,'h415_gate':0,'then':'OPAQUE_HELPER_0x9c8b5'},
  'orientation_edges':[{'from':r['heading_before'],'intent':r['turn_intent'],'to':r['heading_after'],
    'requires':['preceding_animation_and_callbacks_completed_without_invalidating_state'],'then':'OPAQUE_HELPER_0x77b50'} for r in commits],
  'not_claimed':['The complete animation executes correctly.','H415 event helper or default continuation is harmless.','The world is free of softlocks.']}
 p=ROOT/'conditional-turn-stage-ir.json'
 with p.open('x',encoding='utf-8') as f:json.dump(graph,f,indent=2,sort_keys=True)
 report={'schema':'OpenStonekeep.OrientationBoundaryMechanisms.v1','status':'PASS','tests':len(prep)+len(branches)+len(commits),'preparation':prep,'branches':branches,'orientation_commits':commits,
  'source_exe_sha256':EXPECTED_EXE_SHA,'stage_ir_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
  'closed_gate':'Exact source preparation clear of the H415 global and the conditional final heading transform are verified with writes/guards.',
  'scope':'Disjoint source stages with explicit pending-helper obligations; not one artificially successful full turn.',
  'negative_case':'Arguments other than -2 take the +2 branch locally; caller validation must restrict the intended API domain rather than assume this function rejects invalid values.',
  'runtime_orientation_verified':False,'game_runtime_executed':False,'next':'Account for inter-stage helper effects before composing these edges into an accepted turn action.',
  'created_at_utc':datetime.now(timezone.utc).isoformat()}
 out=ROOT/'orientation-boundary-verification.json'
 with out.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2,sort_keys=True)
 print(json.dumps({k:v for k,v in report.items() if k not in ('preparation','branches','orientation_commits')},indent=2));print('SHA256',hashlib.sha256(out.read_bytes()).hexdigest())
if __name__=='__main__':main()
