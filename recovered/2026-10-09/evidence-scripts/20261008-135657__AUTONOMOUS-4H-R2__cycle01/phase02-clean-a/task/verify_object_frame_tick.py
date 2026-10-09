"""Original per-frame 64-record object tick, independent word-accurate state model.
Full source function, no substituted helpers. This is a conditional stage reached
by turn-frame0x390e0 only after its earlier world-update helper has returned.
"""
from datetime import datetime,timezone
from itertools import product
import json,struct,hashlib
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.x86_const import *
from verify_turn_intent import create,STACK,STOP,EXPECTED_EXE_SHA,ROOT
from verify_ordinary_turn_envelope import add_ranges
BASE,STRIDE,COUNT=0x2a80f0,0x66,64

def word(b,p):return struct.unpack_from('<H',b,p)[0]
def signed(w):return w if w<32768 else w-65536

def model(initial):
 after=bytearray(initial);writes=[]
 def store(p,v):v&=65535;struct.pack_into('<H',after,p,v);writes.append((BASE+p,2,v))
 for i in range(COUNT):
  p=i*STRIDE;delay=word(after,p+0x47)
  if delay:store(p+0x47,delay-1)
  elif word(after,p+0x43)!=0 and word(after,p)!=65535:
   store(p+4,1);countdown=(word(after,p+0x13)-1)&65535;store(p+0x13,countdown)
   if signed(countdown)<=0:
    store(p+0xf,word(after,p+0xf)+1);store(p+0x13,word(after,p+0x11))
 return bytes(after),writes

def run(initial,repeat=1):
 if len(initial)!=COUNT*STRIDE or not 1<=repeat<=7:raise ValueError('TICK_BUDGET')
 u,_=create();add_ranges(u,[(0x6fd90,0x6fdfa)]);guard=b'\xa5'*16
 u.mem_write(BASE-16,guard+initial+guard);trace=[];state={'returned':False};allhash=[];expected=initial
 def code(uc,a,n,_):
  if a==STOP:state['returned']=True;uc.emu_stop();return
  if not 0x6fd90<=a or a+n>0x6fdfa:raise ValueError('TICK_CODE_ESCAPE')
 def write(uc,access,a,n,v,_):
  if STACK-32<=a and a+n<=STACK:return
  if BASE<=a and a+n<=BASE+len(initial) and n==2:trace.append((a,n,v&65535));return
  raise ValueError('TICK_WRITE_ESCAPE:'+hex(a))
 u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
 preserved={UC_X86_REG_EBX:0x12345678,UC_X86_REG_ECX:0x34567890,UC_X86_REG_EDX:0x56789012,UC_X86_REG_ESI:0x78901234}
 for tick in range(repeat):
  expected,expected_trace=model(expected);trace.clear();state['returned']=False
  for reg,value in preserved.items():u.reg_write(reg,value)
  u.reg_write(UC_X86_REG_ESP,STACK);u.mem_write(STACK,struct.pack('<I',STOP))
  u.emu_start(0x6fd90,STOP+1,timeout=150000,count=2500)
  if not state['returned'] or bytes(u.mem_read(BASE,len(initial)))!=expected or trace!=expected_trace:raise ValueError('OBJECT_TICK_STATE_OR_TRACE_DIFFERENCE')
  if any(u.reg_read(reg)!=v for reg,v in preserved.items()):raise ValueError('TICK_REGISTER_PRESERVATION')
  if bytes(u.mem_read(BASE-16,16))!=guard or bytes(u.mem_read(BASE+len(initial),16))!=guard:raise ValueError('TICK_ARRAY_GUARD')
  allhash.append({'tick':tick+1,'word_writes':len(trace),'state_sha256':hashlib.sha256(expected).hexdigest(),'trace_sha256':hashlib.sha256(json.dumps(trace).encode()).hexdigest()})
 return {'ticks':repeat,'steps':allhash,'pass':True}

def build(configs):
 b=bytearray((i*29+11)&255 for i in range(COUNT*STRIDE))
 for i in range(COUNT):
  delay,active,identity,counter,period,frame=configs[i%len(configs)]
  for o,v in [(0,identity),(0x47,delay),(0x43,active),(0x13,counter),(0x11,period),(0xf,frame)]:struct.pack_into('<H',b,i*STRIDE+o,v)
 return bytes(b)

def main():
 matrix=list(product((0,1,2,65535),(0,1,65535),(0,65535,65534),(0,1,2,32768,65535),(0,1,7,65535),(0,65535)))
 cases=[]
 for at in range(0,len(matrix),COUNT):
  batch=matrix[at:at+COUNT];case=run(build(batch));case.update(case='field-matrix-'+str(at),distinct_record_fixtures=len(batch));cases.append(case)
 for cfgs in [[(0,1,0,1,3,0),(0,1,7,0,0,65535),(7,1,0,1,2,0)],[(0,0,0,0,0,0)],[(0,1,65535,1,1,0)]]:
  cases.append(dict(run(build(cfgs),7),case='seven-frame-conditional-sequence'))
 one=build([(0,1,5,1,1,65535)]);after,_=model(one)
 assert word(after,0xf)==0 and word(after,0x13)==1
 cases.append({'case':'word_overflow_negative_control','pass':True,'phase_wraps_to_zero':True})
 report={'schema':'OpenStonekeep.ObjectFrameTick.v1','status':'PASS','tests':len(cases),'cases':cases,
  'distinct_record_parameter_combinations':len(matrix),'source_exe_sha256':EXPECTED_EXE_SHA,
  'function':'0x6fd90..0x6fdfa','table':'64 records at linear0x2a80f0, stride0x66',
  'rules':{'nonzero_delay_at_0x47':'Decrement exactly one 16-bit word; do not process the phase countdown this tick.',
   'no_delay':'If active word+0x43 is nonzero and signed identity+0 is not -1, write word+4=1 and decrement countdown+0x13.',
   'countdown_expired':'Signed16 after-decrement <=0 increments phase+0xf modulo65536 and reloads countdown from period+0x11.'},
  'new_dependency':'Turn-frame calls can advance persistent object timers/phase, not only camera orientation. Seven frame requests conditionally induce seven ticks, never one implicit tick.',
  'condition_before_stage':'The earlier 0x76be0 world-update helper must return; this proof does not stub it or prove its completion.',
  'source_game_state_fixture':'Synthetic combinations preserve field widths; not a live save-state snapshot.',
  'full_turn_verified':False,'game_runtime_executed':False,'fidelity_verified':False,
  'next':'Resolve earlier world-update obligations or preserve them explicitly when composing the per-frame state chain.',
  'created_at_utc':datetime.now(timezone.utc).isoformat()}
 p=ROOT/'object-frame-tick-verification.json'
 with p.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2,sort_keys=True)
 print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2));print('SHA256',hashlib.sha256(p.read_bytes()).hexdigest())
if __name__=='__main__':main()
