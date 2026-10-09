import struct,collections
from pathlib import Path

def group_payload(path,name):
    b=Path(path).read_bytes(); n=struct.unpack_from("<H",b,0)[0]; rec=[]
    for i in range(n):
        p=2+i*22
        nm=b[p:p+12].split(b"\0",1)[0].decode("ascii","replace")
        off=struct.unpack_from("<I",b,p+14)[0]
        rec.append((nm,off))
    for i,(nm,off) in enumerate(rec):
        if nm==name:
            end=rec[i+1][1] if i+1<len(rec) else len(b)-4
            return b[off:end]
    raise KeyError(name)

def parse_maz(payload):
    rows,cols=struct.unpack_from("<HH",payload,2); pos=6+2*rows*cols
    n1=struct.unpack_from("<H",payload,pos)[0]; pos+=2+18*n1
    n2=struct.unpack_from("<H",payload,pos)[0]; pos+=2
    for _ in range(n2):
        w=struct.unpack_from("<5h",payload,pos); pos+=10
        if w[0]==3 and (w[4]>=0 or w[4]==-99): pos+=8
    n3=struct.unpack_from("<H",payload,pos)[0]; pos+=2; msp=[]
    for _ in range(n3):
        base=payload[pos:pos+26]; pos+=26; w=struct.unpack("<13h",base)
        pos+=16*w[12]
        nb=struct.unpack_from("<H",payload,pos)[0]; pos+=2
        for _ in range(nb):
            mb=payload[pos:pos+16]; pos+=16; mw=struct.unpack("<8h",mb)
            pos+=14*mw[7]
        msp.append(base)
    return rows,cols,msp

def sig(base):
    w=list(struct.unpack("<13h",base)); w[1]=w[2]=0; return tuple(w)

base=Path(r"F:\Remaster Framework\source\Stonekeep\CD\DATA")
p1=group_payload(base/"GROUP01","LEVEL01.MAZ")
p2=group_payload(base/"GROUP02","LEVEL02.MAZ")
r1,c1,m1=parse_maz(p1); r2,c2,m2=parse_maz(p2)
save=(base/"START"/"SAVEGAME"/"GAME00"/"LEVEL01.SAV").read_bytes()
off=11+r1*c1*21+400*12+2+54*54*2
cnt=struct.unpack_from("<H",save,off)[0]; off+=2
runtime=[save[off+i*48:off+(i+1)*48] for i in range(cnt)]
mp=collections.defaultdict(set)
for i,b in enumerate(m1): mp[sig(b)].add(runtime[i][0x18])
amb={k:v for k,v in mp.items() if len(v)>1}
covered=0; unknown=[]; masks=collections.Counter()
for i,b in enumerate(m2):
    s=sig(b)
    if s in mp and len(mp[s])==1:
        covered+=1; masks[next(iter(mp[s]))]+=1
    else:
        unknown.append((i,struct.unpack("<13h",b)[:5],bool(s in mp),sorted(mp.get(s,()))))
print("L1 records",len(m1),"signatures",len(mp),"ambiguous",len(amb))
print("L2 records",len(m2),"covered",covered,"unknown",len(unknown))
print("covered mask histogram",dict(sorted(masks.items())))
print("unknown",unknown)
