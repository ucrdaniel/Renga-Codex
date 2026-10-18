"""Edit existing registered String properties of Project, Drawing and Topic.

This helper never registers properties, changes type assignments/expressions,
or writes title-block cells. Optional explicit resolved-cell assertions verify
observed title-block values, not the source expression/binding or visual layout.
Only a fresh native save/close/reopen test establishes support for a scenario.
"""
from __future__ import annotations

import copy
from pathlib import Path
import uuid

from .audit import event, save_plan
from .model import parameters
from .project_info import read_project_info
from .session import Session
from .sheet_metadata import REFERENCE_COLLECTIONS, SHEET_PARAMETERS, sheet_identity_snapshot


TARGET_COLLECTIONS = {"Drawing": "Drawings2", "Topic": "Topics"}
STRING_PROPERTY_TYPE = 2


def _uuid(value):
    if not isinstance(value, str):
        raise ValueError("A persistent native UUID string is required")
    try:
        return str(uuid.UUID(value.strip("{}")))
    except (ValueError, AttributeError) as error:
        raise ValueError("A persistent native UUID string is required") from error


def _text(value, label, *, nonempty=False):
    if not isinstance(value, str) or "\0" in value or (nonempty and not value.strip()):
        raise ValueError(label + " requires text without NUL")


def _count(value, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise RuntimeError("Unexpected native collection/table size")
    return value


def validate_existing_property_changes(changes, cell_checks=None):
    """Validate and detach all input before a plan or native session is made."""
    if not isinstance(changes, list) or not 1 <= len(changes) <= 1000:
        raise ValueError("changes requires 1..1000 explicit existing-property requests")
    changes = copy.deepcopy(changes)
    seen = set()
    for change in changes:
        if not isinstance(change, dict) or set(change) != {
                "kind", "uuid", "property_guid", "property_name", "value"}:
            raise ValueError("Each change requires kind, uuid, property_guid, property_name, value")
        if not isinstance(change["kind"], str) or change["kind"] not in {"Project", *TARGET_COLLECTIONS}:
            raise ValueError("Only existing Project, Drawing or Topic properties are supported")
        change["uuid"] = _uuid(change["uuid"])
        change["property_guid"] = _uuid(change["property_guid"])
        _text(change["property_name"], "property_name", nonempty=True)
        _text(change["value"], "value")
        key = change["kind"], change["uuid"], change["property_guid"]
        if key in seen:
            raise ValueError("Duplicate target/property request")
        seen.add(key)
    if cell_checks is None:
        cell_checks = []
    if not isinstance(cell_checks, list) or len(cell_checks) > 1000:
        raise ValueError("cell_checks must be a list of at most 1000 explicit assertions")
    cell_checks = copy.deepcopy(cell_checks)
    seen = set()
    for check in cell_checks:
        if not isinstance(check, dict) or set(check) != {
                "drawing_uuid", "block_index", "block_name", "column", "row",
                "expected_before", "expected_value"}:
            raise ValueError("A cell check requires an explicit drawing, block, column/row and before/after text")
        check["drawing_uuid"] = _uuid(check["drawing_uuid"])
        _text(check["block_name"], "block_name", nonempty=True)
        _text(check["expected_before"], "expected_before")
        _text(check["expected_value"], "expected_value")
        for field, limit in (("block_index", 99), ("column", 9999), ("row", 9999)):
            if type(check[field]) is not int or not 0 <= check[field] <= limit:
                raise ValueError(field + " requires a nonnegative bounded integer")
        key = check["drawing_uuid"], check["block_index"], check["column"], check["row"]
        if key in seen:
            raise ValueError("Duplicate title-block cell assertion")
        seen.add(key)
    return changes, cell_checks


def _resolve(session, kind, identifier):
    expected_type = _uuid(session.sdk.types[kind])
    if kind == "Project":
        entity = session.project.ProjectInfo
        if not entity or _uuid(entity.UniqueIdS) != identifier:
            raise ValueError("Inspected Project UUID is absent from this project")
        return entity, entity.GetProperties(), expected_type
    entity = getattr(session.project, TARGET_COLLECTIONS[kind]).GetByUniqueIdS(identifier)
    if not entity or _uuid(entity.UniqueIdS) != identifier:
        raise ValueError("Inspected " + kind + " UUID is absent from this project")
    if _uuid(entity.TypeIdS) != expected_type:
        raise ValueError("Native target type does not match requested kind")
    return entity, entity.QueryInterface(session.r.IPropertyContainer), expected_type


def _property_value(prop):
    present = bool(prop.HasValue())
    return {"has_value": present, "value": prop.GetStringValue() if present else None}


def _preflight(session, changes):
    """Require existing definitions/assignments/instance values before any setter."""
    manager = session.project.PropertyManager
    pending, observed = [], []
    for change in changes:
        identifier = change["property_guid"]
        if not manager.IsPropertyRegisteredS(identifier):
            raise ValueError("Existing native property definition is absent")
        if (manager.GetPropertyNameS(identifier) != change["property_name"]
                or manager.GetPropertyTypeS(identifier) != STRING_PROPERTY_TYPE):
            raise ValueError("Existing native property name or String type mismatch")
        _, container, type_guid = _resolve(session, change["kind"], change["uuid"])
        if not manager.IsPropertyAssignedToTypeS(identifier, type_guid):
            raise ValueError("Existing native property type assignment is absent")
        if manager.GetExpressionS(identifier, type_guid) not in (None, ""):
            raise ValueError("Expression-backed native properties cannot be edited")
        if not container or not container.ContainsS(identifier):
            raise ValueError("Target does not contain the existing native property")
        prop = container.GetS(identifier)
        if (not prop or _uuid(prop.IdS) != identifier or prop.Name != change["property_name"]
                or prop.Type != STRING_PROPERTY_TYPE):
            raise ValueError("Native instance property identity, name or String type mismatch")
        observed.append({**change, "observed": _property_value(prop)})
        pending.append(prop)
    return pending, observed


def _identity_state(session):
    """Preserve model/sheet contents, project, resources and definition identities."""
    resources = {}
    for name in ("Topics", "LayoutStyles", "PageFormatStyles"):
        collection = getattr(session.project, name)
        identities = {}
        for index in range(_count(collection.Count, 10000)):
            entity = collection.GetByIndex(index)
            uid = _uuid(entity.UniqueIdS)
            if uid in identities:
                raise RuntimeError("Duplicate native resource identity")
            identities[uid] = {"type_guid": _uuid(entity.TypeIdS), "name": entity.Name}
        resources[name] = identities
    manager = session.project.PropertyManager
    definitions = {}
    for index in range(_count(manager.PropertyCount, 10000)):
        native_guid = manager.GetPropertyIdS(index)
        identifier = _uuid(native_guid)
        if identifier in definitions:
            raise RuntimeError("Duplicate registered property identity")
        definitions[identifier] = {"name": manager.GetPropertyNameS(native_guid),
                                   "type": manager.GetPropertyTypeS(native_guid)}
    sheets = {}
    drawings = session.project.Drawings2
    for index in range(_count(drawings.Count, 10000)):
        drawing = drawings.GetByIndex(index)
        uid = _uuid(drawing.UniqueIdS)
        if uid in sheets:
            raise RuntimeError("Duplicate native drawing identity")
        native = parameters(session, drawing)
        values = {}
        for name in sorted(SHEET_PARAMETERS):
            if name not in native:
                continue
            param = native[name]
            value = param["value"]
            if name in REFERENCE_COLLECTIONS and param["has_value"] and value not in (0, -1):
                entity = getattr(session.project, REFERENCE_COLLECTIONS[name]).GetById(value)
                if not entity:
                    raise RuntimeError("Sheet references an absent native resource")
                value = _uuid(entity.UniqueIdS)
            values[name] = {"has_value": param["has_value"], "value": value}
        sheets[uid] = {"name": drawing.Name, "parameters": values}
    return {"objects": sheet_identity_snapshot(session), "project_info": read_project_info(session),
            "sheet_metadata_by_resource_uuid": sheets,
            "resources": resources, "property_definitions": definitions}


def _cell_values(session, checks, *, before=False, expected_shapes=None):
    result = []
    for index, check in enumerate(checks):
        drawing = session.project.Drawings2.GetByUniqueIdS(check["drawing_uuid"])
        if (not drawing or _uuid(drawing.UniqueIdS) != check["drawing_uuid"]
                or _uuid(drawing.TypeIdS) != _uuid(session.sdk.types["Drawing"])):
            raise ValueError("Title-block drawing UUID/type is absent or mismatched")
        native = drawing.QueryInterface(session.r.IDrawing)
        if check["block_index"] >= _count(native.TitleBlockInstanceCount, 100):
            raise ValueError("Native title-block instance is absent")
        block = native.GetTitleBlockInstance(check["block_index"])
        columns, rows = _count(block.ColumnCount, 10000), _count(block.RowCount, 10000)
        if columns * rows > 100000 or check["column"] >= columns or check["row"] >= rows:
            raise ValueError("Native title-block cell is outside inspected bounds")
        shape = {"name": block.Name, "columns": columns, "rows": rows}
        if block.Name != check["block_name"] or (expected_shapes is not None
                and shape != expected_shapes[index]["shape"]):
            raise RuntimeError("Native title-block name or dimensions changed")
        value = block.GetCellValue(check["column"], check["row"])
        if value != check["expected_before" if before else "expected_value"]:
            raise RuntimeError("Native resolved title-block cell value mismatch")
        result.append({**check, "shape": shape, "actual_value": value})
    return result


def _verify_values(observed):
    for row in observed:
        if not row["observed"]["has_value"] or row["observed"]["value"] != row["value"]:
            raise RuntimeError("Native existing-property value did not persist")


def update_existing_properties(project, changes, *, cell_checks=None):
    """Back up and edit existing properties, close/reopen, and read native results.

    No authorization bypass is exposed; Session enforces write-root, fresh STA
    ownership, file hash and verified disk backup. Resource metadata undo is not
    guaranteed by the SDK. All targets and optional stamp-cell preconditions are
    checked before the first setter. A failed cell/value check before Save leaves
    the disk project unchanged; a failed saved-state check reports failure and
    leaves the verified backup available, never silently claiming stamp success.
    """
    changes, cell_checks = validate_existing_property_changes(changes, cell_checks)
    if Path(project).suffix.lower() != ".rnp":
        raise ValueError("Existing resource properties require a native .rnp project")
    plan = save_plan({"action": "update_existing_resource_string_properties",
                      "project": str(project), "changes": changes, "cell_checks": cell_checks})
    with Session(project, write=True) as session:
        before_state = _identity_state(session)
        pending, before_values = _preflight(session, changes)
        before_cells = _cell_values(session, cell_checks, before=True)
        with session.operation():
            for prop, change in zip(pending, changes):
                event("existing_property_setter_requested", status="provisional", path=str(project),
                      plan=plan, **change)
                prop.SetStringValue(change["value"])
        _, current = _preflight(session, changes)
        _verify_values(current)
        _cell_values(session, cell_checks, expected_shapes=before_cells)
        if _identity_state(session) != before_state:
            raise RuntimeError("Native identities, definitions or unrelated metadata changed")
        session.save()
    with Session(project) as reopened:
        _, saved = _preflight(reopened, changes)
        _verify_values(saved)
        cells = _cell_values(reopened, cell_checks, expected_shapes=before_cells)
        if _identity_state(reopened) != before_state:
            raise RuntimeError("Saved native identities, definitions or unrelated metadata changed")
        result = {"status": "saved_reopened_verified", "project": str(project), "plan": plan,
                  "before": before_values, "properties": saved, "title_block_checks": cells,
                  "identities_and_definitions_preserved": True,
                  "identity_verification_scope": ["building/drawing/content UUID/types",
                      "project info fields/UUID", "sheet metadata with resource UUID references",
                      "Topics/LayoutStyles/PageFormatStyles UUID/types/names",
                      "registered property GUID/name/type", "requested assignment/expression/type/value"],
                  "title_block_values_verified": bool(cell_checks),
                  "title_block_source_binding_proven": False, "title_block_cell_authoring": False,
                  "visual_layout_verified": False, "computer_use_calls": 0,
                  "sha256": reopened.initial_sha,
                  "limitations": ["Existing registered String properties only; no registration or assignment changes",
                                  "Resolved-cell equality is not source-binding or visual-layout proof",
                                  "Resource metadata undo is not guaranteed; recover from verified disk backup"]}
        event("existing_properties_reopened_verified", path=str(project), plan=plan,
              target_count=len(changes), cell_check_count=len(cells), computer_use_calls=0)
        return result
