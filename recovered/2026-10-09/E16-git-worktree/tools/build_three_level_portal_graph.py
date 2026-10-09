#!/usr/bin/env python3
"""Compose STONE-K292-E.15 three-level portal evidence graph."""
from __future__ import annotations
import argparse, json
from pathlib import Path

from build_conditional_portal_graph import build as build_e11
from inspect_selection_reachability import inspect as inspect_e12
from inspect_level02_initial_state import inspect as inspect_e13
from inspect_level02_runtime_tail import inspect as inspect_e14
from inspect_h89_reciprocal_return import inspect as inspect_h89

DIR_INDEX={"N":0,"W":1,"S":2,"E":3}
DIR_DELTA=((-1,0),(0,-1),(1,0),(0,1))
OPPOSITE={0:2,1:3,2:0,3:1}


def normalized_edges(e11:dict,e13:dict,e14:dict,e12:dict,h89:dict)->list[dict]:
    physical2={x["handler_id"]:x for x in e14["level02_portals"]}
    edges=[]
    for x in e11["transitions"]:
        h=x["handler_id"]
        if h==87:
            reach="WORLD_INTERACTION_STATE_QUALIFIED"
            producer="ID0_RECORD79_WORLD_INTERACTION"
        elif h in (106,107):
            reach=(
                "INPUT_REACHABLE_CONDITIONAL"
                if e12["id166"]["ui_slot_reachable"]
                else "SELECTION_UNRESOLVED"
            )
            producer="ID166_RECORD162_UI_SLOT5"
        elif x["producer_required"]:
            reach="PRODUCER_CONDITIONAL"
            producer=x["producer_state"]
        else:
            reach="DIRECT_ENABLE_INITIAL_STATE"
            producer="NOT_REQUIRED"
        edges.append({
            "source_level":x["source_level"],
            "handler_id":h,
            "source":list(x["source"]),
            "direction":x["direction"],
            "target_level":x["target_level"],
            "target_spawn":list(x["staged_target"]),
            "enable_class":x["enable_class"],
            "outgoing_reachability":reach,
            "producer_evidence":producer,
            "physical_clear_after_open":bool(
                x["physical_after_low_clear"]["physical_clear_after_low_clear"]
            ),
            "transition_commit":bool(
                x["transition_commit_reached_after_required_enable"]
            ),
            "source_checkpoint":"E.11/E.12",
        })
    # h415 is a conditional transition wrapper rather than one of the E.8
    # simple transition wrappers. E.15 independently closes its h89 reciprocal
    # sequence: h85 special-open -> cross -> turn S->N -> h415 action3.
    if h89.get("pass") and h89.get("immediate_same_interface_reciprocal_verified"):
        p = h89["h415_transition_payload"]
        edges.append({
            "source_level": p["source_level"],
            "handler_id": 415,
            "source": list(p["source_cell"]),
            "direction": p["source_direction"],
            "target_level": p["target_level"],
            "target_spawn": list(p["target_spawn"]),
            "enable_class": "H85_SPECIAL_OPEN_PLUS_TURN",
            "outgoing_reachability": "IMMEDIATE_RECIPROCAL_VERIFIED",
            "producer_evidence": "E15_H89_H415_SEQUENCE",
            "physical_clear_after_open": True,
            "transition_commit": True,
            "source_checkpoint": "E.15",
        })

    for x in e13["return_transitions"]:
        p=physical2.get(x["handler_id"])
        edges.append({
            "source_level":2,
            "handler_id":x["handler_id"],
            "source":list(x["source"]),
            "direction":x["direction"],
            "target_level":x["target_level"],
            "target_spawn":list(x["target_spawn"]),
            "enable_class":"DIRECT_COMMON_FAMILY_ALLOW",
            "outgoing_reachability":"DIRECT_ENABLE_INITIAL_STATE",
            "producer_evidence":"NOT_REQUIRED",
            "physical_clear_after_open":bool(
                p and p["physical_clear_after_low_clear"]
            ),
            "transition_commit":True,
            "source_checkpoint":"E.13/E.14",
        })
    return edges


def immediate_reciprocal(a:dict,b:dict)->bool:
    if a["target_level"]!=b["source_level"] or b["target_level"]!=a["source_level"]:
        return False
    ai=DIR_INDEX[a["direction"]]
    target_row,target_col,target_facing=a["target_spawn"]
    dr,dc=DIR_DELTA[target_facing]
    expected_b_source=[target_row+dr,target_col+dc]
    if b["source"]!=expected_b_source:
        return False
    if DIR_INDEX[b["direction"]]!=OPPOSITE[target_facing]:
        return False
    srow,scol=a["source"]; dr,dc=DIR_DELTA[ai]
    expected_return=[srow+dr,scol+dc,OPPOSITE[ai]]
    return b["target_spawn"]==expected_return


def compose(e11:dict,e12:dict,e13:dict,e14:dict,h89:dict)->dict:
    errors=[]
    for name,obj in (("E.11",e11),("E.12",e12),("E.13",e13),("E.14",e14),("E.15-h89",h89)):
        if not obj.get("pass"):
            errors.append(f"{name} validation failed")
    edges=normalized_edges(e11,e13,e14,e12,h89)
    by_handler={x["handler_id"]:x for x in edges}
    if len(by_handler)!=len(edges):
        errors.append("duplicate handler IDs in transition graph")

    l1=[x for x in edges if x["source_level"]==1]
    results=[]
    for a in sorted(l1,key=lambda x:x["handler_id"]):
        matches=[
            b for b in edges
            if b["handler_id"]!=a["handler_id"] and immediate_reciprocal(a,b)
        ]
        if len(matches)>1:
            errors.append(f"h{a['handler_id']}: multiple immediate reciprocal edges")
        b=matches[0] if len(matches)==1 else None
        if b is not None:
            return_verified=bool(
                b["outgoing_reachability"] in (
                    "DIRECT_ENABLE_INITIAL_STATE",
                    "IMMEDIATE_RECIPROCAL_VERIFIED",
                )
                and b["physical_clear_after_open"]
                and b["transition_commit"]
            )
            if not return_verified:
                errors.append(
                    f"h{a['handler_id']}: reciprocal h{b['handler_id']} is not direct/clear"
                )
            status="IMMEDIATE_SAME_INTERFACE_RETURN_VERIFIED" if return_verified else "RETURN_CONDITIONAL"
        else:
            return_verified=False
            status="NO_IMMEDIATE_RECIPROCAL_HANDLER_OBSERVED"
        results.append({
            "outgoing_handler":a["handler_id"],
            "source_level":1,
            "target_level":a["target_level"],
            "outgoing_reachability":a["outgoing_reachability"],
            "outgoing_physical_clear":a["physical_clear_after_open"],
            "outgoing_commit":a["transition_commit"],
            "reciprocal_handler":None if b is None else b["handler_id"],
            "reciprocal_source_level":None if b is None else b["source_level"],
            "immediate_return_verified":return_verified,
            "classification":status,
        })

    expected_pairs={(87,411),(88,412),(89,415),(90,413),(106,144),(107,145)}
    actual_pairs={
        (x["outgoing_handler"],x["reciprocal_handler"])
        for x in results if x["reciprocal_handler"] is not None
    }
    if actual_pairs!=expected_pairs:
        errors.append(f"unexpected reciprocal pair set: {sorted(actual_pairs)}")
    unmatched=[x["outgoing_handler"] for x in results if not x["immediate_return_verified"]]
    if unmatched:
        errors.append(f"unexpected unresolved L1 outgoing handlers: {unmatched}")

    return {
        "edge_count":len(edges),
        "edges":edges,
        "level_edge_counts":{
            "1->15":sum(x["source_level"]==1 and x["target_level"]==15 for x in edges),
            "15->1":sum(x["source_level"]==15 and x["target_level"]==1 for x in edges),
            "1->2":sum(x["source_level"]==1 and x["target_level"]==2 for x in edges),
            "2->1":sum(x["source_level"]==2 and x["target_level"]==1 for x in edges),
        },
        "level1_outgoing_portals":results,
        "immediate_same_interface_return_count":sum(
            x["immediate_return_verified"] for x in results
        ),
        "immediate_same_interface_unresolved":[
            x["outgoing_handler"] for x in results
            if not x["immediate_return_verified"]
        ],
        "verified_pairs":[list(x) for x in sorted(expected_pairs)],
        "h89_reciprocal_evidence": h89,
        "verdict_scope":{
            "six_pairs":"one-way-at-immediate-interface concern FALSIFIED when the outgoing transition executes",
            "handler89":"IMMEDIATE_SAME_INTERFACE_RETURN_VERIFIED via h85 open + turn + h415",
            "global_one_way":"NOT_AUTHORIZED",
            "global_softlock":"NOT_AUTHORIZED",
        },
        "errors":errors,
        "pass":not errors,
    }


def build(exe:Path,level01:Path,level01a:Path,gameinfo:Path,master:Path,group01:Path,group02:Path)->dict:
    e11=build_e11(exe,level01,level01a)
    e12=inspect_e12(exe,level01,gameinfo)
    e13=inspect_e13(exe,master,group02)
    e14=inspect_e14(exe,group01,group02,level01)
    h89=inspect_h89(exe,level01a)
    return compose(e11,e12,e13,e14,h89)


def main():
    ap=argparse.ArgumentParser()
    for arg in ("exe","level01","level01a","gameinfo","master","group01","group02"):
        ap.add_argument("--"+arg.replace("_","-"),dest=arg,type=Path,required=True)
    ap.add_argument("--json",action="store_true")
    a=ap.parse_args()
    out=build(a.exe,a.level01,a.level01a,a.gameinfo,a.master,a.group01,a.group02)
    if a.json: print(json.dumps(out,indent=2,sort_keys=True))
    else:
        print(("PASS" if out["pass"] else "FAIL"),
              f"edges={out['edge_count']}",
              f"immediate_return={out['immediate_same_interface_return_count']}/6",
              f"unresolved={out['immediate_same_interface_unresolved']}",
              f"errors={len(out['errors'])}")
        for x in out["level1_outgoing_portals"]:
            print(f" h{x['outgoing_handler']} -> L{x['target_level']} return={x['reciprocal_handler']} {x['classification']}")
    return 0 if out["pass"] else 2
if __name__=="__main__": raise SystemExit(main())
