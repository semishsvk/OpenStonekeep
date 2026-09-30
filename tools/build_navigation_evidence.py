#!/usr/bin/env python3
"""Build an evidence-typed candidate player-navigation graph for Stonekeep.

STONE-K292-D uses only K292-C evidence:

DIRECT PLAYER PRIMITIVE
- cell+0x02 low directional bit is the direct forward/backward static barrier.

RUNTIME GATES
- runtime MSP/maze-prop clearance and monster-linked spatial occupancy are
  separate prechecks, so every static-clear edge remains runtime-gated.

SCRIPT/EVENT
- signed cell+0x07 selects the current cell's pre/post action callback.
- a non-zero source handler makes the directed edge SCRIPTED because the
  pre-movement callback can veto/alter behavior.
- a non-zero destination handler is reported only as destination event evidence.

Actor-specific monster-only blockers (cell0 0x10/0x80 and cell2 high nibble)
are reported but never used to suppress a player edge.

This tool does not issue one-way or softlock verdicts.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path

CELL_SIZE=0x15
SENTINEL_NONE=-100

DIRECTIONS=(
    ("N",-1,0,0x08,"S"),
    ("W",0,-1,0x02,"E"),
    ("S",1,0,0x04,"N"),
    ("E",0,1,0x01,"W"),
)
BY_NAME={d[0]:d for d in DIRECTIONS}

def s16(buf:bytes,off:int)->int:
    return struct.unpack_from("<h",buf,off)[0]

def read_level(path:Path):
    data=path.read_bytes()
    if len(data)<11:
        raise ValueError("file too small for level-save header")
    marker=struct.unpack_from("<H",data,0)[0]
    version=data[2:7].rstrip(b"\0").decode("ascii","replace")
    rows,cols=struct.unpack_from("<HH",data,7)
    grid_end=11+rows*cols*CELL_SIZE
    if grid_end>len(data):
        raise ValueError("truncated grid")
    grid=data[11:grid_end]
    cells=[grid[i*CELL_SIZE:(i+1)*CELL_SIZE] for i in range(rows*cols)]
    return data,marker,version,rows,cols,cells

def idx(row:int,col:int,cols:int)->int:
    return row*cols+col

def cell_meta(cell:bytes)->dict:
    return {
        "handler":s16(cell,0x07),
        "msp_head":s16(cell,0x11),
        "monster_head":s16(cell,0x0F),
        "monster_actor_gate_0x10":bool(cell[0x00]&0x10),
        "monster_runtime_gate_0x80":bool(cell[0x00]&0x80),
    }

def classify_directed_edge(cells:list[bytes],rows:int,cols:int,
                           row:int,col:int,direction:str)->dict:
    name,dr,dc,mask,opp=BY_NAME[direction]
    nr,nc=row+dr,col+dc
    if not (0<=nr<rows and 0<=nc<cols):
        return {
            "source":[row,col],"direction":direction,"destination":None,
            "class":"OUT_OF_BOUNDS","candidate":False,
        }
    a=cells[idx(row,col,cols)]
    b=cells[idx(nr,nc,cols)]
    opposite_mask=BY_NAME[opp][3]
    src_set=bool(a[0x02]&mask)
    dst_set=bool(b[0x02]&opposite_mask)

    # K292-A expects reciprocity; retain explicit corruption class here.
    if src_set != dst_set:
        edge_class="STATIC_MISMATCH"
        candidate=False
    elif src_set:
        edge_class="STATIC_BLOCKED"
        candidate=False
    elif s16(a,0x07)!=0:
        edge_class="SCRIPTED"
        candidate=True
    else:
        edge_class="STATIC_CLEAR_RUNTIME_GATED"
        candidate=True

    # High directional bit for the same direction is actor-specific monster
    # evidence only, not player policy.
    high_mask=mask<<4
    # Because the low/high directional mapping is exact x16 for all four masks:
    # N 08->80, W 02->20, S 04->40, E 01->10.
    return {
        "source":[row,col],
        "direction":direction,
        "destination":[nr,nc],
        "class":edge_class,
        "candidate":candidate,
        "source_handler":s16(a,0x07),
        "destination_handler":s16(b,0x07),
        "destination_handler_present":s16(b,0x07)!=0,
        "serialized_runtime_evidence":{
            "source_msp_head":s16(a,0x11),
            "destination_msp_head":s16(b,0x11),
            "source_monster_head":s16(a,0x0F),
            "destination_monster_head":s16(b,0x0F),
        },
        "monster_only_evidence":{
            "source_cell0_0x10":bool(a[0x00]&0x10),
            "source_cell0_0x80":bool(a[0x00]&0x80),
            "source_direction_high_bit":bool(a[0x02]&high_mask),
        },
    }

def components_from_static_clear(cells:list[bytes],rows:int,cols:int)->list[int]:
    adj=[set() for _ in cells]
    for r in range(rows):
        for c in range(cols):
            i=idx(r,c,cols)
            for direction in ("S","E"):
                name,dr,dc,mask,opp=BY_NAME[direction]
                nr,nc=r+dr,c+dc
                if not (0<=nr<rows and 0<=nc<cols):
                    continue
                j=idx(nr,nc,cols)
                om=BY_NAME[opp][3]
                if not(cells[i][0x02]&mask) and not(cells[j][0x02]&om):
                    adj[i].add(j); adj[j].add(i)
    seen=set(); sizes=[]
    for i in range(len(cells)):
        if i in seen: continue
        st=[i];seen.add(i);n=0
        while st:
            u=st.pop();n+=1
            for v in adj[u]:
                if v not in seen:
                    seen.add(v);st.append(v)
        sizes.append(n)
    return sorted(sizes,reverse=True)

def build(path:Path,include_edges:bool=False)->dict:
    data,marker,version,rows,cols,cells=read_level(path)
    counts={}
    directed=[]
    entering_handler_cells=0
    scripted_asym_undirected=0
    clear_undirected=blocked_undirected=mismatch_undirected=0

    # Directed classification.
    for r in range(rows):
        for c in range(cols):
            for direction,_,_,_,_ in DIRECTIONS:
                e=classify_directed_edge(cells,rows,cols,r,c,direction)
                counts[e["class"]]=counts.get(e["class"],0)+1
                if e.get("destination_handler_present"):
                    entering_handler_cells+=1
                if include_edges and e["class"]!="OUT_OF_BOUNDS":
                    directed.append(e)

    # Undirected static layer and script asymmetry on candidate pairs.
    for r in range(rows):
        for c in range(cols):
            i=idx(r,c,cols)
            for direction in ("S","E"):
                _,dr,dc,mask,opp=BY_NAME[direction]
                nr,nc=r+dr,c+dc
                if not (0<=nr<rows and 0<=nc<cols):
                    continue
                j=idx(nr,nc,cols)
                a=bool(cells[i][0x02]&mask)
                b=bool(cells[j][0x02]&BY_NAME[opp][3])
                if a!=b:
                    mismatch_undirected+=1
                elif a:
                    blocked_undirected+=1
                else:
                    clear_undirected+=1
                    if (s16(cells[i],0x07)!=0) != (s16(cells[j],0x07)!=0):
                        scripted_asym_undirected+=1

    comp=components_from_static_clear(cells,rows,cols)

    # Serialized runtime evidence is informational only.
    active_msp=sum(s16(c,0x11) not in (SENTINEL_NONE,-1) for c in cells)
    active_monster=sum(s16(c,0x0F) not in (SENTINEL_NONE,-1) for c in cells)
    nondefault_handlers=sum(s16(c,0x07)!=0 for c in cells)
    cell0_10=sum(bool(c[0]&0x10) for c in cells)
    cell0_80=sum(bool(c[0]&0x80) for c in cells)

    out={
        "path":str(path),
        "sha256":hashlib.sha256(data).hexdigest(),
        "format_marker":marker,
        "version":version,
        "rows":rows,"columns":cols,"cells":len(cells),
        "policy":{
            "static_player_barrier":"cell+0x02 low directional bit",
            "runtime_clearance_required":True,
            "source_nondefault_handler_class":"SCRIPTED",
            "monster_only_cell0_0x10_0x80_used_for_player_graph":False,
            "monster_only_high_cell2_used_for_player_graph":False,
            "one_way_verdict_authorized":False,
            "softlock_verdict_authorized":False,
        },
        "directed_edge_classes":counts,
        "undirected_static":{
            "blocked":blocked_undirected,
            "clear":clear_undirected,
            "mismatched":mismatch_undirected,
        },
        "script_evidence":{
            "nondefault_handler_cells":nondefault_handlers,
            "directed_edges_entering_nondefault_handler_cell":entering_handler_cells,
            "static_clear_undirected_edges_with_handler_asymmetry":scripted_asym_undirected,
        },
        "serialized_runtime_evidence":{
            "cells_with_active_msp_head":active_msp,
            "cells_with_active_monster_head":active_monster,
        },
        "monster_only_evidence":{
            "cells_with_cell0_0x10":cell0_10,
            "cells_with_cell0_0x80":cell0_80,
        },
        "static_clear_candidate_components":{
            "count":len(comp),
            "largest_sizes":comp[:20],
            "isolated_cells":sum(x==1 for x in comp),
            "interpretation":"candidate topology only; runtime/script gates unresolved",
        },
    }
    if include_edges:
        out["edges"]=directed
    return out

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("saves",nargs="+",type=Path)
    ap.add_argument("--json",action="store_true")
    ap.add_argument("--edges",action="store_true")
    args=ap.parse_args()
    results=[build(p,args.edges) for p in args.saves]
    ok=all(r["undirected_static"]["mismatched"]==0 for r in results)
    if args.json:
        print(json.dumps({"valid_evidence_graph":ok,"results":results},
                        indent=2,sort_keys=True))
    else:
        for r in results:
            c=r["directed_edge_classes"]; u=r["undirected_static"]
            s=r["script_evidence"]; comp=r["static_clear_candidate_components"]
            print(
                f'»'PASS' if u['mismatched']==0 else 'FAIL'} {r['path']}: "
                f"{r['rows']}x{r['columns']} "
                f"blocked={u['blocked']} clear={u['clear']} mismatch={u['mismatched']}"
            )
            print(
                "  directed "
                f"STATIC_BLOCKED={c.get('STATIC_BLOCKED',0)} "
                f"RUNTIME_GATED={c.get('STATIC_CLEAR_RUNTIME_GATED',0)} "
                f"SCRIPTED={c.get('SCRIPTED',0)}"
            )
            print(
                f"  scripts cells={s['nondefault_handler_cells']} "
                f"asymmetric_clear_pairs={s['static_clear_undirected_edges_with_handler_asymmetry']} "
                f"entering_handler_cells={s['directed_edges_entering_nondefault_handler_cell']}"
            )
            print(
                f"  candidate_components={comp['count']} "
                f"largest={comp['largest_sizes'][:8]} isolated={comp['isolated_cells']}"
            )
            print("  softlock verdict: NOT AUTHORIZED")
    return 0 if ok else 1

if __name__=="__main__":
    raise SystemExit(main())
