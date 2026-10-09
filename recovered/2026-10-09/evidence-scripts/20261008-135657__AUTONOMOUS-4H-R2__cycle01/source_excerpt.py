"""Anchored bounded LE code observation with actual relocation values."""
from pathlib import Path
import argparse,json,hashlib
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from verify_turn_intent import create,LE_RAW,EXPECTED_EXE_SHA,ROOT
from verify_ordinary_turn_envelope import add_ranges

def main():
 p=argparse.ArgumentParser();p.add_argument('start',type=lambda s:int(s,0));p.add_argument('size',type=lambda s:int(s,0));a=p.parse_args()
 if not 1<=a.size<=4096:raise ValueError('CODE_BUDGET')
 u,_=create();add_ranges(u,[(a.start,a.start+a.size)]);fixed=bytes(u.mem_read(a.start,a.size));raw=LE_RAW.read_va(a.start,a.size)
 rows=[{'va':hex(i.address),'bytes':i.bytes.hex(),'op':i.mnemonic+' '+i.op_str} for i in Cs(CS_ARCH_X86,CS_MODE_32).disasm(fixed,a.start)]
 report={'schema':'OpenStonekeep.RelocatedCodeObservation.v1','source_exe_sha256':EXPECTED_EXE_SHA,'start':hex(a.start),'bytes':a.size,
  'raw_sha256':hashlib.sha256(raw).hexdigest(),'relocated_sha256':hashlib.sha256(fixed).hexdigest(),'raw_hex':raw.hex(),'relocated_hex':fixed.hex(),'instructions':rows,
  'claim':'Observation only; call target alignment must be justified by the calling-source evidence.'}
 path=ROOT/f'lecode_{a.start:x}_{a.size:x}.json'
 with path.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2,sort_keys=True)
 print('EVIDENCE',str(path),'SHA256',hashlib.sha256(path.read_bytes()).hexdigest())
 for i in rows[:75]:print(i['va'],i['op'])
 print('CALLS_AND_RET',[(i['va'],i['op']) for i in rows if i['op'].startswith(('call ','ret'))])
if __name__=='__main__':main()
