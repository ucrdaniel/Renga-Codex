"""Fresh read-only host verification routes; native integration remains separate."""
from types import SimpleNamespace
import asyncio

import pytest

from renga_codex_bridge import geometry as g


FILLING='00000000-0000-4000-8000-000000000041'
HOST='00000000-0000-4000-8000-000000000042'
OTHER='00000000-0000-4000-8000-000000000043'


def context(monkeypatch,*,kind='WINDOW',host_type='WALL',affected=(42,)):
    filling=SimpleNamespace(Id=41,UniqueIdS='{'+FILLING+'}',ObjectTypeS=kind,
        QueryInterface=lambda interface:SimpleNamespace(GetAffectedObjectIds=lambda:list(affected)),
        GetParameters=lambda:None)
    wall=SimpleNamespace(Id=42,UniqueIdS='{'+HOST+'}',ObjectTypeS=host_type)
    objects=[filling,wall];id_reads=[]
    def by_id(identifier):
        id_reads.append(identifier)
        return next((obj for obj in objects if obj.Id==identifier),None)
    collection=SimpleNamespace(Count=2,GetByIndex=lambda index:objects[index],GetById=by_id)
    s=SimpleNamespace(model=SimpleNamespace(GetObjects=lambda:collection),
        sdk=SimpleNamespace(types={'Wall':'WALL','Window':'WINDOW','Door':'DOOR'},parameters={}),
        r=SimpleNamespace(IWindowParams='window-params',IDoorParams='door-params'))
    monkeypatch.setattr(g,'inventory',lambda session:[])
    monkeypatch.setattr(g,'extract',lambda session:{'objects':[]})
    return s,filling,wall,objects,collection,id_reads


@pytest.mark.parametrize('kind',['WINDOW','DOOR'])
def test_readonly_fresh_host_check_reports_actual_uuid_and_parent_evidence(monkeypatch,kind):
    s,*_=context(monkeypatch,kind=kind)
    result=g.verify(s,expected_filling_hosts={'{'+FILLING.upper()+'}':'{'+HOST.upper()+'}'})
    assert result['status']=='passed'
    assert result['checks']==[{'check':'requested_filling_host','uuid':FILLING,
        'expected_host_uuid':HOST,'actual_host_uuid':HOST,'passed':True,
        'affected_wall_verified':True,'parent_uuid':None,'parent_uuid_verified':False}]
    assert result['computer_use_calls']==0


@pytest.mark.parametrize('mapping',[[],True,{1:HOST},{FILLING:42},{FILLING:'not a UUID'},
                                    {FILLING:HOST,'{'+FILLING+'}':OTHER}])
def test_invalid_or_ambiguous_uuid_maps_fail_before_model_inspection(monkeypatch,mapping):
    def forbidden(*args):raise AssertionError('No native reads for invalid expectations')
    monkeypatch.setattr(g,'inventory',forbidden)
    with pytest.raises(ValueError):g.verify(SimpleNamespace(),expected_filling_hosts=mapping)


def test_missing_filling_and_missing_host_fail_instead_of_becoming_passed_rows(monkeypatch):
    s,_,_,objects,collection,_=context(monkeypatch)
    objects.pop(0);collection.Count=1
    with pytest.raises(KeyError):g.verify(s,expected_filling_hosts={FILLING:HOST})
    s,_,_,objects,collection,_=context(monkeypatch)
    objects.pop();collection.Count=1
    with pytest.raises(KeyError):g.verify(s,expected_filling_hosts={FILLING:HOST})


@pytest.mark.parametrize('options,error,match',[
    ({'kind':'ROOM'},ValueError,'requires Door/Window'),
    ({'host_type':'FLOOR'},RuntimeError,'not a native Wall'),
    ({'affected':(99,)},RuntimeError,'no longer affects'),
])
def test_existing_native_helper_failures_are_propagated(monkeypatch,options,error,match):
    s,*_=context(monkeypatch,**options)
    with pytest.raises(error,match=match):g.verify(s,expected_filling_hosts={FILLING:HOST})


def test_stale_reused_numeric_id_is_resolved_by_uuid_before_native_host_check(monkeypatch):
    s,filling,wall,objects,collection,id_reads=context(monkeypatch)
    stale=SimpleNamespace(Id=41,UniqueIdS='{'+OTHER+'}',ObjectTypeS='ROOM')
    filling.Id=44;objects[:]=[stale,wall,filling];collection.Count=3
    s._object_id_cache={FILLING:41,HOST:42}
    result=g.verify(s,expected_filling_hosts={FILLING:HOST})
    assert result['checks'][0]['passed']
    assert id_reads[:2]==[41,44]
    assert s._object_id_cache[FILLING]==44


def test_resolver_returning_wrong_persistent_identity_is_rejected_before_helper(monkeypatch):
    s,*_=context(monkeypatch)
    monkeypatch.setattr(g,'object_by_id',lambda session,identifier:SimpleNamespace(UniqueIdS='{'+OTHER+'}'))
    monkeypatch.setattr(g,'verify_filling_host',lambda *args:pytest.fail('Wrong object must never reach helper'))
    with pytest.raises(RuntimeError,match='native UUID differs'):g.verify(s,expected_filling_hosts={FILLING:HOST})


@pytest.mark.parametrize('wrong',[
    {'host_uuid':OTHER,'affected_wall_verified':True,'parent_uuid':None,'parent_uuid_verified':False},
    {'host_uuid':HOST,'affected_wall_verified':False,'parent_uuid':None,'parent_uuid_verified':False},
])
def test_disagreeing_helper_result_cannot_be_reported_as_passed(monkeypatch,wrong):
    s,*_=context(monkeypatch)
    monkeypatch.setattr(g,'verify_filling_host',lambda *args:wrong)
    with pytest.raises(RuntimeError,match='disagrees'):g.verify(s,expected_filling_hosts={FILLING:HOST})


def test_optional_absent_map_preserves_not_verified_for_an_empty_model(monkeypatch):
    s,*_=context(monkeypatch)
    assert g.verify(s)['status']=='not_verified'
    assert g.verify(s,expected_filling_hosts={})['checks']==[]


def test_mcp_forwards_uuid_host_expectations_to_readonly_worker(monkeypatch):
    from renga_codex_bridge import mcp_server
    seen={}
    async def run(command,**arguments):seen.update(command=command,arguments=arguments);return {'status':'passed'}
    monkeypatch.setattr(mcp_server,'run',run)
    expected={FILLING:HOST}
    assert asyncio.run(mcp_server.bridge_verify('test.rnp',expected_filling_hosts=expected))=={'status':'passed'}
    assert seen=={'command':'verify','arguments':{'project':'test.rnp','expected_areas':None,
        'collision_types':None,'expected_filling_hosts':expected}}


def test_worker_forwards_expected_host_map_without_creating_a_write_session(monkeypatch):
    from renga_codex_bridge import worker
    observed={};session=object()
    class ReadSession:
        def __init__(self,path,**kwargs):
            assert path=='test.rnp' and kwargs=={}
        def __enter__(self):return session
        def __exit__(self,*args):return False
    def verify(actual,areas,types,hosts):
        assert actual is session
        observed.update(areas=areas,types=types,hosts=hosts)
        return {'status':'passed'}
    monkeypatch.setattr(worker,'Session',ReadSession)
    monkeypatch.setattr(worker,'verify',verify)
    expected={FILLING:HOST}
    assert worker.execute('verify',{'project':'test.rnp','expected_filling_hosts':expected})=={'status':'passed'}
    assert observed=={'areas':None,'types':None,'hosts':expected}
