import math
from .model import inventory

def extract(s):
    native=s.project.DataExporter.GetObjects3D();rows=[]
    for i in range(native.Count):
        obj=native.Get(i);grids=[]
        for j in range(obj.MeshCount):
            mesh=obj.GetMesh(j)
            for k in range(mesh.GridCount):
                grid=mesh.GetGrid(k)
                vertices=[list(grid.GetVertexComponents(v)) for v in range(grid.VertexCount)]
                triangles=[list(grid.GetTriangleComponents(t)) for t in range(grid.TriangleCount)]
                if any(any(index<0 or index>=len(vertices) for index in face) for face in triangles):raise RuntimeError('Invalid native triangle indices')
                grids.append({'vertices':vertices,'triangles':triangles})
        model=s.model.GetObjects().GetById(obj.ModelObjectId)
        rows.append({'id':obj.ModelObjectId,'uuid':model.UniqueIdS.strip('{}').lower(),'grids':grids})
    return {'unit':'mm','objects':rows}

def mesh_bottom_area(grids):
    vertices=[v for g in grids for v in g['vertices']]
    if not vertices:raise ValueError('Native mesh empty')
    z=min(v[2] for v in vertices);area=0.0
    for grid in grids:
        for tri in grid['triangles']:
            a,b,c=[grid['vertices'][i] for i in tri]
            if all(abs(p[2]-z)<0.001 for p in (a,b,c)):
                area+=abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2e6
    return area

def verify(s,expected_areas=None,collision_types=None):
    rows=inventory(s);geometry=extract(s);mesh_by_uid={v['uuid']:v for v in geometry['objects']};checks=[];bounds={}
    for row in rows:
        mesh=mesh_by_uid.get(row['uuid'])
        if mesh:
            vertices=[v for g in mesh['grids'] for v in g['vertices']]
            if vertices:bounds[row['uuid']]={'min':list(map(min,zip(*vertices))),'max':list(map(max,zip(*vertices)))}
        key='NetFloorArea' if row['type']=='Room' else 'NetArea' if row['type']=='Floor' else None
        if key and mesh:
            measured=row['quantities'][key]['value'];independent=mesh_bottom_area(mesh['grids'])
            checks.append({'check':'native_area_vs_bottom_mesh','uuid':row['uuid'],'native_m2':measured,'mesh_m2':independent,'passed':abs(measured-independent)<0.01})
    for uid,expected in (expected_areas or {}).items():
        uid=uid.strip('{}').lower();row=next(v for v in rows if v['uuid']==uid)
        if isinstance(expected,bool) or not isinstance(expected,(int,float)) or not math.isfinite(expected):raise ValueError('Expected area must be finite')
        key='NetFloorArea' if row['type']=='Room' else 'NetArea'
        measured=row['quantities'][key]['value'];checks.append({'check':'requested_area','uuid':uid,'actual_m2':measured,'expected_m2':expected,'passed':abs(measured-expected)<0.01})
    pairs=[]
    selected=[row for row in rows if row['type'] in (collision_types or []) and row['uuid'] in bounds]
    for index,a in enumerate(selected):
        for b in selected[index+1:]:
            aa,bb=bounds[a['uuid']],bounds[b['uuid']]
            overlap=[min(aa['max'][i],bb['max'][i])-max(aa['min'][i],bb['min'][i]) for i in range(3)]
            if all(v>0.01 for v in overlap):pairs.append({'a':a['uuid'],'b':b['uuid'],'overlap_mm':overlap,'status':'conservative_aabb_candidate'})
    return {'status':'passed' if all(v['passed'] for v in checks) else 'failed','checks':checks,'bounds':bounds,
            'collision_candidates':pairs,'collision_method':'conservative AABB, not exact clash or code-compliance check','computer_use_calls':0}
