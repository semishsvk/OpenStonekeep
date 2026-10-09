#!/usr/bin/env python3
"""Inspect Stonekeep serialized MSP/maze-prop clearance state.

Evidence basis:
- level loader reads the 21-byte cell grid;
- then 0x12C0 bytes, u16, 0x16C8 bytes;
- then u16 MSP count followed by count*0x30 records into runtime pool 0x1B5210;
- cell+0x11 is the pool head; record+0x10 is next; active type is record+0x02 == 1;
- helper 0x410A0 ORs signed byte record+0x18 across the chain.

This models the serialized/load-state MSP gate. record+0x18 is runtime mutable,
so results are not claimed to hold across later world-state mutations.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, struct
from pathlib import Path

CELL_SIZE=0x15
SENTINELS=(-100,-1)
SPATIAL_RECORD_BYTES=0x12C0
SPATIAL_HEAD_BYTES=0x16C8
MSP_RECORD_SIZE=0x30
DIRECTIONS=(
    ('N',-1,0,0x08,'S'),
    ('W',0,-1,0x02,'E'),
    ('S',1,0,0x04,'N'),
    ('E',0,1,0x01,'W'),
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
    if grid_end>len(data):
        raise ValueError('truncated grid')
    cells=[data[11+i*CELL_SIZE:11+(i+1)*CELL_SIZE] for i in range(rows*cols)]

    # Loader 0x8B9B6: grid -> 0x12C0 spatial records -> u16 ->
    # 0x16C8 spatial heads -> u16 MSP count -> count*0x30 MSP pool.
    count_off=grid_end+SPATIAL_RECORD_BYTES+2+SPATIAL_HEAD_BYTES
    if count_off+2>len(data):
        raise ValueError('truncated before MSP count')
    count=s16(data,count_off)
    if count<0:
        raise ValueError('negative MSP count')
    start=count_off+2
    end=start+count*MSP_RECORD_SIZE
    if end>len(data):
        raise ValueError('truncated MSP pool')
    recs=[
        data[start+i*MSP_RECORD_SIZE:start+(i+1)*MSP_RECORD_SIZE]
        for i in range(count)
    ]
    return data,marker,version,rows,cols,cells,count_off,start,end,recs

def aggregate_masks(cells,recs):
    masks=[]
    chain_lengths=[]
    invalid=[]
    cycles=[]
    for ci,c in enumerate(cells):
        cur=s16(c,0x11)
        mask=0
        seen=set()
        n=0
        while cur not in SENTINELS:
            if cur<0 or cur>=len(recs):
                invalid.append({'cell_index':ci,'record_index':cur})
                break
            if cur in seen:
                cycles.append({'cell_index':ci,'record_index':cur})
                break
            seen.add(cur)
            r=recs[cur]
            n+=1
            if s16(r,0x02)==1:
                # Engine uses a signed-byte load before OR. For mask testing,
                # the low eight bits are the evidence-bearing bits.
                mask |= r[0x18]
            cur=s16(r,0x10)
        masks.append(mask & 0xff)
        chain_lengths.append(n)
    return masks,chain_lengths,invalid,cycles

def classify_edges(cells,masks,rows,cols):
    counts=collections.Counter()
    perdir=collections.Counter()
    blocked=[]
    for row in range(rows):
        for col in range(cols):
            i=row*cols+col
            for name,dr,dc,low,opp in DIRECTIONS:
                nr,nc=row+dr,col+dc
                if not (0<=nr<rows and 0<=nc<cols):
                    continue
                j=nr*cols+nc
                opposite_low=BY_NAME[opp][3]

                # K292-A/D reciprocal low-static-clear candidate only.
                if (cells[i][0x02]&low) or (cells[j][0x02]&opposite_low):
                    continue

                # 0x40EE0 when requested direction == live facing (forward):
                # source mask vs direction|0x10, destination vs opposite.
                fblock=bool(
                    (masks[i]&(low|0x10))
                    or (masks[j]&opposite_low)
                )

                # Backward caller passes requested=(live_facing+2). In the
                # non-equal branch, 0x40EE0 tests destination against
                # requested_dir | live_facing | 0x10.
                bblock=bool(
                    masks[j]&(low|opposite_low|0x10)
                )

                counts['forward_blocked' if fblock else 'forward_clear']+=1
                counts['backward_blocked' if bblock else 'backward_clear']+=1
                perdir[f'{name}_forward_blocked']+=int(fblock)
                perdir[f'{name}_backward_blocked']+=int(bblock)
                if fblock or bblock:
                    blocked.append({
                        'source':[row,col],
                        'direction':name,
                        'destination':[nr,nc],
                        'source_msp_mask':masks[i],
                        'destination_msp_mask':masks[j],
                        'forward_blocked':fblock,
                        'backward_blocked':bblock,
                    })
    return counts,perdir,blocked

def inspect(path:Path,include_edges=False):
    data,marker,version,rows,cols,cells,count_off,start,end,recs=read_level(path)
    masks,lens,invalid,cycles=aggregate_masks(cells,recs)
    counts,perdir,blocked=classify_edges(cells,masks,rows,cols)

    active_heads=[
        s16(c,0x11) for c in cells
        if s16(c,0x11) not in SENTINELS
    ]
    type_hist=collections.Counter(s16(r,0x02) for r in recs)
    type1_masks=collections.Counter(
        r[0x18] for r in recs if s16(r,0x02)==1
    )
    cell_masks=collections.Counter(
        masks[i] for i,c in enumerate(cells)
        if s16(c,0x11) not in SENTINELS
    )

    out={
        'path':str(path),
        'sha256':hashlib.sha256(data).hexdigest(),
        'format_marker':marker,
        'version':version,
        'rows':rows,
        'columns':cols,
        'cell_count':len(cells),
        'serialized_layout':{
            'msp_count_offset':count_off,
            'msp_record_start':start,
            'msp_record_end':end,
            'msp_count':len(recs),
            'msp_record_size':MSP_RECORD_SIZE,
        },
        'chain_validation':{
            'active_head_cells':len(active_heads),
            'unique_active_heads':len(set(active_heads)),
            'invalid_links':invalid,
            'cycles':cycles,
            'chain_length_histogram':dict(
                sorted(collections.Counter(lens).items())
            ),
        },
        'record_evidence':{
            'record_type_histogram':dict(sorted(type_hist.items())),
            'type1_mask_histogram':dict(sorted(type1_masks.items())),
        },
        'active_cell_aggregated_mask_histogram':dict(sorted(cell_masks.items())),
        'static_clear_oriented_edge_count':
            counts['forward_clear']+counts['forward_blocked'],
        'serialized_msp_clearance':dict(counts),
        'blocked_by_direction':dict(sorted(perdir.items())),
        'policy':{
            'forward_rule':
                'source_mask & (dir_low|0x10) == 0 AND '
                'destination_mask & opposite_low == 0',
            'backward_rule':
                'destination_mask & '
                '(requested_dir_low|live_facing_low|0x10) == 0',
            'mask_source':
                'OR record+0x18 for chain records with '
                's16(record+0x02)==1',
            'state_scope':'SERIALIZED_LOAD_STATE',
            'runtime_mutable':True,
            'universal_topology_claimed':False,
        },
    }
    if include_edges:
        out['msp_affected_edges']=blocked
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
        for r in results
    )
    if a.json:
        print(json.dumps({'valid':ok,'results':results},indent=2,sort_keys=True))
    else:
        for r in results:
            c=r['serialized_msp_clearance']
            state='PASS' if (
                not r['chain_validation']['invalid_links']
                and not r['chain_validation']['cycles']
            ) else 'FAIL'
            print(
                f"{state} {r['path']}: "
                f"MSP={r['serialized_layout']['msp_count']} "
                f"active_cells={r['chain_validation']['active_head_cells']} "
                f"static_clear={r['static_clear_oriented_edge_count']} "
                f"forward_blocked={c.get('forward_blocked',0)} "
                f"backward_blocked={c.get('backward_blocked',0)}"
            )
    return 0 if ok else 1

if __name__=='__main__':
    raise SystemExit(main())
