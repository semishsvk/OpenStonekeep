import importlib.util
from pathlib import Path

TOOL=Path(__file__).resolve().parents[1]/'tools'/'inspect_portal_enable_state.py'
spec=importlib.util.spec_from_file_location('tool',TOOL)
tool=importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)

def test_clear_and_set_masks_are_exact_low_complements():
    assert tool.LOW==(0x08,0x02,0x04,0x01)
    assert tool.CLEAR_MASK==(0xF7,0xFD,0xFB,0xFE)
    assert tool.SET_MASK==tool.LOW

def test_high_marker_masks_are_reciprocal():
    assert tool.HIGH==(0x80,0x20,0x40,0x10)
    assert tool.HIGH_OPPOSITE==(0x40,0x10,0x80,0x20)

def test_portal_marker_requires_low_and_high_on_both_sides():
    cells=[bytearray(tool.CELL_SIZE) for _ in range(2)]
    # 1x2, direction E: source LOW+HIGH E; neighbor reciprocal LOW+HIGH W.
    cells[0][2]=0x01|0x10
    cells[1][2]=0x02|0x20
    out=tool.portal_marker_record(1,99,0,0,3,cells,1,2)
    assert out['special_marker_reciprocal']
    cells[1][2]&=~0x20
    out=tool.portal_marker_record(1,99,0,0,3,cells,1,2)
    assert not out['special_marker_reciprocal']

def test_state_machine_contains_open_commit_and_cancel_phases():
    assert tool.STATE_MACHINE['OPENING']['handler_action']==15
    assert tool.STATE_MACHINE['OPEN_ARMED']['after_open_animation_state']==2
    assert tool.STATE_MACHINE['FORWARD_COMMIT']['pre_action']==3
    assert tool.STATE_MACHINE['FORWARD_COMMIT']['post_action']==2
    assert tool.STATE_MACHINE['CANCEL_RECLOSE']['handler_pre_action']==17
    assert tool.STATE_MACHINE['CANCEL_RECLOSE']['handler_post_action']==18
    assert tool.STATE_MACHINE['CANCEL_RECLOSE']['final_state']==0
