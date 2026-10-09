#!/usr/bin/env python3
"""Validate STONE-K292-E.12 selection-source evidence for portal producers.

Read-only evidence tool. It binds E.10 payload IDs 0 and 166 to authoritative
starter GAMEINFO/LEVEL01 serialized POJ state and to exact SK.EXE code anchors.
It distinguishes a directly serialized list/UI selection route (ID166) from a
world-render/hit-test/interaction route whose concrete play-state visibility
remains state-qualified (ID0).
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path

EXPECTED_EXE_SHA='5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2'
EXPECTED_LEVEL01_SHA='2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9'
EXPECTED_GAMEINFO_SHA='eef1dd19f7cb0913a3fe5821aa3bf5906a17b2764e61407279b3bda823d075ca'
CELL_SIZE=0x15
POJ_OFFSET=0x24FF
POJ_COUNT=2000
POJ_STRIDE=0x2F
GLOBAL_LIST_HEAD_OFF=0x1B5DD
GLOBAL_LIST_COUNT_OFF=0x1B5DF
HELD_STATE_OFF=0x1B5E1
ACTIVE_SELECTION_OFF=0x1B5E3
UNKNOWN_1B5E5_OFF=0x1B5E5
SCROLL_OFFSET_OFF=0x1B5E7
LIST_END=-4
NONE_SELECTION=-5
VISIBLE_SLOTS=5

REGIONS={
 'poj_cell_render_dispatch':(0x2E210,0x646,'ec044b120e138db42ae56971b09e8a3d7c3eaeda63028a39ee10b95c47c62b94'),
 'poj_render_hitbox':(0x2E860,0x40A,'9ff427dd6d3c3129986ca29d78603a3cf5916739bac8f56f3b37a9b4e2f461e0'),
 'world_hit_test':(0x7E140,0x8A,'7fdd5c3a20a9386533faad6bd100070d76120a20946dfbc1c047cd2b2dd59dec'),
 'world_interaction_to_selection':(0x7DA60,0x4B5,'ccf4492e002acbced5bfc2551ab502ab1cb576f2520c5592c1373671495f43da'),
 'list_stack_split':(0x4A0BC,0x78,'28812f6ef94b1ec3e35cc14b6c37a3566512767c24acd55be137aa46316733a2'),
 'list_nth_remove':(0x496A0,0xD6,'12e5591c29ae8bea95d24b26e9c1e40827bb1456467c9be579eac51b226c5311'),
 'list_select_active':(0x4AF32,0x6B,'f2e96eb25bc88b07003432b2a45528a90ac19332c0dcadec13a91a8ebc2b7975'),
 'list_ui_slot_caller':(0x48734,0x60,'2996ff5cd4d81ae5289722fe2bf683fa131f1445909043062c75375db524ac94'),
 'visible_slots_init':(0xAA783,0x20,'ba070047798acb2821de817c0614b2ba9a2dfa47a42a3515ce309eb68133ace6'),
}

class LE:
    def __init__(self,data:bytes):
        self.data=data
        if data[:2]!=b'MZ': raise ValueError('not MZ')
        self.le=struct.unpack_from('<I',data,0x3c)[0]
        if data[self.le:self.le+2]!=b'LE': raise ValueError('not LE')
        u32=lambda o: struct.unpack_from('<I',data,self.le+o)[0]
        self.page_size=u32(0x28); self.objtab=u32(0x40); self.num_objects=u32(0x44)
        self.objmap=u32(0x48); self.page_off=u32(0x80); self.num_pages=u32(0x14)
        self.objects=[]
        for i in range(self.num_objects):
            size,base,flags,mapidx,mapsize,_=struct.unpack_from('<IIIIII',data,self.le+self.objtab+i*24)
            self.objects.append({'size':size,'base':base,'flags':flags,'mapidx':mapidx,'mapsize':mapsize})
        self.page_map=[]
        for i in range(self.num_pages):
            q=self.le+self.objmap+i*4
            page_num=(data[q]<<16)|(data[q+1]<<8)|data[q+2]
            self.page_map.append((page_num,data[q+3]))
    def object_file_offset(self,objnum:int,off:int)->int:
        o=self.objects[objnum-1]
        if off<0 or off>=o['size']: raise ValueError('object offset out of range')
        local=off//self.page_size
        gp=(o['mapidx']-1)+local
        page_num,flags=self.page_map[gp]
        if flags!=0: raise ValueError(f'unsupported LE page flags {flags}')
        return self.page_off+(page_num-1)*self.page_size+(off%self.page_size)
    def read_runtime(self,va:int,n:int)->bytes:
        out=bytearray(); cur=va; rem=n
        while rem:
            found=None
            for objnum,o in enumerate(self.objects,1):
                if o['base']<=cur<o['base']+o['size']:
                    found=(objnum,o,cur-o['base']); break
            if found is None: raise ValueError(f'VA 0x{cur:X} outside LE objects')
            objnum,o,off=found
            take=min(rem,self.page_size-(off%self.page_size),o['size']-off)
            fo=self.object_file_offset(objnum,off)
            out+=self.data[fo:fo+take]; cur+=take; rem-=take
        return bytes(out)

def s16(b:bytes,off:int)->int: return struct.unpack_from('<h',b,off)[0]

def poj_record(gameinfo:bytes,index:int)->bytes:
    if not 0<=index<POJ_COUNT: raise ValueError('POJ index out of range')
    p=POJ_OFFSET+index*POJ_STRIDE
    r=gameinfo[p:p+POJ_STRIDE]
    if len(r)!=POJ_STRIDE: raise ValueError('truncated POJ record')
    return r

def walk_global_list(gameinfo:bytes,head:int,count:int)->tuple[list[int],int]:
    chain=[]; seen=set(); cur=head
    while cur not in (LIST_END,-1,-100):
        if cur in seen: raise ValueError(f'cycle in global POJ list at {cur}')
        if not 0<=cur<POJ_COUNT: raise ValueError(f'global POJ index out of range: {cur}')
        seen.add(cur); chain.append(cur)
        cur=s16(poj_record(gameinfo,cur),0x18)
        if len(chain)>POJ_COUNT: raise ValueError('global POJ list runaway')
    if len(chain)!=count: raise ValueError(f'global POJ count mismatch: serialized={count} walked={len(chain)}')
    return chain,cur

def parse_level_cells(data:bytes):
    rows,cols=struct.unpack_from('<HH',data,7)
    end=11+rows*cols*CELL_SIZE
    if end>len(data): raise ValueError('truncated LEVEL01 grid')
    cells=[data[11+i*CELL_SIZE:11+(i+1)*CELL_SIZE] for i in range(rows*cols)]
    return rows,cols,cells

def inspect(exe:Path,level01:Path,gameinfo:Path)->dict:
    errors=[]
    eb=exe.read_bytes(); lb=level01.read_bytes(); gb=gameinfo.read_bytes()
    esha=hashlib.sha256(eb).hexdigest(); lsha=hashlib.sha256(lb).hexdigest(); gsha=hashlib.sha256(gb).hexdigest()
    if esha!=EXPECTED_EXE_SHA: errors.append('unexpected SK.EXE SHA-256')
    if lsha!=EXPECTED_LEVEL01_SHA: errors.append('unexpected LEVEL01 SHA-256')
    if gsha!=EXPECTED_GAMEINFO_SHA: errors.append('unexpected GAMEINFO.SAV SHA-256')
    if POJ_OFFSET+POJ_COUNT*POJ_STRIDE>len(gb): errors.append('GAMEINFO too small for POJ pool')
    le=LE(eb)
    regions={}
    for name,(va,n,expected) in REGIONS.items():
        got=hashlib.sha256(le.read_runtime(va,n)).hexdigest(); ok=got==expected
        regions[name]={'runtime_va':hex(va),'size':n,'sha256':got,'pass':ok}
        if not ok: errors.append(f'region hash mismatch: {name}')

    rows,cols,cells=parse_level_cells(lb)
    r79=poj_record(gb,79); r162=poj_record(gb,162)
    cell79=(18,20); c79=cells[cell79[0]*cols+cell79[1]]
    id0={
      'record_index':79,'record_id':s16(r79,0),'record_row':s16(r79,6),'record_col':s16(r79,8),
      'record_prev':s16(r79,0x16),'record_next':s16(r79,0x18),'cell':[18,20],
      'cell_poj_head':s16(c79,0x0d),'cell_handler':s16(c79,0x07),
      'cell_selector4':s16(c79,0x09),'cell_selector5':s16(c79,0x0b),
      'placement_verified':False,
      'selection_mechanism':'cell+0x0D -> renderer POJ chain -> clickable POJ index -> screen hit-test 0x7E140 -> 0x1BC496 -> 0x7DA60 interaction -> 0x1BC6A8',
      'reachability_class':'WORLD_RENDER_INTERACTION_STATE_QUALIFIED',
    }
    id0['placement_verified']=(id0['record_id']==0 and id0['record_row']==18 and id0['record_col']==20 and id0['cell_poj_head']==79)
    if not id0['placement_verified']: errors.append('ID0 record79 placement mismatch')
    if s16(poj_record(gb,80),0x16)!=79: errors.append('record80 does not backlink to record79')

    head=s16(gb,GLOBAL_LIST_HEAD_OFF); count=s16(gb,GLOBAL_LIST_COUNT_OFF)
    held=s16(gb,HELD_STATE_OFF); active=s16(gb,ACTIVE_SELECTION_OFF); scroll=s16(gb,SCROLL_OFFSET_OFF)
    try: chain,end=walk_global_list(gb,head,count)
    except Exception as e: chain=[]; end=None; errors.append(str(e))
    n162=chain.index(162) if 162 in chain else None
    slot162=(n162-scroll+1) if n162 is not None else None
    id166={
      'record_index':162,'record_id':s16(r162,0),'record_row':s16(r162,6),'record_col':s16(r162,8),
      'record_prev':s16(r162,0x16),'record_next':s16(r162,0x18),'record_stack_count':s16(r162,0x1a),
      'global_list_head':head,'global_list_count':count,'global_list_end':end,
      'global_list_index':n162,'serialized_scroll_offset':scroll,'ui_slot':slot162,
      'visible_slots':VISIBLE_SLOTS,'serialized_active_selection':active,'serialized_held_state':held,
      'list_membership_verified':n162 is not None,
      'ui_slot_reachable':bool(slot162 is not None and 1<=slot162<=VISIBLE_SLOTS),
      'selection_mechanism':'UI slot -> n=(slot-1)+scroll -> 0x4AF32 -> 0x496A0 nth global-list POJ -> 0x1BC6A8',
      'reachability_class':'SERIALIZED_LIST_INPUT_REACHABLE',
    }
    if id166['record_id']!=166: errors.append('record162 ID is not 166')
    if (id166['record_row'],id166['record_col'])!=(-1,-1): errors.append('record162 expected off-grid coordinates')
    if head!=120 or count!=16 or end!=LIST_END: errors.append('serialized global POJ list state mismatch')
    if active!=NONE_SELECTION or scroll!=0: errors.append('serialized active/scroll state mismatch')
    if n162!=4 or slot162!=5: errors.append('record162 expected list index4 / UI slot5')
    if not id166['ui_slot_reachable']: errors.append('record162 UI slot is outside visible range')

    return {
      'exe_sha256':esha,'level01_sha256':lsha,'gameinfo_sha256':gsha,
      'poj_pool':{'file_offset':hex(POJ_OFFSET),'record_count':POJ_COUNT,'stride':POJ_STRIDE},
      'global_list_chain':chain,'id0':id0,'id166':id166,'region_validation':regions,
      'selection_semantics':{
        'id0':'mechanism VERIFIED; concrete render visibility/player interaction remains state-qualified',
        'id166':'serialized global-list membership and visible UI slot selection route VERIFIED',
        'e10_payload_coverage':'2/2 serialized source records present; payload166 input-route reachable, payload0 world-interaction-route qualified',
      },
      'level2_starter_save':'NOT_PRESENT_IN_GAME00 / SOURCE_INCOMPLETE',
      'one_way_verdict_authorized':False,'softlock_verdict_authorized':False,
      'errors':errors,'pass':not errors,
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--exe',required=True,type=Path); ap.add_argument('--level01',required=True,type=Path); ap.add_argument('--gameinfo',required=True,type=Path); ap.add_argument('--json',action='store_true')
    a=ap.parse_args(); out=inspect(a.exe,a.level01,a.gameinfo)
    if a.json: print(json.dumps(out,indent=2,sort_keys=True))
    else:
        print(('PASS' if out['pass'] else 'FAIL'),f"regions={len(out['region_validation'])}",f"errors={len(out['errors'])}")
        x=out['id0']; print(f"ID0 record={x['record_index']} cell={x['cell']} head={x['cell_poj_head']} placement={x['placement_verified']} reach={x['reachability_class']}")
        x=out['id166']; print(f"ID166 record={x['record_index']} list_index={x['global_list_index']} slot={x['ui_slot']}/{x['visible_slots']} reachable={x['ui_slot_reachable']} reach={x['reachability_class']}")
    return 0 if out['pass'] else 2
if __name__=='__main__': raise SystemExit(main())
