#!/usr/bin/env python3
"""Validate Stonekeep movement-callback state-delta evidence anchors.

The semantic manifest is intentionally narrow: it freezes directly traced cell
writes / event branches for the six movement handlers already known to mutate
state. Exact SK.EXE SHA, LE object mapping, selector dispatch tables and byte
region hashes are checked before the manifest is accepted.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path

EXPECTED_EXE_SHA='5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2'
NEGATIVE_EVIDENCE_POLICY='NO_DIRECT_WRITE_OBSERVED != ABSENT_VERIFIED; indirect helper effects remain open'

SELECTOR_MAP={
  1:{'offset':0x00,'kind':'u8'}, 2:{'offset':0x02,'kind':'u8'},
  3:{'offset':0x00,'kind':'bit0'}, 4:{'offset':0x09,'kind':'word'},
  5:{'offset':0x0B,'kind':'word'}, 6:{'offset':0x0D,'kind':'s16'},
  7:{'offset':0x0F,'kind':'s16'}, 8:{'offset':0x11,'kind':'s16'},
  9:{'offset':0x13,'kind':'s16'}, 10:{'offset':0x01,'kind':'dir_N_bit'},
  11:{'offset':0x01,'kind':'dir_W_bit'}, 12:{'offset':0x01,'kind':'dir_S_bit'},
  13:{'offset':0x01,'kind':'dir_E_bit'}, 14:{'offset':0x01,'kind':'u8'},
}
GETTER_TABLE_VA=0x3C115
SETTER_TABLE_VA=0x3C1F9
EXPECTED_GETTER_RAW=[0x2C19F,0x2C1A5,0x2C1AC,0x2C1B6,0x2C1BC,0x2C1C2,0x2C1C8,0x2C1CE,0x2C1D4,0x2C1DA,0x2C1DA,0x2C1DA,0x2C1DA,0x2C1E9]
EXPECTED_SETTER_RAW=[0x2C282,0x2C289,0x2C291,0x2C2A3,0x2C2A9,0x2C2AF,0x2C2B5,0x2C2BB,0x2C2C1,0x2C2C7,0x2C2C7,0x2C2C7,0x2C2C7,0x2C2EB]

REGIONS={
 'selector_get_table':(0x3C115,56,'ed8451c365aa06112d2efd6dc9a50f90a14df66994a88c3d4ef7ffc9ee384d42'),
 'selector_set_table':(0x3C1F9,56,'a2e41517b07a3af34b720abb18bf642f33b88e3406533548e2beee66c43c8355'),
 'h110_111_entry':(0x5F1D9,40,'c8e0c089b8f314eba8af6374bb8b93009fa0e99c34a47304d11d77af1856d730'),
 'h110_action5':(0x5F1BC,29,'8eb4e074eba266ed67f7b6e3e625b0167bb087c8bf75ecac186a01e2290623f2'),
 'h112_entry':(0x5F1FF,32,'372805f47403d2948dde6248f670c11b2acf5c88fed2ebd3388d0a46283391ce'),
 'h112_action3':(0x5F289,64,'5829404ca6fc570515b2cbca5e2f3925f63094a31fad58943ee8bae6dc484620'),
 'h115_entry':(0x5F421,32,'676a0c1d52a6d975e7ae5611b02e19b886b6cfe4c85a231851c705c926099e5a'),
 'h115_move_delta':(0x5F551,80,'3735475d2dfe83def1ab2429b9f6f8b27ab0e9abb5fbca00b3af9430924768e3'),
 'h410_entry_delta':(0x4F862,48,'588687e1b7333f23f48a54111214ca95505bf56daa0443232e0d69a65715aaa0'),
 'h415_entry':(0x4F983,48,'a83b72f18daba08ec86f565ca25563e1f5c3cf78561d76a983d768bea1ba9290'),
 'h415_move23':(0x4FB00,64,'f78f9db35fc4b01d1828bb6aa0b1f5eeacce20e321866190f7fbfda189cc0a8b'),
 'h415_multiwrite':(0x4FB46,170,'d22d50c5d774441818cb4fd3185f77d441a6cb2849947a7c4336477c2d1aa2fe'),
 'h415_common':(0x4FC57,80,'502b14e4382f2ff60e6517b46454811247d3be05d0c6942bf776fcf69222fea8'),
}

HANDLERS={
 110:{'target':0x5F1DA,'actions':{
   2:{'class':'NO_DIRECT_WRITE_OBSERVED'},
   3:{'class':'DIRECT_CELL_WRITE','writes':[{'row':14,'col':8,'selector':5,'value':1}]},
   4:{'class':'NO_DIRECT_WRITE_OBSERVED'},
   5:{'class':'DIRECT_CELL_WRITE','writes':[{'row':14,'col':8,'selector':5,'value':2}]},
 }},
 111:{'target':0x5F1D9,'movement_behavior_alias':110},
 112:{'target':0x5F1FF,'actions':{
   2:{'class':'COMMON_ALLOW_CHAIN'},
   3:{'class':'CONDITIONAL_EVENT_SIDE_EFFECT','condition':{'cell':{'row':14,'col':8,'selector':4,'equals':0}},
      'calls':[{'target':0x6A73A,'args':'EAX=4 EDX=4 EBX=4 ECX=10'},{'target':0x9C984,'args':'EAX=0x231'}]},
   4:{'class':'COMMON_ALLOW_CHAIN'},5:{'class':'COMMON_ALLOW_CHAIN'},
 }},
 115:{'target':0x5F421,'actions':{a:{'class':'CONDITIONAL_CELL_WRITE_AND_EVENT',
      'condition':'u16[0x170D9A]!=0 and cell(8,10,selector5)==1',
      'writes':[{'row':8,'col':10,'selector':5,'from':1,'to':2}],
      'calls':[{'target':0x41B44,'args':'EAX=0x1FB7'}]} for a in (2,3,4,5)}},
 410:{'target':0x4F862,'actions':{a:{'class':'CONDITIONAL_CELL_WRITE_AND_EVENT',
      'condition':'cell(16,3,selector4)==0','writes':[{'row':16,'col':3,'selector':4,'from':0,'to':1}],
      'calls':[{'target':0x34228,'args':'fixed bundle @0x4F89A..0x4F8B3'},
               {'target':0xA91F3,'args':'EAX=0x1AFC'},{'target':0xA91F3,'args':'EAX=0x1B0D'}]} for a in (2,3,4,5)}},
 415:{'target':0x4F983,'actions':{
   2:{'class':'ACTION_2_3_SPECIAL_PLUS_COMMON'},3:{'class':'ACTION_2_3_SPECIAL_PLUS_COMMON'},
   4:{'class':'COMMON_CONDITIONAL_DELTA'},5:{'class':'COMMON_CONDITIONAL_DELTA'},
  },'action_2_3_special':{
      'condition':'u16[0x1BC6AE]==0',
      'writes':[{'row':23,'col':3,'selector':4,'value':30}],
      'conditional_multiwrite':{'condition':'cell(23,3,selector4)<=10 or cell(23,2,selector4)==30',
          'writes':[{'row':23,'col':c,'selector':1,'value':16} for c in (6,7,8,19,20,21,22)]}},
    'common_all_actions':{'condition':'u16[0x170D9A]!=0 and cell(23,2,selector5)==1',
      'writes':[{'row':23,'col':2,'selector':5,'from':1,'to':2}],
      'calls':[{'target':0x41B44,'args':'EAX=0x1B25'}]}}
}

class LEImage:
    def __init__(self,data:bytes):
        self.data=data
        if data[:2]!=b'MZ': raise ValueError('not MZ')
        self.le=struct.unpack_from('<I',data,0x3C)[0]
        if data[self.le:self.le+2]!=b'LE': raise ValueError('not LE')
        u32=lambda o: struct.unpack_from('<I',data,self.le+o)[0]
        self.page_size=u32(0x28); self.objtab=u32(0x40); self.nobj=u32(0x44)
        self.objmap=u32(0x48); self.page_off=u32(0x80)
        self.objects=[]
        for i in range(self.nobj):
            size,base,flags,mapidx,mapsize,_=struct.unpack_from('<IIIIII',data,self.le+self.objtab+i*24)
            self.objects.append((size,base,mapidx,mapsize))
        self.page_map=[]
        total=u32(0x14)
        for i in range(total):
            q=self.le+self.objmap+i*4
            page_num=(data[q]<<16)|(data[q+1]<<8)|data[q+2]
            self.page_map.append((page_num,data[q+3]))
    def read_va(self,va:int,n:int)->bytes:
        for size,base,mapidx,mapsize in self.objects:
            if base<=va and va+n<=base+size:
                off=va-base; out=bytearray()
                while n:
                    lp=off//self.page_size; po=off%self.page_size
                    if lp>=mapsize: raise ValueError('unmapped object page')
                    pg,flags=self.page_map[(mapidx-1)+lp]
                    if flags!=0: raise ValueError(f'unsupported LE page flags {flags}')
                    take=min(n,self.page_size-po)
                    fo=self.page_off+(pg-1)*self.page_size+po
                    out+=self.data[fo:fo+take]
                    off+=take; n-=take
                return bytes(out)
        raise ValueError(f'VA 0x{va:X} outside mapped objects')

def validate(exe:Path):
    data=exe.read_bytes(); errors=[]
    sha=hashlib.sha256(data).hexdigest()
    if sha!=EXPECTED_EXE_SHA: errors.append('unexpected SK.EXE SHA-256')
    le=LEImage(data)
    region_results={}
    for name,(va,n,expected) in REGIONS.items():
        got=hashlib.sha256(le.read_va(va,n)).hexdigest(); ok=(got==expected)
        region_results[name]={'va':hex(va),'size':n,'sha256':got,'pass':ok}
        if not ok: errors.append(f'region hash mismatch: {name}')
    getter=list(struct.unpack('<14I',le.read_va(GETTER_TABLE_VA,56)))
    setter=list(struct.unpack('<14I',le.read_va(SETTER_TABLE_VA,56)))
    if getter!=EXPECTED_GETTER_RAW: errors.append('getter selector table mismatch')
    if setter!=EXPECTED_SETTER_RAW: errors.append('setter selector table mismatch')
    return {'exe':str(exe),'exe_sha256':sha,'selector_map':SELECTOR_MAP,
            'selector_tables':{'getter_raw':[hex(x) for x in getter],'setter_raw':[hex(x) for x in setter]},
            'handlers':HANDLERS,'region_validation':region_results,
            'negative_evidence_policy':NEGATIVE_EVIDENCE_POLICY,
            'errors':errors,'pass':not errors}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--exe',required=True,type=Path); ap.add_argument('--json',action='store_true')
    a=ap.parse_args(); out=validate(a.exe)
    if a.json: print(json.dumps(out,indent=2,sort_keys=True))
    else: print('PASS' if out['pass'] else 'FAIL','regions=%d handlers=%d errors=%d'%(len(REGIONS),len(HANDLERS),len(out['errors'])))
    return 0 if out['pass'] else 2
if __name__=='__main__': raise SystemExit(main())
