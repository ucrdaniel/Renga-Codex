"""Independent source/mesh and disposable-probe contracts, without COM."""
from contextlib import contextmanager
from types import SimpleNamespace
import hashlib
import math

import pytest

from renga_codex_bridge import element_style_geometry as g
from renga_codex_bridge.resources import validate_resource_specs


def source(tmp_path):
    path=tmp_path/'own.step'
    path.write_bytes(b'ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n')
    return {'kind':'ElementStyle','name':'Own test geometry','file_path':str(path),
            'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'expected_dimensions_mm':[1,2,3],
            'expected_geometry':{'volume_mm3':6,'surface_area_mm2':22,'minimum_triangles':12}}


def box_grids(offset=(0,0,0)):
    points=[(0,0,0),(1,0,0),(1,2,0),(0,2,0),(0,0,3),(1,0,3),(1,2,3),(0,2,3)]
    faces=[(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),
           (3,7,6),(3,6,2),(0,4,7),(0,7,3),(1,2,6),(1,6,5)]
    return [{'vertices':[[a+b for a,b in zip(point,offset)] for point in points],
             'triangles':[list(face) for face in faces]}]


def test_step_request_copies_explicit_independent_geometry(tmp_path):
    raw=source(tmp_path)
    actual=validate_resource_specs([raw])[0]
    assert actual['expected_dimensions_mm']==[1.,2.,3.]
    actual['expected_geometry']['volume_mm3']=999
    actual['expected_dimensions_mm'][0]=999
    assert raw['expected_geometry']['volume_mm3']==6
    assert raw['expected_dimensions_mm']==[1,2,3]


@pytest.mark.parametrize('suffix',['.rnp','.ifc','.stdl','.obj','.exe','.step.exe'])
def test_only_the_initial_solid_step_formats_are_accepted(tmp_path,suffix):
    raw=source(tmp_path);raw['file_path']=str(tmp_path/('source'+suffix))
    with pytest.raises(ValueError,match='STEP/STP'):validate_resource_specs([raw])


@pytest.mark.parametrize('field,value',[
    ('file_path','relative.step'),('file_path',None),('source_sha256','x'*64),
    ('source_sha256','a'*63),('expected_dimensions_mm',[1,2]),
    ('expected_dimensions_mm',[1,2,math.inf]),('expected_dimensions_mm',[1,2,True]),
    ('expected_dimensions_mm',[1,2,10**1000]),('expected_geometry',{}),
    ('expected_geometry',{'volume_mm3':6,'surface_area_mm2':22,'minimum_triangles':True}),
    ('expected_geometry',{'volume_mm3':0,'surface_area_mm2':22,'minimum_triangles':12}),
    ('expected_geometry',{'volume_mm3':6,'surface_area_mm2':math.nan,'minimum_triangles':12}),
])
def test_incomplete_or_ambiguous_import_evidence_is_rejected(tmp_path,field,value):
    raw=source(tmp_path);raw[field]=value
    with pytest.raises(ValueError):validate_resource_specs([raw])


def test_source_hash_and_exchange_file_delimiters_are_verified(tmp_path):
    raw=source(tmp_path)
    assert g.verify_step_source(raw)==raw['source_sha256']
    with open(raw['file_path'],'ab') as stream:stream.write(b'changed')
    with pytest.raises(ValueError,match='SHA256'):g.verify_step_source(raw)
    raw['source_sha256']=hashlib.sha256(b'not STEP').hexdigest()
    with open(raw['file_path'],'wb') as stream:stream.write(b'not STEP')
    with pytest.raises(ValueError,match='ISO-10303-21'):g.verify_step_source(raw)


def test_missing_step_file_is_not_replaced_with_a_native_default_model(tmp_path):
    raw=source(tmp_path)
    from pathlib import Path
    Path(raw['file_path']).unlink()
    with pytest.raises(FileNotFoundError):g.verify_step_source(raw)


@pytest.mark.parametrize('offset',[(0,0,0),(10000,-20000,30000)])
def test_mesh_volume_area_and_extents_do_not_depend_on_import_center(offset):
    actual=g.mesh_metrics(box_grids(offset))
    assert actual['dimensions_mm']==[1,2,3]
    assert actual['volume_mm3']==pytest.approx(6)
    assert actual['surface_area_mm2']==pytest.approx(22)
    assert actual['triangle_count']==12


def test_disconnected_closed_solid_grids_are_included_in_volume_and_surface():
    actual=g.mesh_metrics(box_grids()+box_grids((10,0,0)))
    assert actual['dimensions_mm']==[11,2,3]
    assert actual['volume_mm3']==pytest.approx(12)
    assert actual['surface_area_mm2']==pytest.approx(44)
    assert actual['triangle_count']==24


@pytest.mark.parametrize('key,value',[
    ('dimensions_mm',[1,2,4]),('volume_mm3',5),('surface_area_mm2',21),('triangle_count',11)])
def test_matching_bounds_alone_cannot_promote_a_fallback_model_to_success(tmp_path,key,value):
    actual=g.mesh_metrics(box_grids());actual[key]=value
    with pytest.raises(RuntimeError):g.assert_metrics(actual,source(tmp_path))


def test_metric_success_explicitly_limits_claim_to_independent_mesh_invariants(tmp_path):
    raw=source(tmp_path)
    result=g.assert_metrics(g.mesh_metrics(box_grids()),raw)
    assert result['source_sha256']==raw['source_sha256']
    assert result['probe_scope']=='native_Element_mesh_bounds_volume_surface_minimum_triangle_count'
    assert result['full_brep_equivalence_verified'] is False


@pytest.mark.parametrize('grids',[[],[{'vertices':[[0,0,math.nan]],'triangles':[]}],
                                   [{'vertices':[[0,0,0]],'triangles':[[0,1,2]]}],
                                   [{'vertices':[[0,0,0]],'triangles':[]}]])
def test_empty_nonfinite_or_invalid_mesh_cannot_be_success(grids):
    with pytest.raises(RuntimeError):g.mesh_metrics(grids)


def test_export_reads_grids_only_for_the_requested_temporary_element():
    class Unrelated:
        ModelObjectId=41
        @property
        def MeshCount(self):raise AssertionError('Do not read unrelated native geometry')
    data=box_grids()[0]
    grid=SimpleNamespace(VertexCount=8,TriangleCount=12,
        GetVertexComponents=lambda i:data['vertices'][i],GetTriangleComponents=lambda i:data['triangles'][i])
    mesh=SimpleNamespace(GridCount=1,GetGrid=lambda i:grid)
    target=SimpleNamespace(ModelObjectId=42,MeshCount=1,GetMesh=lambda i:mesh)
    values=[Unrelated(),target,Unrelated()]
    exported=SimpleNamespace(Count=3,Get=lambda i:values[i])
    s=SimpleNamespace(project=SimpleNamespace(DataExporter=SimpleNamespace(GetObjects3D=lambda:exported)))
    assert g._native_probe_grids(s,42)==box_grids()


@pytest.mark.parametrize('mismatch',[False,True])
def test_temporary_native_probe_is_deleted_after_success_or_metric_failure(monkeypatch,tmp_path,mismatch):
    raw=source(tmp_path);order=[]
    obj=SimpleNamespace(Id=42,UniqueIdS='{00000000-0000-4000-8000-000000000042}')
    @contextmanager
    def operation():
        order.append('start');yield;order.append('apply')
    s=SimpleNamespace(operation=operation,model=SimpleNamespace(DeleteObjectById=lambda identifier:order.append(('delete',identifier))))
    def create(session,kind,**kwargs):
        assert session is s and kind=='Element' and kwargs=={'parameters':{'ElementStyleId':17}}
        order.append('create');return obj
    monkeypatch.setattr(g,'create',create)
    monkeypatch.setattr(g,'object_by_id',lambda session,identifier:obj)
    monkeypatch.setattr(g,'_native_probe_grids',lambda session,identifier:box_grids())
    if mismatch:
        raw['expected_geometry']['volume_mm3']=100
        with pytest.raises(RuntimeError,match='default-model'):g.probe_element_style(s,17,raw)
    else:
        assert g.probe_element_style(s,17,raw)['volume_mm3']==pytest.approx(6)
    assert order==['start','create','apply','start',('delete',42),'apply']


def test_source_changed_during_native_probe_is_rejected_after_probe_cleanup(monkeypatch,tmp_path):
    raw=source(tmp_path);deleted=[]
    obj=SimpleNamespace(Id=42,UniqueIdS='{00000000-0000-4000-8000-000000000042}')
    @contextmanager
    def operation():yield
    s=SimpleNamespace(operation=operation,model=SimpleNamespace(DeleteObjectById=deleted.append))
    monkeypatch.setattr(g,'create',lambda *args,**kwargs:obj)
    monkeypatch.setattr(g,'object_by_id',lambda *args:obj)
    def changed(session,identifier):
        with open(raw['file_path'],'ab') as stream:stream.write(b'changed while native importer reads')
        return box_grids()
    monkeypatch.setattr(g,'_native_probe_grids',changed)
    with pytest.raises(ValueError,match='SHA256'):g.probe_element_style(s,17,raw)
    assert deleted==[42]
