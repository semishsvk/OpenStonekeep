import importlib.util
from pathlib import Path
import pytest

TOOL=Path(__file__).resolve().parents[1]/'tools'/'verify_starter_level_default_callbacks.py'
spec=importlib.util.spec_from_file_location('tool',TOOL)
tool=importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class FakeLE:
    page_size=0x1000
    objects=[
        {'size':0x90000,'base':0x10000,'mapidx':1,'mapsize':0x90},
        {'size':0x1000,'base':0xE0000,'mapidx':0,'mapsize':0},
        {'size':0x20000,'base':0xF0000,'mapidx':0x91,'mapsize':0x20},
    ]
    def page_for_object_offset(self,objnum,off):
        return (7, off & 0xfff)
    def parse_fixup_page(self,page):
        return [{
            'type':0x07,'flags':0x10,'sources':[0x123],
            'target_kind':0,'target_object':1,'target_offset':0x4567,
        }]


def test_runtime_object_mapping():
    le=FakeLE()
    n,obj,off=tool.object_for_runtime(le,0x14567)
    assert n==1
    assert off==0x4567


def test_internal_off32_resolution():
    le=FakeLE()
    out=tool.resolve_internal(le,3,0x123,'synthetic')
    assert out['target_object']==1
    assert out['target_object_offset']==0x4567
    assert out['target_runtime']==0x14567


def test_missing_fixup_fails():
    le=FakeLE()
    le.parse_fixup_page=lambda page: []
    with pytest.raises(ValueError,match='expected one fixup'):
        tool.resolve_internal(le,3,0x123,'synthetic')


def test_starter_expectations_are_level_1_and_15():
    assert set(tool.EXPECTED_LEVELS)=={1,15}
    assert tool.EXPECTED_LEVELS[1]['callback_runtime']==0x5E867
    assert tool.EXPECTED_LEVELS[15]['callback_runtime']==0x4F861
