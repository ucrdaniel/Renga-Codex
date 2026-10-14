"""Validate plans without COM or SDK; native compatibility is checked separately."""
import math
import uuid
from .planning import polygon_area
from .orientation import validate_creation_axes

MODEL_ACTIONS={'create','set_parameter','baseline','baseline3d','property','delete','move','room_region','roof_slopes'}
def finite_vector(value,length):
    if not isinstance(value,(list,tuple)) or len(value)!=length or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in value):
        raise ValueError(f'Expected {length} finite coordinates')

def validate_plan(operations):
    if not isinstance(operations,list) or len(operations)>10000:raise ValueError('Plan must be a list of at most 10000 operations')
    refs=set()
    for item in operations:
        if not isinstance(item,dict) or not isinstance(item.get('action'),str) or item['action'] not in MODEL_ACTIONS:raise ValueError('Unknown operation action')
        action=item['action']
        if 'origin' in item:finite_vector(item['origin'],3)
        def valid_id(value):
            if isinstance(value,bool):return False
            if isinstance(value,int):return value>0
            if not isinstance(value,str) or not value.strip():return False
            if value in refs:return True
            try:uuid.UUID(value.strip('{}'));return True
            except ValueError:return False
        if action=='create':
            if not isinstance(item.get('kind'),str):raise ValueError('create.kind required')
            validate_creation_axes(item.get('x_axis',(1,0,0)),item.get('z_axis',(0,0,1)),kind=item['kind'])
            for key in ('host','level'):
                if key in item and not valid_id(item[key]):raise ValueError('Host/level must refer to an earlier ref or inspected ID/UUID')
            ref=item.get('ref')
            if ref is not None:
                if not isinstance(ref,str) or not ref or ref in refs:raise ValueError('Invalid or duplicate ref')
                refs.add(ref)
            if item['kind']=='Level' and any(v!=0 for v in item.get('origin',[0,0,0])):
                raise NotImplementedError('Nonzero Level origin is not supported by the verified API')
        elif 'id' not in item or not valid_id(item['id']):raise ValueError('Usable operation id required')
        if action=='move' and 'delta' not in item:raise ValueError('move requires delta')
        if action in {'baseline','baseline3d'} and 'points' not in item:raise ValueError('baseline requires points')
        if 'delta' in item:finite_vector(item['delta'],3)
        if 'point' in item:finite_vector(item['point'],2)
        if 'points' in item:
            points=item['points'];dimension=3 if action=='baseline3d' else 2
            if not isinstance(points,list) or len(points)<2:raise ValueError('At least two points required')
            for point in points:finite_vector(point,dimension)
            if item.get('closed') and (len(points)<3 or polygon_area(points)<=1e-12):raise ValueError('Closed contour needs nonzero area')
        parameters=item.get('parameters',{})
        if not isinstance(parameters,dict):raise ValueError('parameters must be an object')
        for key,value in parameters.items():
            if not isinstance(key,str) or not isinstance(value,(str,int,float,bool)):raise ValueError('Parameter names and primitive values required')
            if isinstance(value,float) and not math.isfinite(value):raise ValueError('Non-finite parameter')
        if action=='set_parameter':
            if not isinstance(item.get('name'),str) or not item['name'].strip() or 'value' not in item:raise ValueError('set_parameter needs name/value')
            value=item['value']
            if not isinstance(value,(str,int,float,bool)) or isinstance(value,float) and not math.isfinite(value):raise ValueError('Invalid parameter value')
        if action=='property':uuid.UUID(item['guid'].strip('{}'))
        if action=='room_region' and 'point' not in item:raise ValueError('room_region requires a control point')
        if action=='roof_slopes':
            if not isinstance(item.get('edges'),list) or not item['edges']:raise ValueError('Explicit roof edges required')
            seen=set()
            for edge in item['edges']:
                if not isinstance(edge,dict) or isinstance(edge.get('index'),bool) or not isinstance(edge.get('index'),int) or edge['index']<0 or edge['index'] in seen:raise ValueError('Unique nonnegative roof edge index required')
                seen.add(edge['index'])
                if isinstance(edge.get('shape'),bool) or not isinstance(edge.get('shape'),int):raise ValueError('Roof edge shape requires native integer enum')
                for name in ('angle','overhang'):
                    if name in edge and (isinstance(edge[name],bool) or not isinstance(edge[name],(int,float)) or not math.isfinite(edge[name])):raise ValueError('Finite roof '+name+' required')
                if 'angle' in edge and not 0<edge['angle']<90:raise ValueError('Roof slope angle must be between 0 and 90 degrees')
                if 'overhang' in edge and edge['overhang']<0:raise ValueError('Roof overhang must be nonnegative')
    return {'valid':True,'operation_count':len(operations),'native_execution_performed':False,
            'note':'Structural validation only; native compatibility and saved output are checked during apply.'}
