import math
import uuid
from .session import Session
from .model import object_by_id,create,set_parameter,inventory,baseline,parameters,placement,curve_points,verify_filling_host
from .validation import validate_plan,execution_batches
from .audit import event,save_plan
from .orientation import validate_creation_axes,assert_pose_matches
from .room_markers import set_room_marker,assert_room_marker_matches

def matches(actual,expected):
    if isinstance(expected,(int,float)) and not isinstance(expected,bool):
        return actual is not None and math.isclose(float(actual),expected,abs_tol=1e-6)
    return actual==expected

def read_roof_slope_check(s,obj,edges):
    """Read requested slope fields after reopen; parameters are not whole-solid QA."""
    slopes=obj.QueryInterface(s.r.IRoofSlopes);actual=[]
    for edge in edges:
        index=edge['index'];row={'index':index,'shape':slopes.GetRoofEdgeShape(index)}
        if row['shape']!=edge['shape']:raise RuntimeError('Roof edge shape mismatch')
        if 'angle' in edge:
            row['angle']=slopes.GetSlopeAngle(index)
            if not matches(row['angle'],edge['angle']):raise RuntimeError('Roof angle mismatch')
        if 'overhang' in edge:
            row['overhang']=slopes.GetOverhang(index)
            if not matches(row['overhang'],edge['overhang']):raise RuntimeError('Roof overhang mismatch')
        actual.append(row)
    return {'uuid':obj.UniqueIdS.strip('{}').lower(),'edges':actual,'persistence_verified_by_this_reader':True,
            'scope':'requested_native_slope_parameters_not_full_roof_geometry'}

def apply_plan(path,operations,*,new=False):
    validate_plan(operations)
    plan_path=save_plan({'project':str(path),'new':new,'units':'mm','operations':operations})
    refs={};requests={};property_checks={};pose_checks={};curves={};curves3d={};roof_checks={};marker_checks={};host_checks={};native_facing={}
    with Session(path,create=new,write=True) as s:
        def resolve(value):return refs[value] if isinstance(value,str) and value in refs else object_by_id(s,value).Id
        for batch in execution_batches(operations):
            deferred=[]
            beam=next((item for item in batch if item['action']=='create' and item['kind']=='Beam' and item.get('level') is not None),None)
            if beam:
                s.app.OpenViewByEntity(resolve(beam['level']))
                event('activate_owned_native_view',path=str(s.path),reason='beam_construction',computer_use_calls=0,status='provisional')
            with s.operation():
                for item in batch:
                    action=item['action']
                    if action=='create':
                        args={k:v for k,v in item.items() if k not in {'action','ref','kind'}}
                        for key in ('host','level'):
                            if key in args:args[key]=resolve(args[key])
                        requested_parameters=dict(args.get('parameters',{}))
                        if item['kind'] in {'Beam','Stair','Ramp'}:args['parameters']={k:v for k,v in requested_parameters.items() if k==item['kind']+'StyleId'}
                        obj=create(s,item['kind'],**args)
                        if item['kind'] in {'Door','Window'}:
                            host_checks[obj.UniqueIdS]=object_by_id(s,args['host']).UniqueIdS
                            if args.get('native_default_facing'):native_facing[obj.UniqueIdS]={}
                        if item.get('ref'):refs[item['ref']]=obj.Id
                        for name,value in requested_parameters.items():
                            requests[(obj.UniqueIdS,name)]=value
                            if item['kind'] in {'Beam','Stair','Ramp'} and name!=item['kind']+'StyleId':deferred.append((obj.UniqueIdS,name,value))
                        if args.get('host') is not None and item['kind'] in {'Door','Window','Opening'}:
                            requests[(obj.UniqueIdS,'Offset')]=args.get('parameters',{}).get('Offset',args.get('origin',[0,0,0])[2])
                        if args.get('points') is not None:curves[obj.UniqueIdS]=args['points']
                        expected_pose={}
                        if 'origin' in args and item['kind']!='Level':
                            expected_pose['origin']=list(args['origin'])
                            if item['kind'] in {'Door','Window'}:expected_pose['origin'][2]=0
                        if 'x_axis' in args or 'z_axis' in args:
                            expected_pose.update(validate_creation_axes(args.get('x_axis',(1,0,0)),args.get('z_axis',(0,0,1)),kind=item['kind']))
                        if expected_pose:pose_checks[obj.UniqueIdS]=expected_pose
                        continue
                    obj=object_by_id(s,resolve(item['id']));uid=obj.UniqueIdS
                    if action=='set_parameter':
                        set_parameter(s,obj,item['name'],item['value']);requests[(uid,item['name'])]=item['value']
                    elif action=='baseline':baseline(s,obj,item['points'],item.get('closed',False));curves[uid]=item['points']
                    elif action=='baseline3d':
                        if len(item['points'])!=2:raise NotImplementedError('First release supports straight native3D baselines')
                        cs=s.r.Placement3D(s.r.Point3D(0,0,0),s.r.Vector3D(1,0,0),s.r.Vector3D(0,0,1))
                        curve=s.app.Math.CreateLineSegment3D(*(s.r.Point3D(*p) for p in item['points']))
                        obj.QueryInterface(s.r.IBaseline3DObject).SetBaselineInCS(cs,curve)
                        curves3d[uid]=item['points']
                    elif action=='property':
                        manager=s.project.PropertyManager;guid=item['guid']
                        if not manager.IsPropertyRegisteredS(guid):manager.RegisterPropertyS(guid,item['name'],s.r.PropertyType_String)
                        manager.AssignPropertyToTypeS(guid,obj.ObjectTypeS)
                        obj.GetProperties().GetS(guid).SetStringValue(item['value']);property_checks[(uid,guid)]=item['value']
                    elif action=='delete':
                        s.model.DeleteObjectById(obj.Id)
                        refs={k:v for k,v in refs.items() if v!=obj.Id}
                        for table in (requests,property_checks):
                            for key in list(table):
                                if key[0]==uid:del table[key]
                        curves.pop(uid,None);curves3d.pop(uid,None);pose_checks.pop(uid,None);roof_checks.pop(uid,None)
                        marker_checks.pop(uid,None)
                        host_checks.pop(uid,None);native_facing.pop(uid,None)
                    elif action=='room_marker':
                        set_room_marker(s,obj,item['point']);marker_checks[uid]=item['point']
                        event('room_marker_requested',uuid=uid,point=item['point'],status='provisional')
                    elif action=='room_region':
                        room=obj.QueryInterface(s.r.IRoom);point=s.r.Point2D(*item['point'])
                        if room.Automatic:room.ControlPoint=point
                        else:
                            description=room.CalculateRegion(point)
                            if not description or not description.Region:raise RuntimeError('No calculated room region')
                            if description.Region.GetContourCount()!=1:raise NotImplementedError('Room region has holes')
                            obj.QueryInterface(s.r.IBaseline2DObject).SetBaseline(description.Region.GetOuterContour())
                        curves[uid]=None
                    elif action=='move':
                        blocked={'Door','Window','Opening','Rebar','RoutePoint','Room','Level','LinearDimension','Tag','Axis'}
                        kind=next((k for k,v in s.sdk.types.items() if v==obj.ObjectTypeS.upper()),obj.ObjectTypeS)
                        if kind in blocked:raise NotImplementedError('ILevelObject.SetPlacement is not verified for '+kind+'; use native parameter/baseline or explicit recreation')
                        old=placement(s,obj);expected=[a+b for a,b in zip(old['origin'],item['delta'])]
                        native=s.app.Math.CreatePlacement3D(s.r.Point3D(*expected),s.r.Vector3D(*old['x_axis']),s.r.Vector3D(*old['z_axis']))
                        obj.QueryInterface(s.r.ILevelObject).SetPlacement(native);pose_checks[uid]={'origin':expected,'x_axis':old['x_axis'],'z_axis':old['z_axis']}
                    elif action=='roof_slopes':
                        slopes=obj.QueryInterface(s.r.IRoofSlopes)
                        for edge in item['edges']:
                            index=edge['index'];slopes.SetRoofEdgeShape(index,edge['shape'])
                            if 'angle' in edge:slopes.SetSlopeAngle(index,edge['angle'])
                            if 'overhang' in edge:slopes.SetOverhang(index,edge['overhang'])
                        roof_checks[uid]=item['edges']
            if deferred:
                with s.operation():
                    for uid,name,value in deferred:set_parameter(s,object_by_id(s,uid),name,value)
        before=inventory(s);by_uid={row['uuid']:row for row in before}
        persistent={row['uuid'] for row in before}
        ref_uids={key:s.model.GetObjects().GetById(value).UniqueIdS for key,value in refs.items()}
        for (uid,name),value in requests.items():
            key=next((k for k,v in s.sdk.parameters.items() if v.lower()==name.lower()),name)
            actual=by_uid[uid.strip('{}').lower()]['parameters'].get(key,{}).get('value')
            if not matches(actual,value):raise RuntimeError('Native committed parameter mismatch: '+name)
        for uid,requested in list(curves.items()):
            actual=curve_points(s,object_by_id(s,uid))
            if requested is not None:
                requested=requested[:-1] if len(requested)>2 and requested[0]==requested[-1] else requested
                if len(actual)!=len(requested) or not all(matches(a,b) for pa,pb in zip(actual,requested) for a,b in zip(pa,pb)):
                    raise RuntimeError('Requested contour differs from native committed contour; native joining may alter endpoints, inspect before retrying')
            curves[uid]=actual
        for uid,expected_pose in pose_checks.items():assert_pose_matches(expected_pose,placement(s,object_by_id(s,uid)))
        for uid,point in marker_checks.items():assert_room_marker_matches(s,object_by_id(s,uid),point)
        for uid,host_uid in host_checks.items():
            host_observation=verify_filling_host(s,object_by_id(s,uid),host_uid)
            if uid in native_facing:
                native_facing[uid]={'committed_placement':placement(s,object_by_id(s,uid)),
                                    'committed_host_observation':host_observation}
                event('native_default_facing_observed',uuid=uid,mode='native_default',
                      phase='committed',requested_swing_verified=False,**native_facing[uid])
        s.save()
    with Session(path) as reopened:
        after=inventory(reopened);by_uid={row['uuid']:row for row in after}
        if set(by_uid)!=persistent:raise RuntimeError('Object persistent identities changed after reopen')
        for (uid,name),value in requests.items():
            key=next((k for k,v in reopened.sdk.parameters.items() if v.lower()==name.lower()),name)
            actual=by_uid[uid.strip('{}').lower()]['parameters'].get(key,{}).get('value')
            if not matches(actual,value):raise RuntimeError('Saved parameter mismatch: '+name)
        for (uid,guid),value in property_checks.items():
            if object_by_id(reopened,uid).GetProperties().GetS(guid).GetStringValue()!=value:raise RuntimeError('Saved custom property mismatch')
        for uid,expected_pose in pose_checks.items():assert_pose_matches(expected_pose,placement(reopened,object_by_id(reopened,uid)))
        for uid,points in curves.items():
            actual=curve_points(reopened,object_by_id(reopened,uid))
            if len(actual)!=len(points) or not all(matches(a,b) for pa,pb in zip(actual,points) for a,b in zip(pa,pb)):
                raise RuntimeError('Saved contour changed')
        roof_slope_checks=[read_roof_slope_check(reopened,object_by_id(reopened,uid),edges) for uid,edges in roof_checks.items()]
        for roof_check in roof_slope_checks:event('native_roof_slope_parameters_reopened_verified',**roof_check)
        for uid,points in curves3d.items():
            cs=reopened.r.Placement3D(reopened.r.Point3D(0,0,0),reopened.r.Vector3D(1,0,0),reopened.r.Vector3D(0,0,1))
            curve=object_by_id(reopened,uid).QueryInterface(reopened.r.IBaseline3DObject).GetBaselineInCS(cs)
            actual=[[getattr(curve.GetPointOn(t),k) for k in ('X','Y','Z')] for t in (curve.MinParameter,curve.MaxParameter)]
            if not all(matches(a,b) for pa,pb in zip(actual,points) for a,b in zip(pa,pb)):raise RuntimeError('Saved3D baseline differs from requested points')
        markers=[assert_room_marker_matches(reopened,object_by_id(reopened,uid),point) for uid,point in marker_checks.items()]
        for marker in markers:marker['persistence_verified_by_this_reader']=True
        facing_observations=[];saved_hosts={}
        for uid,host_uid in host_checks.items():
            saved_hosts[uid]=verify_filling_host(reopened,object_by_id(reopened,uid),host_uid)
            if uid in native_facing:
                facing_observations.append({'uuid':uid.strip('{}').lower(),'mode':'native_default',
                    **native_facing[uid],'actual_placement':placement(reopened,object_by_id(reopened,uid)),
                    'saved_host_observation':saved_hosts[uid],'requested_swing_verified':False,
                    'requested_origin_verified':uid in pose_checks and 'origin' in pose_checks[uid],
                    'saved_offset_verified':(uid,'Offset') in requests})
                event('native_default_facing_reopened_observed',**facing_observations[-1])
        result={'status':'saved_reopened_verified','room_marker_checks':markers,'roof_slope_checks':roof_slope_checks,'native_facing_observations':facing_observations,
                'filling_host_checks':saved_hosts,'plan':plan_path,'refs':{k:by_uid[v.strip('{}').lower()]['id'] for k,v in ref_uids.items()},
                'persistent_refs':{k:v.strip('{}').lower() for k,v in ref_uids.items()},'objects':after,'computer_use_calls':0}
        event('reopen_verified',path=str(reopened.path),sha256=reopened.initial_sha,objects=len(after),plan=plan_path,computer_use_calls=0)
        return result
