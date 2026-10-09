#!/usr/bin/env python3
"""Resolve per-level global action callbacks through Stonekeep LE fixups.

Read-only evidence tool. It ties the current-level init dispatch table to the
9-byte level-name table and resolves the callback written to 0x1B9DDC by each
level initializer. Raw dwords are never treated as final runtime pointers.
"""
from __future__ import annotations
import argparse, hashlib, json, struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_le_handler_dispatch import LE

EXPECTED_EXE_SHA='5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2'
LEVEL_COUNT=22
NAME_OBJECT=3; NAME_OFFSET=0x5D44; NAME_WIDTH=9
INIT_OBJECT=3; INIT_OFFSET=0xF10E
INIT_REF_OBJECT=1; INIT_REF_OFFSET=0x34F37
NAME_REF_OBJECT=1; NAME_REF_OFFSET=0x4D381
CALLBACK_STORE_PATTERN=b'\xc7\x05\xdc\x9d\x1b\x00'
STARTER_LEVELS=('level01','level01a')

def fixup_at(le:LE,objnum:int,off:int):
    page,source=le.page_for_object_offset(objnum,off)
    matches=[f for f in le.parse_fixup_page(page) if source in f['sources']]
    if len(matches)!=1:
        raise ValueError(f'expected one fixup at obj{objnum}+0x{off:X}; got {len(matches)}')
    return matches[0]

def read_object(le:LE,objnum:int)->bytes:
    o=le.objects[objnum-1]; out=bytearray(o['size'])
    for off in range(0,o['size'],le.page_size):
        n=min(le.page_size,o['size']-off)
        try: fo=le.object_file_offset(objnum,off)
        except ValueError: continue
        chunk=le.data[fo:fo+n]
        out[off:off+len(chunk)]=chunk
    return bytes(out)

def decode_names(obj3:bytes)->list[str]:
    out=[]
    for i in range(LEVEL_COUNT):
        raw=obj3[NAME_OFFSET+i*NAME_WIDTH:NAME_OFFSET+(i+1)*NAME_WIDTH]
        out.append(raw.split(b'\0',1)[0].decode('ascii','replace'))
    return out

def find_callback_store(obj1:bytes,start:int,window:int=0x60)->int:
    return obj1.find(CALLBACK_STORE_PATTERN,start,min(len(obj1),start+window))

def require_off32_internal(f,target_object:int,target_offset:int):
    if not ((f['type']&0x0f)==0x07 and f['target_kind']==0 and
            f['target_object']==target_object and f['target_offset']==target_offset):
        raise ValueError('unexpected OFF32 internal relocation')

def inspect(exe:Path):
    data=exe.read_bytes(); sha=hashlib.sha256(data).hexdigest(); le=LE(data); errors=[]
    if sha!=EXPECTED_EXE_SHA: errors.append('unexpected SK.EXE SHA-256')
    obj1=read_object(le,1); obj3=read_object(le,3)
    try:
        require_off32_internal(fixup_at(le,INIT_REF_OBJECT,INIT_REF_OFFSET),INIT_OBJECT,INIT_OFFSET)
        require_off32_internal(fixup_at(le,NAME_REF_OBJECT,NAME_REF_OFFSET),NAME_OBJECT,NAME_OFFSET)
    except Exception as e:
        errors.append(str(e))
    names=decode_names(obj3); levels=[]
    for i,name in enumerate(names):
        slot=INIT_OFFSET+i*4; raw_init=struct.unpack_from('<I',obj3,slot)[0]
        rec={'index':i,'name':name,'init_slot_object_offset':hex(slot),
             'raw_init_entry':hex(raw_init)}
        if raw_init==0:
            rec.update({'init_resolution':'NULL','callback_resolution':'NOT_APPLICABLE'})
            levels.append(rec); continue
        try:
            f=fixup_at(le,INIT_OBJECT,slot); require_off32_internal(f,1,raw_init)
            init_va=le.objects[0]['base']+raw_init
            p=find_callback_store(obj1,raw_init)
            if p<0: raise ValueError('callback store not found near level init')
            imm=p+len(CALLBACK_STORE_PATTERN)
            raw_cb=struct.unpack_from('<I',obj1,imm)[0]
            cf=fixup_at(le,1,imm); require_off32_internal(cf,1,raw_cb)
            cb_va=le.objects[0]['base']+raw_cb; head=obj1[raw_cb:raw_cb+8]
            rec.update({
                'init_resolution':'LE_FIXUP_VERIFIED',
                'init_runtime':hex(init_va),
                'callback_store_runtime':hex(le.objects[0]['base']+p),
                'raw_callback_pre_relocation':hex(raw_cb),
                'callback_runtime':hex(cb_va),
                'callback_head':head.hex(),
                'callback_entry_is_ret':bool(head and head[0]==0xC3),
            })
        except Exception as e:
            rec.update({'init_resolution':'ERROR','error':str(e)})
            errors.append(f'level {i} {name}: {e}')
        levels.append(rec)
    starter={x['name']:x for x in levels if x['name'] in STARTER_LEVELS}
    for name in STARTER_LEVELS:
        if name not in starter or not starter[name].get('callback_entry_is_ret'):
            errors.append(f'{name}: callback RET not verified')
    initialized=[x for x in levels if x.get('init_resolution')=='LE_FIXUP_VERIFIED']
    return {
        'exe_sha256':sha,
        'level_count':LEVEL_COUNT,
        'levels':levels,
        'starter_callbacks':starter,
        'summary':{
            'initialized_level_count':len(initialized),
            'ret_callback_count':sum(bool(x.get('callback_entry_is_ret')) for x in initialized),
            'nonret_callback_count':sum(not bool(x.get('callback_entry_is_ret')) for x in initialized),
        },
        'errors':errors,
        'pass':not errors,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--exe',required=True,type=Path)
    ap.add_argument('--json',action='store_true')
    a=ap.parse_args(); out=inspect(a.exe)
    if a.json:
        print(json.dumps(out,indent=2,sort_keys=True))
    else:
        s=out['summary']
        print('PASS' if out['pass'] else 'FAIL',
              f"levels={out['level_count']} initialized={s['initialized_level_count']} "
              f"ret={s['ret_callback_count']} nonret={s['nonret_callback_count']} "
              f"errors={len(out['errors'])}")
        for name,x in out['starter_callbacks'].items():
            print(name,x.get('init_runtime'),x.get('callback_runtime'),
                  'RET=',x.get('callback_entry_is_ret'))
    return 0 if out['pass'] else 2

if __name__=='__main__':
    raise SystemExit(main())
