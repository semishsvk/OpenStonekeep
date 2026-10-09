"""Typed conditional turn contract from sealed source proofs, not a fake playable graph.
Known stages and unverified inter-stage effects stay distinct. A local PASS never
silently converts a pending callback/animation into a no-op edge.
"""
from pathlib import Path
from datetime import datetime,timezone
import copy,hashlib,json,itertools
ROOT=Path(__file__).resolve().parent
PINS={'callback-verification.json':'3ef8e4567654069b59c57eec6af3a32354092518e76cc99c73c013fd4ddb9e4c',
 'wrapper-delta-verification.json':'1d9f57d0045b519b95db406575e0144b7f9da88c9ecae15a2c52196361bef25d',
 'turn-admission-verification.json':'6d36e7b70ca6e372c0ab7fe1e8e68284f942c4a922861350ad956437a3897062',
 'turn-first-frame-verification.json':'9f13a1bf1b24a76fe5758618f3216053c5000c7223c825fbde0381ae15cae240',
 'heading-actor-commit-verification.json':'b4d6cf6a68e54d1bbada072ed23d42bc42f05020a0e7bc1e59234854b2858d42'}
UNRESOLVED={'ORIGINAL_FRAME_ROUTINE','EVENT_PUMP_COMPLETION','AUDIO_OR_RESOURCE_EFFECTS','H415_EVENT_HELPER','H415_COMMON_CONTINUATION'}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def plan(level,action,heading,callback,selector5=0,gate=0):
 if level not in (1,2,15) or action not in (6,8) or heading not in range(4) or callback not in ('ORDINARY_SOURCE_RET','H415') or selector5 not in (0,1,2) or gate not in (0,1):raise ValueError('UNSUPPORTED_STATE_DOMAIN')
 if callback=='H415' and level!=15:raise ValueError('H415_LEVEL_SCOPE_NOT_ESTABLISHED')
 intent=2 if action==6 else -2;after=(heading+(1 if intent==2 else 3))%4
 common={'level':level,'action':action,'heading':heading,'callback_kind':callback,'input_selector5':selector5,'input_h415_gate':gate,
  'runtime_accepted':False,'runtime_verified':False,'source_proofs':dict(PINS)}
 if callback=='H415':
  event=gate!=0 and selector5==1
  common.update(prefix={'selector5_after':2 if event else selector5,'pending':'H415_EVENT_HELPER' if event else 'H415_COMMON_CONTINUATION'},
   reachable_stage='CALLBACK_BOUNDARY',required_obligations=['H415_EVENT_HELPER' if event else 'H415_COMMON_CONTINUATION'],
   conditional_orientation={'requires':['H415_CALLBACK_ACCEPTED','ORIGINAL_FRAME_ROUTINE','EVENT_PUMP_COMPLETION','AUDIO_OR_RESOURCE_EFFECTS'],'heading_after':after,'intent':intent},
   ordering=['INPUT','H415_STATE_PREFIX','UNRESOLVED_CALLBACK_BOUNDARY'])
 else:
  common.update(prefix={'intent':intent,'preparation_h415_gate':0,'first_frame':0 if intent==2 else 6},
   declared_preconditions=['SOURCE_LEVEL_RET_CALLBACK','CACHED_ENVIRONMENT_EFFECT_IDS','NO_PENDING_RESOURCE_DISPOSAL','QUIET_EFFECT_HANDLES_AND_STATE'],
   reachable_stage='FIRST_FRAME_REQUEST',required_obligations=['ORIGINAL_FRAME_ROUTINE','EVENT_PUMP_COMPLETION','AUDIO_OR_RESOURCE_EFFECTS'],
   conditional_orientation={'requires':['ORIGINAL_FRAME_ROUTINE','EVENT_PUMP_COMPLETION','AUDIO_OR_RESOURCE_EFFECTS'],'heading_after':after,'intent':intent},
   ordering=['INPUT','ORDINARY_CALLBACK','INTENT_STORE','PREPARATION_GATE_CLEAR','FIRST_FRAME_REQUEST','UNRESOLVED_ANIMATION_BOUNDARY'])
 return common

def validate(candidate):
 keys=['level','action','heading','callback_kind','input_selector5','input_h415_gate']
 reference=plan(*[candidate[k] for k in keys[:3]],candidate['callback_kind'],candidate['input_selector5'],candidate['input_h415_gate'])
 if candidate!=reference:raise ValueError('CONTRACT_OR_ORDER_MODIFIED_WITHOUT_SOURCE_PROOF')
 if candidate['runtime_accepted'] or candidate['runtime_verified'] or not candidate['required_obligations']:raise ValueError('UNPROVEN_RUNTIME_PROMOTION')
 if not set(candidate['required_obligations'])<=UNRESOLVED:raise ValueError('UNKNOWN_OBLIGATION')
 return True

def main():
 for p,h in PINS.items():assert sha(ROOT/p)==h and json.loads((ROOT/p).read_text())['status']=='PASS'
 domains=[]
 for level,action,heading in itertools.product((1,2,15),(6,8),range(4)):
  domains.append(plan(level,action,heading,'ORDINARY_SOURCE_RET'))
 for action,heading,selector,gate in itertools.product((6,8),range(4),(0,1,2),(0,1)):
  domains.append(plan(15,action,heading,'H415',selector,gate))
 checks=[]
 for i,p in enumerate(domains):assert validate(p);checks.append({'test':'bounded_state_'+str(i),'pass':True})
 witness=plan(15,6,0,'H415',1,1)
 mutants=[('fake_runtime_acceptance',lambda p:p.__setitem__('runtime_accepted',True)),
  ('drop_pending_event',lambda p:p.__setitem__('required_obligations',[])),
  ('event_becomes_noop',lambda p:p['prefix'].__setitem__('pending','NOOP')),
  ('prep_before_callback',lambda p:p.__setitem__('ordering',['PREPARATION_GATE_CLEAR','H415_STATE_PREFIX'])),
  ('ignore_selector_delta',lambda p:p['prefix'].__setitem__('selector5_after',1)),
  ('fake_heading',lambda p:p['conditional_orientation'].__setitem__('heading_after',2)),
  ('missing_source_fingerprint',lambda p:p['source_proofs'].pop('callback-verification.json'))]
 for name,mutate in mutants:
  bad=copy.deepcopy(witness);mutate(bad)
  try:validate(bad)
  except ValueError:checks.append({'test':name,'pass':True})
  else:raise ValueError('UNSAFE_COMPOSITION_ACCEPTED')
 for params in [(3,6,0,'ORDINARY_SOURCE_RET'),(1,6,4,'ORDINARY_SOURCE_RET'),(1,7,0,'ORDINARY_SOURCE_RET'),(1,6,0,'H415')]:
  try:plan(*params)
  except ValueError:checks.append({'test':'reject_domain_'+str(params),'pass':True})
  else:raise ValueError('UNSUPPORTED_DOMAIN_ACCEPTED')
 graph={'schema':'OpenStonekeep.ConditionalTurnContract.v1','source_proof_sha256':PINS,'bounded_states':domains,
  'runtime_accepted_paths':0,'obligation_policy':'Unknown callbacks, resources, frame routine and event pumps are barriers; conditional orientation is not a traversed path.',
  'source_domains':{'ordinary_levels':[1,2,15],'H415_level':15,'actions':[6,8],'heading':[0,1,2,3]},
  'global_softlock_claim':False,'actual_runtime_state_observed':False}
 out=ROOT/'conditional-turn-contract.json'
 with out.open('x',encoding='utf-8') as f:json.dump(graph,f,indent=2,sort_keys=True)
 report={'schema':'OpenStonekeep.ConditionalTurnContractValidation.v1','status':'PASS','tests':len(checks),'checks':checks,'states':len(domains),
  'evidence_class':'COMPOSITION_AND_FAIL_CLOSED_CONTRACT_VALIDATION','source_proof_sha256':PINS,'contract_sha256':sha(out),
  'new_original_instruction_tests':0,'runtime_paths_accepted':0,'scope':'Preserves and validates the boundary between proven local state transitions and unresolved effects; not a gameplay test.',
  'meaningful_correction':'H415 state must be evaluated before any later preparation clears its gate. Final gate0 cannot retrospectively erase a pending event.',
  'game_runtime_executed':False,'fidelity_verified':False,'next':'Supply original frame/event/resource evidence for the named obligations before promoting a complete turn.',
  'created_at_utc':datetime.now(timezone.utc).isoformat()}
 p=ROOT/'conditional-turn-contract-verification.json'
 with p.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2,sort_keys=True)
 print(json.dumps({k:v for k,v in report.items() if k not in ('checks','source_proof_sha256')},indent=2));print('SHA256',sha(p))
if __name__=='__main__':main()
