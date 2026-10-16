"""Native existing-sheet metadata and title-block readback, without UI.

This module does not author title-block cells, schedules, tables or sections.
References are inspected before mutation and verified by persistent resource
identity after reopening, rather than assuming numeric IDs survive SaveAs.
"""
from __future__ import annotations

import copy
import uuid

from .audit import event, save_plan
from .model import parameters, set_parameter
from .session import Session


REFERENCE_COLLECTIONS = {
    "PageFormatId": "PageFormatStyles",
    "LayoutStyleId": "LayoutStyles",
    "TopicId": "Topics",
}
SHEET_PARAMETERS = {"EntityName", "PageOrientation", *REFERENCE_COLLECTIONS}


def _uuid(value):
    if not isinstance(value, str):
        raise ValueError("A persistent native UUID string is required")
    try:
        return str(uuid.UUID(value.strip("{}")))
    except (ValueError, AttributeError) as error:
        raise ValueError("A persistent native UUID string is required") from error


def validate_sheet_changes(changes):
    """Validate all changes before opening a native write session."""
    if not isinstance(changes, list) or not 1 <= len(changes) <= 100:
        raise ValueError("changes must contain 1..100 explicit sheet requests")
    result = copy.deepcopy(changes)
    seen = set()
    for change in result:
        if not isinstance(change, dict) or set(change) != {"drawing_uuid", "parameters"}:
            raise ValueError("Each change requires only drawing_uuid and parameters")
        change["drawing_uuid"] = _uuid(change["drawing_uuid"])
        if change["drawing_uuid"] in seen:
            raise ValueError("Duplicate drawing UUID in changes")
        seen.add(change["drawing_uuid"])
        values = change["parameters"]
        if not isinstance(values, dict) or not values or set(values) - SHEET_PARAMETERS:
            raise ValueError("Only supported nonempty native sheet parameters are accepted")
        for key, value in values.items():
            if key == "EntityName":
                if not isinstance(value, str) or not value.strip() or "\0" in value:
                    raise ValueError("EntityName requires nonempty text without NUL")
            elif key == "PageOrientation":
                if type(value) is not int or value not in (1, 2):
                    raise ValueError("PageOrientation must be 1 portrait or 2 landscape")
            elif type(value) is not int or not 0 < value < 2**31:
                raise ValueError(key + " requires an inspected positive native int32 ID")
    return result


def read_title_blocks(s, drawing):
    """Read every native cell in documented column,row argument order.

    An empty string remains an empty string. No value is synthesized from the
    drawing name or project metadata. Getter failure propagates to the caller.
    """
    native = drawing.QueryInterface(s.r.IDrawing)
    count = native.TitleBlockInstanceCount
    if type(count) is not int or not 0 <= count <= 100:
        raise RuntimeError("Unexpected native title-block instance count")
    result = []
    for index in range(count):
        block = native.GetTitleBlockInstance(index)
        columns, rows = block.ColumnCount, block.RowCount
        if (type(columns) is not int or type(rows) is not int
                or min(columns, rows) < 0 or columns * rows > 100000):
            raise RuntimeError("Unexpected native title-block table dimensions")
        result.append({"index": index, "name": block.Name,
                       "column_count": columns, "row_count": rows,
                       "rows": [[block.GetCellValue(column, row)
                                 for column in range(columns)] for row in range(rows)]})
    return result


def _identities(collection):
    result = {}
    for index in range(collection.Count):
        entity = collection.GetByIndex(index)
        identifier = _uuid(entity.UniqueIdS)
        if identifier in result:
            raise RuntimeError("Duplicate native persistent identity")
        result[identifier] = entity.ObjectTypeS.upper()
    return result


def sheet_identity_snapshot(s):
    """Object identities/types only; not geometry, cell or binding verification."""
    drawings = {}
    collection = s.project.Drawings2
    for index in range(collection.Count):
        entity = collection.GetByIndex(index)
        identifier = _uuid(entity.UniqueIdS)
        if identifier in drawings:
            raise RuntimeError("Duplicate native drawing persistent identity")
        drawings[identifier] = {
            "type_guid": entity.TypeIdS.upper(),
            "contents": _identities(entity.QueryInterface(s.r.IModel).GetObjects()),
        }
    return {"building": _identities(s.model.GetObjects()), "drawings": drawings}


def snapshot_sheet_metadata(s):
    """Read actual metadata, resource identities and native title-block cells."""
    result = []
    collection = s.project.Drawings2
    for index in range(collection.Count):
        entity = collection.GetByIndex(index)
        values = parameters(s, entity)
        row = {"id": entity.Id, "uuid": _uuid(entity.UniqueIdS), "name": entity.Name,
               "parameters": {key: values[key] for key in sorted(SHEET_PARAMETERS) if key in values},
               "references": {}}
        try:
            row["title_blocks"] = read_title_blocks(s, entity)
            row["title_block_readback"] = {"status": "read"}
        except Exception as error:
            # Native Count throws a server error on some sheets without an
            # assigned layout. Keep that failure instead of reporting zero
            # stamps or discarding otherwise readable sheet metadata.
            row["title_blocks"] = None
            row["title_block_readback"] = {
                "status": "failed", "error": str(error),
                "hresult": getattr(error, "hresult", None)}
        for key, collection_name in REFERENCE_COLLECTIONS.items():
            if key not in values or not values[key]["has_value"]:
                continue
            native_id = values[key]["value"]
            if native_id in (0, -1):
                row["references"][key] = None
                continue
            native_collection = getattr(s.project, collection_name)
            if not native_collection.Contains(native_id):
                raise RuntimeError("Sheet references an absent native resource: " + key)
            resource = native_collection.GetById(native_id)
            row["references"][key] = {
                "id": resource.Id, "uuid": _uuid(resource.UniqueIdS), "name": resource.Name}
        result.append(row)
    return result


def inspect_sheet_metadata(project):
    with Session(project) as s:
        drawings = snapshot_sheet_metadata(s)
        return {"drawings": drawings, "computer_use_calls": 0,
                "scope": "native_sheet_metadata_and_title_block_getters",
                "title_block_readback_complete": all(
                    row["title_block_readback"]["status"] == "read" for row in drawings),
                "title_block_cell_authoring": False, "visual_layout_verified": False}


def update_sheet_metadata(project, changes):
    """Back up, update existing native sheets, save/reopen and read saved data.

    Uses the standard Session write-root restriction, ownership and backup
    controls. There is no authorization bypass. Neither model objects nor sheet
    annotation identities may change. Title-block values are returned as native
    observations, without claiming a literal-cell setter or source binding.
    """
    changes = validate_sheet_changes(changes)
    plan = save_plan({"action": "update_native_sheet_metadata", "project": str(project),
                      "changes": changes})
    expected = []
    with Session(project, write=True) as s:
        before = sheet_identity_snapshot(s)
        pending = []
        for change in changes:
            entity = s.project.Drawings2.GetByUniqueIdS(change["drawing_uuid"])
            if not entity:
                raise ValueError("Inspected drawing UUID is absent from this project")
            actual = parameters(s, entity)
            references = {}
            for key, value in change["parameters"].items():
                if key not in actual:
                    raise ValueError("Native sheet parameter is absent: " + key)
                if actual[key]["readonly"]:
                    raise ValueError("Read-only native sheet parameter: " + key)
                if key in REFERENCE_COLLECTIONS:
                    collection = getattr(s.project, REFERENCE_COLLECTIONS[key])
                    if not collection.Contains(value):
                        raise ValueError("Inspected native sheet resource is absent: " + key)
                    references[key] = _uuid(collection.GetById(value).UniqueIdS)
            pending.append((entity, change))
            expected.append({**change, "resource_uuids": references})
        # Complete all preflight checks before starting the first mutation.
        with s.operation():
            for entity, change in pending:
                for key, value in change["parameters"].items():
                    set_parameter(s, entity, key, value)
        s.save()
    with Session(project) as reopened:
        if sheet_identity_snapshot(reopened) != before:
            raise RuntimeError("Native building/drawing/content identities or types changed")
        saved = snapshot_sheet_metadata(reopened)
        by_uuid = {row["uuid"]: row for row in saved}
        for change in expected:
            row = by_uuid[change["drawing_uuid"]]
            for key, value in change["parameters"].items():
                if key in REFERENCE_COLLECTIONS:
                    reference = row["references"].get(key)
                    if not reference or reference["uuid"] != change["resource_uuids"][key]:
                        raise RuntimeError("Saved native sheet resource identity mismatch: " + key)
                elif row["parameters"].get(key, {}).get("value") != value:
                    raise RuntimeError("Saved native sheet parameter mismatch: " + key)
        event("native_sheet_metadata_reopened_verified", path=str(project), plan=plan,
              drawing_uuids=[row["drawing_uuid"] for row in changes], computer_use_calls=0)
        return {"status": "saved_reopened_verified", "plan": plan, "drawings": saved,
                "requested_parameters_verified": changes,
                "identity_type_preservation_verified": True,
                "title_block_readback_complete": all(
                    row["title_block_readback"]["status"] == "read" for row in saved),
                "computer_use_calls": 0, "visual_layout_verified": False,
                "scope": "existing_sheet_metadata_and_native_title_block_readback",
                "limitations": ["No title-block cell setter or source-binding proof",
                                "No schedule/table definition or section/elevation authoring",
                                "Object identities do not establish geometry or visual layout correctness"]}
