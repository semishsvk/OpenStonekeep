from pathlib import Path
import hashlib,json
from verify_callback import LE_RAW
ROOT=Path(__file__).resolve().parent
assert LE_RAW.read_va(0x3c1ee,9).hex()=='89d083c4085f5e59c3'
p=ROOT/'verify_callback.py';s=p.read_text(encoding='utf-8');assert s.count('(0x3c14d,0x3c1f5)')==1
s=s.replace('(0x3c14d,0x3c1f5)','(0x3c14d,0x3c1f7)')
with (ROOT/'verify_callback_v2.py').open('x',encoding='utf-8') as f:f.write(s)
with (ROOT/'callback-v1-failure.json').open('x',encoding='utf-8') as f:json.dump({'status':'FAIL','reason':'CODE_ESCAPE:0x3c1f5','source_evidence':'Getter epilogue is 89d083c4085f5e59c3, with pop ecx at 0x3c1f5 and ret at 0x3c1f6.','correction':'Whitelist those two verified original epilogue bytes only; no arbitrary helper allowed.','previous_script_sha256':hashlib.sha256(p.read_bytes()).hexdigest()},f,indent=2)
