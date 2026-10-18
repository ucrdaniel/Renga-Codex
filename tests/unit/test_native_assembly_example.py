"""Portable guards of the standalone recipe; never launch native Renga."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
from uuid import UUID

import pytest


def example():
    path = Path(__file__).resolve().parents[2]/'examples/native_beam_assembly.py'
    spec = importlib.util.spec_from_file_location('native_assembly_example_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('bad', [True, False, 0, -1, float('nan'), float('inf'), -float('inf'), '18', None, 10**1000])
@pytest.mark.parametrize('index', [0, 1, 2])
def test_invalid_dimensions_cannot_open_session_or_save_plan(monkeypatch, bad, index):
    m = example()
    def forbidden(*a, **kw): pytest.fail('Invalid dimensions must not start native work')
    monkeypatch.setattr(m, 'Session', forbidden)
    monkeypatch.setattr(m, 'save_plan', forbidden)
    values = [1000, 18, 18]; values[index] = bad
    with pytest.raises(ValueError):
        m.create_native_beam_assembly('never-opened.rnp', length_mm=values[0], width_mm=values[1], depth_mm=values[2])


def test_existing_file_and_outside_root_fail_before_native_work(monkeypatch, tmp_path):
    m = example()
    allowed = tmp_path/'test-root'; allowed.mkdir()
    monkeypatch.setenv('RENGA_BRIDGE_WRITE_ROOT', str(allowed))
    def forbidden(*a, **kw): pytest.fail('Unsafe target must not start native work')
    monkeypatch.setattr(m, 'Session', forbidden); monkeypatch.setattr(m, 'save_plan', forbidden)
    existing = allowed/'exists.rnp'; existing.write_bytes(b'Portable guard fixture, not a BIM model')
    with pytest.raises(FileExistsError):
        m.create_native_beam_assembly(existing, length_mm=1000, width_mm=18, depth_mm=18)
    with pytest.raises(PermissionError):
        m.create_native_beam_assembly(tmp_path/'outside.rnp', length_mm=1000, width_mm=18, depth_mm=18)
    with pytest.raises(ValueError, match='native'):
        m.create_native_beam_assembly(allowed/'invalid.json', length_mm=1000, width_mm=18, depth_mm=18)


def test_uuid_lookup_uses_actual_collection_contract_and_rejects_duplicates():
    m = example(); uid = str(UUID(int=1))
    obj = NS(UniqueIdS='{'+uid.upper()+'}')
    assert m._find(NS(Count=1, GetByIndex=lambda i:obj), uid) is obj
    with pytest.raises(RuntimeError):m._find(NS(Count=0), uid)
    with pytest.raises(RuntimeError):m._find(NS(Count=2, GetByIndex=lambda i:obj), uid)


def mesh():
    return {'grids':[{'vertices':[[0,0,0],[1000,0,0],[0,18,18]], 'triangles':[[0,1,2]]}]}


def test_mesh_bounds_requires_finite_nondegenerate_native_triangles():
    m = example()
    observed = m._mesh_bounds(mesh(), [1000,18,18])
    assert observed['nondegenerate_triangle_count']==1 and observed['size']==[1000,18,18]
    for invalid in (None, {'grids':[]}, {'grids':[{'vertices':[[0,0,0]],'triangles':[]}]}):
        with pytest.raises(RuntimeError):m._mesh_bounds(invalid,[1000,18,18])
    value=mesh();value['grids'][0]['vertices'][0][0]=float('nan')
    with pytest.raises(RuntimeError,match='Nonfinite'):m._mesh_bounds(value,[1000,18,18])
    value=mesh();value['grids'][0]['triangles']=[[0,0,0]]
    with pytest.raises(RuntimeError,match='nondegenerate'):m._mesh_bounds(value,[1000,18,18])
    value=mesh();value['grids'][0]['triangles']=[[0,1,99]]
    with pytest.raises(RuntimeError,match='triangle'):m._mesh_bounds(value,[1000,18,18])
    with pytest.raises(RuntimeError,match='extents'):m._mesh_bounds(mesh(),[500,18,18])


def placement_fixture(monkeypatch):
    m = example()
    point = lambda values: NS(**dict(zip(('X','Y','Z'), values)))
    pose = NS(Origin=point([0,0,0]), AxisX=point([1,0,0]), AxisZ=point([0,0,1]))
    native = NS(LevelId=10, GetPlacement=lambda:pose)
    level = NS(Id=10, UniqueIdS=str(UUID(int=10)), ObjectTypeS=str(UUID(int=100)))
    instance = NS(QueryInterface=lambda interface:native)
    s = NS(model=NS(GetObjects=lambda:NS(GetById=lambda identifier:level if identifier==level.Id else None)),
           sdk=NS(types={'Level':level.ObjectTypeS}), r=NS(ILevelObject='level-object'))
    monkeypatch.setattr(m, 'parameters', lambda s,o:{'LevelElevation':{'has_value':True,'value':0.0}})
    return m,s,instance,pose,level


def test_native_instance_pose_and_host_level_are_read_by_actual_interfaces(monkeypatch):
    m,s,instance,pose,level=placement_fixture(monkeypatch)
    result=m._instance_placement(s,instance,level.UniqueIdS)
    assert result['placement']=={'origin_mm':[0,0,0],'x_axis':[1,0,0],'z_axis':[0,0,1]}
    assert result['level']=={'uuid':level.UniqueIdS,'id':10,'elevation_mm':0.0}


@pytest.mark.parametrize('fault',['origin','x_axis','z_axis','nonfinite','level_uuid','level_type','elevation','QI'])
def test_changed_native_instance_pose_or_host_cannot_report_success(monkeypatch,fault):
    m,s,instance,pose,level=placement_fixture(monkeypatch)
    expected_uuid=level.UniqueIdS
    if fault=='origin':pose.Origin.X=100
    elif fault=='x_axis':pose.AxisX.X=-1
    elif fault=='z_axis':pose.AxisZ.Z=-1
    elif fault=='nonfinite':pose.Origin.Z=float('nan')
    elif fault=='level_uuid':level.UniqueIdS=str(UUID(int=11))
    elif fault=='level_type':level.ObjectTypeS=str(UUID(int=101))
    elif fault=='elevation':monkeypatch.setattr(m,'parameters',lambda s,o:{'LevelElevation':{'has_value':True,'value':3000}})
    else:
        def failed(interface):raise RuntimeError('Native placement interface unsupported')
        instance.QueryInterface=failed
    with pytest.raises(RuntimeError):m._instance_placement(s,instance,expected_uuid)
