"""Explicit native resource references are checked before any mutation."""
from types import SimpleNamespace as NS

import pytest

from renga_codex_bridge import presentation as p
from renga_codex_bridge import resources as r


def collection(*identifiers):
    return NS(Contains=lambda value:value in identifiers,GetById=lambda value:NS(Id=value))


@pytest.mark.parametrize('value',[True,0,-1,2**31,2**40,42.0,'42'])
def test_explicit_material_reference_requires_positive_native_int32(value):
    with pytest.raises(ValueError,match='MaterialId'):
        r.validate_resource_specs([{'kind':'DoorStyle','name':'style','parameters':{'MaterialId':value}}])


def test_filling_material_ids_must_exist_in_the_ordinary_material_collection():
    s=NS(project=NS(Materials=collection(42)))
    specs=r.validate_resource_specs([{'kind':'WindowStyle','name':'window','parameters':{'MaterialId':42}}])
    assert r._preflight_material_references(s,specs) is None
    specs[0]['parameters']['MaterialId']=99
    with pytest.raises(ValueError,match='absent'):r._preflight_material_references(s,specs)


def test_omitted_material_preserves_native_default_without_an_invented_zero_reference():
    assert r._preflight_material_references(NS(),[{'kind':'DoorStyle','name':'native default','parameters':{}}]) is None


@pytest.mark.parametrize('key',sorted(p.INT_VIEW_PARAMETERS))
@pytest.mark.parametrize('value',[True,2**31,-2**31-1,2**40,1.0,'1'])
def test_view_integer_fields_reject_coercion_or_native_truncation(key,value):
    view={'kind':'model','source_entity_id':7,'scale_id':4,'view_parameters':{key:value}}
    if key=='ObjectViewDirection':view.update(kind='entity',object_mark='TEST')
    request={'name':'sheet','page_format_id':3,'views':[view]}
    with pytest.raises(ValueError,match='int32'):p.validate_drawings([request])


@pytest.mark.parametrize('key',['FilterId','DisplayStyleId','ViewDepthLevelId'])
def test_reference_values_require_inspected_positive_ids_not_default_sentinels(key):
    request={'name':'sheet','page_format_id':3,'views':[{'kind':'model','source_entity_id':7,
        'scale_id':4,'view_parameters':{key:0}}]}
    with pytest.raises(ValueError,match='positive native ID'):p.validate_drawings([request])


def test_view_references_resolve_in_their_own_collections_and_require_a_level():
    level=NS(Id=45,ObjectTypeS='LEVEL')
    objects=NS(GetById=lambda identifier:level if identifier==45 else None)
    s=NS(project=NS(Filters=collection(43),DisplayStyles=collection(44)),
         model=NS(GetObjects=lambda:objects),sdk=NS(types={'Level':'LEVEL'}))
    assert p._preflight_view_references(s,{'FilterId':43,'DisplayStyleId':44,'ViewDepthLevelId':45}) is None
    with pytest.raises(ValueError,match='FilterId.*absent'):p._preflight_view_references(s,{'FilterId':44})
    with pytest.raises(ValueError,match='DisplayStyleId.*absent'):p._preflight_view_references(s,{'DisplayStyleId':43})
    level.ObjectTypeS='WALL'
    with pytest.raises(ValueError,match='existing native Level'):p._preflight_view_references(s,{'ViewDepthLevelId':45})


def test_missing_view_resource_fails_before_creating_any_topic_or_drawing(monkeypatch):
    source=NS(Id=7,UniqueIdS='{00000000-0000-4000-8000-000000000007}',ObjectTypeS='LEVEL')
    objects=NS(Count=1,GetByIndex=lambda index:source,GetById=lambda identifier:source)
    session=NS(model=NS(GetObjects=lambda:objects),
        sdk=NS(types={'Level':'LEVEL','Section':'SECTION','Elevation':'ELEVATION'}),
        project=NS(Drawings2=NS(Count=0),PageFormatStyles=collection(3),Scales=collection(4),Filters=collection()))
    class Session:
        def __init__(self,*args,**kwargs):pass
        def __enter__(self):return session
        def __exit__(self,*args):return False
    monkeypatch.setattr(p,'Session',Session)
    monkeypatch.setattr(p,'save_plan',lambda request:'synthetic-plan.json')
    monkeypatch.setattr(p,'ensure_topic',lambda *args:pytest.fail('No topic creation before all references pass'))
    request={'name':'sheet','page_format_id':3,'topic':'AR','views':[{'kind':'model','source_entity_id':7,
        'scale_id':4,'view_parameters':{'FilterId':99}}]}
    with pytest.raises(ValueError,match='FilterId.*absent'):p.create_presentations('test.rnp',[request])
