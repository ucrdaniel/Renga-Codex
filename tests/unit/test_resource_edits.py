"""Portable safety and readback contracts; no native Renga is launched."""
from contextlib import contextmanager
from types import SimpleNamespace as NS
from pathlib import Path
import copy
import uuid

import pytest

from renga_codex_bridge import resource_edits as m


STYLE = str(uuid.UUID(int=1))
OTHER = str(uuid.UUID(int=2))
MATERIAL = str(uuid.UUID(int=3))
STYLE_TYPE = str(uuid.UUID(int=10))
MATERIAL_TYPE = str(uuid.UUID(int=11))
HASH = "a" * 64


def request(**values):
    return [{"resource_uuid": STYLE, "expected_name": "Window", "parameters": values or {"FrameDepth": 50}}]


@pytest.mark.parametrize("bad", [None, [], {}, [None], request(MaterialId=12), request(Width=20),
    request(FrameDepth=True), request(FrameDepth=0), request(FrameDepth=-1), request(FrameDepth=float("inf")),
    request(FrameDepth=float("nan")), request(FrameDepth="50"), request(FrameDepth=10**1000),
    request(EntityName=""), request(EntityName="X\0Y"), request(EntityName="X\nY"),
    [{"resource_uuid": STYLE, "expected_name": "Window"}],
    [{"resource_uuid": "12", "expected_name": "Window", "parameters": {"FrameDepth":50}}],
    [{"resource_uuid": STYLE, "expected_name": "", "parameters": {"FrameDepth":50}}],
    [{"resource_uuid": STYLE, "expected_name": "Window", "material_uuid":0}],
    request()*2, request()*101])
def test_bad_requests_do_not_save_plan_or_open_session(monkeypatch, bad):
    def forbidden(*a, **kw): raise AssertionError("No native work for invalid input")
    monkeypatch.setattr(m, "Session", forbidden)
    monkeypatch.setattr(m, "save_plan", forbidden)
    with pytest.raises(ValueError): m.update_window_styles("unused.rnp", bad)


@pytest.mark.parametrize("bad", [True, "", "f"*63, "g"*64, 15])
def test_hash_guard_requires_exact_digest(bad):
    with pytest.raises(ValueError): m.validate_window_style_changes(request(), bad)


def test_normalization_copies_input_and_preserves_explicit_name():
    source = request(FrameDepth=50)
    source[0]["resource_uuid"] = "{"+STYLE.upper()+"}"
    source[0]["material_uuid"] = "{"+MATERIAL.upper()+"}"
    before = copy.deepcopy(source)
    result = m.validate_window_style_changes(source)
    assert source == before and result[0]["resource_uuid"] == STYLE
    assert result[0]["parameters"]["FrameDepth"] == 50.0
    assert result[0]["material_uuid"] == MATERIAL


class Collection:
    def __init__(self, entities): self.entities = entities
    @property
    def Count(self): return len(self.entities)
    def GetByIndex(self, index): return self.entities[index]
    def GetByUniqueIdS(self, uid):
        return next((e for e in self.entities if m._uuid(e.UniqueIdS)==m._uuid(uid)), None)
    def Contains(self, nid): return any(e.Id == nid for e in self.entities)
    def GetById(self, nid): return next(e for e in self.entities if e.Id == nid)


def value(v, readonly=False, type_=None):
    return {"value":v, "has_value":True, "readonly":readonly,
            "type":type_ if type_ is not None else 4 if isinstance(v,str) else 2 if type(v) is int else 3}


def fixture(monkeypatch):
    style = NS(Id=20, UniqueIdS=STYLE, TypeIdS=STYLE_TYPE, Name="Window",
        values={**{key:value(100.0) for key in m.LENGTH_PARAMETERS},
                "EntityName":value("Window"), "MaterialId":value(30), "Unrelated":value("keep")})
    material = NS(Id=30, UniqueIdS=MATERIAL, TypeIdS=MATERIAL_TYPE, Name="Black PVC")
    project = NS(WindowStyles=Collection([style]), Materials=Collection([material]), HasActiveOperation=lambda:False)
    state = {"sessions":[], "operations":0, "saves":0, "setters":[], "on_save":None,
             "identities":{"building":{"wall":"type"}}, "fingerprint":HASH, "initial_sha":HASH}
    @contextmanager
    def operation(s):
        state["operations"] += 1
        yield
    class Session:
        def __init__(self, path, **kw):
            self.project = project
            self.sdk = NS(types={"WindowStyle":STYLE_TYPE,"Material":MATERIAL_TYPE})
            self.initial_sha = state["initial_sha"]
            self.kw = kw
        def __enter__(self): state["sessions"].append(self.kw); return self
        def __exit__(self,*a): return False
        def save(self):
            state["saves"] += 1
            if state["on_save"]: state["on_save"]()
    def setter(s,e,key,v):
        state["setters"].append(key)
        e.values[key] = value(v)
        if key=="EntityName": e.Name=v
    monkeypatch.setattr(m,"Session",Session)
    monkeypatch.setattr(m,"_resource_operation",operation)
    monkeypatch.setattr(m,"parameters",lambda s,e:copy.deepcopy(e.values))
    monkeypatch.setattr(m,"set_parameter",setter)
    monkeypatch.setattr(m,"checked_path",lambda path,**kw:Path(path))
    monkeypatch.setattr(m,"fingerprint",lambda path:state["fingerprint"])
    monkeypatch.setattr(m,"save_plan",lambda p:"saved-plan.json")
    monkeypatch.setattr(m,"event",lambda *a,**kw:None)
    monkeypatch.setattr(m,"sheet_identity_snapshot",lambda s:copy.deepcopy(state["identities"]))
    return state,style,material,project


def test_all_six_lengths_and_material_resolve_persistent_reference_after_renumber(monkeypatch):
    state,style,material,_ = fixture(monkeypatch)
    changes=request(**{key:50 for key in m.LENGTH_PARAMETERS},EntityName="Updated")
    changes[0]["material_uuid"]=MATERIAL
    def renumber():
        material.Id=31
        style.Id=21
        style.values["MaterialId"]=value(31)
    state["on_save"]=renumber
    out=m.update_window_styles("test.rnp",changes,HASH.upper())
    assert out["status"]=="saved_reopened_verified" and out["updated_resources"][0]["id"]==21
    assert out["updated_resources"][0]["parameters_verified"]["MaterialId"]["uuid"]==MATERIAL
    assert state["saves"]==state["operations"]==1
    assert state["sessions"]==[{"write":True},{}]
    assert out["computer_use_calls"]==0 and not out["undo_history_supported"]
    assert not out["updated_resources"][0]["material_per_node_verified"]


@pytest.mark.parametrize("mode",["missing_style","wrong_type","name","readonly","parameter_type","missing_parameter",
                                  "missing_material","wrong_material_type","conflicting_name","active_operation"])
def test_preflight_rejects_before_any_mutation(monkeypatch,mode):
    state,style,material,project=fixture(monkeypatch)
    changes=request()
    if mode=="missing_style": project.WindowStyles.entities=[]
    elif mode=="wrong_type": style.TypeIdS=MATERIAL_TYPE
    elif mode=="name": style.Name="Different"
    elif mode=="readonly": style.values["FrameDepth"]["readonly"]=True
    elif mode=="parameter_type": style.values["FrameDepth"]["type"]=4
    elif mode=="missing_parameter": del style.values["FrameDepth"]
    elif mode=="missing_material": changes[0]["material_uuid"]=OTHER
    elif mode=="wrong_material_type":
        changes[0]["material_uuid"]=MATERIAL; material.TypeIdS=STYLE_TYPE
    elif mode=="conflicting_name":
        project.WindowStyles.entities.append(NS(Id=21,UniqueIdS=OTHER,TypeIdS=STYLE_TYPE,Name="Taken"))
        changes=request(EntityName="Taken")
    elif mode=="active_operation": project.HasActiveOperation=lambda:True
    with pytest.raises((ValueError,RuntimeError)): m.update_window_styles("test.rnp",changes)
    assert state["operations"]==state["saves"]==0 and not state["setters"]


def test_all_styles_preflight_before_first_setter(monkeypatch):
    state,*_=fixture(monkeypatch)
    changes=request()+[{"resource_uuid":OTHER,"expected_name":"Missing","parameters":{"FrameDepth":50}}]
    with pytest.raises(ValueError): m.update_window_styles("test.rnp",changes)
    assert not state["setters"] and state["operations"]==0


@pytest.mark.parametrize("mode",["disk","opened"])
def test_digest_change_is_rejected(monkeypatch,mode):
    state,*_=fixture(monkeypatch)
    state["fingerprint" if mode=="disk" else "initial_sha"]="b"*64
    with pytest.raises(RuntimeError,match="SHA256"): m.update_window_styles("test.rnp",request(),HASH)
    assert not state["setters"] and state["saves"]==0
    if mode=="disk": assert not state["sessions"]


@pytest.mark.parametrize("corrupt",["value","unrequested","identity","resource_name","resource_uuid","material_reference"])
def test_reopened_corruption_cannot_be_reported_successful(monkeypatch,corrupt):
    state,style,material,project=fixture(monkeypatch)
    changes=request(); changes[0]["material_uuid"]=MATERIAL
    def corruption():
        if corrupt=="value": style.values["FrameDepth"]=value(49.0)
        elif corrupt=="unrequested": style.values["Unrelated"]=value("changed")
        elif corrupt=="identity": state["identities"]={"building":{}}
        elif corrupt=="resource_name": material.Name="Changed"
        elif corrupt=="resource_uuid": style.UniqueIdS=OTHER
        else: style.values["MaterialId"]=value(999)
    state["on_save"]=corruption
    with pytest.raises(RuntimeError): m.update_window_styles("test.rnp",changes)
    assert state["saves"]==1 and len(state["sessions"])==2


def test_setter_that_silently_ignores_value_prevents_save(monkeypatch):
    state,*_=fixture(monkeypatch)
    monkeypatch.setattr(m,"set_parameter",lambda *a:None)
    with pytest.raises(RuntimeError,match="parameter mismatch"): m.update_window_styles("test.rnp",request())
    assert state["saves"]==0


def test_snapshot_reports_unavailable_but_does_not_hide_getter_errors(monkeypatch):
    state,style,material,project=fixture(monkeypatch)
    result=m.resource_identity_snapshot(NS(project=project))
    assert result["WindowStyles"]["entries"][STYLE]["name"]=="Window"
    assert result["Tables"]["status"]=="unavailable"
    class Failed:
        @property
        def Materials(self): raise RuntimeError("native getter failed")
    with pytest.raises(RuntimeError,match="native getter failed"):
        m.resource_identity_snapshot(NS(project=Failed()))
