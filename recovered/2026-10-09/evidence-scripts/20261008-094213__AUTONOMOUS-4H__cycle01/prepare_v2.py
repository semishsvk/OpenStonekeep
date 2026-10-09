"""Preserve failed preflight script; read the observed UTF-16 BOM correctly."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent
p=ROOT/'prepare_lane.py';s=p.read_text(encoding='utf-8')
s=s.replace("with (ROOT/'source_manifest.py').open('xb') as f:f.write(source.read_bytes())", "assert (ROOT/'source_manifest.py').read_bytes()==source.read_bytes()")
s=s.replace("callbacks=json.loads((BASE/'e17_callbacks.json').read_text())", "cb=(BASE/'e17_callbacks.json').read_bytes(); assert cb.startswith(b'\\xff\\xfe'); callbacks=json.loads(cb.decode('utf-16'))")
with (ROOT/'prepare_lane_v2.py').open('x',encoding='utf-8') as f:f.write(s)
with (ROOT/'preflight-encoding-failure.json').open('x',encoding='utf-8') as f:json.dump({'status':'FAIL','stage':'preflight_json_decode','reason':'UTF-16 BOM ff fe was not decoded by implicit UTF-8','repair':'Explicit observed encoding; unchanged evidence bytes and semantic assertions.','previous_script_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'repairs_without_new_evidence':0},f,indent=2)
