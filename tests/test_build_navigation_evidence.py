import importlib.util
import struct
from pathlib import Path

MODULE=Path(__file__).resolve().parents[1]/"tools"/"build_navigation_evidence.py"
spec=importlib.util.spec_from_file_location("build_navigation_evidence",MODULE)
mod=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

def save_2x2(path:Path,*,handler0=0,block_top=False,monster_only=False):
    # all outer boundaries set, internal edges clear
    masks=[0x0A,0x09,0x06,0x05]
    if block_top:
        masks[0]|=0x01  # TL E
        masks[1]|=0x02  # TR W
    data=bytearray(struct.pack("<H",2)+b"1.05\0"+struct.pack("<HH",2,2))
    for i,mask in enumerate(masks):
        c=bytearray([0]*0x15)
        c[2]=mask
        if i==0:
            struct.pack_into("<h",c,0x07,handler0)
            if monster_only:
                c[0]|=0x90
                c[2]|=0x10  # E high bit, player low E remains controlled above
        for off in (0x0D,0x0F,0x11,0x13):
            struct.pack_into("<h",c,off,-100)
        data+=c
    path.write_bytes(data)

def test_all_clear_internal_edges_are_runtime_gated(tmp_path:Path):
    p=tmp_path/"x.SAV"; save_2x2(p)
    out=mod.build(p)
    assert out["undirected_static"]=={"blocked":0,"clear":4,"mismatched":0}
    assert out["directed_edge_classes"]["STATIC_CLEAR_RUNTIME_GATED"]==8
    assert out["policy"]["softlock_verdict_authorized"] is False

def test_source_handler_makes_directed_edges_scripted(tmp_path:Path):
    p=tmp_path/"x.SAV"; save_2x2(p,handler0=7)
    out=mod.build(p)
    assert out["directed_edge_classes"]["SCRIPTED"]==2
    assert out["directed_edge_classes"]["STATIC_CLEAR_RUNTIME_GATED"]==6
    assert out["script_evidence"]["static_clear_undirected_edges_with_handler_asymmetry"]==2
    assert out["script_evidence"]["directed_edges_entering_nondefault_handler_cell"]==2

def test_static_blocked_pair_is_not_candidate(tmp_path:Path):
    p=tmp_path/"x.SAV"; save_2x2(p,block_top=True)
    out=mod.build(p)
    assert out["undirected_static"]["blocked"]==1
    assert out["undirected_static"]["clear"]==3
    assert out["directed_edge_classes"]["STATIC_BLOCKED"]==2

def test_monster_only_layers_do_not_remove_player_candidate(tmp_path:Path):
    p=tmp_path/"x.SAV"; save_2x2(p,monster_only=True)
    out=mod.build(p)
    # TL E remains low-static clear even though cell0 0x90 and high E are set.
    e=mod.classify_directed_edge(
        mod.read_level(p)[5],2,2,0,0,"E"
    )
    assert e["class"]=="STATIC_CLEAR_RUNTIME_GATED"
    assert e["monster_only_evidence"]["source_cell0_0x10"] is True
    assert e["monster_only_evidence"]["source_cell0_0x80"] is True
    assert e["monster_only_evidence"]["source_direction_high_bit"] is True
