import math
import uuid
from collections import Counter
from .model import inventory, object_by_id, verify_filling_host

def extract(s):
    native=s.project.DataExporter.GetObjects3D();rows=[]
    for i in range(native.Count):
        obj=native.Get(i);grids=[]
        for j in range(obj.MeshCount):
            mesh=obj.GetMesh(j)
            # Keep native part classifications with each flattened grid. A
            # nonempty mesh alone cannot distinguish a filling panel from an
            # aperture, or a handrail from its balusters. Missing properties in
            # older adapters remain None; real getter failures are not hidden.
            try:mesh_type=mesh.MeshTypeS
            except AttributeError:mesh_type=None
            for k in range(mesh.GridCount):
                grid=mesh.GetGrid(k)
                try:grid_type=grid.GridType
                except AttributeError:grid_type=None
                vertices=[list(grid.GetVertexComponents(v)) for v in range(grid.VertexCount)]
                triangles=[list(grid.GetTriangleComponents(t)) for t in range(grid.TriangleCount)]
                if any(any(index<0 or index>=len(vertices) for index in face) for face in triangles):raise RuntimeError('Invalid native triangle indices')
                grids.append({'vertices':vertices,'triangles':triangles,
                              'mesh_type_guid':mesh_type,'grid_type':grid_type,
                              'mesh_index':j,'grid_index':k})
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

def room_horizontal_down_area(grids):
    """Sum every horizontal downward face of a closed outward-wound Room mesh.

    Interior floor cuts can add downward faces above the minimum Z. Their area
    belongs to the exported Room solid's gross quantity, not just its footprint.
    Unknown/open/inward or sloping-floor geometry is reported as unverified.
    """
    parsed=[];all_points=[]
    for grid in grids:
        vertices=[]
        for point in grid['vertices']:
            if len(point)!=3 or any(isinstance(v,bool) or not isinstance(v,(int,float)) for v in point):
                raise RuntimeError('Invalid native Room mesh vertex')
            try:point=[float(v) for v in point]
            except (ValueError,OverflowError) as error:raise RuntimeError('Nonfinite native Room mesh vertex') from error
            if not all(math.isfinite(v) for v in point):raise RuntimeError('Nonfinite native Room mesh vertex')
            vertices.append(point)
        parsed.append((vertices,grid['triangles']));all_points.extend(vertices)
    if not all_points:return {'status':'not_verified','reason':'Room mesh has no vertices'}
    low=list(map(min,zip(*all_points)));high=list(map(max,zip(*all_points)))
    center=[a+(b-a)/2 for a,b in zip(low,high)]
    edges=Counter();directions=Counter();areas={};volumes=[];sloped=0
    for vertices,triangles in parsed:
        for triangle in triangles:
            if len(triangle)!=3 or any(type(i) is not int or not 0<=i<len(vertices) for i in triangle):
                raise RuntimeError('Invalid native Room triangle indices')
            points=[vertices[i] for i in triangle]
            a,b,c=[[v-center[i] for i,v in enumerate(point)] for point in points]
            ab=[b[i]-a[i] for i in range(3)];ac=[c[i]-a[i] for i in range(3)]
            cross=[ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0]]
            length=math.hypot(*cross)
            if not math.isfinite(length):raise RuntimeError('Nonfinite native Room triangle normal')
            if length==0:continue
            welded=[tuple(round(v,6) for v in point) for point in points]
            for p,q in zip(welded,welded[1:]+welded[:1]):
                if p==q:continue
                key=tuple(sorted((p,q)));edges[key]+=1;directions[key]+=1 if p<q else -1
            bc=[b[1]*c[2]-b[2]*c[1],b[2]*c[0]-b[0]*c[2],b[0]*c[1]-b[1]*c[0]]
            volumes.append(sum(a[i]*bc[i] for i in range(3))/6e9)
            if cross[2]<-length*1e-9:
                if max(p[2] for p in points)-min(p[2] for p in points)>0.001:
                    sloped+=1
                else:
                    z=round(sum(p[2] for p in points)/3,6)
                    areas[z]=areas.get(z,0)+abs(cross[2])/2e6
    if not edges or any(count!=2 or directions[key]!=0 for key,count in edges.items()):
        return {'status':'not_verified','reason':'Room mesh closure/winding is not established at 1e-6 mm vertex welding'}
    volume=math.fsum(volumes)
    if not math.isfinite(volume) or volume<=0:
        return {'status':'not_verified','reason':'Room mesh does not have positive outward signed shell volume'}
    if sloped:return {'status':'not_verified','reason':'Room has nonhorizontal downward faces; gross-area equivalence is not established'}
    if not areas:return {'status':'not_verified','reason':'Room has no horizontal downward faces'}
    return {'status':'measured','area_m2':math.fsum(areas.values()),'signed_volume_m3':volume,
            'area_by_elevation_m2':[{'z_mm':z,'area_m2':area} for z,area in sorted(areas.items())],
            'mesh_method':'all_horizontal_downward_faces','closed_outward_winding_checked':True}

def _filling_host_expectations(expected):
    if expected is None:return {}
    if not isinstance(expected,dict) or len(expected)>10000:
        raise ValueError('expected_filling_hosts must be a UUID-to-UUID dictionary of at most 10000 entries')
    result={}
    for filling,host in expected.items():
        if not isinstance(filling,str) or not isinstance(host,str):
            raise ValueError('Expected filling and Wall identities must be UUID strings, not numeric IDs')
        filling=str(uuid.UUID(filling.strip('{}')));host=str(uuid.UUID(host.strip('{}')))
        if filling in result:raise ValueError('Duplicate normalized filling UUID in expected_filling_hosts')
        result[filling]=host
    return result

def verify(s,expected_areas=None,collision_types=None,expected_filling_hosts=None):
    filling_hosts=_filling_host_expectations(expected_filling_hosts)
    rows=inventory(s);geometry=extract(s);mesh_by_uid={v['uuid']:v for v in geometry['objects']};checks=[];unverified=[];bounds={}
    for row in rows:
        mesh=mesh_by_uid.get(row['uuid'])
        if mesh:
            vertices=[v for g in mesh['grids'] for v in g['vertices']]
            if vertices:bounds[row['uuid']]={'min':list(map(min,zip(*vertices))),'max':list(map(max,zip(*vertices)))}
        # A Room's exported region corresponds to GrossFloorArea. NetFloorArea
        # uses different native boundary/opening rules and is only checked
        # against an explicit independent requested target below.
        key='GrossFloorArea' if row['type']=='Room' else 'NetArea' if row['type']=='Floor' else None
        if key and mesh:
            quantity=row['quantities'].get(key,{})
            if 'value' not in quantity:
                unverified.append({'check':'native_area_vs_room_mesh' if row['type']=='Room' else 'native_area_vs_bottom_mesh','uuid':row['uuid'],'quantity_key':key,
                                   'status':'not_verified','reason':'Native matching area quantity is unavailable; no Net/Gross substitution'})
            else:
                room_measure=room_horizontal_down_area(mesh['grids']) if row['type']=='Room' else None
                if room_measure and room_measure['status']!='measured':
                    unverified.append({'check':'native_area_vs_room_mesh','uuid':row['uuid'],'quantity_key':key,**room_measure})
                else:
                    measured=quantity['value'];independent=room_measure['area_m2'] if room_measure else mesh_bottom_area(mesh['grids'])
                    checks.append({'check':'native_area_vs_room_mesh' if room_measure else 'native_area_vs_bottom_mesh',
                                   'uuid':row['uuid'],'quantity_key':key,'native_m2':measured,'mesh_m2':independent,
                                   'passed':abs(measured-independent)<0.01})
                    if room_measure:checks[-1].update({name:room_measure[name] for name in ('mesh_method','area_by_elevation_m2','closed_outward_winding_checked')})
    for uid,expected in (expected_areas or {}).items():
        uid=uid.strip('{}').lower();row=next(v for v in rows if v['uuid']==uid)
        if isinstance(expected,bool) or not isinstance(expected,(int,float)) or not math.isfinite(expected):raise ValueError('Expected area must be finite')
        key='NetFloorArea' if row['type']=='Room' else 'NetArea'
        measured=row['quantities'][key]['value'];checks.append({'check':'requested_area','uuid':uid,'quantity_key':key,
                                                              'actual_m2':measured,'expected_m2':expected,'passed':abs(measured-expected)<0.01})
    for filling_uid,host_uid in filling_hosts.items():
        obj=object_by_id(s,filling_uid)
        if str(uuid.UUID(obj.UniqueIdS.strip('{}')))!=filling_uid:
            raise RuntimeError('Resolved filling native UUID differs from requested persistent identity')
        observed=verify_filling_host(s,obj,host_uid)
        actual_host=str(uuid.UUID(observed['host_uuid'].strip('{}')))
        if actual_host!=host_uid or observed['affected_wall_verified'] is not True:
            raise RuntimeError('Native filling host verification disagrees with the requested Wall identity')
        checks.append({'check':'requested_filling_host','uuid':filling_uid,
                       'expected_host_uuid':host_uid,'actual_host_uuid':actual_host,'passed':True,
                       'affected_wall_verified':True,'parent_uuid':observed['parent_uuid'],
                       'parent_uuid_verified':observed['parent_uuid_verified']})
    pairs=[]
    selected=[row for row in rows if row['type'] in (collision_types or []) and row['uuid'] in bounds]
    for index,a in enumerate(selected):
        for b in selected[index+1:]:
            aa,bb=bounds[a['uuid']],bounds[b['uuid']]
            overlap=[min(aa['max'][i],bb['max'][i])-max(aa['min'][i],bb['min'][i]) for i in range(3)]
            if all(v>0.01 for v in overlap):pairs.append({'a':a['uuid'],'b':b['uuid'],'overlap_mm':overlap,'status':'conservative_aabb_candidate'})
    status='failed' if any(not row['passed'] for row in checks) else 'not_verified' if unverified or not checks else 'passed'
    return {'status':status,'checks':checks,'unverified_checks':unverified,'bounds':bounds,
            'collision_candidates':pairs,'collision_method':'conservative AABB, not exact clash or code-compliance check','computer_use_calls':0}
