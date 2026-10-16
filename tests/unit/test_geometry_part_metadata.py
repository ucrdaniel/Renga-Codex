"""Native part labels accompany real vertices; mocks do not establish BIM coverage."""
from types import SimpleNamespace

import pytest

from renga_codex_bridge.geometry import extract


class Collection:
    def __init__(self, values): self.values = values; self.Count = len(values)
    def Get(self, index): return self.values[index]
    def GetById(self, identifier):
        assert identifier == 42
        return SimpleNamespace(UniqueIdS="{00000000-0000-4000-8000-000000000042}")


class Grid:
    VertexCount = 3
    TriangleCount = 1
    def __init__(self, kind): self.GridType = kind
    def GetVertexComponents(self, index): return ((0,0,1000),(100,0,1000),(0,100,1000))[index]
    def GetTriangleComponents(self, index): return (0,1,2)


class Mesh:
    def __init__(self, mesh_type, grids): self.MeshTypeS = mesh_type; self.grids = grids; self.GridCount = len(grids)
    def GetGrid(self, index): return self.grids[index]


def session(meshes):
    # Synthetic type labels avoid shipping SDK constants. Actual type semantics
    # require the caller's local SDK and native fixture.
    exported = SimpleNamespace(ModelObjectId=42, MeshCount=len(meshes), GetMesh=lambda index: meshes[index])
    objects = Collection([exported])
    return SimpleNamespace(project=SimpleNamespace(DataExporter=SimpleNamespace(GetObjects3D=lambda: objects)),
                           model=SimpleNamespace(GetObjects=lambda: objects))


def test_all_flattened_grids_keep_their_own_mesh_and_grid_classifications():
    result = extract(session([Mesh("{00000000-0000-4000-8000-000000000001}", [Grid(11),Grid(12)]),
                              Mesh("{00000000-0000-4000-8000-000000000002}", [Grid(21)])]))
    grids = result["objects"][0]["grids"]
    assert [(grid["mesh_index"],grid["grid_index"],grid["grid_type"]) for grid in grids] == [(0,0,11),(0,1,12),(1,0,21)]
    assert grids[0]["mesh_type_guid"].endswith("000000000001}")
    assert grids[2]["mesh_type_guid"].endswith("000000000002}")
    assert grids[0]["vertices"] == [[0,0,1000],[100,0,1000],[0,100,1000]]
    assert grids[0]["triangles"] == [[0,1,2]]
    assert result["unit"] == "mm"
    assert result["objects"][0]["uuid"] == "00000000-0000-4000-8000-000000000042"


def test_zero_grid_type_is_preserved_as_a_value_not_missing_metadata():
    assert extract(session([Mesh("native-label",[Grid(0)])]))["objects"][0]["grids"][0]["grid_type"] == 0


def test_missing_properties_on_old_adapter_do_not_break_original_geometry_fields():
    grid = Grid(1); del grid.GridType
    mesh = Mesh("label",[grid]); del mesh.MeshTypeS
    actual = extract(session([mesh]))["objects"][0]["grids"][0]
    assert actual["mesh_type_guid"] is None and actual["grid_type"] is None
    assert len(actual["vertices"]) == 3 and actual["triangles"] == [[0,1,2]]


def test_real_metadata_getter_failures_are_not_silently_reported_as_missing():
    class FailingMesh(Mesh):
        @property
        def MeshTypeS(self): raise RuntimeError("Native part getter failed")
    mesh = FailingMesh.__new__(FailingMesh); mesh.grids=[Grid(1)];mesh.GridCount=1
    with pytest.raises(RuntimeError,match="Native part getter"):
        extract(session([mesh]))


def test_existing_triangle_validation_still_rejects_invalid_native_indices():
    class BrokenGrid(Grid):
        def GetTriangleComponents(self, index): return (0,1,99)
    with pytest.raises(RuntimeError,match="Invalid native triangle"):
        extract(session([Mesh("label",[BrokenGrid(1)])]))
