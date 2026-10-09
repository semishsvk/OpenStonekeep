"""Verify the actual H415 entry routes into the proven conditional delta.
Action 2/3 are explicitly excluded from the direct-common shortcut. The turn
path is source-linked, but unknown post-prefix effects are still not assumed away.
"""
from datetime import datetime,timezone
import hashlib,json,itertools
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.x86_const import *
from verify_callback_v2 import machine,LE_RAW,EXPECTED_EXE_SHA,ROOT,STACK,run
WRAPPER=LE_RAW.read_va(0x4f983,0x51)
DESTINATIONS={2:0x4fb00,3:0x4fb00,15:0x4fa53,31:0x4fc2c,49:0x4faca,56:0x4f9d4}

def route(action):
 u,_=machine();u.mem_write(0x4f983,WRAPPER);u.reg_write(UC_X86_REG_ESP,STACK);u.reg_write(UC_X86_REG_EAX,action)
 result={'target':None,'instructions':0}
 ends={0x4fc57,*DESTINATIONS.values()}
 def code(uc,a,n,_):
  result['instructions']+=1
  if a in ends:result['target']=a;uc.emu_stop();return
  if not 0x4f983<=a or a+n>0x4f9d4:raise ValueError('WRAPPER_CODE_ESCAPE')
 def write(uc,access,a,n,v,_):
  if not STACK-20<=a or a+n>STACK:raise ValueError('WRAPPER_WROTE_NONSTACK_STATE')
 u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
 u.emu_start(0x4f983,0x60000000,timeout=100000,count=80)
 expected=DESTINATIONS.get(action&65535,0x4fc57)
 if result['target']!=expected or u.reg_read(UC_X86_REG_ESI)!=action:raise ValueError('WRAPPER_ROUTE_MISMATCH')
 return {'action_raw32':action,'action_low16':action&65535,'target':hex(result['target']),'instructions':result['instructions'],'pass':True}

def main():
 routes=[route(a|high) for a in (0,1,2,3,4,5,6,7,8,15,30,31,32,48,49,50,55,56,57,65535) for high in (0,0x12340000)]
 facts=[]
 for action,g,s in itertools.product((4,5,6,8),(0,1,65535),(0,1,2,65535)):
  rr=route(action);delta=run(g,s,action)
  if rr['target']!='0x4fc57':raise ValueError('ACTION_NOT_DIRECT_COMMON')
  facts.append({'input':{'handler':415,'action':action,'global_linear_0x260d9a':g,'cell_23_2_selector5':s},
   'after_prefix':{'cell_23_2_selector5':delta['selector5_after'],'pending':delta['boundary']},
   'sequence':['H415_ENTRY','COMMON_PREFIX',*delta['helper_trace'],delta['boundary']],
   'further_movement_or_turn_authorized':False})
 # Negative control: a graph builder must not classify all movement actions alike.
 if route(2)['target']=='0x4fc57' or route(3)['target']=='0x4fc57':raise ValueError('SPECIAL_MOVEMENT_ROUTE_COLLAPSED')
 graph={'schema':'OpenStonekeep.CallbackDeltaEdgeIR.v1','handler':415,'scope':'ENTRY_TO_POST_DIRECT_DELTA_BOUNDARY',
  'source_exe_sha256':EXPECTED_EXE_SHA,'edges':facts,'unknown_helpers_are_barriers':True,
  'allowed_global_graph_claims':[],'coordinates':{'cell_row':23,'cell_column':2,'selector5_byte_offset':11},
  'negative_evidence':'A prefix with no direct write is not equivalent to a no-effect callback.',
  'action2_3':'Transition-specific branch, not represented by these common-prefix edges.'}
 p=ROOT/'callback-delta-edge-ir.json'
 with p.open('x',encoding='utf-8') as f:json.dump(graph,f,indent=2,sort_keys=True)
 result={'schema':'OpenStonekeep.H415EntryDeltaLink.v1','status':'PASS','tests':len(routes)+len(facts)+1,'entry_route_tests':len(routes),
  'linked_state_edges':len(facts),'routes':routes,'edge_ir_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
  'conclusion':'Actions 4/5/6/8 go directly to the common state-delta prefix. Actions 2/3 take the special transition branch first; merging these into a single movement gate is invalid.',
  'original_runtime_executed':False,'navigation_success_proven':False,'source_exe_sha256':EXPECTED_EXE_SHA,
  'next':'Resolve the post-prefix common continuation separately, preserving the event barrier when the condition is true.',
  'created_at_utc':datetime.now(timezone.utc).isoformat()}
 with (ROOT/'wrapper-delta-verification.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,sort_keys=True)
 print(json.dumps({k:v for k,v in result.items() if k!='routes'},indent=2))
if __name__=='__main__':main()
