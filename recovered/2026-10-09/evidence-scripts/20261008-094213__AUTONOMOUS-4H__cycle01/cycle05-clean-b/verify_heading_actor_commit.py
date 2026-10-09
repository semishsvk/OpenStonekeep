"""Close the post-heading helper using its actual 104-record source loop.
This starts after unverified animation completion and stops before later helpers.
No entity counts are asserted for a live world; 104 is the original fixed loop bound.
"""
from datetime import datetime,timezone
import hashlib,json,struct
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.x86_const import *
from verify_turn_intent import create,STACK,EXPECTED_EXE_SHA,ROOT
from verify_ordinary_turn_envelope import add_ranges
ARRAY,STRIDE,COUNT=0x2871f8,0x111,104;HEADING=0x2ac6ae

def run(heading,negative,pattern):
 u,_=create();add_ranges(u,[(0x82940,0x829b3),(0x77b38,0x77bc9)])
 table=struct.unpack('<4I',u.mem_read(0x77b38,16))
 if set(table)!={0x77ba7,0x77bad}:raise ValueError('UNKNOWN_DIRECTION_DISPATCH')
 before=bytearray((i*37+19)&255 for i in range(COUNT*STRIDE));valid=[]
 for i in range(COUNT):
  pos=i*STRIDE;identifier=(-1,0,1,32767)[(i+pattern)%4];active=(0,1,65535)[(i*3+i//4+pattern)%3]
  struct.pack_into('<h',before,pos,identifier);struct.pack_into('<H',before,pos+0x64,active)
  struct.pack_into('<HH',before,pos+0x14,(1000+i)&65535,(2000+i*3)&65535)
  if identifier>=0 and active:valid.append(i)
 u.mem_write(ARRAY,bytes(before));u.mem_write(HEADING,struct.pack('<h',heading));u.reg_write(UC_X86_REG_ESP,STACK)
 state={'done':False,'instructions':0};writes=[]
 def code(uc,a,n,_):
  state['instructions']+=1
  if a==0x829b3:state['done']=True;uc.emu_stop();return
  if not any(lo<=a and a+n<=hi for lo,hi in [(0x82940,0x8294c),(0x82993,0x829b3),(0x77b50,0x77bc9)]):raise ValueError('HEADING_HELPER_CODE_ESCAPE:'+hex(a))
 def write(uc,access,a,n,v,_):
  if STACK-32<=a and a+n<=STACK:return
  if a==HEADING and n==2:writes.append((a,n,v&65535));return
  idx,rel=divmod(a-ARRAY,STRIDE)
  if not 0<=idx<COUNT or n!=2 or rel not in (0x22,0xcd):raise ValueError('ACTOR_STATE_WRITE_ESCAPE')
  writes.append((a,n,v&65535))
 u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
 u.emu_start(0x82940 if negative else 0x82993,0x4000f000,timeout=150000,count=4000)
 afterheading=(heading+(3 if negative else 1))%4;facing=(afterheading+2)&3;axis=0x16 if table[facing]==0x77ba7 else 0x14
 expected=bytearray(before);expected_writes=[(HEADING,2,afterheading)]
 for i in valid:
  pos=i*STRIDE;dimension=struct.unpack_from('<H',before,pos+axis)[0]
  struct.pack_into('<H',expected,pos+0x22,facing);struct.pack_into('<H',expected,pos+0xcd,dimension)
  expected_writes +=[(ARRAY+pos+0x22,2,facing),(ARRAY+pos+0xcd,2,dimension)]
 if not state['done'] or bytes(u.mem_read(ARRAY,len(before)))!=bytes(expected) or writes!=expected_writes or struct.unpack('<h',u.mem_read(HEADING,2))[0]!=afterheading:raise ValueError('ACTOR_COMMIT_DIFFERENCE')
 return {'heading_before':heading,'turn_intent':-2 if negative else 2,'heading_after':afterheading,'derived_actor_facing':facing,'axis_source_offset':hex(axis),'pattern':pattern,
  'eligible_slots':len(valid),'source_loop_bound':COUNT,'writes':len(writes),'output_sha256':hashlib.sha256(expected).hexdigest(),'instructions':state['instructions'],'pass':True},table

def main():
 cases=[];table=None
 for h in range(4):
  for negative in (False,True):
   for pattern in range(6):r,table=run(h,negative,pattern);cases.append(r)
 result={'schema':'OpenStonekeep.HeadingActorCommit.v1','status':'PASS','tests':len(cases),'cases':cases,'source_exe_sha256':EXPECTED_EXE_SHA,
  'direction_jump_targets':[hex(x) for x in table],'original_fixed_record_loop':{'count':104,'stride':STRIDE},
  'rule':'After committing heading modulo4, original helper updates each eligible record with facing=(heading+2)&3 and the source-selected axis word; slots with signed id<0 or word+0x64==0 remain byte-identical.',
  'gate_closed':'The previously opaque post-heading helper 0x77b50 now executes completely with exact state buffer and write-order verification.',
  'scope':'Post-animation heading+actor-state commit, not proof that preceding animation/callbacks complete correctly.',
  'next':'Validate or explicitly retain the unresolved pre-animation/effect obligations before accepting a full deterministic turn.',
  'runtime_turn_verified':False,'game_runtime_executed':False,'created_at_utc':datetime.now(timezone.utc).isoformat()}
 p=ROOT/'heading-actor-commit-verification.json'
 with p.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,sort_keys=True)
 print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2));print('SHA256',hashlib.sha256(p.read_bytes()).hexdigest())
if __name__=='__main__':main()
