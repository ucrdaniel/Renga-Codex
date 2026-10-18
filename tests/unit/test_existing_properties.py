"""Portable safety/persistence contracts only; these never run native Renga."""
from contextlib import contextmanager
import copy
from types import SimpleNamespace as NS
import uuid

import pytest

from renga_codex_bridge import existing_properties as m


def uid(number):
    return str(uuid.UUID(int=number))


PROJECT, DRAWING, TOPIC, PROPERTY = (uid(i) for i in range(1, 5))
BUILDING, ANNOTATION, LAYOUT, PAGE = (uid(i) for i in range(5, 9))
TYPES = {name: uid(100 + index) for index, name in enumerate(("Project", "Drawing", "Topic"))}


def request(kind="Drawing", **updates):
    row = {"kind": kind, "uuid": {"Project": PROJECT, "Drawing": DRAWING, "Topic": TOPIC}[kind],
           "property_guid": PROPERTY, "property_name": "Author", "value": "Example Author"}
    row.update(updates)
    return [row]


def cell_request(**updates):
    row = {"drawing_uuid": DRAWING, "block_index": 0, "block_name": "Main",
           "column": 0, "row": 1, "expected_before": "", "expected_value": "Example Author"}
    row.update(updates)
    return [row]


@pytest.mark.parametrize("changes,cells", [
    (None, None), ([], None), ([None], None), (request() * 1001, None),
    (request(kind="Drawing", kind_invalid=True), None), (request(uuid=1), None),
    (request(uuid="not-uuid"), None), (request(property_guid=12), None),
    (request(property_guid="bad"), None), (request(property_name=""), None),
    (request(value=None), None), (request(value="NUL\0"), None),
    (request() * 2, None), (request(), {}), (request(), cell_request(column=True)),
    (request(), cell_request(row=-1)), (request(), cell_request(block_index=100)),
    (request(), cell_request(expected_before=None)), (request(), cell_request(expected_value="x\0")),
    (request(), cell_request(block_name="")), (request(), cell_request(drawing_uuid="missing")),
    (request(), cell_request() * 2),
])
def test_bad_inputs_fail_before_plan_or_session(monkeypatch, changes, cells):
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid request reached plan/native session")
    monkeypatch.setattr(m, "Session", forbidden)
    monkeypatch.setattr(m, "save_plan", forbidden)
    with pytest.raises(ValueError):
        m.update_existing_properties("unused.rnp", changes, cell_checks=cells)


@pytest.mark.parametrize("kind", ["Wall", [], {}, None])
def test_unsupported_target_kind_rejected(kind):
    value = request()
    value[0]["kind"] = kind
    with pytest.raises(ValueError):
        m.validate_existing_property_changes(value)


def test_non_native_project_rejected_before_session(monkeypatch):
    monkeypatch.setattr(m, "Session", lambda *a, **k: pytest.fail("opened a session"))
    with pytest.raises(ValueError, match="native .rnp"):
        m.update_existing_properties("file.json", request())


def test_validator_detaches_normalizes_and_accepts_explicit_clear():
    source, cells = request(value=""), cell_request(expected_value="")
    source[0]["uuid"] = "{" + DRAWING.upper() + "}"
    original = copy.deepcopy((source, cells))
    changes, checks = m.validate_existing_property_changes(source, cells)
    assert changes[0]["uuid"] == DRAWING
    changes[0]["value"] = "mutated"
    checks[0]["expected_value"] = "mutated"
    assert (source, cells) == original


class Collection:
    def __init__(self, values):
        self.values = values

    @property
    def Count(self):
        return len(self.values)

    def GetByIndex(self, index):
        return self.values[index]

    def GetByUniqueIdS(self, identifier):
        return next((item for item in self.values if m._uuid(item.UniqueIdS) == identifier), None)

    def GetById(self, identifier):
        return next((item for item in self.values if item.Id == identifier), None)


def fixture(monkeypatch):
    state = {"sessions": [], "operations": 0, "saves": 0, "writes": [], "events": [],
             "bound": True, "on_apply": None, "on_save": None, "on_reopen": None, "cell_calls": []}

    class Property:
        IdS, Name, Type = PROPERTY, "Author", 2
        value = None

        def HasValue(self):
            return self.value is not None

        def GetStringValue(self):
            return self.value

        def SetStringValue(self, value):
            state["writes"].append(value)
            self.value = value

    class Container:
        def __init__(self):
            self.prop = Property()
            self.contains = True

        def ContainsS(self, identifier):
            return self.contains and identifier == PROPERTY

        def GetS(self, identifier):
            assert self.ContainsS(identifier)
            return self.prop

    project_props, drawing_props, topic_props = (Container() for _ in range(3))
    assignments = {value: True for value in TYPES.values()}
    expressions = {value: None for value in TYPES.values()}
    definition = {"name": "Author", "type": 2, "registered": True}
    manager = NS(PropertyCount=1, GetPropertyIdS=lambda i: PROPERTY,
                 GetPropertyNameS=lambda g: definition["name"],
                 GetPropertyTypeS=lambda g: definition["type"],
                 IsPropertyRegisteredS=lambda g: definition["registered"],
                 IsPropertyAssignedToTypeS=lambda g, t: assignments[t],
                 GetExpressionS=lambda g, t: expressions[t])
    info = NS(UniqueIdS=PROJECT, Name="Project", Code="Code", Stage="Design", Description="",
              GetProperties=lambda: project_props)
    annotation = NS(UniqueIdS=ANNOTATION, ObjectTypeS=uid(201), Id=11)
    building = NS(UniqueIdS=BUILDING, ObjectTypeS=uid(202), Id=12)
    block_rows = [["Author", "Reference"], ["", "Unchanged"]]

    def cell(column, row):
        state["cell_calls"].append((column, row))
        return block_rows[row][column]

    block = NS(Name="Main", ColumnCount=2, RowCount=2, GetCellValue=cell)
    title_blocks = NS(TitleBlockInstanceCount=1, GetTitleBlockInstance=lambda index: block)
    drawing = NS(UniqueIdS=DRAWING, TypeIdS=TYPES["Drawing"], Id=13, Name="Drawing")
    drawing.QueryInterface = lambda interface: {"properties": drawing_props,
        "model": NS(GetObjects=lambda: Collection([annotation])), "drawing": title_blocks}[interface]
    topic = NS(UniqueIdS=TOPIC, TypeIdS=TYPES["Topic"], Id=14, Name="Topic",
               QueryInterface=lambda interface: topic_props)
    layout = NS(UniqueIdS=LAYOUT, TypeIdS=uid(203), Id=15, Name="Layout")
    page = NS(UniqueIdS=PAGE, TypeIdS=uid(204), Id=16, Name="Page")
    project = NS(ProjectInfo=info, PropertyManager=manager, Drawings2=Collection([drawing]),
                 Topics=Collection([topic]), LayoutStyles=Collection([layout]),
                 PageFormatStyles=Collection([page]))
    drawing.metadata = {"PageOrientation": 2, "LayoutStyleId": layout.Id,
                        "PageFormatId": page.Id, "TopicId": topic.Id}

    @contextmanager
    def operation():
        state["operations"] += 1
        yield
        if state["bound"]:
            block_rows[1][0] = drawing_props.prop.value or ""
        if state["on_apply"]:
            state["on_apply"]()

    class Session:
        def __init__(self, path, **kwargs):
            self.kwargs, self.project = kwargs, project
            self.model = NS(GetObjects=lambda: Collection([building]))
            self.sdk, self.r = NS(types=TYPES), NS(IPropertyContainer="properties", IModel="model", IDrawing="drawing")
            self.operation, self.initial_sha = operation, "native-saved-sha"

        def __enter__(self):
            state["sessions"].append(self.kwargs)
            if not self.kwargs and state["on_reopen"]:
                state["on_reopen"]()
            return self

        def __exit__(self, *args):
            return False

        def save(self):
            state["saves"] += 1
            if state["on_save"]:
                state["on_save"]()

    monkeypatch.setattr(m, "Session", Session)
    monkeypatch.setattr(m, "parameters", lambda s, entity: {
        key: {"has_value": True, "value": value}
        for key, value in {"EntityName": entity.Name, **entity.metadata}.items()})
    monkeypatch.setattr(m, "save_plan", lambda plan: "operation-plan.json")
    monkeypatch.setattr(m, "event", lambda *args, **kwargs: state["events"].append((args, kwargs)))
    return NS(state=state, project=project, definition=definition, assignments=assignments,
              expressions=expressions, project_props=project_props, drawing_props=drawing_props,
              topic_props=topic_props, drawing=drawing, topic=topic, layout=layout,
              annotation=annotation, building=building, block=block, rows=block_rows, blocks=title_blocks)


@pytest.mark.parametrize("kind", ["Project", "Drawing", "Topic"])
def test_three_existing_target_scopes_save_reopen_and_verify(monkeypatch, kind):
    f = fixture(monkeypatch)
    result = m.update_existing_properties("test.rnp", request(kind))
    assert result["status"] == "saved_reopened_verified"
    assert result["properties"][0]["observed"] == {"has_value": True, "value": "Example Author"}
    assert f.state["sessions"] == [{"write": True}, {}]
    assert f.state["saves"] == f.state["operations"] == 1
    assert not result["title_block_values_verified"]
    assert not result["title_block_source_binding_proven"] and not result["visual_layout_verified"]


def test_existing_string_clear_is_a_real_present_empty_value(monkeypatch):
    f = fixture(monkeypatch)
    f.drawing_props.prop.value = "Previous"
    result = m.update_existing_properties("test.rnp", request(value=""))
    assert result["properties"][0]["observed"] == {"has_value": True, "value": ""}


def test_native_titleblock_cell_checked_column_then_row_after_reopen(monkeypatch):
    f = fixture(monkeypatch)
    result = m.update_existing_properties("test.rnp", request(), cell_checks=cell_request())
    assert result["title_block_values_verified"]
    assert result["title_block_checks"][0]["actual_value"] == "Example Author"
    assert f.state["cell_calls"] == [(0, 1)] * 3
    assert not result["title_block_source_binding_proven"]


@pytest.mark.parametrize("failure", ["unregistered", "name", "type", "assignment", "expression",
                                    "container", "property_uuid", "property_name", "property_type", "target_type"])
def test_preflight_guards_all_before_first_mutation(monkeypatch, failure):
    f = fixture(monkeypatch)
    if failure == "unregistered": f.definition["registered"] = False
    elif failure == "name": f.definition["name"] = "Other"
    elif failure == "type": f.definition["type"] = 1
    elif failure == "assignment": f.assignments[TYPES["Drawing"]] = False
    elif failure == "expression": f.expressions[TYPES["Drawing"]] = "{Name}"
    elif failure == "container": f.drawing_props.contains = False
    elif failure == "property_uuid": f.drawing_props.prop.IdS = uid(99)
    elif failure == "property_name": f.drawing_props.prop.Name = "Other"
    elif failure == "property_type": f.drawing_props.prop.Type = 1
    else: f.drawing.TypeIdS = TYPES["Topic"]
    with pytest.raises(ValueError):
        m.update_existing_properties("test.rnp", request())
    assert f.state["writes"] == [] and f.state["operations"] == f.state["saves"] == 0


def test_later_absent_target_prevents_earlier_valid_write(monkeypatch):
    f = fixture(monkeypatch)
    changes = request() + request("Topic", uuid=uid(99))
    with pytest.raises(ValueError, match="UUID is absent"):
        m.update_existing_properties("test.rnp", changes)
    assert not f.state["writes"] and f.state["operations"] == 0


@pytest.mark.parametrize("failure", ["before_value", "block_name", "block_index", "column", "row", "drawing"])
def test_cell_preconditions_are_checked_before_any_setter(monkeypatch, failure):
    f = fixture(monkeypatch)
    changes = {"before_value": {"expected_before": "stale"}, "block_name": {"block_name": "Other"},
               "block_index": {"block_index": 1}, "column": {"column": 2}, "row": {"row": 2},
               "drawing": {"drawing_uuid": uid(99)}}[failure]
    with pytest.raises((ValueError, RuntimeError)):
        m.update_existing_properties("test.rnp", request(), cell_checks=cell_request(**changes))
    assert not f.state["writes"] and f.state["saves"] == 0


def test_property_setter_return_does_not_imply_a_filled_stamp(monkeypatch):
    f = fixture(monkeypatch)
    f.state["bound"] = False
    with pytest.raises(RuntimeError, match="resolved title-block"):
        m.update_existing_properties("test.rnp", request(), cell_checks=cell_request())
    assert f.state["writes"] == ["Example Author"] and f.state["saves"] == 0


@pytest.mark.parametrize("corruption", ["value", "definition", "expression", "annotation_uuid",
                                      "annotation_type", "resource_name", "project_info", "stamp", "stamp_shape",
                                      "sheet_name", "sheet_orientation"])
def test_reopened_corruption_cannot_report_success(monkeypatch, corruption):
    f = fixture(monkeypatch)

    def corrupt():
        if corruption == "value": f.drawing_props.prop.value = "lost"
        elif corruption == "definition": f.definition["name"] = "Changed"
        elif corruption == "expression": f.expressions[TYPES["Drawing"]] = "{Name}"
        elif corruption == "annotation_uuid": f.annotation.UniqueIdS = uid(99)
        elif corruption == "annotation_type": f.annotation.ObjectTypeS = uid(99)
        elif corruption == "resource_name": f.layout.Name = "Changed"
        elif corruption == "project_info": f.project.ProjectInfo.Name = "Changed"
        elif corruption == "stamp": f.rows[1][0] = "lost"
        elif corruption == "stamp_shape": f.block.RowCount = 3
        elif corruption == "sheet_name": f.drawing.Name = "Changed"
        else: f.drawing.metadata["PageOrientation"] = 1

    f.state["on_reopen"] = corrupt
    with pytest.raises((ValueError, RuntimeError)):
        m.update_existing_properties("test.rnp", request(), cell_checks=cell_request())
    assert f.state["saves"] == 1


def test_native_numeric_id_changes_do_not_break_persistent_targets(monkeypatch):
    f = fixture(monkeypatch)
    f.state["on_save"] = lambda: setattr(f.drawing, "Id", 9876)
    result = m.update_existing_properties("test.rnp", request(), cell_checks=cell_request())
    assert result["status"] == "saved_reopened_verified"
    assert result["properties"][0]["uuid"] == DRAWING


def test_sheet_resource_id_changes_are_compared_by_persistent_uuid(monkeypatch):
    f = fixture(monkeypatch)

    def renumber():
        f.layout.Id = 9876
        f.topic.Id = 9877
        f.project.PageFormatStyles.values[0].Id = 9878
        f.drawing.metadata.update(LayoutStyleId=9876, TopicId=9877, PageFormatId=9878)

    f.state["on_save"] = renumber
    result = m.update_existing_properties("test.rnp", request())
    assert result["status"] == "saved_reopened_verified"


def test_noop_native_setter_is_rejected_before_save(monkeypatch):
    f = fixture(monkeypatch)
    f.drawing_props.prop.SetStringValue = lambda value: None
    with pytest.raises(RuntimeError, match="did not persist"):
        m.update_existing_properties("test.rnp", request())
    assert f.state["saves"] == 0


def test_project_type_assignment_is_not_inferred_from_drawing_assignment(monkeypatch):
    f = fixture(monkeypatch)
    f.assignments[TYPES["Project"]] = False
    with pytest.raises(ValueError, match="assignment is absent"):
        m.update_existing_properties("test.rnp", request("Project"))
    assert not f.state["writes"]


def test_wrong_project_uuid_cannot_target_current_project(monkeypatch):
    f = fixture(monkeypatch)
    with pytest.raises(ValueError, match="Project UUID is absent"):
        m.update_existing_properties("test.rnp", request("Project", uuid=uid(99)))
    assert not f.state["writes"]


def test_native_stamp_getter_failure_is_not_replaced_by_expected_value(monkeypatch):
    f = fixture(monkeypatch)

    def fail(column, row):
        raise RuntimeError("Native cell getter failed")

    f.block.GetCellValue = fail
    with pytest.raises(RuntimeError, match="cell getter failed"):
        m.update_existing_properties("test.rnp", request(), cell_checks=cell_request())
    assert not f.state["writes"] and f.state["saves"] == 0
