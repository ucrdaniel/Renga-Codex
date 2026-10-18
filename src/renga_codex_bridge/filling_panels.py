"""Read native filling panel meshes without inferring panels from style values.

``PanelDepth``, a nonzero style ID, frames and thresholds do not establish that
a Door contains a leaf. This reader uses the installed SDK's mesh-type IDs and
actual nondegenerate exported triangles. It creates or edits no objects.
Presence is a narrower claim than leaf count, closure, opening direction or a
complete manufacturer's assembly; those semantics are deliberately unverified.
"""
from __future__ import annotations

import math
import uuid

from .model import object_by_id


def _guid(value):
    if not isinstance(value, str):
        raise ValueError("Native identity must be a UUID string")
    return str(uuid.UUID(value.strip("{}")))


def validate_filling_identifiers(identifiers):
    if not isinstance(identifiers, (list, tuple)) or not 1 <= len(identifiers) <= 2000:
        raise ValueError("identifiers must contain 1 to 2000 inspected filling UUIDs")
    result = [_guid(value) for value in identifiers]
    if len(set(result)) != len(result):
        raise ValueError("Duplicate normalized filling UUID")
    return result


def summarize_panel_geometry(kind, grids, panel_mesh_guid, *, exported=True):
    """Summarize one exported Door/Window, retaining missing vs absent evidence.

    ``grids`` use geometry.extract's shape, including native mesh_index and
    mesh_type_guid. Surface and extents cover panel triangles only, in mm units.
    Multiple grids per mesh are not counted as separate panels or leaves.
    """
    if kind not in {"Door", "Window"}:
        raise ValueError("Panel verification applies only to native Door/Window")
    expected = _guid(panel_mesh_guid)
    if not isinstance(exported, bool):
        raise ValueError("exported must be a strict boolean")
    if not isinstance(grids, (list, tuple)):
        raise ValueError("Native grids must be an explicit sequence")
    if not exported and grids:
        raise ValueError("Nonexported filling cannot contain exported grids")
    panel_grids = []
    unknown_classification = False
    for grid in grids:
        classification = grid.get("mesh_type_guid")
        if classification is None:
            unknown_classification = True
        elif _guid(classification) == expected:
            panel_grids.append(grid)
    mesh_ids = set()
    points = []
    areas = []
    triangle_count = 0
    nondegenerate = 0
    for grid in panel_grids:
        mesh_index = grid.get("mesh_index")
        if type(mesh_index) is not int or mesh_index < 0:
            raise ValueError("Native panel mesh_index must be a nonnegative integer")
        mesh_ids.add(mesh_index)
        vertices = grid["vertices"]
        for point in vertices:
            if len(point) != 3 or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in point):
                raise ValueError("Invalid native panel vertex")
            try:
                finite = all(math.isfinite(value) for value in point)
            except OverflowError as error:
                raise ValueError("Nonfinite native panel vertex") from error
            if not finite:
                raise ValueError("Nonfinite native panel vertex")
        for triangle in grid["triangles"]:
            if len(triangle) != 3 or any(type(index) is not int or not 0 <= index < len(vertices) for index in triangle):
                raise ValueError("Invalid native panel triangle")
            a, b, c = [vertices[index] for index in triangle]
            ab = [b[index] - a[index] for index in range(3)]
            ac = [c[index] - a[index] for index in range(3)]
            cross = (ab[1]*ac[2] - ab[2]*ac[1], ab[2]*ac[0] - ab[0]*ac[2], ab[0]*ac[1] - ab[1]*ac[0])
            area = math.hypot(*cross) / 2
            if not math.isfinite(area):
                raise ValueError("Nonfinite native panel triangle area")
            triangle_count += 1
            if area > 0:
                nondegenerate += 1
                areas.append(area)
                points.extend((a, b, c))
    observed = nondegenerate > 0
    if observed:
        status, reason = "passed", "Native panel-classified nondegenerate triangles observed"
    elif not exported:
        status, reason = "not_verified", "Filling absent from native 3D export"
    elif unknown_classification:
        status, reason = "not_verified", "At least one exported grid has no native mesh-type classification"
    else:
        status, reason = "failed", "No nondegenerate native panel geometry observed"
    minimum = list(map(min, zip(*points))) if points else None
    maximum = list(map(max, zip(*points))) if points else None
    try:
        surface = math.fsum(areas)
    except OverflowError as error:
        raise ValueError("Nonfinite native panel total surface area") from error
    if not math.isfinite(surface):
        raise ValueError("Nonfinite native panel total surface area")
    return {
        "status": status, "reason": reason, "kind": kind,
        "panel_mesh_type_guid": expected, "panel_presence_verified": observed,
        "panel_mesh_count": len(mesh_ids), "panel_grid_count": len(panel_grids),
        "panel_triangle_count": triangle_count, "nondegenerate_panel_triangle_count": nondegenerate,
        "panel_surface_area_mm2": surface,
        "panel_bounds_mm": {"min": minimum, "max": maximum} if points else None,
        "panel_extents_mm": [high-low for low, high in zip(minimum, maximum)] if points else None,
        "leaf_count_verified": False, "closed_solid_verified": False,
        "opening_direction_verified": False, "manufacturer_assembly_verified": False,
        "scope": "native_panel_mesh_classification_and_nondegenerate_triangle_presence",
    }


def inspect_filling_panels(session, identifiers=None):
    """Read inspected UUIDs through a caller-owned Session; never save/mutate.

    A fresh read-only Session on a saved file establishes that these are the
    persisted meshes. This low-level reader does not itself create that session
    and therefore does not claim a save/reopen cycle performed by this call.
    """
    mesh_types = session.sdk.read_guids("MeshTypes")
    requested = {}
    rows = []
    if identifiers is None:
        objects = session.model.GetObjects()
        selected = []
        native_types = {_guid(session.sdk.types[name]) for name in ("Door", "Window")}
        for index in range(objects.Count):
            obj = objects.GetByIndex(index)
            if _guid(obj.ObjectTypeS) in native_types:
                selected.append((_guid(obj.UniqueIdS), obj))
                if len(selected) > 2000:
                    raise ValueError("Automatic panel inspection is limited to 2000 native fillings; select UUIDs explicitly")
    else:
        selected = [(uid, object_by_id(session, uid)) for uid in validate_filling_identifiers(identifiers)]
    for uid, obj in selected:
        if _guid(obj.UniqueIdS) != uid:
            raise RuntimeError("Resolved filling native UUID differs from requested identity")
        kind = next((name for name in ("Door", "Window") if _guid(obj.ObjectTypeS) == _guid(session.sdk.types[name])), None)
        if kind is None:
            raise ValueError("Selected object is not a native Door/Window")
        if obj.Id in requested:
            raise RuntimeError("Distinct filling UUIDs resolved to one numeric ID")
        requested[obj.Id] = (uid, kind)
    if not requested:
        return {"status": "not_verified", "reason": "No native Door/Window objects selected by automatic inspection",
                "fillings": [], "computer_use_calls": 0, "save_reopen_performed_by_this_reader": False,
                "scope": "read_only_native_panel_mesh_presence_not_complete_door_or_window_assembly"}
    native = session.project.DataExporter.GetObjects3D()
    exported = {}
    for index in range(native.Count):
        obj = native.Get(index)
        if obj.ModelObjectId not in requested:
            continue
        if obj.ModelObjectId in exported:
            raise RuntimeError("Duplicate filling object in native 3D export")
        grids = []
        for mesh_index in range(obj.MeshCount):
            mesh = obj.GetMesh(mesh_index)
            try:
                mesh_type = mesh.MeshTypeS
            except AttributeError:
                mesh_type = None
            for grid_index in range(mesh.GridCount):
                grid = mesh.GetGrid(grid_index)
                grids.append({"mesh_type_guid": mesh_type, "mesh_index": mesh_index,
                              "vertices": [list(grid.GetVertexComponents(v)) for v in range(grid.VertexCount)],
                              "triangles": [list(grid.GetTriangleComponents(t)) for t in range(grid.TriangleCount)]})
        exported[obj.ModelObjectId] = grids
    for identifier, (uid, kind) in requested.items():
        row = summarize_panel_geometry(kind, exported.get(identifier, []), mesh_types[kind+"Panel"],
                                       exported=identifier in exported)
        rows.append({"uuid": uid, "id": identifier, **row})
    status = "failed" if any(row["status"] == "failed" for row in rows) else "not_verified" if any(row["status"] != "passed" for row in rows) else "passed"
    return {"status": status, "fillings": rows, "computer_use_calls": 0,
            "save_reopen_performed_by_this_reader": False,
            "scope": "read_only_native_panel_mesh_presence_not_complete_door_or_window_assembly"}
