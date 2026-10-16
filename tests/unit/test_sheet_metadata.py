"""Portable contract and saved-state tests; these do not run native Renga."""
from contextlib import contextmanager
from types import SimpleNamespace as NS
import copy
import uuid

import pytest

from renga_codex_bridge import sheet_metadata as m


DRAWING = str(uuid.UUID(int=1))
OTHER_DRAWING = str(uuid.UUID(int=2))
RESOURCE = str(uuid.UUID(int=3))
ANNOTATION = str(uuid.UUID(int=4))
BUILDING = str(uuid.UUID(int=5))


def request(**values):
    return [{"drawing_uuid": DRAWING, "parameters": values or {"EntityName": "Updated"}}]


@pytest.mark.parametrize("value", [None, [], {}, [None], request(Author="X"),
    request(SetCellValue="fake"), request(PageOrientation=True), request(PageOrientation=3),
    request(EntityName=""), request(EntityName="x\0y"), request(LayoutStyleId=False),
    request(LayoutStyleId=0), request(TopicId=-1), request(PageFormatId=2**31),
    [{"drawing_uuid": "not-uuid", "parameters": {"EntityName": "X"}}],
    [{"drawing_uuid": DRAWING, "parameters": {}, "table": []}],
    request() * 2, request() * 101])
def test_invalid_request_fails_before_session_or_plan(monkeypatch, value):
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid request must not open or mutate native data")

    monkeypatch.setattr(m, "Session", forbidden)
    monkeypatch.setattr(m, "save_plan", forbidden)
    with pytest.raises(ValueError):
        m.update_sheet_metadata("never-opened.rnp", value)


def test_validator_normalizes_uuid_and_copies_the_request():
    source = request(LayoutStyleId=123, PageOrientation=2)
    source[0]["drawing_uuid"] = "{" + DRAWING.upper() + "}"
    before = copy.deepcopy(source)
    result = m.validate_sheet_changes(source)
    assert source == before
    assert result[0]["drawing_uuid"] == DRAWING
    result[0]["parameters"]["LayoutStyleId"] = 999
    assert source == before


def test_title_block_reads_documented_column_row_order_and_keeps_empty_cells():
    calls = []

    def cell(column, row):
        calls.append((column, row))
        return [["A", ""], ["C", "D"]][row][column]

    native = NS(TitleBlockInstanceCount=1, GetTitleBlockInstance=lambda i: NS(
        Name="Native", ColumnCount=2, RowCount=2, GetCellValue=cell))
    entity = NS(QueryInterface=lambda interface: native)
    assert m.read_title_blocks(NS(r=NS(IDrawing=object())), entity) == [
        {"index": 0, "name": "Native", "column_count": 2, "row_count": 2,
         "rows": [["A", ""], ["C", "D"]]}]
    assert calls == [(0, 0), (1, 0), (0, 1), (1, 1)]


def test_getter_failure_is_never_silently_replaced_by_drawing_name():
    def fail(*args):
        raise RuntimeError("Native getter failed")

    entity = NS(Name="Guessed title", QueryInterface=fail)
    with pytest.raises(RuntimeError, match="Native getter"):
        m.read_title_blocks(NS(r=NS(IDrawing=object())), entity)


class Collection:
    def __init__(self, entities):
        self.entities = entities

    @property
    def Count(self):
        return len(self.entities)

    def GetByIndex(self, index):
        return self.entities[index]

    def Contains(self, native_id):
        return any(entity.Id == native_id for entity in self.entities)

    def GetById(self, native_id):
        return next(entity for entity in self.entities if entity.Id == native_id)

    def GetByUniqueIdS(self, identifier):
        return next((entity for entity in self.entities
                     if m._uuid(entity.UniqueIdS) == m._uuid(identifier)), None)


def value(value, readonly=False):
    return {"value": value, "readonly": readonly, "has_value": True}


def fixture(monkeypatch):
    annotation = NS(UniqueIdS=ANNOTATION, ObjectTypeS="NATIVE_ANNOTATION", Id=7)
    building = NS(UniqueIdS=BUILDING, ObjectTypeS="NATIVE_WALL", Id=8)
    resource = NS(UniqueIdS=RESOURCE, ObjectTypeS="NATIVE_LAYOUT", Id=123, Name="Native layout")
    drawing = NS(UniqueIdS=DRAWING, TypeIdS="NATIVE_DRAWING", Id=9, Name="Old",
                 values={"EntityName": value("Old"), "LayoutStyleId": value(0),
                         "PageOrientation": value(1), "PageFormatId": value(0), "TopicId": value(0)})
    drawing.QueryInterface = lambda interface: (
        NS(GetObjects=lambda: Collection([annotation])) if interface == "model"
        else NS(TitleBlockInstanceCount=0))
    project = NS(Drawings2=Collection([drawing]), LayoutStyles=Collection([resource]),
                 PageFormatStyles=Collection([]), Topics=Collection([]))
    state = {"operations": 0, "saves": 0, "sessions": [], "on_save": None}

    @contextmanager
    def operation():
        state["operations"] += 1
        yield

    def save():
        state["saves"] += 1
        if state["on_save"]:
            state["on_save"]()

    class Session:
        def __init__(self, path, **kwargs):
            self.path = path
            self.kwargs = kwargs
            self.project, self.model = project, NS(GetObjects=lambda: Collection([building]))
            self.r = NS(IModel="model", IDrawing="drawing")
            self.operation, self.save = operation, save

        def __enter__(self):
            state["sessions"].append(self.kwargs)
            return self

        def __exit__(self, *args):
            return False

    def setter(session, entity, key, requested):
        entity.values[key] = value(requested)
        if key == "EntityName":
            entity.Name = requested

    monkeypatch.setattr(m, "Session", Session)
    monkeypatch.setattr(m, "parameters", lambda session, entity: copy.deepcopy(entity.values))
    monkeypatch.setattr(m, "set_parameter", setter)
    monkeypatch.setattr(m, "save_plan", lambda plan: "saved-operation-plan.json")
    monkeypatch.setattr(m, "event", lambda *args, **kwargs: None)
    return state, drawing, annotation, resource


def test_existing_sheet_saved_name_and_persistent_reference_verified_even_when_ids_change(monkeypatch):
    state, drawing, annotation, resource = fixture(monkeypatch)

    def renumber_after_save():
        resource.Id = 456
        drawing.Id = 777
        annotation.Id = 888
        drawing.values["LayoutStyleId"] = value(456)

    state["on_save"] = renumber_after_save
    result = m.update_sheet_metadata("test.rnp", request(EntityName="New", LayoutStyleId=123))
    assert result["status"] == "saved_reopened_verified"
    assert result["drawings"][0]["references"]["LayoutStyleId"]["id"] == 456
    assert result["drawings"][0]["references"]["LayoutStyleId"]["uuid"] == RESOURCE
    assert state["sessions"] == [{"write": True}, {}]
    assert state["operations"] == state["saves"] == 1
    assert result["computer_use_calls"] == 0 and not result["visual_layout_verified"]


@pytest.mark.parametrize("parameter,requested", [("PageFormatId", 99), ("LayoutStyleId", 99), ("TopicId", 99)])
def test_absent_resource_preflight_prevents_native_mutation(monkeypatch, parameter, requested):
    state, drawing, _, _ = fixture(monkeypatch)
    with pytest.raises(ValueError, match="resource is absent"):
        m.update_sheet_metadata("test.rnp", request(**{parameter: requested}))
    assert state["operations"] == state["saves"] == 0
    assert drawing.Name == "Old"


def test_all_requested_sheets_preflight_before_first_setter(monkeypatch):
    state, drawing, _, _ = fixture(monkeypatch)
    changes = request(EntityName="Should not apply") + [
        {"drawing_uuid": OTHER_DRAWING, "parameters": {"EntityName": "Missing"}}]
    with pytest.raises(ValueError, match="UUID is absent"):
        m.update_sheet_metadata("test.rnp", changes)
    assert state["operations"] == state["saves"] == 0
    assert drawing.Name == "Old"


def test_readonly_is_never_bypassed(monkeypatch):
    state, drawing, _, _ = fixture(monkeypatch)
    drawing.values["EntityName"]["readonly"] = True
    with pytest.raises(ValueError, match="Read-only"):
        m.update_sheet_metadata("test.rnp", request())
    assert state["operations"] == state["saves"] == 0


@pytest.mark.parametrize("corruption", ["uuid", "type", "value", "resource"])
def test_saved_state_corruption_prevents_success(monkeypatch, corruption):
    state, drawing, annotation, resource = fixture(monkeypatch)

    def corrupt_saved_state():
        if corruption == "uuid":
            annotation.UniqueIdS = str(uuid.UUID(int=99))
        elif corruption == "type":
            annotation.ObjectTypeS = "REPLACED_ANNOTATION"
        elif corruption == "value":
            drawing.values["EntityName"] = value("Setter returned but data did not persist")
        else:
            resource.UniqueIdS = str(uuid.UUID(int=98))

    state["on_save"] = corrupt_saved_state
    with pytest.raises(RuntimeError, match="changed|mismatch"):
        m.update_sheet_metadata("test.rnp", request(EntityName="New", LayoutStyleId=123))


def test_inspection_opens_readonly_session_and_never_saves(monkeypatch):
    state, _, _, _ = fixture(monkeypatch)
    result = m.inspect_sheet_metadata("test.rnp")
    assert state["sessions"] == [{}]
    assert state["operations"] == state["saves"] == 0
    assert not result["title_block_cell_authoring"]


def test_snapshot_keeps_getter_failure_explicit_and_retains_readable_metadata(monkeypatch):
    state, drawing, _, _ = fixture(monkeypatch)

    def fail_count(session, entity):
        raise RuntimeError("Native TitleBlockInstanceCount failed")

    monkeypatch.setattr(m, "read_title_blocks", fail_count)
    result = m.inspect_sheet_metadata("test.rnp")
    row = result["drawings"][0]
    assert row["name"] == "Old" and row["title_blocks"] is None
    assert row["title_block_readback"]["status"] == "failed"
    assert "TitleBlockInstanceCount" in row["title_block_readback"]["error"]
    assert not result["title_block_readback_complete"]
    assert state["saves"] == 0
