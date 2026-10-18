"""ElementStyle file binding and roundtrip control flow, never native proof."""
from types import SimpleNamespace
from pathlib import Path
import hashlib

import pytest

from renga_codex_bridge import resources as r


UID='{00000000-0000-4000-8000-000000000073}'


def scenario(monkeypatch,tmp_path,*,dimensions=(1200,600,750),mutate_source=False):
    path=tmp_path/'native.rnp';path.write_bytes(b'original native fixture')
    source=tmp_path/'own.step';source.write_bytes(b'ISO-10303-21;\nEND-ISO-10303-21;')
    spec={'kind':'ElementStyle','name':'Independent STEP test','ref':'own',
          'file_path':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
          'expected_dimensions_mm':[1200,600,750],
          'expected_geometry':{'volume_mm3':100,'surface_area_mm2':200,'minimum_triangles':24}}
    observed={'writes':[],'sessions':[],'probes':[],'saves':0,'args':None}
    values={'EntityName':'default','ElementWidth':dimensions[0],'ElementDepth':dimensions[1],'ElementHeight':dimensions[2]}
    entity=SimpleNamespace(Id=73,UniqueIdS=UID,TypeIdS='ELEMENTSTYLE',Name='default')
    parameter=lambda name:SimpleNamespace(HasValue=True,ValueType=4,GetStringValue=lambda:values[name])
    entity.QueryInterface=lambda interface:SimpleNamespace(GetS=parameter)

    class Collection:
        items=[]
        @property
        def Count(self):return len(self.items)
        def GetByIndex(self,index):return self.items[index]
        def GetByUniqueIdS(self,uid):return entity if uid==UID.lower().strip('{}') else None
        def CreateNewEntityArgs(self):return SimpleNamespace()
        def Create(self,args):
            assert args.TypeIdS=='ELEMENTSTYLE' and args.FilePath==str(source)
            observed['args']=args;self.items.append(entity)
            if mutate_source:source.write_bytes(b'changed after native resource factory')
            return entity
    collection=Collection()
    native_operation=lambda:SimpleNamespace(Start=lambda:None,Apply=lambda:None,Rollback=lambda:None)

    class Session:
        def __init__(self,target,**kwargs):
            self.path=Path(target);observed['sessions'].append(kwargs)
            self.sdk=SimpleNamespace(types={'ElementStyle':'ELEMENTSTYLE'},parameters={})
            self.r=SimpleNamespace(IParameterContainer='parameter-container')
            self.project=SimpleNamespace(ElementStyles=collection,CreateOperation=native_operation)
            self.model=SimpleNamespace(GetObjects=lambda:SimpleNamespace(Count=0))
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def save(self):
            observed['saves']+=1;path.write_bytes(b'saved imported style without probe elements')

    def set_parameter(session,obj,name,value):
        assert obj is entity
        observed['writes'].append((name,value));values[name]=value
        if name=='EntityName':entity.Name=value
    def probe(session,style_id,request):
        assert style_id==73
        observed['probes'].append({'phase':len(observed['sessions']),'source_sha256':request['source_sha256']})
        return {'dimensions_mm':list(dimensions),'volume_mm3':100,'surface_area_mm2':200,'triangle_count':24,
                'source_sha256':request['source_sha256'],'full_brep_equivalence_verified':False}
    monkeypatch.setattr(r,'Session',Session)
    monkeypatch.setattr(r,'checked_path',lambda target,**kwargs:Path(target))
    monkeypatch.setattr(r,'save_plan',lambda request:'synthetic-plan.json')
    monkeypatch.setattr(r,'event',lambda *args,**kwargs:None)
    monkeypatch.setattr(r,'set_parameter',set_parameter)
    monkeypatch.setattr(r,'parameters',lambda session,obj:{key:{'value':value} for key,value in values.items()})
    monkeypatch.setattr(r,'probe_element_style',probe)
    return path,source,spec,observed


def test_file_is_bound_before_factory_and_saved_style_is_probed_after_reopen(monkeypatch,tmp_path):
    path,source,spec,observed=scenario(monkeypatch,tmp_path)
    original=source.read_bytes()
    result=r.author_resources(path,[spec])
    assert result['status']=='saved_reopened_verified'
    assert result['created'][0]['kind']=='ElementStyle' and result['created'][0]['ref']=='own'
    assert observed['writes']==[('EntityName',spec['name'])]  # Never scale a fallback to match expected bounds.
    assert observed['sessions']==[{'write':True},{'write':True}]
    assert [probe['phase'] for probe in observed['probes']]==[1,2]
    assert observed['saves']==1 and source.read_bytes()==original


def test_wrong_actual_resource_dimensions_fail_before_save_and_mesh_success(monkeypatch,tmp_path):
    path,source,spec,observed=scenario(monkeypatch,tmp_path,dimensions=(1000,1000,1000))
    with pytest.raises(RuntimeError,match='possible default-model fallback'):r.author_resources(path,[spec])
    assert observed['saves']==0 and observed['probes']==[]
    assert path.read_bytes()==b'original native fixture'


def test_source_changed_by_native_read_is_rejected_before_save(monkeypatch,tmp_path):
    path,source,spec,observed=scenario(monkeypatch,tmp_path,mutate_source=True)
    with pytest.raises(ValueError,match='SHA256'):r.author_resources(path,[spec])
    assert observed['saves']==0
    assert path.read_bytes()==b'original native fixture'
