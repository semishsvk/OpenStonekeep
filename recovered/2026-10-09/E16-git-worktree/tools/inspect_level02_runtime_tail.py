#!/usr/bin/env python3
"""Validate STONE-K292-E.14 LEVEL02 typed MAZ runtime-tail evidence.

Read-only evidence tool. It decodes the variable-length tail consumed by the
generic MAZ materializer and uses LEVEL01.MAZ -> LEVEL01.SAV as an independent
runtime oracle before applying the same contracts to LEVEL02.

Scope is deliberately narrow: enough initial MSP and monster placement state
to evaluate the two verified LEVEL02 return portals after their E.9 LOW clear.
"""
from __future__ import annotations
import argparse, hashlib, json, struct, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inspect_group import parse as parse_group
from resolve_le_handler_dispatch import LE

EXPECTED_EXE_SHA="5517ddeb49c7087d6b2449182020200c58084feb4cae55e31ac8acc6cdbdddd2"
EXPECTED_GROUP01_SHA="7677db711fa51144ba4f88349241e136680d11c8c03a1dbf50b645b69829cb56"
EXPECTED_GROUP02_SHA="ae4fadcddfb3f722330cbcda1362e8ed4b77a1642de5b20aa4f668151fbea425"
EXPECTED_LEVEL01_SAVE_SHA="2375c9d383ca4425ebb99b904eedc6417923a1332ff84c416566e663ef6326a9"
EXPECTED_LEVEL01_MAZ_SHA="58bb761f67a6660b704cb126822e252e76d0a64bb56765b665ff540793d8daa3"
EXPECTED_LEVEL02_MAZ_SHA="2255a617c1470bc388fa33667944d9df7dac350b2f0a5943a95fc719ae475b84"
CELL_SIZE=0x15
MSP_STRIDE=0x30
LOW=(0x08,0x02,0x04,0x01)
LOW_OPP=(0x04,0x01,0x08,0x02)
DIRS=(( -1,0),(0,-1),(1,0),(0,1))

REGIONS={
 "typed_tail_msp_block":(0x6E220,0x770,"1b9e13fe981fb2a1f200a31d6a28f1c18b3de1faba760477118e84a0aafc0a54"),
 "typed_tail_monster_block":(0x6E990,0x184,"a8140ca8280fb6690e5bbe5397cd5a4c53c7c9c8807a4a9467c02a5dd4f7fe28"),
 "monster_spatial_placement":(0x76980,0x100,"cde2298ed479f24a350207a344468daa1ba68c92ad3c12c71ecfaffc4b66c79d"),
 "msp_allocate":(0x11B40,0x100,"f4fb73bb65e3dae6e4b52818340f815eee451703de6d6bdbf9b2ffef0dc94d92"),
}

PORTALS=(
 {"handler":144,"source":(6,2),"direction":2,"adjacent":(7,2)},
 {"handler":145,"source":(2,17),"direction":3,"adjacent":(2,18)},
)

def s16(b,o): return struct.unpack_from("<h",b,o)[0]
def u16(b,o): return struct.unpack_from("<H",b,o)[0]

def read_runtime(le:LE,va:int,n:int)->bytes:
    out=bytearray(); cur=va; rem=n
    while rem:
        found=None
        for objnum,obj in enumerate(le.objects,1):
            if obj["base"]<=cur<obj["base"]+obj["size"]:
                found=(objnum,obj,cur-obj["base"]); break
        if found is None: raise ValueError(f"VA 0x{cur:X} outside LE objects")
        objnum,obj,off=found
        take=min(rem,le.page_size-(off%le.page_size),obj["size"]-off)
        fo=le.object_file_offset(objnum,off)
        out+=le.data[fo:fo+take]; cur+=take; rem-=take
    return bytes(out)

def extract_named(group:Path,name:str):
    info=parse_group(group); data=group.read_bytes()
    hits=[e for e in info["entries"] if e["name"]==name]
    if len(hits)!=1: raise ValueError(f"{name}: GROUP entries={len(hits)}")
    e=hits[0]; payload=data[e["payload_start"]:e["payload_end"]]
    return info,e,payload

def parse_maz(payload:bytes)->dict:
    if payload[:2]!=b"ON": raise ValueError("MAZ marker is not ON")
    rows,cols=struct.unpack_from("<HH",payload,2); cells=rows*cols
    pos=6+2*cells
    if pos>len(payload): raise ValueError("truncated grid planes")

    n1=u16(payload,pos); pos+=2
    block1=[]
    for _ in range(n1):
        if pos+18>len(payload): raise ValueError("truncated block1")
        block1.append(payload[pos:pos+18]); pos+=18

    n2=u16(payload,pos); pos+=2
    block2=[]
    for _ in range(n2):
        if pos+10>len(payload): raise ValueError("truncated block2 base")
        base=payload[pos:pos+10]; pos+=10; w=struct.unpack("<5h",base)
        extra=b""
        if w[0]==3 and (w[4]>=0 or w[4]==-99):
            if pos+8>len(payload): raise ValueError("truncated block2 extra")
            extra=payload[pos:pos+8]; pos+=8
        block2.append((base,extra))

    n3=u16(payload,pos); pos+=2
    msp=[]
    for outer in range(n3):
        if pos+26>len(payload): raise ValueError("truncated MSP base")
        base=payload[pos:pos+26]; pos+=26; w=struct.unpack("<13h",base)
        count_a=w[12]
        if count_a<0: raise ValueError("negative MSP POJ count")
        poj_a=[]
        for _ in range(count_a):
            if pos+16>len(payload): raise ValueError("truncated MSP POJ")
            poj_a.append(payload[pos:pos+16]); pos+=16

        count_b=u16(payload,pos); pos+=2
        monsters=[]
        for _ in range(count_b):
            if pos+16>len(payload): raise ValueError("truncated nested monster")
            mb=payload[pos:pos+16]; pos+=16; mw=struct.unpack("<8h",mb)
            count_c=mw[7]
            if count_c<0: raise ValueError("negative nested monster POJ count")
            attached=[]
            for _ in range(count_c):
                if pos+14>len(payload): raise ValueError("truncated nested monster POJ")
                attached.append(payload[pos:pos+14]); pos+=14
            monsters.append((mb,attached))
        msp.append((base,poj_a,monsters))

    n4=u16(payload,pos); pos+=2
    monsters=[]
    for _ in range(n4):
        if pos+18>len(payload): raise ValueError("truncated standalone monster")
        base=payload[pos:pos+18]; pos+=18; w=struct.unpack("<9h",base)
        count=w[8]
        if count<0: raise ValueError("negative standalone monster POJ count")
        attached=[]
        for _ in range(count):
            if pos+14>len(payload): raise ValueError("truncated standalone monster POJ")
            attached.append(payload[pos:pos+14]); pos+=14
        monsters.append((base,attached))

    if pos!=len(payload):
        raise ValueError(f"MAZ tail did not end on EOF: 0x{pos:X}/0x{len(payload):X}")

    return {
      "rows":rows,"columns":cols,"cell_count":cells,
      "block1_count":n1,"block2_count":n2,"msp_count":n3,
      "standalone_monster_count":n4,"msp":msp,"monsters":monsters,
      "end_offset":pos,
    }

def parse_save_msp(path:Path)->dict:
    data=path.read_bytes(); rows,cols=struct.unpack_from("<HH",data,7)
    grid_end=11+rows*cols*CELL_SIZE
    msp_count_off=grid_end+400*0x0C+2+54*54*2
    count=u16(data,msp_count_off); start=msp_count_off+2
    recs=[data[start+i*MSP_STRIDE:start+(i+1)*MSP_STRIDE] for i in range(count)]
    return {"sha256":hashlib.sha256(data).hexdigest(),"rows":rows,"columns":cols,"records":recs}

def msp_signature(base:bytes):
    w=list(struct.unpack("<13h",base))
    # Coordinates are the only fields intentionally ignored.
    w[1]=0; w[2]=0
    return tuple(w)

def monster_positions(parsed:dict):
    nested=[]
    for oi,(base,_poj,mons) in enumerate(parsed["msp"]):
        w=struct.unpack("<13h",base); row,col=w[1],w[2]
        for mi,(mb,_attached) in enumerate(mons):
            # 0x6E4C1/0x6E4C9 copy the parent MSP row/column into the
            # nested monster runtime record.
            nested.append((row,col,oi,mi))
    standalone=[]
    for i,(base,_attached) in enumerate(parsed["monsters"]):
        w=struct.unpack("<9h",base)
        # 0x6EA20..0x6EA37 pass words +2/+4 as row/column to 0x76980.
        standalone.append((w[1],w[2],i))
    return nested,standalone

def inspect(exe:Path,group01:Path,group02:Path,level01_save:Path)->dict:
    errors=[]
    eb=exe.read_bytes(); esha=hashlib.sha256(eb).hexdigest()
    if esha!=EXPECTED_EXE_SHA: errors.append("unexpected SK.EXE SHA-256")
    if hashlib.sha256(group01.read_bytes()).hexdigest()!=EXPECTED_GROUP01_SHA:
        errors.append("unexpected GROUP01 SHA-256")
    if hashlib.sha256(group02.read_bytes()).hexdigest()!=EXPECTED_GROUP02_SHA:
        errors.append("unexpected GROUP02 SHA-256")

    _g1,e1,maz1=extract_named(group01,"LEVEL01.MAZ")
    _g2,e2,maz2=extract_named(group02,"LEVEL02.MAZ")
    if hashlib.sha256(maz1).hexdigest()!=EXPECTED_LEVEL01_MAZ_SHA:
        errors.append("unexpected LEVEL01.MAZ SHA-256")
    if hashlib.sha256(maz2).hexdigest()!=EXPECTED_LEVEL02_MAZ_SHA:
        errors.append("unexpected LEVEL02.MAZ SHA-256")

    try:
        p1=parse_maz(maz1); p2=parse_maz(maz2)
    except Exception as exc:
        errors.append(str(exc)); p1=p2=None

    save=parse_save_msp(level01_save)
    if save["sha256"]!=EXPECTED_LEVEL01_SAVE_SHA:
        errors.append("unexpected LEVEL01.SAV SHA-256")

    oracle={"msp_prefix_count":0,"type13_records":[],"pass":False}
    type13_sig=None
    if p1 is not None:
        if len(save["records"])<p1["msp_count"]:
            errors.append("LEVEL01 save MSP pool shorter than MAZ initial MSP count")
        else:
            mism=[]
            for i,(base,_a,_m) in enumerate(p1["msp"]):
                mw=struct.unpack("<13h",base); sw=struct.unpack("<24h",save["records"][i])
                if (mw[0],mw[1],mw[2],mw[3],mw[4]) != (sw[0],sw[2],sw[3],sw[4],sw[5]):
                    mism.append(i)
            if mism: errors.append(f"LEVEL01 MAZ/save MSP identity mismatches={mism[:8]}")
            oracle["msp_prefix_count"]=p1["msp_count"]
            type13=[]
            for i,(base,_a,_m) in enumerate(p1["msp"]):
                w=struct.unpack("<13h",base)
                if w[0]==13:
                    mask=save["records"][i][0x18]
                    type13.append({"index":i,"row":w[1],"column":w[2],"movement_mask":mask})
            oracle["type13_records"]=type13
            sigs={msp_signature(p1["msp"][x["index"]][0]) for x in type13}
            masks={x["movement_mask"] for x in type13}
            if len(type13)!=4 or len(sigs)!=1 or masks!={0}:
                errors.append("LEVEL01 type13 oracle is not four identical mask-zero records")
            else:
                type13_sig=next(iter(sigs)); oracle["pass"]=True

    portals=[]
    if p2 is not None:
        nested,standalone=monster_positions(p2)
        for spec in PORTALS:
            sr,sc=spec["source"]; ar,ac=spec["adjacent"]; didx=spec["direction"]
            src_msp=[]; dst_msp=[]
            for i,(base,_a,_m) in enumerate(p2["msp"]):
                w=struct.unpack("<13h",base)
                if (w[1],w[2])==(sr,sc): src_msp.append((i,w))
                if (w[1],w[2])==(ar,ac): dst_msp.append((i,w))
            src_masks=[]
            dst_masks=[]
            unknown_msp=False
            for _idx,w in src_msp:
                sig=list(w); sig[1]=sig[2]=0
                if type13_sig is not None and tuple(sig)==type13_sig: src_masks.append(0)
                else: unknown_msp=True
            for _idx,w in dst_msp:
                sig=list(w); sig[1]=sig[2]=0
                if type13_sig is not None and tuple(sig)==type13_sig: dst_masks.append(0)
                else: unknown_msp=True
            source_mask=0
            for x in src_masks: source_mask|=x
            dest_mask=0
            for x in dst_masks: dest_mask|=x
            msp_blocked=bool(source_mask & (LOW[didx]|0x10) or dest_mask & LOW_OPP[didx])
            monster_here=[
                x for x in nested if x[:2] in ((sr,sc),(ar,ac))
            ] + [
                x for x in standalone if x[:2] in ((sr,sc),(ar,ac))
            ]
            spatial_blocked=bool(monster_here)
            if unknown_msp:
                errors.append(f"h{spec['handler']}: unknown MSP mask signature at portal")
            if msp_blocked:
                errors.append(f"h{spec['handler']}: MSP blocks after LOW clear")
            if spatial_blocked:
                errors.append(f"h{spec['handler']}: initial monster occupies portal source/adjacent")
            portals.append({
              "handler_id":spec["handler"],"source":[sr,sc],"adjacent":[ar,ac],
              "source_msp":[{"index":i,"type":w[0]} for i,w in src_msp],
              "adjacent_msp":[{"index":i,"type":w[0]} for i,w in dst_msp],
              "source_msp_mask":source_mask,"adjacent_msp_mask":dest_mask,
              "msp_blocked_after_low_clear":msp_blocked,
              "monster_records_at_source_or_adjacent":monster_here,
              "spatial_blocked_initial":spatial_blocked,
              "physical_clear_after_low_clear":not(msp_blocked or spatial_blocked or unknown_msp),
            })

    le=LE(eb); regions={}
    for name,(va,n,expected) in REGIONS.items():
        got=hashlib.sha256(read_runtime(le,va,n)).hexdigest(); ok=got==expected
        regions[name]={"runtime_va":hex(va),"size":n,"sha256":got,"pass":ok}
        if not ok: errors.append(f"region hash mismatch: {name}")

    return {
      "exe_sha256":esha,
      "level01_oracle":oracle,
      "level01_counts":None if p1 is None else {
        "block1":p1["block1_count"],"block2":p1["block2_count"],
        "msp":p1["msp_count"],"standalone_monsters":p1["standalone_monster_count"],
        "nested_monsters":sum(len(x[2]) for x in p1["msp"]),"end":p1["end_offset"],
      },
      "level02_counts":None if p2 is None else {
        "block1":p2["block1_count"],"block2":p2["block2_count"],
        "msp":p2["msp_count"],"standalone_monsters":p2["standalone_monster_count"],
        "nested_monsters":sum(len(x[2]) for x in p2["msp"]),"end":p2["end_offset"],
      },
      "level02_portals":portals,
      "physical_clear_portal_count":sum(x["physical_clear_after_low_clear"] for x in portals),
      "region_validation":regions,
      "evidence":{
        "block4_nested_count_field":"record +0x10 u16; parser consumes exact EOF on LEVEL01 and LEVEL02",
        "block3_nested_monster_position":"inherits parent MSP row/column via runtime writes at 0x6E4C1/0x6E4C9",
        "block4_monster_position":"record words +0x02/+0x04 passed to 0x76980 spatial placement",
        "type13_movement_mask":"LEVEL01 MAZ->SAVE oracle: identical non-coordinate signature, 4/4 mask=0",
      },
      "one_way_verdict_authorized":False,
      "softlock_verdict_authorized":False,
      "errors":errors,"pass":not errors,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--exe",type=Path,required=True)
    ap.add_argument("--group01",type=Path,required=True)
    ap.add_argument("--group02",type=Path,required=True)
    ap.add_argument("--level01-save",type=Path,required=True)
    ap.add_argument("--json",action="store_true")
    a=ap.parse_args(); out=inspect(a.exe,a.group01,a.group02,a.level01_save)
    if a.json: print(json.dumps(out,indent=2,sort_keys=True))
    else:
        c=out["level02_counts"] or {}
        print(("PASS" if out["pass"] else "FAIL"),
              f"msp={c.get('msp')}",f"nested_monsters={c.get('nested_monsters')}",
              f"standalone_monsters={c.get('standalone_monsters')}",
              f"portal_clear={out['physical_clear_portal_count']}/2",
              f"regions={len(out['region_validation'])}",f"errors={len(out['errors'])}")
    return 0 if out["pass"] else 2
if __name__=="__main__": raise SystemExit(main())
