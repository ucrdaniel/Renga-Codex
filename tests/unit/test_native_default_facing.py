"""Explicit opt-in, host evidence and old strict placement contracts; no COM."""
from types import SimpleNamespace

import pytest

from renga_codex_bridge.model import creation_axes, verify_filling_host
from renga_codex_bridge.orientation import assert_pose_matches, NativePlacementVerificationError
from renga_codex_bridge.validation import validate_plan


@pytest.mark.parametrize("kind", ["Door","Window"])
def test_native_default_facing_is_explicit_and_uses_only_default_constructor_axes(kind):
    assert validate_plan([{"action":"create","kind":kind,"host":42,"native_default_facing":True}])["valid"]
    assert creation_axes(kind,native_default_facing=True) == {"x_axis":[1,0,0],"z_axis":[0,0,1]}


@pytest.mark.parametrize("value", [None,0,1,"true",[],{}])
def test_mode_never_coerces_non_boolean_values(value):
    with pytest.raises(ValueError,match="strict boolean"):
        validate_plan([{"action":"create","kind":"Window","host":42,"native_default_facing":value}])
    with pytest.raises(ValueError,match="strict boolean"):
        creation_axes("Window",native_default_facing=value)


@pytest.mark.parametrize("kind", ["Wall","Room","Railing","Level",None,[]])
def test_mode_cannot_be_ignored_on_another_category(kind):
    with pytest.raises(ValueError):
        validate_plan([{"action":"create","kind":kind,"native_default_facing":True}])


def test_mode_is_for_creation_only_and_false_still_requires_a_filling_category():
    with pytest.raises(ValueError): validate_plan([{"action":"delete","id":42,"native_default_facing":True}])
    with pytest.raises(ValueError): validate_plan([{"action":"create","kind":"Wall","native_default_facing":False}])


@pytest.mark.parametrize("field,value", [("x_axis",[1,0,0]),("x_axis",[0,1,0]),("z_axis",[0,0,1])])
def test_native_default_cannot_silently_discard_even_default_explicit_axes(field,value):
    with pytest.raises(ValueError,match="explicit"):
        validate_plan([{"action":"create","kind":"Window","host":42,"native_default_facing":True,field:value}])
    with pytest.raises(ValueError,match="explicit"):
        creation_axes("Window",native_default_facing=True,**{field:value})


def test_old_explicit_axes_are_preserved_and_mismatch_is_still_rejected():
    requested=creation_axes("Window",[0,1,0],[0,0,1],native_default_facing=False)
    assert requested["x_axis"] == [0,1,0]
    with pytest.raises(NativePlacementVerificationError):
        assert_pose_matches(requested,{"origin":[0,0,0],"x_axis":[1,0,0],"z_axis":[0,0,1]})
    assert validate_plan([{"action":"create","kind":"Window","host":42,"native_default_facing":False,"x_axis":[0,1,0]}])["valid"]


HOST="00000000-0000-4000-8000-000000000042"
OTHER="00000000-0000-4000-8000-000000000099"


def native_host_probe(*,affected=(42,),parent=HOST,kind="Window",host_type="wall"):
    host=SimpleNamespace(Id=42,UniqueIdS="{"+HOST+"}",ObjectTypeS=host_type)
    objects=SimpleNamespace(Count=1,GetByIndex=lambda index:host,
                            GetById=lambda identifier:host if identifier==host.Id else None)
    parameter=SimpleNamespace(HasValue=parent is not None,GetStringValue=lambda:parent)
    container=SimpleNamespace(ContainsS=lambda guid:True,GetS=lambda guid:parameter)
    params=SimpleNamespace(GetAffectedObjectIds=lambda:list(affected))
    obj=SimpleNamespace(ObjectTypeS=kind.lower(),GetParameters=lambda:container,QueryInterface=lambda interface:params)
    s=SimpleNamespace(model=SimpleNamespace(GetObjects=lambda:objects),
                      sdk=SimpleNamespace(types={"Wall":"WALL","Window":"WINDOW","Door":"DOOR"},parameters={"ParentObjectUniqueId":"parent-guid"}),
                      r=SimpleNamespace(IDoorParams="door-params",IWindowParams="window-params"))
    return s,obj


@pytest.mark.parametrize("kind", ["Door","Window"])
def test_requested_wall_uuid_is_resolved_and_native_affected_ids_and_parent_are_checked(kind):
    s,obj=native_host_probe(kind=kind)
    result=verify_filling_host(s,obj,HOST)
    assert result["host_uuid"] == HOST and result["affected_wall_verified"]
    assert result["parent_uuid_verified"] and result["parent_uuid"] == HOST


def test_no_parent_value_does_not_become_a_fake_parent_identity_check():
    s,obj=native_host_probe(parent=None)
    result=verify_filling_host(s,obj,HOST)
    assert result["affected_wall_verified"] and result["parent_uuid"] is None and not result["parent_uuid_verified"]


def test_wrong_wall_effect_or_disagreeing_native_parent_is_rejected():
    s,obj=native_host_probe(affected=(99,))
    with pytest.raises(RuntimeError,match="no longer affects"):verify_filling_host(s,obj,HOST)
    s,obj=native_host_probe(parent=OTHER)
    with pytest.raises(RuntimeError,match="ParentObjectUniqueId"):verify_filling_host(s,obj,HOST)
    s,obj=native_host_probe(host_type="floor")
    with pytest.raises(RuntimeError,match="native Wall"):verify_filling_host(s,obj,HOST)
