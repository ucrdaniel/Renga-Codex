"""Verify imported STEP style geometry using a disposable native Element.

The source remains immutable data. Numerical mesh invariants are independently
requested by the caller; a successful factory or matching bounding box alone
does not demonstrate that Renga loaded the source instead of its default model.
"""
from pathlib import Path
import math
import re

from .model import create, object_by_id
from .safety import fingerprint


STEP_EXTENSIONS=frozenset({'.step','.stp'})
GEOMETRY_KEYS=frozenset({'volume_mm3','surface_area_mm2','minimum_triangles'})


def _positive(value,label):
    if isinstance(value,bool) or not isinstance(value,(int,float)):
        raise ValueError(label+' must be a finite positive number')
    try:value=float(value)
    except (ValueError,OverflowError) as error:raise ValueError(label+' must be finite') from error
    if not math.isfinite(value) or value<=0:raise ValueError(label+' must be finite and positive')
    return value


def validate_step_spec(raw):
    path=raw.get('file_path')
    if not isinstance(path,str) or not path.strip() or '\x00' in path:
        raise ValueError('ElementStyle requires an explicit absolute file_path')
    source=Path(path)
    if not source.is_absolute():raise ValueError('ElementStyle file_path must be absolute')
    if source.suffix.lower() not in STEP_EXTENSIONS:
        raise ValueError('ElementStyle authoring initially supports only STEP/STP, not RNP/IFC/STDL or arbitrary files')
    digest=raw.get('source_sha256')
    if not isinstance(digest,str) or not re.fullmatch(r'[0-9a-fA-F]{64}',digest):
        raise ValueError('ElementStyle requires the independently selected source_sha256')
    dimensions=raw.get('expected_dimensions_mm')
    if not isinstance(dimensions,(list,tuple)) or len(dimensions)!=3:
        raise ValueError('expected_dimensions_mm must contain explicit X,Y,Z extents')
    geometry=raw.get('expected_geometry')
    if not isinstance(geometry,dict) or set(geometry)!=GEOMETRY_KEYS:
        raise ValueError('expected_geometry requires volume_mm3, surface_area_mm2 and minimum_triangles')
    triangles=geometry['minimum_triangles']
    if isinstance(triangles,bool) or not isinstance(triangles,int) or not 1<=triangles<=2**31-1:
        raise ValueError('minimum_triangles must be a positive native int32 count')
    return {'file_path':str(source),'source_sha256':digest.lower(),
            'expected_dimensions_mm':[_positive(value,'expected dimension') for value in dimensions],
            'expected_geometry':{'volume_mm3':_positive(geometry['volume_mm3'],'expected volume_mm3'),
                                 'surface_area_mm2':_positive(geometry['surface_area_mm2'],'expected surface_area_mm2'),
                                 'minimum_triangles':triangles}}


def verify_step_source(spec):
    """Check a local STEP data file and immutable hash; never execute source."""
    path=Path(spec['file_path'])
    if not path.is_file():raise FileNotFoundError(path)
    if fingerprint(path)!=spec['source_sha256']:raise ValueError('STEP source SHA256 differs from the requested immutable input')
    with path.open('rb') as stream:
        beginning=stream.read(4096)
        stream.seek(max(0,path.stat().st_size-4096));ending=stream.read()
    if b'ISO-10303-21;' not in beginning.upper() or b'END-ISO-10303-21;' not in ending.upper():
        raise ValueError('STEP source lacks ISO-10303-21 exchange-file delimiters')
    return spec['source_sha256']


def mesh_metrics(grids):
    """Dimensions, signed-shell volume and surface area in explicit mm units."""
    points=[point for grid in grids for point in grid['vertices']]
    if not points or any(len(point)!=3 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in point) for point in points):
        raise RuntimeError('Imported Element has empty or nonfinite native vertices')
    minimum=list(map(min,zip(*points)));maximum=list(map(max,zip(*points)))
    reference=[(a+b)/2 for a,b in zip(minimum,maximum)]
    area=0.;signed_volume=0.;triangles=0
    for grid in grids:
        vertices=grid['vertices']
        for face in grid['triangles']:
            if len(face)!=3 or any(isinstance(i,bool) or not isinstance(i,int) or not 0<=i<len(vertices) for i in face):
                raise RuntimeError('Invalid imported Element native triangle indices')
            a,b,c=[[v-reference[i] for i,v in enumerate(vertices[index])] for index in face]
            ab=[b[i]-a[i] for i in range(3)];ac=[c[i]-a[i] for i in range(3)]
            cross=[ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0]]
            area+=math.hypot(*cross)/2
            bc=[b[1]*c[2]-b[2]*c[1],b[2]*c[0]-b[0]*c[2],b[0]*c[1]-b[1]*c[0]]
            signed_volume+=sum(a[i]*bc[i] for i in range(3))/6
            triangles+=1
    volume=abs(signed_volume)
    if not triangles or not math.isfinite(area) or not math.isfinite(volume) or area<=0 or volume<=0:
        raise RuntimeError('Imported Element mesh has no finite nonzero shell volume/surface')
    return {'dimensions_mm':[b-a for a,b in zip(minimum,maximum)],'volume_mm3':volume,
            'surface_area_mm2':area,'triangle_count':triangles}


def assert_metrics(actual,spec):
    for got,wanted in zip(actual['dimensions_mm'],spec['expected_dimensions_mm']):
        if not math.isclose(got,wanted,rel_tol=1e-6,abs_tol=1e-3):
            raise RuntimeError('Imported Element mesh extent differs from independent STEP expectation')
    expected=spec['expected_geometry']
    for key in ('volume_mm3','surface_area_mm2'):
        if not math.isclose(actual[key],expected[key],rel_tol=0.001,abs_tol=0.001):
            raise RuntimeError('Imported Element '+key+' differs from independent STEP expectation; possible default-model fallback')
    if actual['triangle_count']<expected['minimum_triangles']:
        raise RuntimeError('Imported Element has fewer triangles than independently required; possible default-model fallback')
    return {**actual,'source_sha256':spec['source_sha256'],
            'probe_scope':'native_Element_mesh_bounds_volume_surface_minimum_triangle_count',
            'full_brep_equivalence_verified':False}


def _native_probe_grids(s,identifier):
    objects=s.project.DataExporter.GetObjects3D()
    for index in range(objects.Count):
        obj=objects.Get(index)
        if obj.ModelObjectId!=identifier:continue
        grids=[]
        for mesh_index in range(obj.MeshCount):
            mesh=obj.GetMesh(mesh_index)
            for grid_index in range(mesh.GridCount):
                grid=mesh.GetGrid(grid_index)
                grids.append({'vertices':[list(grid.GetVertexComponents(i)) for i in range(grid.VertexCount)],
                              'triangles':[list(grid.GetTriangleComponents(i)) for i in range(grid.TriangleCount)]})
        return grids
    raise RuntimeError('Temporary imported-style native Element has no exported geometry')


def probe_element_style(s,style_id,spec):
    """Temporary native model edit; delete before save and verify caller's model IDs."""
    verify_step_source(spec)
    with s.operation():obj=create(s,'Element',parameters={'ElementStyleId':style_id})
    uid=obj.UniqueIdS
    try:return assert_metrics(mesh_metrics(_native_probe_grids(s,obj.Id)),spec)
    finally:
        with s.operation():s.model.DeleteObjectById(object_by_id(s,uid).Id)
        verify_step_source(spec)
