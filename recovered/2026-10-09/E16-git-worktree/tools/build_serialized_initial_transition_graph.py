#!/usr/bin/env python3
from __future__ import annotations
import argparse, collections, hashlib, json, struct
from pathlib import Path

CELL_SIZE=0x15
SPATIAL_RECORD_SIZE=0x0C
SPATIAL_RECORD_COUNT=400
SPATIAL_HEAD_ROWS=54
SPATIAL_HEAD_COLS=54
SPATIAL_HEAD_COUNT=SPATIAL_HEAD_ROWS*SPATIAL_HEAD_COLS
MSP_RECORD_SIZE=0x30
SENTINEL_MSP=(-100,-1)
SENTINEL_SPATIAL=-1
DIRECTIONS=(
    ('N',-1,0,0x08,'S',0),
    ('W',0,-1,0x02,'E',1),
    ('S',1,0,0x04,'N',2),
    ('E',0,1,0x01,'W',3),
)
BY_NAME={d[0]:d for d in DIRECTIONS}
# K292-E.2 coverage-complete non-default movement-source handlers.
CALLBACK_ALLOW_HANDLERS={
    2,3,13,14,15,16,21,22,23,24,42,43,60,75,76,77,78,79,80,86,87,88,89,90,
    91,92,93,94,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,
    111,112,113,115,116,410,411,412,413,414,415,416,417,418,419,
}
OBSERVED_SIDE_EFFECT_HANDLERS={110,111,112,115,410,415}

def s16(b,o): return struct.unpack_from('<h',b,o)[0]

def read_state(path:Path):
    data=path.read_bytes()
    if len(data)<11: raise ValueError('file too small')
    rows,cols=struct.unpack_from('<HH',data,7)
    n=rows*cols
    grid_end=11+n*CELL_SIZE
    if grid_end>len(data): raise ValueError('truncated grid')
    cells=[data[11+i*CELL_SIZE:11+(i+1)*CELL_SIZE] for i in range(n)]
    spatial_start=grid_end
    spatial_end=spatial_start+SPATIAL_RECORD_COUNT*SPATIAL_RECORD_SIZE
    free_head_off=spatial_end
    heads_start=free_head_off+2
    heads_end=heads_start+SPATIAL_HEAD_COUNT*2
    if heads_end+2>len(data): raise ValueError('truncated spatial block')
    srecords=[data[spatial_start+i*SPATIAL_RECORD_SIZE:spatial_start+(i+1)*SPATIAL_RECORD_SIZE]
              for i in range(SPATIAL_RECORD_COUNT)]
    heads=list(struct.unpack_from('<'+'h'*SPATIAL_HEAD_COUNT,data,heads_start))
    msp_count=s16(data,heads_end)
    if msp_count<0: raise ValueError('negative MSP count')
    msp_start=heads_end+2
    msp_end=msp_start+msp_count*MSP_RECORD_SIZE
    if msp_end>len(data): raise ValueError('truncated MSP pool')
    mrecs=[data[msp_start+i*MSP_RECORD_SIZE:msp_start+(i+1)*MSP_RECORD_SIZE]
           for i in range(msp_count)]
    return data,rows,cols,cells,srecords,heads,mrecs

def aggregate_msp(cells,recs):
    masks=[]; invalid=[]; cycles=[]
    for ci,c in enumerate(cells):
        cur=s16(c,0x11); mask=0; seen=set()
        while cur not in SENTINEL_MSP:
            if cur<0 or cur>=len(recs): invalid.append((ci,cur)); break
            if cur in seen: cycles.append((ci,cur)); break
            seen.add(cur); r=recs[cur]
            if s16(r,0x02)==1: mask |= r[0x18]
            cur=s16(r,0x10)
        masks.append(mask&0xff)
    return masks,invalid,cycles

def spatial_categories(records,heads):
    by_cell={}; invalid=[]; cycles=[]; mismatches=[]; duplicate_refs=[]; globally_used={}
    for hi,head in enumerate(heads):
        if head==SENTINEL_SPATIAL: continue
        row,col=divmod(hi,SPATIAL_HEAD_COLS); cur=head; seen=set(); cats=[]
        while cur!=SENTINEL_SPATIAL:
            if cur<0 or cur>=len(records): invalid.append(((row,col),cur)); break
            if cur in seen: cycles.append(((row,col),cur)); break
            seen.add(cur)
            if cur in globally_used and globally_used[cur]!=(row,col):
                duplicate_refs.append((cur,globally_used[cur],(row,col)))
            globally_used[cur]=(row,col)
            rec=records[cur]
            rc=s16(rec,0x02); rr=s16(rec,0x04)
            if (rr,rc)!=(row,col): mismatches.append((cur,(row,col),(rr,rc)))
            cats.append(s16(rec,0x06)); cur=s16(rec,0x0A)
        by_cell[(row,col)]=tuple(cats)
    return by_cell,invalid,cycles,mismatches,duplicate_refs

def forward_block_sets(facing):
    parity=facing&1
    return ({facing+0x10,facing+0x20,0x16 if parity==0 else 0x17,
             0x26 if parity==0 else 0x27,0x15,0x25},
            {0x50,facing+0x40,0x46 if parity==0 else 0x47})

def backward_block_sets(requested):
    live=(requested+2)&3; parity=live&1
    return ({requested+0x10,0x16 if parity==0 else 0x17,0x15},
            {0x50,requested+0x30,0x36 if parity==0 else 0x37,
             live+0x40,0x46 if parity==0 else 0x47})

def physical_reason(msp,spatial):
    if msp and spatial: return 'BLOCKED_MSP_AND_SPATIAL'
    if msp: return 'BLOCKED_MSP'
    if spatial: return 'BLOCKED_SPATIAL'
    return 'TRAVERSE'

def callback_evidence(handler):
    if handler==0:
        return {'pre_return_gate':'ALLOW_VERIFIED_DEFAULT','side_effect_semantics':'DEFAULT_ALLOW_PATH'}
    if handler not in CALLBACK_ALLOW_HANDLERS:
        return {'pre_return_gate':'UNRESOLVED','side_effect_semantics':'UNRESOLVED'}
    return {
        'pre_return_gate':'ALLOW_VERIFIED',
        'side_effect_semantics':'OBSERVED_MUTATION_POSSIBLE' if handler in OBSERVED_SIDE_EFFECT_HANDLERS else 'PARTIAL_UNRESOLVED',
    }

def build(path:Path,include_attempts=False):
    data,rows,cols,cells,srecords,heads,mrecs=read_state(path)
    msp_masks,msp_invalid,msp_cycles=aggregate_msp(cells,mrecs)
    by_cell,sp_invalid,sp_cycles,sp_mismatch,sp_dupes=spatial_categories(srecords,heads)
    errors=[]
    if msp_invalid: errors.append(f'msp_invalid={msp_invalid[:5]}')
    if msp_cycles: errors.append(f'msp_cycles={msp_cycles[:5]}')
    if sp_invalid: errors.append(f'spatial_invalid={sp_invalid[:5]}')
    if sp_cycles: errors.append(f'spatial_cycles={sp_cycles[:5]}')
    if sp_mismatch: errors.append(f'spatial_coord_mismatch={sp_mismatch[:5]}')
    if sp_dupes: errors.append(f'spatial_duplicate_refs={sp_dupes[:5]}')

    counts={'forward':collections.Counter(),'backward':collections.Counter()}
    callback_counts=collections.Counter(); attempts=[]; static_clear=0
    paired=collections.Counter(); pair_records={}
    traverse_nondefault=collections.Counter(); traverse_observed_mutator=collections.Counter()
    nondefault_sources=set(); unknown_callback=set(); affected_interfaces=set()
    for row in range(rows):
      for col in range(cols):
        i=row*cols+col; src_handler=s16(cells[i],0x07)
        for name,dr,dc,low,opp,didx in DIRECTIONS:
            nr,nc=row+dr,col+dc
            if not (0<=nr<rows and 0<=nc<cols): continue
            j=nr*cols+nc; opp_low=BY_NAME[opp][3]
            if (cells[i][0x02]&low) or (cells[j][0x02]&opp_low): continue
            static_clear += 1
            if src_handler: nondefault_sources.add(src_handler)
            cb=callback_evidence(src_handler)
            if cb['pre_return_gate'].startswith('UNRESOLVED'): unknown_callback.add(src_handler)
            callback_counts[cb['pre_return_gate']]+=1
            sm=msp_masks[i]; dm=msp_masks[j]
            src_cats=set(by_cell.get((row,col),()))
            dst_cats=set(by_cell.get((nr,nc),()))

            fmsp=bool((sm&(low|0x10)) or (dm&opp_low))
            bmsp=bool(dm&(low|opp_low|0x10))
            fsrc,fdst=forward_block_sets(didx)
            bsrc,bdst=backward_block_sets(didx)
            fsp=bool((src_cats&fsrc) or (dst_cats&fdst))
            bsp=bool((src_cats&bsrc) or (dst_cats&bdst))
            for mode,msp,spatial,facing,pre,post in (
                ('forward',fmsp,fsp,didx,3,2),
                ('backward',bmsp,bsp,(didx+2)&3,5,4),
            ):
                reason=physical_reason(msp,spatial)
                callback_invoked=(reason=='TRAVERSE')
                if reason=='TRAVERSE' and cb['pre_return_gate'].startswith('UNRESOLVED'):
                    outcome='CALLBACK_RETURN_UNRESOLVED'
                elif reason=='TRAVERSE': outcome='TRANSLATION_EXECUTES'
                else: outcome=reason
                counts[mode][outcome]+=1
                if outcome=='TRANSLATION_EXECUTES' and src_handler:
                    traverse_nondefault[mode]+=1
                    if src_handler in OBSERVED_SIDE_EFFECT_HANDLERS:
                        traverse_observed_mutator[mode]+=1
                pair_records.setdefault((row,col,name,nr,nc),{})[mode]=outcome
                if reason!='TRAVERSE': affected_interfaces.add((min(i,j),max(i,j)))
                if include_attempts:
                    attempts.append({
                        'source':[row,col],'destination':[nr,nc],'direction':name,
                        'mode':mode,'source_facing':facing,'destination_facing':facing,
                        'pre_action':pre,'post_action':post,'source_handler':src_handler,
                        'callback_return_gate':cb['pre_return_gate'],
                        'callback_side_effect_semantics':cb['side_effect_semantics'],
                        'callback_invoked':callback_invoked,
                        'translation_outcome':'EXECUTES' if outcome=='TRANSLATION_EXECUTES' else 'DOES_NOT_EXECUTE',
                        'action_complete_state_semantics':('POST_CALLBACK_STATE_DELTA_PARTIAL' if outcome=='TRANSLATION_EXECUTES' and src_handler else ('DEFAULT_ALLOW_PATH' if outcome=='TRANSLATION_EXECUTES' else 'UNCHANGED_BY_CALLBACK_NOT_INVOKED')),
                        'msp_blocked':msp,'spatial_blocked':spatial,'outcome':outcome,
                    })
    for v in pair_records.values():
        if 'forward' in v and 'backward' in v:
            paired[(v['forward'],v['backward'])]+=1
    mode_asym=sum(n for (f,b),n in paired.items() if f!=b)
    missing=sorted(nondefault_sources-CALLBACK_ALLOW_HANDLERS)
    extra=sorted(CALLBACK_ALLOW_HANDLERS-nondefault_sources)
    if missing: errors.append(f'nondefault candidate handlers missing callback evidence: {missing}')
    # Extra is allowed only if a save alone does not contain every corpus handler.
    out={
        'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),'rows':rows,'columns':cols,
        'oriented_player_state_count':rows*cols*4,
        'static_clear_oriented_edge_count':static_clear,
        'movement_attempt_count':static_clear*2,
        'movement_candidate_source_handler_ids':sorted(nondefault_sources),
        'callback_evidence_missing_handlers':missing,
        'callback_evidence_extra_corpus_handlers':extra,
        'transition_counts':{k:dict(v) for k,v in counts.items()},
        'paired_forward_backward_outcomes':{f'{a}|{b}':n for (a,b),n in sorted(paired.items())},
        'mode_asymmetric_oriented_edge_count':mode_asym,
        'translation_executes_with_nondefault_callback':dict(traverse_nondefault),
        'translation_executes_with_observed_mutator_handler':dict(traverse_observed_mutator),
        'physical_affected_undirected_interface_count':len(affected_interfaces),
        'validation':{
            'msp_invalid_links':len(msp_invalid),'msp_cycles':len(msp_cycles),
            'spatial_invalid_links':len(sp_invalid),'spatial_cycles':len(sp_cycles),
            'spatial_coordinate_mismatches':len(sp_mismatch),'spatial_duplicate_refs':len(sp_dupes),
            'errors':errors,'pass':not errors,
        },
        'policy':{
            'state_scope':'SERIALIZED_INITIAL_LOAD_STATE',
            'callback_return_gate':'K292-E.2 VERIFIED for all non-default movement-source handlers; default allow path verified',
            'callback_side_effects':'PARTIAL; may mutate state before translation; not used to predict later transitions',
            'one_step_transition':'translation executes iff static clear and serialized MSP/spatial precheck clear and callback return allows; post-callback state may remain partial',
            'one_way_verdict_authorized':False,'softlock_verdict_authorized':False,
        },
    }
    if include_attempts: out['attempts']=attempts
    return out

def build_corpus(paths:list[Path],include_attempts=False):
    results=[build(p,include_attempts) for p in paths]
    handlers=sorted(set().union(*(set(r['movement_candidate_source_handler_ids']) for r in results)))
    aggregate={'forward':collections.Counter(),'backward':collections.Counter()}
    for r in results:
        for mode in aggregate:
            aggregate[mode].update(r['transition_counts'][mode])
    return {
        'valid':all(r['validation']['pass'] for r in results),
        'corpus_summary':{
            'save_count':len(results),
            'movement_candidate_source_handler_count':len(handlers),
            'movement_candidate_source_handler_ids':handlers,
            'oriented_player_state_count':sum(r['oriented_player_state_count'] for r in results),
            'static_clear_oriented_edge_count':sum(r['static_clear_oriented_edge_count'] for r in results),
            'movement_attempt_count':sum(r['movement_attempt_count'] for r in results),
            'transition_counts':{k:dict(v) for k,v in aggregate.items()},
            'mode_asymmetric_oriented_edge_count':sum(r['mode_asymmetric_oriented_edge_count'] for r in results),
            'physical_affected_undirected_interface_count':sum(r['physical_affected_undirected_interface_count'] for r in results),
        },
        'results':results,
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('saves',nargs='+',type=Path); ap.add_argument('--json',action='store_true'); ap.add_argument('--attempts',action='store_true')
    a=ap.parse_args(); out=build_corpus(a.saves,a.attempts)
    if a.json: print(json.dumps(out,indent=2,sort_keys=True))
    else:
        for r in out['results']:
            print(('PASS' if r['validation']['pass'] else 'FAIL'),r['path'], 'static_clear=',r['static_clear_oriented_edge_count'],'attempts=',r['movement_attempt_count'])
            for mode in ('forward','backward'): print(' ',mode,r['transition_counts'][mode])
        c=out['corpus_summary']; print('corpus handlers=%d static_clear=%d attempts=%d mode_asym=%d' % (c['movement_candidate_source_handler_count'],c['static_clear_oriented_edge_count'],c['movement_attempt_count'],c['mode_asymmetric_oriented_edge_count']))
    return 0 if out['valid'] else 2
if __name__=='__main__': raise SystemExit(main())
