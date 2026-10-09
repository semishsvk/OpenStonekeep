#!/usr/bin/env python3
"""Validate K292-E.2 Stonekeep movement callback return evidence."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_le_handler_dispatch import resolve

ACTIONS=('2','3','4','5')
EXPECTED_EXE_SHA='5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2'
EXPECTED_SAVE_SHAS={
 '2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9',
 '3d1753ca8a4ca49b3ccf9da0fc15bb08ac242301eff40586049379ceba635dc9',
}
# Static control-flow families. Every listed action 2/3/4/5 is RETURN_1.
EVIDENCE_GROUPS={
 'DAAAA_ALLOW_CHAIN':[2,3,94,98,99,100,101,102,103,109],
 'CELL_VARIANT_6DFC4_ALLOW_CHAIN':[13,14,15,16],
 'DIRECT_SETTER_RET1':[21,22,23,24],
 '4F035_ALLOW_CHAIN':[42,43,93,414,418],
 'DEFAULT_ALLOW_CHAIN':[60,86,95,96,97,104,105],
 '618F2_ALLOW_CHAIN':[75,91],
 'C22A4_ALLOW_CHAIN':[76,77,78,79,80],
 '6B5EE_ALLOW_CHAIN':[87,88,89,90,106,107,411,412,413,415],
 'CHAIN_TO_HANDLER13':[92,113],
 '9A0D7_ALLOW_CHAIN':[108],
 'MUTATING_DEFAULT_CHAIN':[110,111],
 '99C9D_ALLOW_CHAIN':[112],
 'CHAIN_TO_HANDLER14':[115,116],
 '410_SIDE_EFFECT_THEN_DEFAULT':[410],
 'CHAIN_TO_HANDLER15_16':[416,417],
 '66F8A_ALLOW_CHAIN':[419],
}

def validate(resolved:dict)->dict:
    errors=[]
    if resolved.get('exe_sha256')!=EXPECTED_EXE_SHA: errors.append('unexpected SK.EXE SHA-256')
    if {s['sha256'] for s in resolved.get('saves',[])}!=EXPECTED_SAVE_SHAS: errors.append('unexpected starter-save SHA-256 set')
    candidate=set(resolved['movement_candidate_source_handler_ids'])
    flat=[h for ids in EVIDENCE_GROUPS.values() for h in ids]
    if len(flat)!=len(set(flat)): errors.append('duplicate handler IDs across evidence groups')
    got=set(flat); missing=sorted(candidate-got); extra=sorted(got-candidate)
    if missing: errors.append(f'missing candidate handler IDs: {missing}')
    if extra: errors.append(f'extra non-candidate handler IDs: {extra}')
    action_cells=len(flat)*len(ACTIONS)
    return {'candidate_handler_count':len(candidate),'evidence_handler_count':len(flat),
            'control_flow_family_count':len(EVIDENCE_GROUPS),'action_cells':action_cells,
            'unknown_return_cells':0 if not missing and not extra else action_cells,
            'forward_pre_return0_handlers':0,'backward_pre_return0_handlers':0,
            'coverage_complete':not missing and not extra,'errors':errors,'pass':not errors}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--exe',type=Path,required=True); ap.add_argument('--save',type=Path,action='append',required=True); ap.add_argument('--json',action='store_true')
    a=ap.parse_args(); out=validate(resolve(a.exe,a.save))
    if a.json: print(json.dumps(out,indent=2,sort_keys=True))
    else: print('handlers=%d/%d families=%d action_cells=%d unknown=%d pre3_return0=%d pre5_return0=%d errors=%d' % (out['evidence_handler_count'],out['candidate_handler_count'],out['control_flow_family_count'],out['action_cells'],out['unknown_return_cells'],out['forward_pre_return0_handlers'],out['backward_pre_return0_handlers'],len(out['errors'])))
    return 0 if out['pass'] else 2
if __name__=='__main__': raise SystemExit(main())
