#!/usr/bin/env python3
"""Resolve Stonekeep cell-handler dispatch slots through LE internal fixups.

Read-only evidence tool. It does not patch the executable or saves.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path

CELL_SIZE = 0x15
DISPATCH_OBJECT = 3
DISPATCH_OBJECT_OFFSET = 0xF16A
DIRS = ((-1,0,0x08),(0,-1,0x02),(1,0,0x04),(0,1,0x01)) # N W S E

class LE:
    def __init__(self, data:bytes):
        self.data=data
        if data[:2] != b'MZ': raise ValueError('not MZ')
        self.le=struct.unpack_from('<I',data,0x3c)[0]
        if data[self.le:self.le+2] != b'LE': raise ValueError('not LE')
        u32=lambda o: struct.unpack_from('<I',data,self.le+o)[0]
        self.num_pages=u32(0x14); self.page_size=u32(0x28); self.last_page=u32(0x2c)
        self.objtab=u32(0x40); self.num_objects=u32(0x44); self.objmap=u32(0x48)
        self.fixpage=u32(0x68); self.fixrec=u32(0x6c); self.page_off=u32(0x80)
        self.objects=[]
        for i in range(self.num_objects):
            size,base,flags,mapidx,mapsize,_=struct.unpack_from('<IIIIII',data,self.le+self.objtab+i*24)
            self.objects.append({'size':size,'base':base,'flags':flags,'mapidx':mapidx,'mapsize':mapsize})
        self.page_map=[]
        for i in range(self.num_pages):
            q=self.le+self.objmap+i*4
            page_num=(data[q]<<16)|(data[q+1]<<8)|data[q+2]
            self.page_map.append((page_num,data[q+3]))
        self.fixmap=list(struct.unpack_from('<'+'I'*(self.num_pages+1),data,self.le+self.fixpage))

    def object_file_offset(self,objnum:int,off:int)->int:
        o=self.objects[objnum-1]
        if off<0 or off>=o['size']: raise ValueError('object offset out of range')
        local_page=off//self.page_size
        if local_page>=o['mapsize']: raise ValueError('object page not mapped')
        global_page=(o['mapidx']-1)+local_page
        page_num,flags=self.page_map[global_page]
        if flags != 0: raise ValueError(f'unsupported LE page flags {flags}')
        return self.page_off+(page_num-1)*self.page_size+(off%self.page_size)

    def page_for_object_offset(self,objnum:int,off:int):
        o=self.objects[objnum-1]; local=off//self.page_size
        return (o['mapidx']-1)+local, off%self.page_size

    def parse_fixup_page(self,page_index:int):
        p=self.le+self.fixrec+self.fixmap[page_index]
        end=self.le+self.fixrec+self.fixmap[page_index+1]
        out=[]
        while p<end:
            start=p; typ=self.data[p]; flags=self.data[p+1]; p+=2
            if typ & 0x20:
                count=self.data[p]; p+=1; sources=None
            else:
                sources=[struct.unpack_from('<h',self.data,p)[0]]; p+=2; count=None
            if flags & 0x40:
                obj=struct.unpack_from('<H',self.data,p)[0]; p+=2
            else:
                obj=self.data[p]; p+=1
            target_kind=flags&0x03; target_off=None
            if target_kind==0:
                if (typ&0x0f) != 0x02:
                    if flags&0x10: target_off=struct.unpack_from('<I',self.data,p)[0]; p+=4
                    else: target_off=struct.unpack_from('<H',self.data,p)[0]; p+=2
            elif target_kind==1:
                p += 2 if flags&0x40 else 1
                if flags&0x80:p+=1
                elif flags&0x10:p+=4
                else:p+=2
                if flags&0x04:p+=4
            elif target_kind==2:
                p += 2 if flags&0x40 else 1
                p += 4 if flags&0x10 else 2
                if flags&0x04:p+=4
            else:
                p += 2 if flags&0x40 else 1
                if flags&0x04:p+=4
            if typ&0x20:
                sources=list(struct.unpack_from('<'+'h'*count,self.data,p)); p+=2*count
            out.append({'record_file_offset':start,'type':typ,'flags':flags,'sources':sources,
                        'target_kind':target_kind,'target_object':obj,'target_offset':target_off})
        if p!=end: raise ValueError('fixup parser did not end on page boundary')
        return out

def read_save(path:Path):
    b=path.read_bytes(); rows,cols=struct.unpack_from('<HH',b,7); n=rows*cols
    end=11+n*CELL_SIZE
    if end>len(b): raise ValueError('truncated save')
    cells=[b[11+i*CELL_SIZE:11+(i+1)*CELL_SIZE] for i in range(n)]
    ids=[]; candidate=set()
    for i,c in enumerate(cells):
        h=struct.unpack_from('<h',c,7)[0]
        if h: ids.append(h)
        if not h: continue
        r,co=divmod(i,cols)
        for dr,dc,mask in DIRS:
            rr,cc=r+dr,co+dc
            if 0<=rr<rows and 0<=cc<cols and not (c[2]&mask):
                candidate.add(h); break
    return {'path':str(path),'sha256':hashlib.sha256(b).hexdigest(),'rows':rows,'columns':cols,
            'nondefault_handler_ids':sorted(set(ids)),'movement_candidate_source_handler_ids':sorted(candidate)}

def resolve(exe:Path,saves:list[Path]):
    b=exe.read_bytes(); le=LE(b)
    sv=[read_save(p) for p in saves]
    all_ids=sorted(set().union(*(set(x['nondefault_handler_ids']) for x in sv)))
    cand=sorted(set().union(*(set(x['movement_candidate_source_handler_ids']) for x in sv)))
    page_idx,base_in_page=le.page_for_object_offset(DISPATCH_OBJECT,DISPATCH_OBJECT_OFFSET)
    fixups=le.parse_fixup_page(page_idx)
    result={}; errors=[]
    for h in all_ids:
        src=base_in_page+h*4
        matches=[f for f in fixups if src in f['sources']]
        ent={'handler_id':h,'dispatch_object':DISPATCH_OBJECT,
             'dispatch_object_offset':DISPATCH_OBJECT_OFFSET+h*4,
             'source_page_1based':page_idx+1,'source_page_offset':src,
             'movement_candidate_source':h in cand,'fixup_match_count':len(matches)}
        if len(matches)==1:
            f=matches[0]; ent.update({'source_type':f['type']&0x0f,'source_type_flags':f['type'],
                'target_flags':f['flags'],'target_kind':f['target_kind'],'target_object':f['target_object'],
                'target_object_offset':f['target_offset']})
            if f['target_kind']==0 and f['target_offset'] is not None and 1<=f['target_object']<=len(le.objects):
                obj=le.objects[f['target_object']-1]
                ent['target_runtime_linear']=obj['base']+f['target_offset']
                try: ent['target_file_offset']=le.object_file_offset(f['target_object'],f['target_offset'])
                except ValueError as e: ent['target_file_offset_error']=str(e)
            if not ((f['type']&0x0f)==0x07 and f['target_kind']==0 and f['target_object']==1 and (f['flags']&0x10)):
                errors.append(f'handler {h}: unexpected fixup shape')
        else: errors.append(f'handler {h}: fixup matches={len(matches)}')
        result[str(h)]=ent
    targets=[x.get('target_object_offset') for x in result.values() if x.get('target_object_offset') is not None]
    return {'exe':str(exe),'exe_sha256':hashlib.sha256(b).hexdigest(),'format':'LE',
            'page_size':le.page_size,'object_count':len(le.objects),'objects':le.objects,
            'dispatch':{'object':DISPATCH_OBJECT,'object_offset':DISPATCH_OBJECT_OFFSET,
                        'page_1based':page_idx+1,'page_offset':base_in_page},
            'saves':sv,'all_nondefault_handler_count':len(all_ids),'all_nondefault_handler_ids':all_ids,
            'movement_candidate_source_handler_count':len(cand),'movement_candidate_source_handler_ids':cand,
            'resolved_slot_count':sum(x['fixup_match_count']==1 for x in result.values()),
            'unique_target_count':len(set(targets)),'resolution_errors':errors,'entries':result}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--exe',required=True,type=Path); ap.add_argument('--save',action='append',required=True,type=Path); ap.add_argument('--json',action='store_true')
    a=ap.parse_args(); out=resolve(a.exe,a.save)
    if a.json: print(json.dumps(out,indent=2,sort_keys=True))
    else:
        print('all_nondefault=%d movement_candidates=%d resolved=%d unique_targets=%d errors=%d' %
              (out['all_nondefault_handler_count'],out['movement_candidate_source_handler_count'],out['resolved_slot_count'],out['unique_target_count'],len(out['resolution_errors'])))
        for k,v in out['entries'].items():
            print('%3s candidate=%s obj%d+0x%X linear=0x%X file=0x%X' % (k,v['movement_candidate_source'],v.get('target_object',0),v.get('target_object_offset',0),v.get('target_runtime_linear',0),v.get('target_file_offset',0)))
    return 0 if not out['resolution_errors'] else 2
if __name__=='__main__': raise SystemExit(main())
