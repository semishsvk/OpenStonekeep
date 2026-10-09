#!/usr/bin/env python3
"""Validate Stonekeep post-translation destination action-1 evidence.

K292-E.6.2 proves that successful ordinary translation invokes the destination
cell handler with action 1. This manifest covers exactly the 56 non-default
handler IDs observed as physically executable destinations in the two
authoritative starter snapshots.

The manifest distinguishes direct serialized-cell writes from indirect
event/runtime effects. NO_DIRECT_CELL_WRITE does not mean no side effects.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_callback_state_delta_manifest import LEImage, EXPECTED_EXE_SHA

DESTINATION_HANDLER_IDS={
 2,3,13,14,15,16,21,22,23,24,42,43,60,76,77,78,79,86,87,88,89,90,
 91,92,93,94,95,96,97,98,99,100,101,102,103,104,105,106,107,109,
 110,111,112,113,115,116,410,411,412,413,414,415,416,417,418,419,
}

REGIONS={
 'cell_variant_core':(0x3F9C4,335,'c930ca121869c9dd033f1d9201b7cd8d87f7f16621c7586e1dfcfa34a43489a4'),
 'family_20a35_core':(0x20A35,166,'1618282d256128168164dc4260f3f23ba3af69c0bdf7bcbe12b98e2994e137d8'),
 'family_ac4aa_core':(0xAC4AA,494,'039c79542dff0643055bf302d69879d76a71c477d18cd6506a852fa7ecc6f54c'),
 'family_93ca4_core':(0x93CA4,265,'60c249391322fcbb2b8d16c268399cee18684176e4e371141fedf8bdd3f0d8ec'),
 'family_3cfee_core':(0x3CFEE,154,'36a2889a901c1c4be9c5f4b88868942e9226d6d779ddffb9b21478958b8fb7fa'),
 'family_3898a_core':(0x3898A,505,'3fbe69fb761573352e45e94236dfe02abcb528a1a16588810a7e20c6a77f6e89'),
 'family_af87f_core':(0xAF87F,444,'37395bb8ed68b6c7aa7e97792aa3cd754be913cf38519e63138a38ba3ec55a02'),
 'family_6a2fb_core':(0x6A2FB,228,'ef19d11bad983039e6a751083c0e0be74a8dd865617272458019e210ea51e4c4'),
 'h86_action1':(0x3D86A,162,'b5d42b69d072d77253ea3e2daa1d9a4e1b9a3b88cb524d1393f34a95a4812683'),
 'h91_action1':(0x5E946,464,'15301341bfb6d949cb054a48bf6d53dfd6c98189565c286c3608a68419471655'),
 'h96_action1':(0x5ECB1,234,'387a7f48630b92e0c3cbd2165f1e5184abb0c83578f0d1af7057ace7ce6158f9'),
 'h105_action1':(0x5EFDC,75,'52bd3ae3e5c6dbb69d77c6dac7021bed86b907c5e145f020eddceb956bbd70c1'),
 'h112_action1':(0x5F1FF,233,'3dd64bbee1abd71a5e2e168444d66892fa734e1bd3717ffe83e3c2712a385468'),
 'h115_action1':(0x5F421,388,'28745c53cb2ee7cefe66503b73f4971877747dfef2eee2dd52daaa012f445d15'),
 'h410_action1':(0x4F862,154,'20eef5170cd3d759551f216c34cd2e6c6a0be33a5aae17235833cb57c714f327'),
 'h415_action1':(0x4F983,806,'651937d197a5b8495b722d6f83191434994f05ef652a1ab9c57106f7723e8b5a'),
 'h416_action1':(0x4FCA9,315,'1e5dd8225155e7da960690d8e5c4ba43d6c015e74391b4b7ad110509271e4b90'),
 'h417_action1':(0x4FDE4,208,'dc2470b38deb342ac7f812d400691a1eba331d56f38bb7421347e375d6b60598'),
}

FAMILIES={
 'DIRECT_SERIALIZED_CELL_WRITE':{86,91,96,105,112,115,410,415},
 'CELL_VARIANT_RUNTIME_EVENT':{13,14,15,16,92,113,116},
 'CELL_VARIANT_CONDITIONAL_WRAPPER':{416,417},
 'FAMILY_20A35_RUNTIME_EVENT':{42,43,93,414,418},
 'AC4AA_INDIRECT_EVENT':{2,3,21,22,23,24,94,98,99,100,101,102,103,109},
 'THREE_CFEE_COMMON':{87,89,90,411,412,413},
 'AC4AA_THEN_THREE_CFEE':{88,106,107},
 'NINETY3CA4_INDIRECT_EVENT':{76,77,78,79},
 'DEFAULT_COMMON':{60,95,97,104,110,111},
 'THREE898A_INDIRECT_EVENT':{419},
}

DIRECT_WRITES={
 86:{
   'class':'CONDITIONAL_CURRENT_DESTINATION_WRITE',
   'condition':'destination selector4 == 0',
   'writes':[{'cell':'current_destination','selector':4,'from':0,'to':1}],
   'effects':['formatted event via 0x41B44','then common continuation'],
 },
 91:{
   'class':'CONDITIONAL_FIXED_CELL_WRITE_AND_WORLD_SEQUENCE',
   'condition':'cell(row=5,col=9,selector4) == 1',
   'writes':[{'row':5,'col':9,'selector':4,'from':1,'to':2}],
   'effects':['large world/event sequence','then action-dependent continuation'],
 },
 96:{
   'class':'CONDITIONAL_FIXED_CELL_WRITE_AND_EVENT',
   'condition':'dword[0x1B9D84] == 0',
   'writes':[{'row':7,'col':8,'selector':4,'value':1}],
   'effects':['0x5ED9B','0x3DEF7','0x3DECB','then common continuation'],
 },
 105:{
   'class':'CONDITIONAL_FIXED_CELL_WRITE_AND_EVENT',
   'condition':'cell(row=7,col=18,selector4) == 0',
   'writes':[{'row':7,'col':18,'selector':4,'from':0,'to':1}],
   'effects':['0x41B44 with EAX=0x1FB0','then common continuation'],
 },
 112:{
   'class':'FIXED_CELL_RESET_WITH_CONDITIONAL_EVENT',
   'condition':'action1 always reaches the setter',
   'writes':[{'row':14,'col':8,'selector':5,'value':0}],
   'effects':['if prior selector5==2 and selector4==0: 0x6B320,0x6A73A,0x9C984','then 0x6B69D'],
 },
 115:{
   'class':'CONDITIONAL_FIXED_CELL_WRITE_AND_EVENT',
   'condition':'u16[0x170D9A] != 0 and cell(row=8,col=10,selector5) == 1',
   'writes':[{'row':8,'col':10,'selector':5,'from':1,'to':2}],
   'effects':['0x41B44 with EAX=0x1FB7','then handler14 action1 semantics'],
 },
 410:{
   'class':'CONDITIONAL_FIXED_CELL_WRITE_AND_EVENT',
   'condition':'cell(row=16,col=3,selector4) == 0',
   'writes':[{'row':16,'col':3,'selector':4,'from':0,'to':1}],
   'effects':['0x34228 fixed bundle','0xA91F3 EAX=0x1AFC','0xA91F3 EAX=0x1B0D','then common continuation'],
 },
 415:{
   'class':'CONDITIONAL_FIXED_CELL_WRITE_AND_EVENT',
   'condition':'u16[0x170D9A] != 0 and cell(row=23,col=2,selector5) == 1',
   'writes':[{'row':23,'col':2,'selector':5,'from':1,'to':2}],
   'effects':['0x41B44 with EAX=0x1B25','then 0x6A230 / AC4AA-family action1'],
 },
}

FAMILY_SEMANTICS={
 'CELL_VARIANT_RUNTIME_EVENT':
   'action1 may update runtime globals 0x1BC3F0/0x1B9F28/0x1B9F2B/0x1B9F2F and call 0x3FB7B when facing matches; no direct serialized-cell setter in core',
 'CELL_VARIANT_CONDITIONAL_WRAPPER':
   '416/417 either delegate to handler15/16 action1 or take a 0x2A7FA event branch depending serialized state; no direct action1 setter in wrapper',
 'FAMILY_20A35_RUNTIME_EVENT':
   'action1 may update runtime globals 0x1BC424/0x1BC428 and call 0x20B25, or call 0x2A7FA(0/1); no direct serialized-cell setter in core',
 'AC4AA_INDIRECT_EVENT':
   'action1 calls 0x2A7FA when facing matches and may reach 0x2A5F1 world/event logic; AF87F and 6A2FB wrappers have no action1 direct cell write',
 'THREE_CFEE_COMMON':
   'action1 immediately reaches the common 0x3D4F5 continuation; no direct serialized-cell setter in 0x3CFEE action1 path',
 'AC4AA_THEN_THREE_CFEE':
   'action1 composes AC4AA indirect-event behavior and the 0x3CFEE common continuation; no direct serialized-cell setter in wrapper/core path',
 'NINETY3CA4_INDIRECT_EVENT':
   'action1 calls 0x2A7FA with 0/1/2 and may call 0x93DDC when direction matches; no direct serialized-cell setter in 0x93CA4 core',
 'DEFAULT_COMMON':
   'action1 reaches 0x3D4F5/0x3C36A common post-processing without a handler-local direct serialized-cell setter',
 'THREE898A_INDIRECT_EVENT':
   'action1 calls 0x2A7FA(0/1) and can reach 0x2A5F1 world/event logic before common continuation; no direct serialized-cell setter in core',
}

NEGATIVE_EVIDENCE_POLICY=(
 'NO_DIRECT_SERIALIZED_CELL_WRITE means no direct call to the verified cell '
 'setter on the traced action1 handler/core path; indirect helper effects '
 'remain open and are not ABSENT_VERIFIED.'
)

def validate(exe:Path):
    data=exe.read_bytes(); errors=[]
    sha=hashlib.sha256(data).hexdigest()
    if sha!=EXPECTED_EXE_SHA:
        errors.append('unexpected SK.EXE SHA-256')
    try:
        le=LEImage(data)
    except Exception as e:
        return {'pass':False,'errors':errors+[f'LE parse failed: {e}']}
    region_results={}
    for name,(va,n,expected) in REGIONS.items():
        got=hashlib.sha256(le.read_va(va,n)).hexdigest()
        ok=(got==expected)
        region_results[name]={'va':hex(va),'size':n,'sha256':got,'pass':ok}
        if not ok:
            errors.append(f'region hash mismatch: {name}')
    groups=[set(v) for v in FAMILIES.values()]
    if any(groups[i]&groups[j] for i in range(len(groups)) for j in range(i+1,len(groups))):
        errors.append('action1 family overlap')
    covered=set().union(*groups)
    if covered!=DESTINATION_HANDLER_IDS:
        errors.append('destination action1 handler coverage mismatch')
    if set(DIRECT_WRITES)!=FAMILIES['DIRECT_SERIALIZED_CELL_WRITE']:
        errors.append('direct-write manifest mismatch')
    return {
      'exe':str(exe),'exe_sha256':sha,
      'destination_handler_count':len(DESTINATION_HANDLER_IDS),
      'destination_handler_ids':sorted(DESTINATION_HANDLER_IDS),
      'family_counts':{k:len(v) for k,v in FAMILIES.items()},
      'families':{k:sorted(v) for k,v in FAMILIES.items()},
      'family_semantics':FAMILY_SEMANTICS,
      'direct_write_handlers':DIRECT_WRITES,
      'direct_write_handler_count':len(DIRECT_WRITES),
      'region_validation':region_results,
      'negative_evidence_policy':NEGATIVE_EVIDENCE_POLICY,
      'errors':errors,'pass':not errors,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--exe',required=True,type=Path)
    ap.add_argument('--json',action='store_true')
    a=ap.parse_args(); out=validate(a.exe)
    if a.json:
        print(json.dumps(out,indent=2,sort_keys=True))
    else:
        print(('PASS' if out['pass'] else 'FAIL'),
              'handlers=%d direct=%d regions=%d errors=%d'%(
                out.get('destination_handler_count',0),
                out.get('direct_write_handler_count',0),
                len(out.get('region_validation',{})),
                len(out['errors'])))
    return 0 if out['pass'] else 2

if __name__=='__main__':
    raise SystemExit(main())
