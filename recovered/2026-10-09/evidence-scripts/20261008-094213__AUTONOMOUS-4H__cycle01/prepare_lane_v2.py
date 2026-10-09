"""Lane B: reconcile E.15/E.17 and isolate one directly evidenced callback delta."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path(__file__).resolve().parent
BASE=Path(r'F:\Remaster Framework\work\OpenStonekeep-E16')
EXE=Path(r'F:\Remaster Framework\source\Stonekeep\SK.EXE')
PIN='5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):
 with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,sort_keys=True)
source=BASE/'tools'/'validate_callback_state_delta_manifest.py'
assert (ROOT/'source_manifest.py').read_bytes()==source.read_bytes()
from source_manifest import LEImage,REGIONS
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
assert sha(EXE)==PIN
le=LEImage(EXE.read_bytes());md=Cs(CS_ARCH_X86,CS_MODE_32);regions=[]
for va,n in [(0x4fc57,0x52),(0x3c180,0x174),(0x82899,0x136)]:
 raw=le.read_va(va,n)
 regions.append({'va':hex(va),'bytes_sha256':hashlib.sha256(raw).hexdigest(),'raw_hex':raw.hex(),'instructions':[{'va':hex(i.address),'bytes':i.bytes.hex(),'op':i.mnemonic+' '+i.op_str} for i in md.disasm(raw,va)]})
cb=(BASE/'e17_callbacks.json').read_bytes(); assert cb.startswith(b'\xff\xfe'); callbacks=json.loads(cb.decode('utf-16'))
put(ROOT/'callback-code.json',{'exe_sha256':PIN,'regions':regions})
put(ROOT/'job-contract.json',{'schema':'OpenRemaster.BoundedEvidenceJob.v1','task':'H415_COMMON_CALLBACK_STATE_DELTA',
 'hypothesis':'The conditional selector5=1 to selector5=2 write belongs to turn/movement callback execution, even where the callback ultimately allows traversal.',
 'expected_unlock':'One explicit state dependency for a bounded movement/turn graph; not a global softlock proof.',
 'source_sha256':{str(EXE):PIN,str(source):sha(source),str(BASE/'checkpoints'/'STONE-K292-E.15.md'):sha(BASE/'checkpoints'/'STONE-K292-E.15.md'),str(BASE/'e17_callbacks.json'):sha(BASE/'e17_callbacks.json')},
 'repo_HEAD_observed':'3855836c00e5e446537ca1eac85007ed55e14a48','repo_mutated':False,
 'source_status_inconsistency':'CURRENT_STATUS E.12 is older than E.15 and E.17 artifacts; not restarting E.13.',
 'budget':{'seconds_per_probe':10,'instructions_per_case':3000,'game_runtime_jobs':0},
 'created_at_utc':datetime.now(timezone.utc).isoformat(),'e17_level_count':callbacks.get('level_count')})
print(json.dumps({'source_identity':'PINNED','task':'H415 callback direct-state prefix','e17_level_count':callbacks.get('level_count'),'source_manifest_sha256':sha(source),'regions':[{ 'va':r['va'],'instructions':len(r['instructions'])} for r in regions]}))
