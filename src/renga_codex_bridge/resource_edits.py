"""Existing-only WindowStyle common-parameter edits with saved-state checks.

This edits exposed entity parameters, not the private pane/mullion tree. The
SDK explicitly disables undo history for project resources; project-operation
rollback, verified disk backup and discard of unsaved failures protect edits.
"""
from __future__ import annotations

import copy
import math
import re
import unicodedata

from .audit import event, save_plan
from .catalogs import COLLECTIONS
from .model import parameters, set_parameter
from .resources import _resource_operation
from .safety import checked_path, fingerprint
from .session import Session
from .sheet_metadata import _uuid, sheet_identity_snapshot


LENGTH_PARAMETERS = frozenset({"FrameThickness", "FrameDepth", "VerticalMullionThickness",
                               "HorizontalMullionThickness", "WindowLiningThickness", "WindowLiningDepth"})
RESOURCE_COLLECTIONS = tuple(dict.fromkeys((*COLLECTIONS, "Tables", "Profiles", "DisplayStyles", "LegendStyles")))


def _name(value, label):
    if (not isinstance(value, str) or not value.strip()
            or any(unicodedata.category(char) in {"Cc", "Cs"} for char in value)):
        raise ValueError(label + " requires nonempty text without controls/surrogates")
    return value


def validate_window_style_changes(changes, expected_project_sha256=None):
    if expected_project_sha256 is not None and (not isinstance(expected_project_sha256, str)
            or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_project_sha256)):
        raise ValueError("expected_project_sha256 must be a complete SHA256 digest")
    if not isinstance(changes, list) or not 1 <= len(changes) <= 100:
        raise ValueError("changes must contain 1..100 existing WindowStyle requests")
    result = copy.deepcopy(changes)
    seen = set()
    for change in result:
        if (not isinstance(change, dict) or set(change) - {"resource_uuid", "expected_name", "parameters", "material_uuid"}
                or not {"resource_uuid", "expected_name"} <= set(change)):
            raise ValueError("Only resource_uuid, expected_name, parameters and material_uuid are accepted")
        change["resource_uuid"] = _uuid(change["resource_uuid"])
        if change["resource_uuid"] in seen:
            raise ValueError("Duplicate normalized WindowStyle UUID")
        seen.add(change["resource_uuid"])
        _name(change["expected_name"], "expected_name")
        values = change.get("parameters", {})
        if not isinstance(values, dict) or set(values) - (LENGTH_PARAMETERS | {"EntityName"}):
            raise ValueError("Only six common WindowStyle lengths and EntityName are supported; use material_uuid for MaterialId")
        change["parameters"] = values
        if not values and "material_uuid" not in change:
            raise ValueError("At least one common parameter or material_uuid is required")
        for key, value in list(values.items()):
            if key == "EntityName":
                _name(value, "EntityName")
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(key + " requires a finite positive millimeter number")
            try: value = float(value)
            except OverflowError as error: raise ValueError(key + " must be finite") from error
            if not math.isfinite(value) or value <= 0:
                raise ValueError(key + " requires a finite positive millimeter number")
            values[key] = value
        if "material_uuid" in change:
            change["material_uuid"] = _uuid(change["material_uuid"])
    return result


def resource_identity_snapshot(session):
    """Read exposed resource identity/type/name collections, retaining gaps."""
    result = {}
    for name in RESOURCE_COLLECTIONS:
        try: collection = getattr(session.project, name)
        except AttributeError:
            result[name] = {"status": "unavailable"}
            continue
        if not collection:
            result[name] = {"status": "unavailable"}
            continue
        entries = {}
        for index in range(collection.Count):
            entity = collection.GetByIndex(index)
            uid = _uuid(entity.UniqueIdS)
            if uid in entries: raise RuntimeError("Duplicate native resource UUID")
            entries[uid] = {"type_guid": _uuid(entity.TypeIdS), "name": entity.Name}
        result[name] = {"status": "read", "entries": entries}
    return result


def _parameter_state(session, entity):
    values = parameters(session, entity)
    return {key: {"value": item["value"], "has_value": bool(item["has_value"]), "type": item["type"]}
            for key, item in values.items()}


def _preflight(session, changes):
    collection = session.project.WindowStyles
    names = {}
    for index in range(collection.Count):
        entity = collection.GetByIndex(index)
        names.setdefault(entity.Name.casefold(), set()).add(_uuid(entity.UniqueIdS))
    pending = []
    wanted_names = set()
    for change in changes:
        uid = change["resource_uuid"]
        entity = collection.GetByUniqueIdS(uid)
        if not entity or _uuid(entity.UniqueIdS) != uid:
            raise ValueError("Inspected WindowStyle UUID is absent from this project")
        if _uuid(entity.TypeIdS) != _uuid(session.sdk.types["WindowStyle"]):
            raise ValueError("Selected resource is not a native WindowStyle")
        if entity.Name != change["expected_name"]:
            raise ValueError("Native WindowStyle name differs from the inspected expected_name")
        expected = dict(change["parameters"])
        if "material_uuid" in change:
            material = session.project.Materials.GetByUniqueIdS(change["material_uuid"])
            if not material or _uuid(material.UniqueIdS) != change["material_uuid"]:
                raise ValueError("Inspected ordinary Material UUID is absent from this project")
            if _uuid(material.TypeIdS) != _uuid(session.sdk.types["Material"]):
                raise ValueError("Selected material UUID is not an ordinary Material")
            expected["MaterialId"] = material.Id
        values = parameters(session, entity)
        for key in expected:
            if key not in values:
                raise ValueError("Native WindowStyle parameter is absent: " + key)
            if values[key]["readonly"]:
                raise ValueError("Read-only native WindowStyle parameter: " + key)
            required_type = 4 if key == "EntityName" else 2 if key == "MaterialId" else 3
            if values[key]["type"] != required_type:
                raise ValueError("Unexpected native WindowStyle parameter type: " + key)
        new_name = expected.get("EntityName", entity.Name)
        if names.get(new_name.casefold(), set()) - {uid} or new_name.casefold() in wanted_names:
            raise ValueError("Requested WindowStyle name conflicts with an existing/planned resource")
        wanted_names.add(new_name.casefold())
        pending.append((entity, change, expected, _parameter_state(session, entity)))
    return pending


def _readback(session, change, expected, original, *, compare_unrequested=True):
    entity = session.project.WindowStyles.GetByUniqueIdS(change["resource_uuid"])
    if not entity or _uuid(entity.TypeIdS) != _uuid(session.sdk.types["WindowStyle"]):
        raise RuntimeError("Saved WindowStyle identity/type is absent or changed")
    if _uuid(entity.UniqueIdS) != change["resource_uuid"] or entity.Name != expected.get("EntityName", change["expected_name"]):
        raise RuntimeError("Saved WindowStyle UUID/name mismatch")
    actual = _parameter_state(session, entity)
    observed = {}
    for key, wanted in expected.items():
        if key not in actual or not actual[key]["has_value"]:
            raise RuntimeError("Saved WindowStyle parameter absent/unset: " + key)
        value = actual[key]["value"]
        if key == "MaterialId":
            if type(value) is not int or not session.project.Materials.Contains(value):
                raise RuntimeError("Saved WindowStyle references an absent ordinary Material")
            material = session.project.Materials.GetById(value)
            if _uuid(material.UniqueIdS) != change["material_uuid"]:
                raise RuntimeError("Saved WindowStyle Material UUID mismatch")
            observed[key] = {"id": value, "uuid": _uuid(material.UniqueIdS), "name": material.Name}
        else:
            matches = value == wanted if key == "EntityName" else (
                not isinstance(value, bool) and isinstance(value, (int, float))
                and math.isclose(value, wanted, rel_tol=0, abs_tol=1e-6))
            if not matches: raise RuntimeError("Saved WindowStyle parameter mismatch: " + key)
            observed[key] = value
    if compare_unrequested:
        before = {key: value for key, value in original.items() if key not in expected}
        after = {key: value for key, value in actual.items() if key not in expected}
        if before != after:
            raise RuntimeError("Unrequested exposed WindowStyle parameters changed")
    return {"resource_uuid": change["resource_uuid"], "id": entity.Id, "name": entity.Name,
            "parameters_verified": observed, "unrequested_exposed_parameters_preserved": True,
            "panel_tree_authoring_verified": False, "material_per_node_verified": False}


def update_window_styles(project, changes, expected_project_sha256=None):
    """Edit existing styles only, back up, save, reopen and verify native data.

    material_uuid is resolved to the current native MaterialId. Native undo
    history is unsupported for project resources by the official SDK; the
    result explicitly reports that limit. No new style or material is created.
    """
    changes = validate_window_style_changes(changes, expected_project_sha256)
    target = checked_path(project, write=True)
    if target.suffix.lower() != ".rnp": raise ValueError("Existing native .rnp project required")
    if expected_project_sha256 is not None and fingerprint(target) != expected_project_sha256.lower():
        raise RuntimeError("Project SHA256 differs from the pinned inspected file")
    plan = save_plan({"action": "update_existing_window_styles", "project": str(target), "changes": changes,
                      "expected_project_sha256": expected_project_sha256, "units": "mm"})
    with Session(target, write=True) as session:
        if expected_project_sha256 is not None and session.initial_sha != expected_project_sha256.lower():
            raise RuntimeError("Opened project SHA256 differs from the pinned inspected file")
        identities = sheet_identity_snapshot(session)
        resources = resource_identity_snapshot(session)
        pending = _preflight(session, changes)
        wanted_resources = copy.deepcopy(resources)
        for entity, change, expected, original in pending:
            if "EntityName" in expected:
                wanted_resources["WindowStyles"]["entries"][change["resource_uuid"]]["name"] = expected["EntityName"]
        if session.project.HasActiveOperation():
            raise RuntimeError("Native operation already active")
        with _resource_operation(session):
            for entity, change, expected, original in pending:
                for key, value in expected.items():
                    set_parameter(session, entity, key, value)
        for entity, change, expected, original in pending:
            _readback(session, change, expected, original)
        if sheet_identity_snapshot(session) != identities or resource_identity_snapshot(session) != wanted_resources:
            raise RuntimeError("Committed native identities/resources differ before save")
        # Persist plain expectations only across Session teardown/reinitializing
        # COM. Numeric entity pointers must not survive into a fresh process.
        expectations = [(change, expected, original) for _, change, expected, original in pending]
        pending.clear()
        entity = None
        session.save()
    with Session(target) as reopened:
        if sheet_identity_snapshot(reopened) != identities or resource_identity_snapshot(reopened) != wanted_resources:
            raise RuntimeError("Saved native identities/resources differ after reopen")
        verified = [_readback(reopened, change, expected, original)
                    for change, expected, original in expectations]
        event("native_existing_window_styles_reopened_verified", path=str(target), plan=plan,
              updated_resources=verified, computer_use_calls=0, undo_history_supported=False)
        return {"status": "saved_reopened_verified", "plan": plan, "updated_resources": verified,
                "identity_type_preservation_verified": True, "resource_identity_name_preservation_verified": True,
                "observed_resource_collections": [key for key, value in resources.items() if value["status"] == "read"],
                "unavailable_resource_collections": [key for key, value in resources.items() if value["status"] != "read"],
                "computer_use_calls": 0, "undo_history_supported": False,
                "scope": "existing_WindowStyle_exposed_common_parameters_not_internal_pane_tree",
                "limitations": ["SDK disables undo history for styles/materials; project rollback, backup and unsaved discard are used",
                                "Common MaterialId does not prove each internal node's material",
                                "No pane/mullion tree, per-node material or opening-direction authoring",
                                "Identity checks do not establish geometry, color or visual layout correctness"]}
