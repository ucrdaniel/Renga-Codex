"""Native IProjectInfo access; setters are verified after save/close/reopen.

SDK API 2.50 documents IProject.ProjectInfo as a getter, and IProjectInfo
Code/Name/Stage/Description as BSTR get/set properties. UniqueIdS is getter-only
and identifies the project (also the IFC project), not an editable parameter.

An operation is mandatory for entity modification. The normal undo transaction
is used, but SDK documentation limits undo to model objects: project metadata
undo must not be promised. Verified disk backup remains the recovery mechanism.
"""

from __future__ import annotations

from pathlib import Path
import uuid

from .audit import event, save_plan
from .safety import checked_path
from .session import Session

PROJECT_INFO_FIELDS = ("Code", "Name", "Stage", "Description")


def validate_project_info_values(values: dict) -> dict[str, str]:
    """Whitelist only documented writable BSTR properties before any COM work."""
    if not isinstance(values, dict) or not values:
        raise ValueError("Project info values must be a nonempty object")
    unknown = set(values) - set(PROJECT_INFO_FIELDS)
    if unknown:
        raise ValueError("Unsupported/immutable project info field: " + ", ".join(sorted(map(str, unknown))))
    for name, value in values.items():
        if not isinstance(value, str):
            raise ValueError(f"Project info {name} requires a string")
        if "\x00" in value:
            raise ValueError(f"Project info {name} must not contain NUL characters")
    # A copy prevents caller mutation from changing the saved operation plan.
    return dict(values)


def _canonical_uuid(value: str) -> str:
    if not isinstance(value, str):
        raise RuntimeError("Native IProjectInfo.UniqueIdS is not a string")
    try:
        return str(uuid.UUID(value.strip("{}")))
    except ValueError as exc:
        raise RuntimeError("Native IProjectInfo.UniqueIdS is not a valid UUID") from exc


def read_project_info(s) -> dict:
    info = s.project.ProjectInfo
    if not info:
        raise RuntimeError("Native IProject.ProjectInfo is absent")
    result = {field: getattr(info, field) for field in PROJECT_INFO_FIELDS}
    for field, value in result.items():
        # A null BSTR is reported honestly, not coerced into an empty string.
        if value is not None and not isinstance(value, str):
            raise RuntimeError(f"Native IProjectInfo.{field} is not a BSTR value")
    result["UniqueIdS"] = info.UniqueIdS
    _canonical_uuid(result["UniqueIdS"])
    return result


def _model_identities(s) -> set[str]:
    objects = s.model.GetObjects()
    return {objects.GetByIndex(index).UniqueIdS.strip("{}").lower() for index in range(objects.Count)}


def _verify_metadata(actual: dict, expected: dict):
    if _canonical_uuid(actual["UniqueIdS"]) != _canonical_uuid(expected["UniqueIdS"]):
        raise RuntimeError("Project info persistent UniqueIdS changed")
    for field in PROJECT_INFO_FIELDS:
        if actual[field] != expected[field]:
            raise RuntimeError("Native project info mismatch: " + field)


def edit_project_info(path: str | Path, values: dict) -> dict:
    requested = validate_project_info_values(values)
    project = checked_path(path, write=True)
    if project.suffix.lower() != ".rnp":
        raise ValueError("Project info editing requires a native .rnp project")
    plan = save_plan({"action": "edit_project_info", "project": str(project), "values": requested})
    with Session(project, write=True) as s:
        # Session verifies/preserves the source backup before opening for writes.
        before = read_project_info(s)
        expected = {**before, **requested}
        model_uuids = _model_identities(s)
        with s.operation():
            native = s.project.ProjectInfo
            for field, value in requested.items():
                setattr(native, field, value)
                event("project_info_setter_requested", status="provisional", path=str(project),
                      resource_uuid=before["UniqueIdS"], field=field, value=value, plan=plan)
        _verify_metadata(read_project_info(s), expected)
        s.save()
    with Session(project) as reopened:
        actual = read_project_info(reopened)
        _verify_metadata(actual, expected)
        if _model_identities(reopened) != model_uuids:
            raise RuntimeError("Model identities changed during project info edit")
        result = {
            "status": "saved_reopened_verified", "project": str(project), "plan": plan,
            "before": before, "project_info": actual,
            "verified_fields": list(PROJECT_INFO_FIELDS),
            "resource_uuid_preserved": True, "model_object_count": len(model_uuids),
            "model_identities_preserved": True, "sha256": reopened.initial_sha,
            "undo_note": "SDK undo is limited to model objects; project metadata undo is not guaranteed. Use the verified backup for recovery.",
            "computer_use_calls": 0,
        }
        event("project_info_reopened_verified", path=str(project), resource_uuid=actual["UniqueIdS"],
              fields=list(PROJECT_INFO_FIELDS), plan=plan, sha256=reopened.initial_sha,
              model_objects=len(model_uuids), computer_use_calls=0)
        return result
