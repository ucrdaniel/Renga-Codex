"""Requested-field readback evidence preserves the original mismatch failures."""
from types import SimpleNamespace

import pytest

from renga_codex_bridge.operations import read_roof_slope_check


def probe(shape=0,angle=1,overhang=0):
    calls=[]
    def getter(name,value):
        def get(index):calls.append((name,index));return value
        return get
    slopes=SimpleNamespace(GetRoofEdgeShape=getter('shape',shape),GetSlopeAngle=getter('angle',angle),GetOverhang=getter('overhang',overhang))
    s=SimpleNamespace(r=SimpleNamespace(IRoofSlopes='roof-interface'))
    obj=SimpleNamespace(UniqueIdS='{00000000-0000-4000-8000-000000000001}',QueryInterface=lambda interface:slopes)
    return s,obj,calls


def test_only_requested_native_fields_are_read_and_included():
    s,obj,calls=probe()
    result=read_roof_slope_check(s,obj,[{'index':2,'shape':0,'angle':1,'overhang':0}])
    assert result['edges']==[{'index':2,'shape':0,'angle':1,'overhang':0}]
    assert calls==[('shape',2),('angle',2),('overhang',2)]
    assert result['persistence_verified_by_this_reader']


def test_gable_has_no_invented_slope_angle():
    s,obj,calls=probe(shape=1)
    assert read_roof_slope_check(s,obj,[{'index':0,'shape':1}])['edges']==[{'index':0,'shape':1}]
    assert calls==[('shape',0)]


@pytest.mark.parametrize('values,edge,message', [
    ({'shape':1},{'index':0,'shape':0},'shape'),
    ({'angle':2},{'index':0,'shape':0,'angle':1},'angle'),
    ({'overhang':10},{'index':0,'shape':0,'overhang':0},'overhang')])
def test_wrong_native_values_remain_failures(values,edge,message):
    s,obj,_=probe(**values)
    with pytest.raises(RuntimeError,match=message):read_roof_slope_check(s,obj,[edge])
