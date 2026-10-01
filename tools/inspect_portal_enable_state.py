#!/usr/bin/env python3
"""Validate Stonekeep starter portal enable/cancel state machine (K292-E.9).

Read-only evidence tool. It composes:
- E.8 transition source/direction inventory,
- serialized LOW+HIGH edge bits,
- the high-secondary barrier scan,
- action-15 special movement path,
- reciprocal selector-2 LOW clear/set masks,
- E.7 starter per-level no-op callbacks.

It does not claim multi-step reachability beyond the evidenced state machine.
"""
from __future__ import annotations
import argparse, hashlib, json, struct, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_le_handler_dispatch import LE
from inspect_transition_handlers import TRANSITIONS
from inspect_level_callback_hooks import inspect as inspect_level_hooks

EXPECTED_EXE_SHA='5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2'
EXPECTED_SAVE_SHAS={
    1:'2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9',
    15:'3d1753ca8a4ca49b3ccf9da0fc15bb08ac242301eff40586049379ceba635dc9',
}
CELL_SIZE=0x15

LOW=(0x08,0x02,0x04,0x01)          # N W S E
LOW_OPPOSITE=(0x04,0x01,0x08,0x02)
HIGH=(0x80,0x20,0x40,0x10)
HIGH_OPPOSITE=(0x40,0x10,0x80,0x20)
CLEAR_MASK=tuple((~x)&0xff for x in LOW)
SET_MASK=LOW
DIR_DELTA=((-1,0),(0,-1),(1,0),(0,1))

MASK_OBJECT=3
CLEAR_MASK_OFFSET=0xFCD5
SET_MASK_OFFSET=0xFCD9

REGIONS={
    'high_barrier_scan':(0x13646,181,'ca7a8df7065677a38a0e91324be55048e7e435918bf2c7b78a593755461bd04a'),
    'forward_input_special_dispatch':(0x31770,188,'cec5388f32108ed09856ba03ea35bc61d46a274bd79c9870eb85ea5a4b457fe4'),
    'portal_open_action15_path':(0x2CE8B,709,'aff41406e904486137b74adc4bb7115dba2ffacf5a88274db21ea93b2f9a3f0d'),
    'portal_cancel_reclose_path':(0x2D150,425,'0c2b059e2103ac28d64a88ac716db9fa71060ac4fc56860ce464f261549d697c'),
    'transition_handler_family':(0x3CFEE,154,'36a2889a901c1c4be9c5f4b88868942e9226d6d779ddffb9b21478958b8fb7fa'),
    'default_callback_chain':(0x3D4F5,13,'31df3bff112887d59319063795e39acb86572dc47835dd26d6f2b480b723e315'),
}

STATE_MACHINE={
    'CLOSED_SPECIAL':{
        'serialized_requirement':'source and reciprocal edge each have LOW+HIGH direction bits',
        'forward_detection':'0x13646 sees immediate LOW wall, stores matching HIGH in 0x1BC4E4 and returns distance 0',
    },
    'OPENING':{
        'entry':'forward input diverts to 0x2CE8B when 0x1BC4E4!=0, distance 0, 0x1BC4E2==0',
        'handler_action':15,
        'mutation':'selector2 AND CLEAR_MASK on source and reciprocal adjacent edge',
        'special_state':1,
    },
    'OPEN_ARMED':{
        'after_open_animation_state':2,
        'handler_action':16,
        'edge':'LOW clear on both sides; HIGH marker preserved',
    },
    'FORWARD_COMMIT':{
        'next_forward':'ordinary path because immediate LOW edge is clear',
        'pre_action':3,
        'armed_state_transition':'0x1BC4E2 2 -> 4 before ordinary translation',
        'translation':'ordinary forward primitive',
        'post_action':2,
        'result':'E.8 level-transfer payload/event path',
    },
    'CANCEL_RECLOSE':{
        'entry':'input branches that see 0x1BC4E2==2 call 0x2D150',
        'handler_pre_action':17,
        'mutation':'selector2 OR SET_MASK on source and reciprocal adjacent edge',
        'intermediate_state':3,
        'final_state':0,
        'handler_post_action':18,
        'edge':'LOW restored on both sides; HIGH marker preserved',
    },
}

def read_runtime(le:LE,va:int,n:int)->bytes:
    out=bytearray(); cur=va; rem=n
    while rem:
        found=None
        for objnum,o in enumerate(le.objects,1):
            if o['base']<=cur<o['base']+o['size']:
                found=(objnum,o,cur-o['base']); break
        if found is None:
            raise ValueError(f'VA 0x{cur:X} outside LE objects')
        objnum,o,off=found
        take=min(rem,le.page_size-(off%le.page_size),o['size']-off)
        fo=le.object_file_offset(objnum,off)
        out+=le.data[fo:fo+take]
        cur+=take; rem-=take
    return bytes(out)

def object_bytes(le:LE,objnum:int,off:int,n:int)->bytes:
    out=bytearray(); rem=n; cur=off
    while rem:
        take=min(rem,le.page_size-(cur%le.page_size))
        fo=le.object_file_offset(objnum,cur)
        out+=le.data[fo:fo+take]
        cur+=take; rem-=take
    return bytes(out)

def read_save(path:Path):
    b=path.read_bytes(); rows,cols=struct.unpack_from('<HH',b,7)
    end=11+rows*cols*CELL_SIZE
    if end>len(b): raise ValueError('truncated save')
    cells=[b[11+i*CELL_SIZE:11+(i+1)*CELL_SIZE] for i in range(rows*cols)]
    return b,rows,cols,cells

def portal_marker_record(level,h,row,col,didx,cells,rows,cols):
    dr,dc=DIR_DELTA[didx]; nr,nc=row+dr,col+dc
    if not (0<=nr<rows and 0<=nc<cols): raise ValueError('portal neighbor out of bounds')
    src=cells[row*cols+col][2]; dst=cells[nr*cols+nc][2]
    return {
        'source_level':level,'handler_id':h,'source':[row,col],
        'direction_index':didx,'adjacent':[nr,nc],
        'source_cell02':src,'adjacent_cell02':dst,
        'source_low':bool(src&LOW[didx]),
        'source_high':bool(src&HIGH[didx]),
        'adjacent_low':bool(dst&LOW_OPPOSITE[didx]),
        'adjacent_high':bool(dst&HIGH_OPPOSITE[didx]),
        'special_marker_reciprocal':bool(
            (src&LOW[didx]) and (src&HIGH[didx]) and
            (dst&LOW_OPPOSITE[didx]) and (dst&HIGH_OPPOSITE[didx])
        ),
    }

def inspect(exe:Path,level01:Path,level01a:Path):
    data=exe.read_bytes(); sha=hashlib.sha256(data).hexdigest(); errors=[]
    if sha!=EXPECTED_EXE_SHA: errors.append('unexpected SK.EXE SHA-256')
    le=LE(data)

    clear=tuple(object_bytes(le,MASK_OBJECT,CLEAR_MASK_OFFSET,4))
    setm=tuple(object_bytes(le,MASK_OBJECT,SET_MASK_OFFSET,4))
    if clear!=CLEAR_MASK: errors.append(f'clear-mask table mismatch: {clear}')
    if setm!=SET_MASK: errors.append(f'set-mask table mismatch: {setm}')

    regions={}
    for name,(va,n,expected) in REGIONS.items():
        got=hashlib.sha256(read_runtime(le,va,n)).hexdigest(); ok=got==expected
        regions[name]={'runtime_va':hex(va),'size':n,'sha256':got,'pass':ok}
        if not ok: errors.append(f'region hash mismatch: {name}')

    hook=inspect_level_hooks(exe)
    if not hook.get('pass'): errors.append('E.7 level-hook validation failed')
    for name in ('level01','level01a'):
        if not hook.get('starter_callbacks',{}).get(name,{}).get('callback_entry_is_ret'):
            errors.append(f'{name}: global callback is not verified RET')

    saves={}
    for lvl,p in ((1,level01),(15,level01a)):
        b,rows,cols,cells=read_save(p); got=hashlib.sha256(b).hexdigest()
        if got!=EXPECTED_SAVE_SHAS[lvl]: errors.append(f'level {lvl}: unexpected save SHA-256')
        saves[lvl]=(rows,cols,cells,got)

    markers=[]
    for t in TRANSITIONS:
        lvl,h,row,col,didx,*_=t
        rows,cols,cells,_=saves[lvl]
        rec=portal_marker_record(lvl,h,row,col,didx,cells,rows,cols)
        if not rec['special_marker_reciprocal']:
            errors.append(f'level {lvl} handler {h}: LOW+HIGH marker not reciprocal')
        markers.append(rec)

    return {
        'exe_sha256':sha,
        'save_sha256':{str(k):v[3] for k,v in saves.items()},
        'mask_tables':{
            'clear_object_offset':hex(CLEAR_MASK_OFFSET),
            'clear':list(clear),'expected_clear':list(CLEAR_MASK),
            'set_object_offset':hex(SET_MASK_OFFSET),
            'set':list(setm),'expected_set':list(SET_MASK),
        },
        'transition_portal_count':len(markers),
        'reciprocal_low_high_marker_count':sum(x['special_marker_reciprocal'] for x in markers),
        'portal_markers':markers,
        'starter_global_callbacks':{
            name:{
                'callback_runtime':hook['starter_callbacks'][name].get('callback_runtime'),
                'entry_is_ret':hook['starter_callbacks'][name].get('callback_entry_is_ret'),
            } for name in ('level01','level01a')
        },
        'region_validation':regions,
        'state_machine':STATE_MACHINE,
        'action_semantics':{
            'transition_family_actions_15_16_17_18':
                'fall through 0x3CFEE -> 0x3D4F5; E.7 starter global callback is RET; default handler returns 1',
            'action15_return_gate':'ALLOW_VERIFIED',
            'action17_return_gate':'ALLOW_VERIFIED',
        },
        'errors':errors,'pass':not errors,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--exe',type=Path,required=True)
    ap.add_argument('--level01',type=Path,required=True)
    ap.add_argument('--level01a',type=Path,required=True)
    ap.add_argument('--json',action='store_true')
    a=ap.parse_args(); out=inspect(a.exe,a.level01,a.level01a)
    if a.json: print(json.dumps(out,indent=2,sort_keys=True))
    else:
        print(('PASS' if out['pass'] else 'FAIL'),
              f"portals={out['transition_portal_count']} reciprocal_low_high={out['reciprocal_low_high_marker_count']} "
              f"regions={len(out['region_validation'])} errors={len(out['errors'])}")
        print('clear_masks=',out['mask_tables']['clear'],'set_masks=',out['mask_tables']['set'])
    return 0 if out['pass'] else 2

if __name__=='__main__':
    raise SystemExit(main())
