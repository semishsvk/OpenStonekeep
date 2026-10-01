#!/usr/bin/env python3
"""Inspect Stonekeep serialized monster-linked spatial occupancy clearance.

The level loader reads 0x12C0 bytes = 400*0x0C spatial records immediately
following the 21-byte cell grid, then a u16 free-list head and 0x16C8 bytes =
54*54*u16 spatial grid heads. Player prechecks walk grid heads via record+0x0A
and compare record+0x06 category IDs against direction/mode-specific blockers.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, struct
from pathlib import Path

CELL_SIZE=0x15
RECORD_SIZE=0x0C
RECORD_COUNT=400
HEAD_ROWS=54
HEAD_COLS=54
HEAD_BYTES=HEAD_ROWS*HEAD_COLS*2
SENTINEL=-1
DIRECTIONS=(
    ('N',-1,0,0x08,'S',0),
    ('W',0,-1,0x02,'E',1),
    ('S',1,0,0x04,'N',2),
    ('E',0,1,0x01,'W',3),
)
BY_NAME={d[0]:d for d in DIRECTIONS}

def s16(b:bytes,o:int)->int:
    return struct.unpack_from('<h',b,o)[0]

def read_level(path:Path):
    data=path.read_bytes()
    if len(data)<11:
        raise ValueError('file too small')
    marker=struct.unpack_from('<H',data,0)[0]
    version=data[2:7].rstrip(b'\0').decode('ascii','replace')
    rows,cols=struct.unpack_from('<HH',data,7)
    grid_end=11+rows*cols*CELL_SIZE
    record_start=grid_end
    record_end=record_start+RECORD_COUNT*RECORD_SIZE
    free_head_off=record_end
    head_start=free_head_off+2
    head_end=head_start+HEAD_BYTES
    if head_end>len(data):
        raise ValueError('truncated spatial occupancy block')
    cells=[
        data[11+i*CELL_SIZE:11+(i+1)*CELL_SIZE]
        for i in range(rows*cols)
    ]
    records=[
        data[record_start+i*RECORD_SIZE:record_start+(i+1)*RECORD_SIZE]
        for i in range(RECORD_COUNT)
    ]
    free_head=s16(data,free_head_off)
    heads=list(struct.unpack_from(
        '<'+'h'*(HEAD_ROWS*HEAD_COLS),data,head_start
    ))
    return (
        data,marker,version,rows,cols,cells,
        record_start,record_end,free_head_off,free_head,
        head_start,head_end,records,heads
    )

def walk_heads(records,heads):
    by_cell={}
    invalid=[]
    cycles=[]
    coord_mismatches=[]
    used=[]
    for hi,head in enumerate(heads):
        if head==SENTINEL:
            continue
        row,col=divmod(hi,HEAD_COLS)
        cur=head
        seen=set()
        chain=[]
        while cur!=SENTINEL:
            if cur<0 or cur>=len(records):
                invalid.append({
                    'head_cell':[row,col],
                    'record_index':cur,
                })
                break
            if cur in seen:
                cycles.append({
                    'head_cell':[row,col],
                    'record_index':cur,
                })
                break
            seen.add(cur)
            used.append(cur)
            rec=records[cur]
            rec_col=s16(rec,0x02)
            rec_row=s16(rec,0x04)
            cat=s16(rec,0x06)
            if (rec_row,rec_col)!=(row,col):
                coord_mismatches.append({
                    'head_cell':[row,col],
                    'record_index':cur,
                    'record_cell':[rec_row,rec_col],
                })
            chain.append({
                'record_index':cur,
                'monster_ref':s16(rec,0x00),
                'column':rec_col,
                'row':rec_row,
                'category':cat,
                'monster_next':s16(rec,0x08),
                'cell_next':s16(rec,0x0A),
            })
            cur=s16(rec,0x0A)
        by_cell[(row,col)]=chain
    return by_cell,invalid,cycles,coord_mismatches,used

def categories(by_cell,row,col):
    return [x['category'] for x in by_cell.get((row,col),())]

def forward_block_sets(facing:int):
    parity=facing&1
    return (
        {
            facing+0x10,
            facing+0x20,
            0x16 if parity==0 else 0x17,
            0x26 if parity==0 else 0x27,
            0x15,
            0x25,
        },
        {
            0x50,
            facing+0x40,
            0x46 if parity==0 else 0x47,
        },
    )

def backward_block_sets(requested:int):
    # For source->destination direction requested, backward live facing is
    # the opposite direction.
    live=(requested+2)&3
    parity=live&1
    return (
        {
            requested+0x10,
            0x16 if parity==0 else 0x17,
            0x15,
        },
        {
            0x50,
            requested+0x30,
            0x36 if parity==0 else 0x37,
            live+0x40,
            0x46 if parity==0 else 0x47,
        },
    )

def classify_edges(cells,by_cell,rows,cols):
    counts=collections.Counter()
    perdir=collections.Counter()
    affected=[]
    for row in range(rows):
        for col in range(cols):
            i=row*cols+col
            for name,dr,dc,low,opp,didx in DIRECTIONS:
                nr,nc=row+dr,col+dc
                if not (0<=nr<rows and 0<=nc<cols):
                    continue
                j=nr*cols+nc
                opposite_low=BY_NAME[opp][3]
                if (
                    (cells[i][0x02]&low)
                    or (cells[j][0x02]&opposite_low)
                ):
                    continue

                src=set(categories(by_cell,row,col))
                dst=set(categories(by_cell,nr,nc))
                fsrc,fdst=forward_block_sets(didx)
                bsrc,bdst=backward_block_sets(didx)

                fblock=bool((src&fsrc) or (dst&fdst))
                bblock=bool((src&bsrc) or (dst&bdst))

                counts[
                    'forward_blocked' if fblock else 'forward_clear'
                ]+=1
                counts[
                    'backward_blocked' if bblock else 'backward_clear'
                ]+=1
                perdir[f'{name}_forward_blocked']+=int(fblock)
                perdir[f'{name}_backward_blocked']+=int(bblock)

                if fblock or bblock:
                    affected.append({
                        'source':[row,col],
                        'direction':name,
                        'destination':[nr,nc],
                        'source_categories':sorted(src),
                        'destination_categories':sorted(dst),
                        'forward_blocked':fblock,
                        'backward_blocked':bblock,
                    })
    return counts,perdir,affected

def inspect(path:Path,include_edges=False):
    (
        data,marker,version,rows,cols,cells,
        record_start,record_end,free_head_off,free_head,
        head_start,head_end,records,heads
    )=read_level(path)

    by_cell,invalid,cycles,coord_mismatches,used=walk_heads(records,heads)
    counts,perdir,affected=classify_edges(cells,by_cell,rows,cols)

    linked_categories=collections.Counter()
    for chain in by_cell.values():
        linked_categories.update(x['category'] for x in chain)

    active_heads=[h for h in heads if h!=SENTINEL]

    out={
        'path':str(path),
        'sha256':hashlib.sha256(data).hexdigest(),
        'format_marker':marker,
        'version':version,
        'rows':rows,
        'columns':cols,
        'cell_count':len(cells),
        'serialized_layout':{
            'record_start':record_start,
            'record_end':record_end,
            'record_count':RECORD_COUNT,
            'record_size':RECORD_SIZE,
            'free_head_offset':free_head_off,
            'free_head':free_head,
            'head_grid_start':head_start,
            'head_grid_end':head_end,
            'head_rows':HEAD_ROWS,
            'head_columns':HEAD_COLS,
        },
        'chain_validation':{
            'active_head_cells':len(active_heads),
            'unique_active_heads':len(set(active_heads)),
            'linked_record_references':len(used),
            'unique_linked_records':len(set(used)),
            'invalid_links':invalid,
            'cycles':cycles,
            'record_coordinate_mismatches':coord_mismatches,
        },
        'linked_category_histogram':dict(
            sorted(linked_categories.items())
        ),
        'static_clear_oriented_edge_count':
            counts['forward_clear']+counts['forward_blocked'],
        'serialized_spatial_clearance':dict(counts),
        'blocked_by_direction':dict(sorted(perdir.items())),
        'policy':{
            'record_category_offset':6,
            'record_cell_next_offset':10,
            'head_sentinel':-1,
            'head_addressing':'54x54 signed-u16 grid; row*54+column',
            'state_scope':'SERIALIZED_LOAD_STATE',
            'runtime_mutable':True,
            'universal_topology_claimed':False,
        },
    }
    if include_edges:
        out['spatial_affected_edges']=affected
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('saves',nargs='+',type=Path)
    ap.add_argument('--json',action='store_true')
    ap.add_argument('--edges',action='store_true')
    a=ap.parse_args()
    results=[inspect(p,a.edges) for p in a.saves]
    ok=all(
        not r['chain_validation']['invalid_links']
        and not r['chain_validation']['cycles']
        and not r['chain_validation']['record_coordinate_mismatches']
        for r in results
    )
    if a.json:
        print(json.dumps(
            {'valid':ok,'results':results},
            indent=2,
            sort_keys=True,
        ))
    else:
        for r in results:
            c=r['serialized_spatial_clearance']
            v=r['chain_validation']
            state='PASS' if (
                not v['invalid_links']
                and not v['cycles']
                and not v['record_coordinate_mismatches']
            ) else 'FAIL'
            print(
                f"{state} {r['path']}: "
                f"active_heads={v['active_head_cells']} "
                f"linked_records={v['unique_linked_records']} "
                f"static_clear={r['static_clear_oriented_edge_count']} "
                f"forward_blocked={c.get('forward_blocked',0)} "
                f"backward_blocked={c.get('backward_blocked',0)}"
            )
    return 0 if ok else 1

if __name__=='__main__':
    raise SystemExit(main())
