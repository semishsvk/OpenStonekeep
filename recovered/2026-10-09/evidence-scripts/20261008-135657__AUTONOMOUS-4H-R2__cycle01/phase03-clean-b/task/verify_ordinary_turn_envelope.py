"""Three-level ordinary turn-action state envelope with real source environment tables.
Source RET callback -> intent write -> real cell getter -> environment selection.
Stops at any external effect/region helper; no opaque helper is assumed successful.
"""
from datetime import datetime,timezone
from collections import Counter
import hashlib,json,struct
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.x86_const import *
from verify_turn_intent import create,LE_RAW,LF,EXPECTED_EXE_SHA,ROOT,STACK,STOP,INTENT,CALLBACK,SUPPRESS
GRID=0x50000000
LEVELS={1:('LEVEL01',0x5e867),2:('LEVEL02',0x6005e),15:('LEVEL01A',0x4f861)}

def data_for(level):
 pair=struct.unpack('<hh',LE_RAW.read_va(0xfe9ae+level*4,4))
 off=0xf0b2+level*4;page,s=LF.page_for_object_offset(3,off)
 fs=[f for f in LF.parse_fixup_page(page) if s in f['sources']]
 if len(fs)!=1 or fs[0]['target_kind']!=0 or fs[0]['type']&15!=7:raise ValueError('REGION_POINTER_FIXUP')
 f=fs[0];base=LF.objects[f['target_object']-1]['base']+f['target_offset'];regions=[]
 for j in range(128):
  raw=LE_RAW.read_va(base+j*12,12);v=struct.unpack('<6h',raw)
  if v[0]==-1:return pair,base,regions,LE_RAW.read_va(base,12*(j+1))
  if v[0]>v[2] or v[1]>v[3]:raise ValueError('SOURCE_RECTANGLE_INVALID')
  regions.append(v)
 raise ValueError('MISSING_REGION_SENTINEL')

def add_ranges(u,ranges):
 for a,b in ranges:u.mem_write(a,LE_RAW.read_va(a,b-a))
 for obj in LF.objects:
  for lp in range(obj['mapsize']):
   base=obj['base']+lp*LF.page_size
   if not any(a<base+LF.page_size and base<b for a,b in ranges):continue
   for f in LF.parse_fixup_page(obj['mapidx']-1+lp):
    for so in f['sources']:
     p=base+so
     if not any(a<=p and p+4<=b for a,b in ranges):continue
     if f['type']&15!=7 or f['target_kind']!=0 or f['target_offset'] is None:raise ValueError('UNSUPPORTED_EXTRA_FIXUP')
     target=LF.objects[f['target_object']-1]['base']+f['target_offset'];u.mem_write(p,struct.pack('<I',target))

def run(level,action,row,col,flag,cache):
 pair,base,regions,rawregions=data_for(level)
 if not 0<=row<32 or not 0<=col<32:raise ValueError('GRID_FIXTURE_DOMAIN')
 u,_=create();ranges=[(0x3c0c9,0x3c1f7),(0x3d35e,0x3d454),(0xfe9ae,0xfe9ae+88),(0xff0b2,0xff0b2+88),(base,base+len(rawregions)),(LEVELS[level][1],LEVELS[level][1]+1)]
 add_ranges(u,ranges);u.mem_map(GRID,0x8000)
 source_grid=bytearray(32*32*21);source_grid[(row*32+col)*21]=flag;u.mem_write(GRID,bytes(source_grid))
 for p,v in [(0xfcd0d,GRID),(SUPPRESS,0),(CALLBACK,LEVELS[level][1])]:u.mem_write(p,struct.pack('<I',v))
 for p,v in [(0x2ac698,row),(0x2ac69a,col),(0x2ac6a0,level)]:u.mem_write(p,struct.pack('<h',v))
 u.mem_write(0x2a9df8,struct.pack('<32h',*[i*32 for i in range(32)]));u.mem_write(0x2a9d58,struct.pack('<hh',*cache))
 u.mem_write(INTENT,struct.pack('<h',77));u.mem_write(STACK,struct.pack('<I',STOP));u.reg_write(UC_X86_REG_ESP,STACK);u.reg_write(UC_X86_REG_EAX,action)
 state={'end':None,'instructions':0};trace=[];writes=[]
 def code(uc,a,n,_):
  state['instructions']+=1
  if a==STOP:state['end']='ORDINARY_STAGE_RETURNED';uc.emu_stop();return
  if a==0x81d73:state['end']='EXTERNAL_EFFECT_PENDING';state['effect_argument']=uc.reg_read(UC_X86_REG_EAX);uc.emu_stop();return
  if a==0x3d454:state['end']='REGION_HELPER_PENDING';state['region_index']=uc.reg_read(UC_X86_REG_EAX);uc.emu_stop();return
  if a==0x3c14d:trace.append('SOURCE_CELL_GETTER')
  if a==LEVELS[level][1]:trace.append('SOURCE_LEVEL_RET_CALLBACK')
  if not any(lo<=a and a+n<=hi for lo,hi in [(0x3d4f5,0x3d502),(0x3c36a,0x3c4bd),(0x3d35e,0x3d454),(0x3c14d,0x3c1f7),(LEVELS[level][1],LEVELS[level][1]+1)]):raise ValueError('ORDINARY_CODE_ESCAPE:'+hex(a))
 def write(uc,access,a,n,v,_):
  if STACK-128<=a and a+n<=STACK:return
  if (a==INTENT or a in (0x2a9d58,0x2a9d5a)) and n==2:writes.append((a,n,v&65535));return
  raise ValueError('UNDECLARED_STATE_WRITE:'+hex(a))
 u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
 u.emu_start(0x3d4f5,STOP+1,timeout=200000,count=2000)
 expected='ORDINARY_STAGE_RETURNED';effect=None;region=None
 if flag&2:
  region=next((i for i,r in enumerate(regions) if r[0]<=col<=r[2] and r[1]<=row<=r[3]),None)
  if region is not None:expected='REGION_HELPER_PENDING'
 else:
  effect=next((v for v,old in zip(pair,cache) if v!=-1 and v!=old),None)
  if effect is not None:expected='EXTERNAL_EFFECT_PENDING'
 want=2 if action==6 else -2
 if state['end']!=expected or struct.unpack('<h',u.mem_read(INTENT,2))[0]!=want:raise ValueError('MODEL_OR_INTENT_DIFFERENCE')
 if effect is not None and state.get('effect_argument')!=effect:raise ValueError('EFFECT_ARGUMENT')
 if region is not None and state.get('region_index')!=region:raise ValueError('REGION_INDEX')
 if trace!=['SOURCE_LEVEL_RET_CALLBACK','SOURCE_CELL_GETTER'] or writes[0]!=(INTENT,2,want&65535):raise ValueError('CALL_ORDER_OR_INTENT_WRITE')
 if bytes(u.mem_read(GRID,len(source_grid)))!=bytes(source_grid):raise ValueError('SOURCE_CELL_GRID_MUTATION')
 if expected=='ORDINARY_STAGE_RETURNED' and u.reg_read(UC_X86_REG_EAX)!=1:raise ValueError('RETURN_VALUE')
 return {'level':level,'action':action,'cell':[row,col],'cell_flag':flag,'cache_pair':cache,'intent':want,'boundary':state['end'],'trace':trace,'writes':writes,'instructions':state['instructions'],'pass':True}

def main():
 cases=[];metadata=[]
 for level,(name,callback) in LEVELS.items():
  pair,base,regions,raw=data_for(level)
  positions={(0,0),(31,31),(23,2)}
  for xmin,ymin,xmax,ymax,*_ in regions:
   positions|={(r,c) for r,c in [(ymin,xmin),(ymax,xmax),(ymin-1,xmin),(ymax+1,xmax)] if 0<=r<32 and 0<=c<32}
  for action in (6,8):
   for row,col in sorted(positions):
    for flag in (0,2):
     for cache in [pair,(-1,-1)]:cases.append(run(level,action,row,col,flag,cache))
  metadata.append({'level':level,'name':name,'callback':hex(callback),'pair':pair,'region_base':hex(base),'region_records':regions,'source_region_sha256':hashlib.sha256(raw).hexdigest()})
 result={'schema':'OpenStonekeep.OrdinaryTurnEnvelope.v1','status':'PASS','tests':len(cases),'cases':cases,'source_exe_sha256':EXPECTED_EXE_SHA,
  'level_metadata':metadata,'boundary_counts':dict(Counter(r['boundary'] for r in cases)),
  'closed_gate':'Source-level RET callback, turn-intent store, source cell getter and per-level environment-table selection are linked end-to-end for declared fixtures.',
  'negative_gate':'A changed effect id or a matching special region stops at an explicit opaque-helper boundary; no movement success is inferred.',
  'scope':'Three-level ordinary-action envelope with source tables and synthetic current-cell/cache state; not the complete H415 callback/event/animation chain.',
  'grid_fixture':'Only current-cell flag is varied in a synthetic 32x32 grid; no claim these are actual save states.',
  'native_game_executed':False,'full_turn_orientation_verified':False,'softlock_freedom_verified':False,
  'next':'Bind the downstream animation/orientation consumer to verified intent states; retain pending effect obligations.',
  'created_at_utc':datetime.now(timezone.utc).isoformat()}
 p=ROOT/'ordinary-turn-envelope-verification.json'
 with p.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,sort_keys=True)
 print(json.dumps({k:v for k,v in result.items() if k not in ('cases','level_metadata')},indent=2))
 print('SHA256',hashlib.sha256(p.read_bytes()).hexdigest())
if __name__=='__main__':main()
