"""Typed native model operations. All dimensions are explicit millimeters."""
import math
import uuid
from .audit import event
from .orientation import DEFAULT_X_AXIS,DEFAULT_Z_AXIS,validate_creation_axes,validate_wall_host_orientation

_AXIS_UNSET=object()

def creation_axes(kind,x_axis=_AXIS_UNSET,z_axis=_AXIS_UNSET,*,native_default_facing=False):
    """An explicit native default makes no promise about a filling's outer side."""
    if not isinstance(native_default_facing,bool):raise ValueError('native_default_facing must be a strict boolean')
    if native_default_facing:
        if not isinstance(kind,str) or kind not in {'Door','Window'}:raise ValueError('native_default_facing is only available for Door/Window')
        if x_axis is not _AXIS_UNSET or z_axis is not _AXIS_UNSET:
            raise ValueError('native_default_facing cannot accompany explicit x_axis/z_axis')
    return validate_creation_axes(DEFAULT_X_AXIS if x_axis is _AXIS_UNSET else x_axis,
                                  DEFAULT_Z_AXIS if z_axis is _AXIS_UNSET else z_axis,kind=kind)

def parameter_value(parameter):
    if not parameter.HasValue:return None
    method={1:'GetBoolValue',2:'GetIntValue',3:'GetDoubleValue',4:'GetStringValue'}.get(parameter.ValueType)
    if method is None:raise NotImplementedError('Unsupported native parameter type')
    return getattr(parameter,method)()

def parameter_definition_metadata(s,guid,parameter):
    """Cache definition-only data on this Session, never native value/state.

    IParameterDefinition exposes the description/type/reference/enum metadata.
    These describe the parameter GUID within this session's project/locale;
    IsReadOnly, HasValue, ValueType and the actual value are read on each visit.
    Cache plain data only, avoiding long-lived COM interface references.
    """
    cache=getattr(s,'_parameter_definition_metadata_cache',None)
    if cache is None:
        cache={};s._parameter_definition_metadata_cache=cache
    key=guid.upper()
    if key not in cache:
        definition=parameter.Definition
        cache[key]={'text':definition.Text,'definition_name':definition.Name,
                    'parameter_type':definition.ParameterType,'referenced_entity_type':definition.ReferencedEntityTypeS,
                    'enumeration_texts':tuple(definition.EnumerationItemTexts or [])}
    stored=cache[key]
    # Return an independent list/dict: caller mutation must not poison later
    # observations or silently alter another object's reported definition.
    return {**stored,'enumeration_texts':list(stored['enumeration_texts'])}

def parameters(s,entity):
    pc=entity.GetParameters() if hasattr(entity,'GetParameters') else entity.QueryInterface(s.r.IParameterContainer)
    if not pc:return {}
    result={}
    identifiers=pc.GetIds();names={v:k for k,v in s.sdk.parameters.items()}
    for i in range(identifiers.Count):
        guid=identifiers.GetS(i);name=names.get(guid.upper(),guid)
        p=pc.GetS(guid);definition=parameter_definition_metadata(s,guid,p)
        result[name]={'guid':guid,'value':parameter_value(p),'has_value':p.HasValue,
                      'readonly':p.IsReadOnly,'type':p.ValueType,**definition}
    return result

def set_parameter(s,entity,name,value):
    pc=entity.GetParameters() if hasattr(entity,'GetParameters') else entity.QueryInterface(s.r.IParameterContainer)
    guid=s.sdk.parameters.get(name,name)
    if not pc or not pc.ContainsS(guid):raise ValueError('Parameter absent: '+name)
    p=pc.GetS(guid)
    if p.IsReadOnly:raise ValueError('Read-only native parameter: '+name)
    if p.ValueType==1 and not isinstance(value,bool):raise ValueError('Boolean parameter requires bool')
    if p.ValueType==2 and (not isinstance(value,int) or isinstance(value,bool)):raise ValueError('Integer parameter requires int')
    if p.ValueType==3 and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value)):raise ValueError('Double parameter requires finite number')
    if p.ValueType==4 and not isinstance(value,str):raise ValueError('String parameter requires string')
    getattr(p,{1:'SetBoolValue',2:'SetIntValue',3:'SetDoubleValue',4:'SetStringValue'}[p.ValueType])(value)
    event('set_parameter_requested',uuid=entity.UniqueIdS,parameter=name,value=value,status='provisional')

def _cache_object_identity(s,obj):
    """Remember plain identities only; every later hit validates native state."""
    cache=getattr(s,'_object_id_cache',None)
    if cache is None:
        cache={};s._object_id_cache=cache
    cache[str(uuid.UUID(obj.UniqueIdS.strip('{}')))]=obj.Id

def object_by_id(s,identifier):
    if isinstance(identifier,int):
        obj=s.model.GetObjects().GetById(identifier)
        if not obj:raise KeyError(identifier)
        return obj
    target=str(uuid.UUID(identifier.strip('{}')))
    objs=s.model.GetObjects()
    cache=getattr(s,'_object_id_cache',None)
    if cache is not None and target in cache:
        obj=objs.GetById(cache[target])
        if obj and str(uuid.UUID(obj.UniqueIdS.strip('{}')))==target:return obj
    # Numeric IDs can move on SaveAs or be reused after deletion. Rebuild from
    # the current model on a miss/stale hit; do not retain COM objects or negative
    # results. This also handles a Session whose model has been reopened/replaced.
    cache={}
    for i in range(objs.Count):
        obj=objs.GetByIndex(i)
        cache[str(uuid.UUID(obj.UniqueIdS.strip('{}')))]=obj.Id
    s._object_id_cache=cache
    if target in cache:
        obj=objs.GetById(cache[target])
        if obj and str(uuid.UUID(obj.UniqueIdS.strip('{}')))==target:return obj
    raise KeyError(identifier)

def baseline(s,obj,points,closed=False):
    pts=[s.r.Point2D(*p) for p in points]
    if closed:
        if points[-1]==points[0]:pts.pop()
        pts.append(pts[0])
    segments=[s.app.Math.CreateLineSegment2D(a,b) for a,b in zip(pts,pts[1:])]
    curve=segments[0] if len(segments)==1 else s.app.Math.CreateCompositeCurve2D(segments)
    obj.QueryInterface(s.r.IBaseline2DObject).SetBaseline(curve)

def curve_points(s,obj):
    if obj.ObjectTypeS.upper()==s.sdk.types['Room'] and obj.QueryInterface(s.r.IRoom).Automatic:
        room=obj.QueryInterface(s.r.IRoom)
        description=room.CalculateRegion(room.ControlPoint)
        if not description or not description.Region:raise RuntimeError('Automatic room has no calculated region')
        if description.Region.GetContourCount()!=1:raise NotImplementedError('Automatic room with internal holes needs multiple-contour verification')
        curve=description.Region.GetOuterContour()
    else:curve=obj.QueryInterface(s.r.IBaseline2DObject).GetBaseline()
    try:
        poly=curve.GetInterfaceByName('IPolyCurve2D').QueryInterface(s.r.IPolyCurve2D)
        points=[[poly.GetSegment(i).GetBeginPoint().X,poly.GetSegment(i).GetBeginPoint().Y] for i in range(poly.GetSegmentCount())]
        end=poly.GetSegment(poly.GetSegmentCount()-1).GetEndPoint()
        if not points or any(abs(a-b)>1e-6 for a,b in zip(points[0],[end.X,end.Y])):points.append([end.X,end.Y])
        return points
    except Exception:
        return [[curve.GetBeginPoint().X,curve.GetBeginPoint().Y],[curve.GetEndPoint().X,curve.GetEndPoint().Y]]

def create(s,kind,*,points=None,closed=False,origin=(0,0,0),host=None,level=None,parameters=None,x_axis=_AXIS_UNSET,z_axis=_AXIS_UNSET,native_default_facing=False):
    axes=creation_axes(kind,x_axis,z_axis,native_default_facing=native_default_facing)
    if kind not in s.sdk.types:raise ValueError('Unknown SDK entity type: '+kind)
    if kind in {'Axis','LinearDimension','Tag','DrawingAxis'}:
        raise NotImplementedError('No verified public constructor/feature binding for '+kind+'; inspect capabilities')
    if kind=='Level' and any(origin):raise NotImplementedError('Nonzero Level origin is ignored by the verified API')
    values=dict(parameters or {})
    if kind in {'Beam','Element'} and (isinstance(values.get(kind+'StyleId'),bool) or not isinstance(values.get(kind+'StyleId'),int) or values[kind+'StyleId']<=0):
        raise ValueError(kind+' requires an inspected existing '+kind+'StyleId')
    args=s.model.CreateNewEntityArgs();args.TypeIdS=s.sdk.types[kind]
    args.Placement3D=s.r.Placement3D(s.r.Point3D(*origin),s.r.Vector3D(*axes['x_axis']),s.r.Vector3D(*axes['z_axis']))
    if kind+'StyleId' in values:args.StyleId=values.pop(kind+'StyleId')
    if host is not None:args.HostObjectId=object_by_id(s,host).Id
    elif level is not None:args.HostObjectId=object_by_id(s,level).Id
    if kind in {'Door','Window'}:
        if host is None:raise ValueError('Door/Window require an inspected Wall host')
        wall=object_by_id(s,host)
        if wall.ObjectTypeS.upper()!=s.sdk.types['Wall']:raise ValueError('Door/Window host must be a Wall')
        cs=s.r.Placement2D(s.r.Point2D(0,0),s.r.Vector2D(1,0))
        curve=wall.QueryInterface(s.r.IBaseline2DObject).GetBaselineInCS(cs)
        if curve.Curve2DType!=s.r.Curve2DType_LineSegment:raise NotImplementedError('Hosted-side placement currently requires a straight Wall')
        a=curve.GetBeginPoint();b=curve.GetEndPoint()
        if not native_default_facing:validate_wall_host_orientation(axes['x_axis'],axes['z_axis'],[b.X-a.X,b.Y-a.Y,0])
    obj=s.model.CreateObject(args)
    if not obj:raise RuntimeError('Native CreateObject failed: '+kind+'; LastError='+str(s.app.LastError))
    _cache_object_identity(s,obj)
    if points is not None:baseline(s,obj,points,closed)
    if host is not None and kind in {'Door','Window','Opening'}:set_parameter(s,obj,'Offset',origin[2])
    for name,value in values.items():set_parameter(s,obj,name,value)
    event('create_object_requested',kind=kind,uuid=obj.UniqueIdS,status='provisional')
    return obj

def verify_filling_host(s,obj,host_uuid):
    """Check the inspected host's persistent identity against actual native cuts.

    A stored constructor argument is not saved-output evidence. A nonempty
    exposed ParentObjectUniqueId additionally has to agree with the same wall.
    """
    host=object_by_id(s,host_uuid)
    if host.ObjectTypeS.upper()!=s.sdk.types['Wall']:raise RuntimeError('Saved filling host is not a native Wall')
    if obj.ObjectTypeS.upper()==s.sdk.types['Door']:interface=s.r.IDoorParams
    elif obj.ObjectTypeS.upper()==s.sdk.types['Window']:interface=s.r.IWindowParams
    else:raise ValueError('Filling host verification requires Door/Window')
    affected=set(obj.QueryInterface(interface).GetAffectedObjectIds() or [])
    if host.Id not in affected:raise RuntimeError('Saved filling no longer affects the requested Wall host')
    parent_guid=s.sdk.parameters.get('ParentObjectUniqueId')
    parent=None;container=obj.GetParameters()
    if parent_guid and container and container.ContainsS(parent_guid):
        parameter=container.GetS(parent_guid)
        if parameter.HasValue:
            value=parameter.GetStringValue()
            if value:
                parent=str(uuid.UUID(value.strip('{}')))
                if parent!=str(uuid.UUID(host_uuid.strip('{}'))):raise RuntimeError('Saved filling ParentObjectUniqueId differs from requested Wall')
    return {'host_uuid':str(uuid.UUID(host.UniqueIdS.strip('{}'))),'affected_wall_verified':True,
            'parent_uuid':parent,'parent_uuid_verified':parent is not None}

def placement(s,obj):
    p=obj.QueryInterface(s.r.ILevelObject).GetPlacement()
    return {'origin':[p.Origin.X,p.Origin.Y,p.Origin.Z],
            'x_axis':[p.AxisX.X,p.AxisX.Y,p.AxisX.Z],'z_axis':[p.AxisZ.X,p.AxisZ.Y,p.AxisZ.Z]}

def inventory(s,*,details=True):
    objects=s.model.GetObjects();names={v:k for k,v in s.sdk.types.items()};rows=[]
    for i in range(objects.Count):
        obj=objects.GetByIndex(i)
        row={'id':obj.Id,'uuid':obj.UniqueIdS.strip('{}').lower(),'type':names.get(obj.ObjectTypeS.upper(),obj.ObjectTypeS),
             'type_guid':obj.ObjectTypeS,'name':obj.Name,'parameters':{},'quantities':{}}
        if details:
            row['parameters']=parameters(s,obj)
            qc=obj.GetQuantities()
            for key,guid in s.sdk.quantities.items():
                if not qc or not qc.ContainsS(guid):continue
                q=qc.GetS(guid)
                if not q.HasValue():continue
                if q.Type==s.r.QuantityType_Area:row['quantities'][key]={'value':q.AsArea(s.r.AreaUnit_Meters2),'unit':'m2'}
                elif q.Type==s.r.QuantityType_Length:row['quantities'][key]={'value':q.AsLength(s.r.LengthUnit_Millimeters),'unit':'mm'}
                elif q.Type==getattr(s.r,'QuantityType_Volume',None):row['quantities'][key]={'value':q.AsVolume(s.r.VolumeUnit_Meters3),'unit':'m3'}
                else:row['quantities'][key]={'text':q.Text,'type':q.Type}
            if row['type']=='Room':
                room=obj.QueryInterface(s.r.IRoom);row['automatic']=room.Automatic
                marker=room.MarkerPosition;row['room_marker_mm']=[marker.X,marker.Y]
            if row['type']=='Level':
                level=obj.QueryInterface(s.r.ILevel)
                row['level']={'name':level.LevelName,'elevation_mm':level.Elevation,'origin_z_mm':level.Placement.Origin.Z}
        rows.append(row)
    return rows
