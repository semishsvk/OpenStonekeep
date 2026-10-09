#!/usr/bin/env python3
"""Inventory Stonekeep cell+0x07 handler dispatch evidence.

K292-E correction: cell+0x07 is an index into a relocation-sensitive
4-byte dispatch table. Raw on-disk bytes are not treated as final
linear function pointers. Final action classification is deliberately gated.
"""
from __future__ import annotations
import argparse, hashlib, json, re, struct
from pathlib import Path

CELL_SIZE=0x15
DISPATCH_TABLE_VA=0xF16A

def handler_ids(path: Path):
    data=path.read_bytes()
    rows,cols=struct.unpack_from('<HH',data,7)
    ids=set()
    for i in range(rows*cols):
        h=struct.unpack_from('<h',data,11+i*CELL_SIZE+7)[0]
        if h: ids.add(h)
    return rows,cols,sorted(ids)

def parse_disassembly_bytes(path: Path):
    mem={}
    rx=re.compile(r'^\\s*([0-9a-f]+):\\s*([0-9a-f ]+)')
    for line in path.read_text(errors='replace').splitlines():
        m=rx.match(line)
        if not m: continue
        try: raw=bytes.fromhex(m.group(2).strip())
        except ValueError: continue
        addr=int(m.group(1),16)
        for i,b in enumerate(raw): mem[addr+i]=b
    return mem

def table_entry(mem,handler_id):
    addr=DISPATCH_TABLE_VA+handler_id*4
    if not all(addr+i in mem for i in range(4)):
        return {'table_virtual_address':hex(addr),'raw_entry':None}
    raw=bytes(mem[addr+i] for i in range(4))
    return {'table_virtual_address':hex(addr),'raw_entry':raw.hex()}

def build(saves,disasm):
    by_save={}; ids=set()
    for save in saves:
        rows,cols,h=handler_ids(save); ids.update(h)
        by_save[str(save)]={'sha256':hashlib.sha256(save.read_bytes()).hexdigest(),
                            'rows':rows,'columns':cols,'nondefault_handler_ids':h}
    mem=parse_disassembly_bytes(disasm)
    return {'dispatch_table_virtual_base':hex(DISPATCH_TABLE_VA),
            'saves':by_save,
            'entries':{str(h):table_entry(mem,h) for h in sorted(ids)},
            'dispatch_resolution':'RELOCATION_REQUIRED',
            'action_classification':'NOT_YET_AUTHORIZED',
            'next_required':['resolve LE relocation/fixup semantics for the dispatch table',
                             'resolve final indirect targets for relevant handler IDs',
                             'trace movement action selectors 2/3/4/5',
                             'classify allow/veto/state mutation only from direct evidence']}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--save',action='append',required=True,type=Path)
    ap.add_argument('--disasm',required=True,type=Path); ap.add_argument('--json',action='store_true')
    a=ap.parse_args(); out=build(a.save,a.disasm)
    if a.json: print(json.dumps(out,indent=2,sort_keys=True))
    else: print('handlers=',sum(len(x['nondefault_handler_ids']) for x in out['saves'].values()),
                ' dispatch=0x%X resolution=%s' % (DISPATCH_TABLE_VA,out['dispatch_resolution']))

if __name__=='__main__': main()