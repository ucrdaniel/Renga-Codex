import asyncio
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest

from renga_codex_bridge import filling_panels as panels


PANEL = str(uuid4())
FRAME = str(uuid4())
DOOR = str(uuid4())
WINDOW = str(uuid4())
UID = str(uuid4())


def grid(**updates):
    return {"mesh_type_guid": PANEL, "mesh_index": 0,
            "vertices": [[0., 0., 0.], [100., 0., 0.], [0., 200., 0.]],
            "triangles": [[0, 1, 2]], **updates}


def test_panel_is_measured_from_classified_nondegenerate_triangles():
    result = panels.summarize_panel_geometry("Door", [grid()], "{"+PANEL.upper()+"}")
    assert result["status"] == "passed"
    assert result["panel_surface_area_mm2"] == 10000.
    assert result["panel_bounds_mm"] == {"min": [0., 0., 0.], "max": [100., 200., 0.]}
    assert result["panel_extents_mm"] == [100., 200., 0.]
    assert result["panel_presence_verified"] is True
    assert result["leaf_count_verified"] is result["closed_solid_verified"] is False
    assert result["opening_direction_verified"] is result["manufacturer_assembly_verified"] is False


def test_two_grids_in_one_mesh_do_not_claim_two_leaves():
    result = panels.summarize_panel_geometry("Window", [grid(), grid()], PANEL)
    assert result["panel_grid_count"] == result["panel_triangle_count"] == 2
    assert result["panel_mesh_count"] == 1
    assert result["leaf_count_verified"] is False


def test_native_mesh_indices_are_counted_and_frames_do_not_contribute():
    result = panels.summarize_panel_geometry("Door", [grid(), grid(mesh_index=3), grid(mesh_type_guid=FRAME)], PANEL)
    assert result["panel_mesh_count"] == 2
    assert result["panel_surface_area_mm2"] == 20000.


@pytest.mark.parametrize("grids", [[], [grid(mesh_type_guid=FRAME)], [grid(triangles=[])], [grid(triangles=[[0, 0, 0]])]])
def test_style_frame_empty_or_degenerate_geometry_cannot_pass(grids):
    result = panels.summarize_panel_geometry("Door", grids, PANEL)
    assert result["status"] == "failed"
    assert result["panel_presence_verified"] is False
    assert result["panel_bounds_mm"] is None


def test_missing_export_differs_from_missing_panel():
    result = panels.summarize_panel_geometry("Door", [], PANEL, exported=False)
    assert result["status"] == "not_verified"
    assert "absent" in result["reason"]


def test_export_flag_cannot_contradict_actual_grids():
    with pytest.raises(ValueError, match="Nonexported"):
        panels.summarize_panel_geometry("Door", [grid()], PANEL, exported=False)


def test_vertical_translated_and_reversed_triangle_preserves_true_surface():
    result = panels.summarize_panel_geometry("Door", [grid(
        vertices=[[10., 20., 30.], [10., 120., 30.], [10., 20., 230.]], triangles=[[2, 1, 0]])], PANEL)
    assert result["status"] == "passed"
    assert result["panel_surface_area_mm2"] == 10000.
    assert result["panel_bounds_mm"] == {"min": [10., 20., 30.], "max": [10., 120., 230.]}
    assert result["panel_extents_mm"] == [0., 100., 200.]


def test_finite_coordinates_with_overflowing_area_are_rejected():
    with pytest.raises(ValueError, match="Nonfinite"):
        panels.summarize_panel_geometry("Door", [grid(vertices=[[0., 0., 0.], [1e308, 0., 0.], [0., 1e308, 0.]])], PANEL)


def test_multiple_finite_triangle_areas_cannot_overflow_total_silently():
    large = grid(vertices=[[0., 0., 0.], [1e154, 0., 0.], [0., 1e154, 0.]])
    with pytest.raises(ValueError, match="total surface"):
        panels.summarize_panel_geometry("Door", [large]*4, PANEL)


def test_missing_mesh_type_is_not_misreported_as_known_absent_panel():
    result = panels.summarize_panel_geometry("Door", [grid(mesh_type_guid=None)], PANEL)
    assert result["status"] == "not_verified"


def test_actual_panel_presence_can_be_verified_even_with_other_unknown_mesh():
    result = panels.summarize_panel_geometry("Door", [grid(), grid(mesh_type_guid=None)], PANEL)
    assert result["status"] == "passed"


@pytest.mark.parametrize("changes", [
    {"mesh_index": True}, {"mesh_index": -1}, {"triangles": [[0, 1, 3]]},
    {"triangles": [[0, True, 2]]}, {"triangles": [[0, 1]]},
    {"vertices": [[0, 0, float("nan")]]}, {"vertices": [[0, 0, float("inf")]]},
    {"vertices": [[0, 0, True]]}, {"vertices": [[0, 0, 10**999]]},
    {"vertices": [[0, 0]]}, {"mesh_type_guid": "not a UUID"},
])
def test_malformed_panel_geometry_rejected(changes):
    with pytest.raises(ValueError):
        panels.summarize_panel_geometry("Door", [grid(**changes)], PANEL)


@pytest.mark.parametrize("values", [[], None, UID, [1], [UID, "{"+UID.upper()+"}"]])
def test_identifier_contract_rejects_missing_numeric_or_duplicate_identifiers(values):
    with pytest.raises(ValueError):
        panels.validate_filling_identifiers(values)


def test_identifiers_are_normalized():
    assert panels.validate_filling_identifiers(["{"+UID.upper()+"}"]) == [UID]


def test_explicit_identifier_limit_is_preflighted():
    with pytest.raises(ValueError, match="2000"):
        panels.validate_filling_identifiers([str(uuid4()) for _ in range(2001)])


def native_session(monkeypatch, *, object_type=DOOR, native_mesh_type=PANEL, include_export=True):
    obj = NS(Id=7, UniqueIdS=UID, ObjectTypeS=object_type)
    monkeypatch.setattr(panels, "object_by_id", lambda session, uid: obj)
    vertices = grid()["vertices"]
    native_grid = NS(VertexCount=3, TriangleCount=1,
                     GetVertexComponents=lambda i: vertices[i], GetTriangleComponents=lambda i: [0, 1, 2])
    mesh = NS(MeshTypeS=native_mesh_type, GridCount=1, GetGrid=lambda i: native_grid)
    native_obj = NS(ModelObjectId=7, MeshCount=1, GetMesh=lambda i: mesh)
    native = NS(Count=1 if include_export else 0, Get=lambda i: native_obj)
    return NS(sdk=NS(types={"Door": DOOR, "Window": WINDOW},
                     read_guids=lambda name: {"DoorPanel": PANEL, "WindowPanel": PANEL}),
              project=NS(DataExporter=NS(GetObjects3D=lambda: native))), obj


def test_native_adapter_reports_observed_panel_and_never_saves(monkeypatch):
    session, obj = native_session(monkeypatch)
    result = panels.inspect_filling_panels(session, [UID])
    assert result["status"] == "passed"
    assert result["fillings"][0]["uuid"] == UID
    assert result["fillings"][0]["panel_triangle_count"] == 1
    assert result["computer_use_calls"] == 0
    assert result["save_reopen_performed_by_this_reader"] is False


def test_native_adapter_frame_only_is_failed(monkeypatch):
    session, _ = native_session(monkeypatch, native_mesh_type=FRAME)
    assert panels.inspect_filling_panels(session, [UID])["status"] == "failed"


def test_native_adapter_missing_export_is_unverified(monkeypatch):
    session, _ = native_session(monkeypatch, include_export=False)
    assert panels.inspect_filling_panels(session, [UID])["status"] == "not_verified"


def test_native_adapter_rejects_wrong_identity_before_export(monkeypatch):
    session, obj = native_session(monkeypatch)
    obj.UniqueIdS = str(uuid4())
    with pytest.raises(RuntimeError, match="differs"):
        panels.inspect_filling_panels(session, [UID])


def test_native_adapter_rejects_nonfilling(monkeypatch):
    session, _ = native_session(monkeypatch, object_type=str(uuid4()))
    with pytest.raises(ValueError, match="not a native"):
        panels.inspect_filling_panels(session, [UID])


def test_none_selects_actual_native_fillings_without_numeric_id_lookup(monkeypatch):
    session, obj = native_session(monkeypatch)
    unrelated = NS(Id=12, UniqueIdS=str(uuid4()), ObjectTypeS=str(uuid4()))
    session.model = NS(GetObjects=lambda: NS(Count=2, GetByIndex=lambda i: (unrelated, obj)[i]))
    monkeypatch.setattr(panels, "object_by_id", lambda *args: pytest.fail("Automatic selection must read actual objects"))
    result = panels.inspect_filling_panels(session)
    assert result["status"] == "passed"
    assert result["fillings"][0]["uuid"] == UID


def test_none_empty_project_is_unverified_not_vacuous_pass(monkeypatch):
    session, _ = native_session(monkeypatch)
    session.model = NS(GetObjects=lambda: NS(Count=0))
    result = panels.inspect_filling_panels(session)
    assert result["status"] == "not_verified"
    assert result["fillings"] == []


def test_none_limit_is_preflighted_before_geometry_export(monkeypatch):
    session, obj = native_session(monkeypatch)
    session.model = NS(GetObjects=lambda: NS(Count=2001, GetByIndex=lambda i: obj))
    with pytest.raises(ValueError, match="2000"):
        panels.inspect_filling_panels(session)


@pytest.mark.parametrize("identifiers", [None, [UID]])
def test_worker_forwards_panel_selection_through_readonly_session(monkeypatch, identifiers):
    from renga_codex_bridge import worker
    owned = object()
    class ReadonlySession:
        def __init__(self, project, **options):
            assert project == "saved.rnp" and options == {}
        def __enter__(self): return owned
        def __exit__(self, *args): return False
    monkeypatch.setattr(worker, "Session", ReadonlySession)
    def inspect(actual, selected):
        assert actual is owned and selected == identifiers
        return {"status": "not_verified", "fillings": []}
    monkeypatch.setattr(panels, "inspect_filling_panels", inspect)
    assert worker.execute("filling_panels", {"project": "saved.rnp", "identifiers": identifiers})["status"] == "not_verified"


@pytest.mark.parametrize("identifiers", [None, [UID]])
def test_mcp_forwards_panel_selection_without_new_or_write_bypass(monkeypatch, identifiers):
    from renga_codex_bridge import mcp_server
    seen = {}
    async def run(command, **arguments):
        seen.update(command=command, arguments=arguments)
        return {"status": "passed"}
    monkeypatch.setattr(mcp_server, "run", run)
    assert asyncio.run(mcp_server.bridge_inspect_filling_panels("saved.rnp", identifiers))["status"] == "passed"
    assert seen == {"command": "filling_panels", "arguments": {"project": "saved.rnp", "identifiers": identifiers}}


def test_registered_tool_schema_has_optional_uuid_array_and_no_authorization_switch():
    from renga_codex_bridge.mcp_server import server
    tool = next(tool for tool in asyncio.run(server.list_tools()) if tool.name == "bridge_inspect_filling_panels")
    # MCP package versions expose either wire names or the internal registry's
    # ``parameters`` dictionary. Check the actual schema, not one wrapper name.
    schema = (getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None)
              or getattr(tool, "parameters", None))
    assert isinstance(schema, dict)
    assert set(schema["properties"]) == {"project", "identifiers"}
    assert schema["required"] == ["project"]
    options = schema["properties"]["identifiers"]["anyOf"]
    assert {"type": "array", "items": {"type": "string"}} in options
    assert {"type": "null"} in options
