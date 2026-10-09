"""Preserve the v1 trace counterexample; match the original intermediate write6.
Validation still requires exact write order, not only the final modulo6 state.
"""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent
p=ROOT/'verify_frame_prefix_chain.py';s=p.read_text();needle=' store(WORLD_PHASE,(worldphase+1)%6,4);store(INDEX,0 if worldphase==0 else 77,4)'
assert s.count(needle)==1
s=s.replace(needle,' store(WORLD_PHASE,worldphase+1,4)\n if worldphase+1>=6:store(WORLD_PHASE,0,4)\n store(INDEX,0 if worldphase==0 else 77,4)')
s=s.replace("'frame-prefix-chain-verification.json'","'frame-prefix-chain-verification-v2.json'")
s=s.replace("'frame-prefix-counterexample.json'","'frame-prefix-counterexample-v2.json'")
s=s.replace("'OpenStonekeep.FramePrefixStateChain.v1'","'OpenStonekeep.FramePrefixStateChain.v2'")
with (ROOT/'verify_frame_prefix_chain_v2.py').open('x',encoding='utf-8') as f:f.write(s)
with (ROOT/'frame-prefix-v1-supersession.json').open('x',encoding='utf-8') as f:json.dump({'status':'MODEL_TRACE_CORRECTION','prior_script_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
 'counterexample_sha256':hashlib.sha256((ROOT/'frame-prefix-counterexample.json').read_bytes()).hexdigest(),
 'source_evidence':'Original 0x76c15 writes incremented phase6, then 0x76c22 writes0. Collapsing these to a single modulo write changes the execution trace.',
 'scope':'Correct the expected intermediate write, preserving original instructions, guard and exact write-order assertions.'},f,indent=2)
