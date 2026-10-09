"""Retain failed stack guard and permit only the original call's exact return push."""
from pathlib import Path
import json,hashlib
from verify_turn_intent import LE_RAW
ROOT=Path(__file__).resolve().parent
code=LE_RAW.read_va(0x828ed,5)
assert code.hex()=='e8c39f0100'
p=ROOT/'verify_orientation_boundaries.py';s=p.read_text()
old=" def write(uc,access,a,n,v,_):\n  if (a,n) not in write_allowed:raise ValueError('UNDECLARED_TURN_WRITE:'+hex(a))"
new=" def write(uc,access,a,n,v,_):\n  if start==0x828da and a==STACK-4 and n==4 and v==0x828f2:return\n  if (a,n) not in write_allowed:raise ValueError('UNDECLARED_TURN_WRITE:'+hex(a))"
assert s.count(old)==1;s=s.replace(old,new)
s=s.replace("'orientation-boundary-verification.json'","'orientation-boundary-verification-v2.json'")
with (ROOT/'verify_orientation_boundaries_v2.py').open('x',encoding='utf-8') as f:f.write(s)
with (ROOT/'orientation-stack-counterexample.json').open('x',encoding='utf-8') as f:json.dump({'status':'FAIL','old_script_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'reason':'The source call at 0x828ed pushes a return address before reaching the stop boundary.','call_bytes':code.hex(),'permitted_new_write':{'address':'STACK-4','size':4,'value':'0x828f2'},'state_write_rules_unchanged':True,'opaque_helper_executed':False},f,indent=2)
