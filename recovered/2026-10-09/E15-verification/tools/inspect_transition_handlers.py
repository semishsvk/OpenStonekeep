#!/usr/bin/env python3
"""Validate Stonekeep starter-level transition-handler evidence (K292-E.8).

Read-only evidence tool. It validates the nine currently evidenced transition
handlers against SK.EXE LE relocations, executable code-region hashes and the
authoritative starter-save cell records. It intentionally does NOT infer the
portal unlock mechanism from the transition payload.
"""
from __future__ import annotations
import argparse, hashlib, json, struct, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_le_handler_dispatch import LE

EXPECTED_EXE_SHA='5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2'
EXPECTED_SAVE_SHAS={
    1:'2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9',
    15:'3d1753ca8a4ca49b3ccf9da0fc15bb08ac242301eff40586049379ceba635dc9',
}
CELL_SIZE=0x15
DISPATCH_OBJECT=3
DISPATCH_OFFSET=0xF16A
DIRS={0:('N',-1,0,0x08,0x04),1:('W',0,-1,0x02,0x01),2:('S',1,0,0x04,0x08),3:('E',0,1,0x01,0x02)}
REGIONS={
    'family_3cfee_core':(0x3CFEE,154,'36a2889a901c1c4be9c5f4b88868942e9226d6d779ddffb9b21478958b8fb7fa'),
    'a2ba6_stage_and_queue':(0xA2BA6,342,'a03bb8bb52860e9c44cc312f2ff457f33ad616afbb80e544f285cec6e9f0adba'),
    'a2d76_pretransition_event':(0xA2D76,81,'4dcfb7842bac548ee9f709f7b5bc902cbc249ff266e83b2393a7390475a2b8cf'),
    'a2dc7_transition_payload':(0xA2DC7,88,'357adec0ad8466eb486112cc997b0e4d2b06121305f8a6af74abaf2b74e99399'),
    'event_type8_consumer':(0x853A0,18,'1e8dd943a3aabf61f2798be3d484937759ddd1aba62e4638dbe12be32bc7d06c'),
    'level_loader_transfer_core':(0x5DC10,152,'4c836e0e7baaafdd27b397c913c533ef2ffda126eb1053b57b9a27b1586b94c7'),
    'h87_wrapper':(0x5F3B9,68,'52760f9c70718ddf0244354251a07d600807d3ce02f14f1b012bd3562659e15a'),
    'h88_wrapper':(0x5E868,106,'3d843300c461bbb5a9db99aa32ba3796b7c2d92bb001afd526d6fcdff995d594'),
    'h89_90_wrappers':(0x5E8D2,116,'d5fb61c0bf66ccba53828d002a400b40ce75f13de66736d4fadb3b24a311a44d'),
    'h106_107_wrappers':(0x5F027,203,'70ee5c07364911ae6b2262ca49a719bea429635467b568b676c7d09a5286877b'),
    'h411_413_wrappers':(0x4F8FC,64,'6100553dfc00d4ee5146e48d6354ab5822994ea9c61c666d9527eaa670d5166f'),
}
TRANSITIONS=[
    (1,87,2,3,2,15,3,3,0,0x5F3B9),(1,88,2,25,2,15,3,25,0,0x5E868),
    (1,89,23,3,0,15,22,3,2,0x5E8D2),(1,90,23,25,0,15,22,25,2,0x5E92E),
    (1,106,11,5,0,2,7,2,0,0x5F027),(1,107,7,25,1,2,2,18,1,0x5F08B),
    (15,411,2,3,2,1,3,3,0,0x4F8FC),(15,412,2,25,2,1,3,25,0,0x4F91A),
    (15,413,23,25,0,1,22,25,2,0x4F925),
]

def read_runtime(le,va,n):
    out=bytearray(); remaining=n; cur=va
    while remaining:
        objnum=None
        for i,o in enumerate(le.objects,1):
            if o['base']<=cur<o['base']+o['size']: objnum=i; off=cur-o['base']; break
        if objnum is None: raise ValueError(f'VA 0x{cur:X} outside LE objects')
        take=min(remaining,le.page_size-(off%le.page_size),le.objects[objnum-1]['size']-off)
        fo=le.object_file_offset(objnum,off); out+=le.data[fo:fo+take]
        cur+=take; remaining-=take
    return bytes(out)

def fixup_at(le,objnum,off):
    page,source=le.page_for_object_offset(objnum,off)
    m=[f for f in le.parse_fixup_page(page) if source in f['sources']]
    if len(m)!=1: raise ValueError(f'obj{objnum}+0x{off:X}: fixups={len(m)}')
    return m[0]

def resolve_dispatch(le,h):
    page,base=le.page_for_object_offset(DISPATCH_OBJECT,DISPATCH_OFFSET); src=base+h*4
    m=[f for f in le.parse_fixup_page(page) if src in f['sources']]
    if len(m)!=1: raise ValueError(f'handler {h}: dispatch fixups={len(m)}')
    f=m[0]
    if not ((f['type']&0x0f)==7 and f['target_kind']==0 and f['target_object']==1 and (f['flags']&0x10)):
        raise ValueError(f'handler {h}: unexpected fixup shape')
    return le.objects[0]['base']+f['target_offset']

def parse_save(path:Path):
    b=path.read_bytes(); rows,cols=struct.unpack_from('<HH',b,7); end=11+rows*cols*CELL_SIZE
    if end>len(b): raise ValueError('truncated save grid')
    cells=[b[11+i*CELL_SIZE:11+(i+1)*CELL_SIZE] for i in range(rows*cols)]
    return b,rows,cols,cells

def check_transition_cell(cells,rows,cols,t):
    source_level,h,row,col,didx,target_level,tr,tc,tf,expected_va=t
    name,dr,dc,src_mask,dst_mask=DIRS[didx]; nr,nc=row+dr,col+dc
    if not (0<=row<rows and 0<=col<cols and 0<=nr<rows and 0<=nc<cols): raise ValueError('transition cell outside save grid')
    src=cells[row*cols+col]; dst=cells[nr*cols+nc]; got_h=struct.unpack_from('<h',src,7)[0]
    return {'handler_id':h,'source_level':source_level,'source':[row,col],'direction':name,'direction_index':didx,
            'adjacent':[nr,nc],'target_level':target_level,'staged_destination':[tr,tc,tf],
            'source_handler_observed':got_h,'source_cell02':src[2],'adjacent_cell02':dst[2],
            'source_edge_closed':bool(src[2]&src_mask),'reciprocal_edge_closed':bool(dst[2]&dst_mask),
            'expected_handler_runtime':expected_va}

def inspect(exe:Path,level1:Path,level1a:Path):
    data=exe.read_bytes(); errors=[]; le=LE(data); sha=hashlib.sha256(data).hexdigest()
    if sha!=EXPECTED_EXE_SHA: errors.append('unexpected SK.EXE SHA-256')
    saves={}
    for lvl,p in ((1,level1),(15,level1a)):
        b,r,c,cells=parse_save(p); got=hashlib.sha256(b).hexdigest()
        if got!=EXPECTED_SAVE_SHAS[lvl]: errors.append(f'level {lvl}: unexpected save SHA-256')
        saves[lvl]=(r,c,cells,got)
    region_results={}
    for name,(va,n,expected) in REGIONS.items():
        got=hashlib.sha256(read_runtime(le,va,n)).hexdigest(); ok=(got==expected)
        region_results[name]={'runtime_va':hex(va),'size':n,'sha256':got,'pass':ok}
        if not ok: errors.append(f'region hash mismatch: {name}')
    event_slot=0x7525E+7*4
    try:
        ef=fixup_at(le,1,event_slot); event8_runtime=le.objects[ef['target_object']-1]['base']+ef['target_offset']
        if not ((ef['type']&0x0f)==7 and ef['target_kind']==0 and event8_runtime==0x853A0): errors.append('event type 8 dispatch relocation mismatch')
    except Exception as e: event8_runtime=None; errors.append(f'event type 8 fixup: {e}')
    transitions=[]
    for t in TRANSITIONS:
        lvl,h,*_=t; rows,cols,cells,_sha=saves[lvl]; rec=check_transition_cell(cells,rows,cols,t)
        try: resolved=resolve_dispatch(le,h)
        except Exception as e: resolved=None; errors.append(str(e))
        rec['resolved_handler_runtime']=resolved; rec['handler_target_match']=(resolved==rec['expected_handler_runtime'])
        rec['serialized_portal_edge_closed_both_sides']=rec['source_edge_closed'] and rec['reciprocal_edge_closed']
        if rec['source_handler_observed']!=h: errors.append(f'level {lvl} handler {h}: source cell contains {rec["source_handler_observed"]}')
        if not rec['handler_target_match']: errors.append(f'handler {h}: runtime target mismatch')
        if not rec['serialized_portal_edge_closed_both_sides']: errors.append(f'handler {h}: serialized portal edge not closed on both sides')
        transitions.append(rec)
    return {'exe_sha256':sha,'save_sha256':{str(k):v[3] for k,v in saves.items()},'transition_count':len(transitions),
            'transitions':transitions,'region_validation':region_results,
            'event_type8_consumer_runtime':hex(event8_runtime) if event8_runtime is not None else None,
            'transition_semantics':{'action3':'A2D76 pre-transition/event path when facing gate matches',
              'action2':'A2DC7 -> A2BA6 stages target col/row/facing and queues event type 8',
              'event8':'consumer 0x853A0 calls 0x5DC10(source_level,target_level)',
              'loader_transfer':'0x5DC10 transfers staged col/row/facing to live player state and target level to live current-level state',
              'portal_unlock':'OPEN; no direct low-static cell+0x02 write is claimed from A2D76'},
            'serialized_closed_both_sides_count':sum(x['serialized_portal_edge_closed_both_sides'] for x in transitions),
            'errors':errors,'pass':not errors}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--exe',type=Path,required=True); ap.add_argument('--level01',type=Path,required=True); ap.add_argument('--level01a',type=Path,required=True); ap.add_argument('--json',action='store_true')
    a=ap.parse_args(); out=inspect(a.exe,a.level01,a.level01a)
    if a.json: print(json.dumps(out,indent=2,sort_keys=True))
    else:
        print(('PASS' if out['pass'] else 'FAIL'),f"transitions={out['transition_count']} closed_both={out['serialized_closed_both_sides_count']} regions={len(out['region_validation'])} errors={len(out['errors'])}")
        for x in out['transitions']:
            print(' level%d h%d %s%s -> level%d spawn=(%d,%d,%d) handler_va=0x%X closed=%s' % (x['source_level'],x['handler_id'],x['direction'],'@'+','.join(map(str,x['source'])),x['target_level'],*x['staged_destination'],x['resolved_handler_runtime'] or 0,x['serialized_portal_edge_closed_both_sides']))
    return 0 if out['pass'] else 2
if __name__=='__main__': raise SystemExit(main())
