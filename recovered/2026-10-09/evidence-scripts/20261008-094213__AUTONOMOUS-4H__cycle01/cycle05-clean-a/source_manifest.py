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


TRANCHE2_REGIONS={
 'cell_variant_core':(0x3F9C4,335,'c930ca121869c9dd033f1d9201b7cd8d87f7f16621c7586e1dfcfa34a43489a4'),
 'cell_variant_wrappers':(0x3FB13,104,'67174bbdea78bdc1418e8ff4f7121a394e5d29e8d4a459c542faa389c95148fc'),
 'family_20a35_core':(0x20A35,166,'1618282d256128168164dc4260f3f23ba3af69c0bdf7bcbe12b98e2994e137d8'),
 'family_20a35_wrappers':(0x20ADD,72,'c3fe0b3b6f366131138562458b268ee80fad85b01e8ee9ac545bb54d5aed6e5d'),
 'h93_wrapper':(0x5EC5E,71,'a0d7a075224b9607f1eaac564345db8dc5b8c81cf3845b95ff4aeea75267f4fc'),
 'h414_wrapper':(0x4F93C,71,'4aa0c5cd6b3e29ebdb97de44baa229d19314ce50ca804f43920f2afa6874de20'),
 'h418_wrapper':(0x4FEB4,71,'0b8c5340574c027c03b7633f9fca4a8798cb7887f931ebfcaa3f7b5617f1bd11'),
 'family_93ca4_core':(0x93CA4,265,'60c249391322fcbb2b8d16c268399cee18684176e4e371141fedf8bdd3f0d8ec'),
 'family_93ca4_wrappers':(0x93DAD,47,'e541e86703dc641a7a12903c9e1166341eba8ada8ae49b58dfc7150851c3ac9d'),
 'family_332f2_core':(0x332F2,302,'3d731ec327fdb241268b5e823343222d1938f2718186752c28c00c6a23d64882'),
 'h75_wrappers':(0x33420,47,'516055b46a8e546b9a455795068ded0b18d0ed2128036d1236fd98a51c4c2eab'),
 'h91_movement_common':(0x5E946,464,'15301341bfb6d949cb054a48bf6d53dfd6c98189565c286c3608a68419471655'),
 'h116_entry':(0x5F5A5,41,'61594849269f61a0c60d852f07819a39c4fce927f0bf079bffeb4af5dd3ffa2b'),
 'h416':(0x4FCA9,315,'1e5dd8225155e7da960690d8e5c4ba43d6c015e74391b4b7ad110509271e4b90'),
 'h417':(0x4FDE4,208,'dc2470b38deb342ac7f812d400691a1eba331d56f38bb7421347e375d6b60598'),
 'family_3898a_core':(0x3898A,505,'3fbe69fb761573352e45e94236dfe02abcb528a1a16588810a7e20c6a77f6e89'),
 'h419_wrapper':(0x4FEFB,28,'98a276a23330a1c5ae2c7f429ae4c72592768b3b5d375284a2624f0d9aa9f919'),
}

TRANCHE3_REGIONS={
 'family_ac4aa_core':(0xAC4AA,494,'039c79542dff0643055bf302d69879d76a71c477d18cd6506a852fa7ecc6f54c'),
 'h2_h3_wrappers':(0x6A2D5,38,'37f1c0e827e734d3761bdd0301621897d60f5b7e462ea857d3af87c9ec017268'),
 'family_af87f_core':(0xAF87F,444,'37395bb8ed68b6c7aa7e97792aa3cd754be913cf38519e63138a38ba3ec55a02'),
 'h21_24_wrappers':(0xAFA3B,38,'d1b5f6ef8dae091abb1012f8830580bcd47315e7d3a4605f5a1239d3db3da2ae'),
 'h94_core':(0x84F3A,107,'c35d8d82f611fbf32882f8ab2d5a270c88e9247d220321d4d212e79c9ee6a1c3'),
 'h94_wrapper':(0x84FC2,9,'a4f09cc514aeaea058d9444164c2f517c9675548bb4456fe25cfab9ef65d6679'),
 'h98_103_common':(0x5EEEA,110,'2f116e9ba08d9a728923e9e614ca2050852eba1d6945c29c76f5ed25720bb957'),
 'h98_103_wrappers':(0x5EF58,72,'8cd744c1aeaf873c95cc3a7dc78712c439bf9c32729ddb07952861afafea5e5c'),
 'h109_wrapper':(0x5F116,166,'1442183a1f119b7e18771a419c4d975388c4d97885a2171d88d7fadd2231b094'),
 'h109_ac4_wrapper':(0x6A183,144,'ead634a971d2113fa7f055f7ca7810d19c966722689be1984f05a37c4a15372d'),
 'default_callback_core':(0x3D4F5,13,'31df3bff112887d59319063795e39acb86572dc47835dd26d6f2b480b723e315'),
 'h60_wrapper':(0x3C57B,200,'0b2e78491631414f5ced28fa2add11f692958e1f1fd8e4cc79ed85e565b59208'),
 'h86_wrapper':(0x3D86A,162,'b5d42b69d072d77253ea3e2daa1d9a4e1b9a3b88cb524d1393f34a95a4812683'),
 'h95_97_region':(0x5ECAB,575,'8b91a1a2e7e0491f6861b6323f38e70c5bdad520819677736be40e172d65aa70'),
 'h104_105_region':(0x5EFA0,135,'aea67732ce82977a9efc4fa5e052abcdb5d86fd4eb0e58992d6e32801a69e9b8'),
 'family_3cfee_core':(0x3CFEE,154,'36a2889a901c1c4be9c5f4b88868942e9226d6d779ddffb9b21478958b8fb7fa'),
 'h87_wrapper':(0x5F3B9,68,'52760f9c70718ddf0244354251a07d600807d3ce02f14f1b012bd3562659e15a'),
 'h89_90_wrappers':(0x5E8D2,116,'d5fb61c0bf66ccba53828d002a400b40ce75f13de66736d4fadb3b24a311a44d'),
 'h411_413_wrappers':(0x4F8FC,64,'6100553dfc00d4ee5146e48d6354ab5822994ea9c61c666d9527eaa670d5166f'),
 'h88_wrapper':(0x5E868,106,'3d843300c461bbb5a9db99aa32ba3796b7c2d92bb001afd526d6fcdff995d594'),
 'h106_107_wrappers':(0x5F027,203,'70ee5c07364911ae6b2262ca49a719bea429635467b568b676c7d09a5286877b'),
 'h92_wrapper':(0x5EB8B,211,'1315ac31e14234a2c0367bd109bf73d472f17fbe6f254f34630f148fe68f9d6b'),
 'h113_wrapper':(0x5F2E8,209,'b65c8769fecfb987403042f81036cd177041f7d7243bf56643fed95f879f97e4'),
 'h108_wrapper':(0x5F0F2,36,'181c623f07a0b550591cfdcc16742a27dce1700d85c70a518bbd2ba7d2df6d82'),
 'h108_core':(0x6BAD7,169,'c42f75db531d7cc478e906605d9d5854b5f4947453bda144b256d36f1e2da07c'),
 'h98_103_core_6a2fb':(0x6A2FB,228,'ef19d11bad983039e6a751083c0e0be74a8dd865617272458019e210ea51e4c4'),
}
ALL_REGIONS={**REGIONS,**TRANCHE2_REGIONS,**TRANCHE3_REGIONS}

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


TRANCHE2_HANDLERS={
 13:{'family':'CELL_VARIANT','actions':{2:'DELEGATE_NO_PREWRITE_OBSERVED',3:'DELEGATE_NO_PREWRITE_OBSERVED',4:'CONDITIONAL_INDIRECT_EVENT',5:'CONDITIONAL_INDIRECT_EVENT'}},
 14:{'family':'CELL_VARIANT','alias_action_semantics':13},
 15:{'family':'CELL_VARIANT','alias_action_semantics':13},
 16:{'family':'CELL_VARIANT','alias_action_semantics':13},
 42:{'family':'20A35','actions':{2:'DELEGATE_NO_PREWRITE_OBSERVED',3:'DELEGATE_NO_PREWRITE_OBSERVED',4:'INDIRECT_EVENT_2A7FA_0_1',5:'DELEGATE_NO_PREWRITE_OBSERVED'}},
 43:{'family':'20A35','alias_action_semantics':42},
 93:{'family':'20A35_WRAPPER','alias_action_semantics':42},
 414:{'family':'20A35_WRAPPER','alias_action_semantics':42},
 418:{'family':'20A35_WRAPPER','alias_action_semantics':42},
 75:{'family':'332F2','actions':{2:'DELEGATE_NO_PREWRITE_OBSERVED',3:'DELEGATE_NO_PREWRITE_OBSERVED',4:'INDIRECT_EVENT_2A7FA_0_1_2',5:'DELEGATE_NO_PREWRITE_OBSERVED'}},
 76:{'family':'93CA4','actions':{2:'INDIRECT_EVENT_2A7FA_0_1_2',3:'DELEGATE_NO_PREWRITE_OBSERVED',4:'INDIRECT_EVENT_2A7FA_0_1_2',5:'DELEGATE_NO_PREWRITE_OBSERVED'}},
 77:{'family':'93CA4','alias_action_semantics':76},
 78:{'family':'93CA4','alias_action_semantics':76},
 79:{'family':'93CA4','alias_action_semantics':76},
 80:{'family':'93CA4','alias_action_semantics':76},
 91:{'family':'91_WORLD_STATE','actions':{a:{
      'class':'CONDITIONAL_DIRECT_CELL_WRITE_AND_WORLD_EVENT',
      'condition':'cell(row=5,col=9,selector4)==1',
      'writes':[{'row':5,'col':9,'selector':4,'from':1,'to':2}],
      'continuation':'large world/event sequence then action-specific 33446/33434 delegation',
  } for a in (2,3,4,5)}},
 116:{'family':'115_COMMON_DELTA','actions':{a:{
      'class':'CONDITIONAL_CELL_WRITE_AND_EVENT',
      'condition':'u16[0x170D9A]!=0 and cell(8,10,selector5)==1',
      'writes':[{'row':8,'col':10,'selector':5,'from':1,'to':2}],
      'calls':[{'target':0x41B44,'args':'EAX=0x1FB7'}],
  } for a in (2,3,4,5)}},
 416:{'family':'CHAIN_TO_HANDLER15','actions':{2:'DELEGATE_NO_PREWRITE_OBSERVED',3:'DELEGATE_NO_PREWRITE_OBSERVED',4:'INHERITS_CELL_VARIANT_CONDITIONAL_INDIRECT_EVENT',5:'INHERITS_CELL_VARIANT_CONDITIONAL_INDIRECT_EVENT'}},
 417:{'family':'CHAIN_TO_HANDLER16','alias_action_semantics':416},
 419:{'family':'3898A','actions':{2:'DELEGATE_NO_PREWRITE_OBSERVED',3:'DELEGATE_NO_PREWRITE_OBSERVED',4:'INDIRECT_EVENT_2A7FA_0_1',5:'DELEGATE_NO_PREWRITE_OBSERVED'}},
}


AC4AA_MOVEMENT_ACTIONS={
 2:'INDIRECT_GLOBAL_CALLBACK_1B9DDC_THEN_DEFAULT',
 3:'INDIRECT_GLOBAL_CALLBACK_1B9DDC_THEN_DEFAULT',
 4:'CONDITIONAL_INDIRECT_EVENT_2A7FA_THEN_GLOBAL_CALLBACK_1B9DDC',
 5:'INDIRECT_GLOBAL_CALLBACK_1B9DDC_THEN_DEFAULT',
}
DEFAULT_MOVEMENT_ACTIONS={
 a:'INDIRECT_GLOBAL_CALLBACK_1B9DDC_THEN_DEFAULT' for a in (2,3,4,5)
}
CFEE_MOVEMENT_ACTIONS={
 2:'CONDITIONAL_INDIRECT_EVENT_A2DC7_THEN_GLOBAL_CALLBACK_1B9DDC',
 3:'CONDITIONAL_INDIRECT_EVENT_A2D76_THEN_GLOBAL_CALLBACK_1B9DDC',
 4:'INDIRECT_GLOBAL_CALLBACK_1B9DDC_THEN_DEFAULT',
 5:'INDIRECT_GLOBAL_CALLBACK_1B9DDC_THEN_DEFAULT',
}
DUAL_AC4AA_CFEE_MOVEMENT_ACTIONS={
 2:'AC4AA_GLOBAL_CALLBACK_THEN_CONDITIONAL_A2DC7_THEN_SECOND_GLOBAL_CALLBACK',
 3:'AC4AA_GLOBAL_CALLBACK_THEN_CONDITIONAL_A2D76_THEN_SECOND_GLOBAL_CALLBACK',
 4:'CONDITIONAL_2A7FA_THEN_AC4AA_GLOBAL_CALLBACK_THEN_SECOND_GLOBAL_CALLBACK',
 5:'AC4AA_GLOBAL_CALLBACK_THEN_SECOND_GLOBAL_CALLBACK',
}
HANDLER13_INHERITED_ACTIONS={
 2:'DELEGATE_NO_PREWRITE_OBSERVED',
 3:'DELEGATE_NO_PREWRITE_OBSERVED',
 4:'INHERITS_CELL_VARIANT_CONDITIONAL_INDIRECT_EVENT',
 5:'INHERITS_CELL_VARIANT_CONDITIONAL_INDIRECT_EVENT',
}
TRANCHE3_HANDLERS={
 **{h:{'family':'AC4AA_MOVEMENT','actions':dict(AC4AA_MOVEMENT_ACTIONS),
       'direct_cell_write':'NO_DIRECT_WRITE_OBSERVED_FOR_ACTIONS_2_3_4_5'}
    for h in (2,3,21,22,23,24,94,98,99,100,101,102,103,109)},
 **{h:{'family':'DEFAULT_GLOBAL_CALLBACK','actions':dict(DEFAULT_MOVEMENT_ACTIONS),
       'direct_cell_write':'NO_DIRECT_WRITE_OBSERVED_FOR_ACTIONS_2_3_4_5'}
    for h in (60,86,95,96,97,104,105)},
 **{h:{'family':'3CFEE_MOVEMENT','actions':dict(CFEE_MOVEMENT_ACTIONS),
       'direct_cell_write':'NO_DIRECT_WRITE_OBSERVED_FOR_ACTIONS_2_3_4_5'}
    for h in (87,89,90,411,412,413)},
 **{h:{'family':'AC4AA_THEN_3CFEE_MOVEMENT','actions':dict(DUAL_AC4AA_CFEE_MOVEMENT_ACTIONS),
       'direct_cell_write':'NO_DIRECT_WRITE_OBSERVED_FOR_ACTIONS_2_3_4_5'}
    for h in (88,106,107)},
 92:{'family':'CHAIN_TO_HANDLER13','actions':dict(HANDLER13_INHERITED_ACTIONS),
     'direct_cell_write':'WRAPPER_MOVEMENT_DIRECT_WRITE_NOT_OBSERVED'},
 113:{'family':'CHAIN_TO_HANDLER13','actions':dict(HANDLER13_INHERITED_ACTIONS),
      'direct_cell_write':'WRAPPER_MOVEMENT_DIRECT_WRITE_NOT_OBSERVED'},
 108:{'family':'6BAD7_MOVEMENT_DEFAULT',
      'actions':dict(DEFAULT_MOVEMENT_ACTIONS),
      'direct_cell_write':'NO_DIRECT_WRITE_OBSERVED_FOR_ACTIONS_2_3_4_5',
      'note':'movement actions branch to 0x6BA90 before the 0x6BBxx/0x6BDxx setter paths'},
}
EXPECTED_MOVEMENT_HANDLER_IDS={
 2,3,13,14,15,16,21,22,23,24,42,43,60,75,76,77,78,79,80,86,87,88,89,90,
 91,92,93,94,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,
 111,112,113,115,116,410,411,412,413,414,415,416,417,418,419,
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
    for name,(va,n,expected) in ALL_REGIONS.items():
        got=hashlib.sha256(le.read_va(va,n)).hexdigest(); ok=(got==expected)
        region_results[name]={'va':hex(va),'size':n,'sha256':got,'pass':ok}
        if not ok: errors.append(f'region hash mismatch: {name}')
    getter=list(struct.unpack('<14I',le.read_va(GETTER_TABLE_VA,56)))
    setter=list(struct.unpack('<14I',le.read_va(SETTER_TABLE_VA,56)))
    if getter!=EXPECTED_GETTER_RAW: errors.append('getter selector table mismatch')
    if setter!=EXPECTED_SETTER_RAW: errors.append('setter selector table mismatch')
    tranche_sets=[set(HANDLERS),set(TRANCHE2_HANDLERS),set(TRANCHE3_HANDLERS)]
    if any(tranche_sets[i]&tranche_sets[j] for i in range(3) for j in range(i+1,3)):
        errors.append('handler overlap across state-delta tranches')
    covered=set().union(*tranche_sets)
    if covered!=EXPECTED_MOVEMENT_HANDLER_IDS:
        errors.append('movement-handler state-delta coverage mismatch')
    return {'exe':str(exe),'exe_sha256':sha,'selector_map':SELECTOR_MAP,
            'selector_tables':{'getter_raw':[hex(x) for x in getter],'setter_raw':[hex(x) for x in setter]},
            'handlers':HANDLERS,'tranche2_handlers':TRANCHE2_HANDLERS,'tranche3_handlers':TRANCHE3_HANDLERS,'region_validation':region_results,
            'negative_evidence_policy':NEGATIVE_EVIDENCE_POLICY,
            'errors':errors,'pass':not errors}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--exe',required=True,type=Path); ap.add_argument('--json',action='store_true')
    a=ap.parse_args(); out=validate(a.exe)
    if a.json: print(json.dumps(out,indent=2,sort_keys=True))
    else: print('PASS' if out['pass'] else 'FAIL','regions=%d handlers=%d errors=%d'%(len(ALL_REGIONS),len(HANDLERS)+len(TRANCHE2_HANDLERS)+len(TRANCHE3_HANDLERS),len(out['errors'])))
    return 0 if out['pass'] else 2
if __name__=='__main__': raise SystemExit(main())
