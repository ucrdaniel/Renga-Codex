"""Identity lookup optimization still validates the live object on every hit."""
from types import SimpleNamespace
from uuid import UUID

import pytest

from renga_codex_bridge import model


ONE=str(UUID(int=1));TWO=str(UUID(int=2));THREE=str(UUID(int=3))


def entity(identifier,unique_id):
    return SimpleNamespace(Id=identifier,UniqueIdS='{'+unique_id.upper()+'}')


class Collection:
    def __init__(self,objects):
        self.objects=list(objects);self.index_reads=0;self.id_reads=[]
    @property
    def Count(self):return len(self.objects)
    def GetByIndex(self,index):
        self.index_reads+=1
        return self.objects[index]
    def GetById(self,identifier):
        self.id_reads.append(identifier)
        return next((obj for obj in self.objects if obj.Id==identifier),None)


def session(objects):
    collection=Collection(objects)
    return SimpleNamespace(model=SimpleNamespace(GetObjects=lambda:collection)),collection


def test_first_uuid_lookup_indexes_once_then_every_hit_reads_native_identity():
    one=entity(10,ONE);two=entity(20,TWO)
    s,collection=session([one,two])
    assert model.object_by_id(s,'{'+ONE.upper()+'}') is one
    assert model.object_by_id(s,ONE) is one
    assert model.object_by_id(s,TWO) is two
    assert collection.index_reads==2
    assert collection.id_reads==[10,10,20]
    assert s._object_id_cache=={ONE:10,TWO:20}
    assert all(isinstance(key,str) and type(value) is int for key,value in s._object_id_cache.items())


def test_numeric_id_lookup_keeps_direct_lookup_and_missing_key_contract():
    obj=entity(10,ONE);s,collection=session([obj])
    assert model.object_by_id(s,10) is obj
    with pytest.raises(KeyError) as missing:model.object_by_id(s,999)
    assert missing.value.args==(999,)
    assert collection.index_reads==0


def test_reused_cached_id_rebuilds_and_finds_requested_uuid_at_new_id():
    one=entity(10,ONE);s,collection=session([one,entity(20,TWO)])
    assert model.object_by_id(s,ONE) is one
    moved=entity(30,ONE)
    collection.objects=[entity(10,THREE),entity(20,TWO),moved]
    assert model.object_by_id(s,ONE) is moved
    assert collection.index_reads==5
    assert collection.id_reads==[10,10,30]
    assert s._object_id_cache[ONE]==30


@pytest.mark.parametrize('replacement',[None,THREE])
def test_deleted_uuid_never_resolves_to_an_absent_or_reused_numeric_id(replacement):
    s,collection=session([entity(10,ONE),entity(20,TWO)])
    model.object_by_id(s,ONE)
    collection.objects=[entity(20,TWO)]
    if replacement is not None:collection.objects.append(entity(10,replacement))
    with pytest.raises(KeyError) as missing:model.object_by_id(s,ONE)
    assert missing.value.args==(ONE,)
    assert ONE not in s._object_id_cache


def test_missing_uuid_is_not_negatively_cached_and_later_insertion_is_found():
    s,collection=session([entity(10,ONE)])
    with pytest.raises(KeyError):model.object_by_id(s,TWO)
    new=entity(20,TWO);collection.objects.append(new)
    assert model.object_by_id(s,TWO) is new
    assert collection.index_reads==3


def test_reopened_or_replaced_model_uses_current_collection_and_remapped_ids():
    old=entity(10,ONE);s,original=session([old])
    assert model.object_by_id(s,ONE) is old
    new=entity(200,ONE);current=Collection([entity(10,TWO),new])
    s.model=SimpleNamespace(GetObjects=lambda:current)
    assert model.object_by_id(s,ONE) is new
    assert current.id_reads==[10,200] and current.index_reads==2
    assert original.index_reads==1


def test_session_caches_are_independent_even_when_models_share_uuid_and_id():
    one=entity(10,ONE);other=entity(10,ONE)
    first,a=session([one]);second,b=session([other])
    assert model.object_by_id(first,ONE) is one
    assert model.object_by_id(second,ONE) is other
    assert first._object_id_cache is not second._object_id_cache
    assert a.index_reads==b.index_reads==1
    first._object_id_cache[ONE]=999
    assert second._object_id_cache[ONE]==10


def test_create_remembers_new_identity_before_deferred_uuid_lookup(monkeypatch):
    existing=entity(10,ONE);created=entity(20,TWO)
    s,collection=session([existing])
    assert model.object_by_id(s,ONE) is existing
    s.sdk=SimpleNamespace(types={'Floor':'FLOOR'})
    s.r=SimpleNamespace(Point3D=lambda *args:args,Vector3D=lambda *args:args,
                        Placement3D=lambda *args:args)
    s.model.CreateNewEntityArgs=lambda:SimpleNamespace()
    def create(args):
        assert args.TypeIdS=='FLOOR'
        collection.objects.append(created)
        return created
    s.model.CreateObject=create
    monkeypatch.setattr(model,'event',lambda *args,**kwargs:None)
    assert model.create(s,'Floor') is created
    assert model.object_by_id(s,TWO) is created
    assert collection.index_reads==1
    assert s._object_id_cache=={ONE:10,TWO:20}


def test_rolled_back_created_identity_is_revalidated_and_removed(monkeypatch):
    created=entity(20,TWO);s,collection=session([])
    s.sdk=SimpleNamespace(types={'Floor':'FLOOR'})
    s.r=SimpleNamespace(Point3D=lambda *args:args,Vector3D=lambda *args:args,
                        Placement3D=lambda *args:args)
    s.model.CreateNewEntityArgs=lambda:SimpleNamespace()
    s.model.CreateObject=lambda args:created
    monkeypatch.setattr(model,'event',lambda *args,**kwargs:None)
    model.create(s,'Floor')
    with pytest.raises(KeyError):model.object_by_id(s,TWO)
    assert s._object_id_cache=={}
