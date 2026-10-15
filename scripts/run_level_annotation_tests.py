"""Actual new-project levels/axes and intrinsic Room marker tests; zero UI automation."""
from datetime import datetime,timezone
import json,os,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from renga_codex_bridge.runner import run_worker
from renga_codex_bridge.config import settings
from renga_codex_bridge.safety import fingerprint
from renga_codex_bridge.ifc_grid_verify import verify_exported_grid
from renga_codex_bridge.session import Session
from renga_codex_bridge.ownership import create_ownership_lease,register_worker_identity,cleanup_after_timeout
from renga_codex_bridge.audit import save_plan


def constructor_probe(target):
    register_worker_identity();rows=[]
    save_plan({'action':'research_annotation_constructors','project':str(target),'contexts':['building','drawing']})
    with Session(target,create=True) as s:
        with s.operation():
            args=s.project.Drawings2.CreateNewEntityArgs();args.TypeIdS=s.sdk.types['Drawing']
            drawing=s.project.Drawings2.Create(args)
        for context,model in [('building',s.model),('drawing',drawing.QueryInterface(s.r.IModel))]:
            for kind in ('Axis','DrawingAxis','LinearDimension','Tag','DrawingElevationMark'):
                with s.operation(model):
                    args=model.CreateNewEntityArgs();args.TypeIdS=s.sdk.types[kind]
                    args.Placement3D=s.r.Placement3D(s.r.Point3D(0,0,0),s.r.Vector3D(1,0,0),s.r.Vector3D(0,0,1))
                    args.Placement2D=s.r.Placement2D(s.r.Point2D(10,10),s.r.Vector2D(1,0))
                    obj=model.CreateObject(args)
                    rows.append({'context':context,'kind':kind,'created':bool(obj),'last_error':s.app.LastError})
                    if obj:raise RuntimeError('Constructor availability changed; inspect bindings before updating coverage')
        s.save()
    with Session(target) as s:
        if s.model.GetObjects().Count!=1:raise RuntimeError('Unexpected annotation created in building model')
    return rows


def bounded_constructor_probe(target):
    lease=create_ownership_lease()
    p=subprocess.Popen([sys.executable,__file__,'--constructor-probe',str(target)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                       text=True,encoding='utf8',env={**os.environ,**lease.environment()})
    identity=lease.observe_worker(p.pid)
    try:out,err=p.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        p.kill();p.communicate(timeout=5);cleanup_after_timeout(lease,identity);raise
    if p.returncode:raise RuntimeError(err)
    return json.loads(out)


def run():
    folder=settings().write_root/('levels-annotations-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));folder.mkdir(parents=True)
    report={'schema_version':1,'checks':[],'computer_use_calls':0,'limitations':[
        {'feature':'existing_project_level_and_grid_merge','status':'NOT_VERIFIED','reason_code':'new_project_import_only'},
        {'feature':'new_associative_dimensions_and_tags','status':'API_LIMITATION','reason_code':'native_model_and_drawing_factories_reject_types'}]}
    def passed(name,**details):report['checks'].append({'check':name,'status':'passed',**details});print('PASS LEVELS',name,flush=True)
    def request(command,**arguments):
        result=run_worker(command,arguments,timeout=300)
        (folder/('response-'+str(len(report['checks']))+'-'+command+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        return result
    try:
        project=folder/'levels-grid.rnp'
        levels=[{'name':'Этаж 1','elevation_mm':0},{'name':'Этаж 2','elevation_mm':3000},{'name':'Кровля','elevation_mm':6000}]
        grid={'x':[{'name':'1','position_mm':0},{'name':'2','position_mm':3000},{'name':'3','position_mm':9000}],
              'y':[{'name':'А','position_mm':0},{'name':'Б','position_mm':6000}], 'bounds_mm':[-1000,-1000,10000,7000]}
        bootstrap=request('create_levels',project=str(project),levels=levels,grid=grid)
        assert bootstrap['status']=='saved_reopened_verified' and bootstrap['only_native_levels_and_axes']
        assert bootstrap['removed_import_carriers']==3 and len(bootstrap['levels'])==3 and len(bootstrap['axes'])==5
        passed('native_nonzero_levels_and_axes_clean_saved_project',levels=3,axes=5)
        assert bootstrap['grid_verification']['status']=='passed' and bootstrap['grid_verification']['axis_count']==5
        passed('saved_axis_coordinates_via_fresh_native_ifc_export',x_steps_mm=[3000,6000],y_step_mm=6000)
        before=fingerprint(project)
        try:request('create_levels',project=str(project),levels=levels)
        except RuntimeError:pass
        else:raise AssertionError('Existing target overwritten')
        assert fingerprint(project)==before;passed('bootstrap_refuses_existing_project_unchanged')
        upper=next(row for row in bootstrap['levels'] if row['elevation_mm']==3000)
        wall=request('apply',project=str(project),operations=[{'action':'create','ref':'upper_wall','kind':'Wall','level':upper['uuid'],
            'points':[[0,0],[6000,0]],'parameters':{'WallHeight':2800,'WallThickness':200}}])
        uid=wall['persistent_refs']['upper_wall'];geometry=request('geometry',project=str(project))
        item=next(o for o in geometry['objects'] if o['uuid']==uid)
        zs=[v[2] for g in item['grids'] for v in g['vertices']]
        assert abs(min(zs)-3000)<1e-6 and abs(max(zs)-5800)<1e-6
        passed('native_wall_hosted_on_imported_3000_level',bottom_mm=min(zs),top_mm=max(zs))
        axis=next(row for row in bootstrap['axes'] if row['name']=='2')
        request('apply',project=str(project),operations=[{'action':'set_parameter','id':axis['uuid'],'name':'GridLineName','value':'2b'}])
        grid['x'][1]['name']='2b'
        exported=request('ifc',project=str(project),output=str(folder/'renamed-axis.ifc'))
        assert verify_exported_grid(Path(exported['output']).read_text(encoding='utf-8-sig'),grid)['status']=='passed'
        passed('native_axis_name_edit_reflected_in_fresh_export')
        before=fingerprint(project)
        try:request('apply',project=str(project),operations=[{'action':'set_parameter','id':upper['uuid'],'name':'LevelElevation','value':4500}])
        except RuntimeError as error:assert 'Read-only' in str(error)
        else:raise AssertionError('Readonly direct level setter accepted')
        assert fingerprint(project)==before;passed('direct_level_setter_refused_disk_unchanged')
        extra=request('create_levels',project=str(folder/'negative-fractional.rnp'),levels=[{'name':"Basement O'Brien",'elevation_mm':-3000},
            {'name':'Ground','elevation_mm':0},{'name':'Верхний','elevation_mm':4500.5}])
        assert sorted(r['elevation_mm'] for r in extra['levels'])==[-3000,0,4500.5]
        passed('negative_fractional_levels_unicode_and_apostrophe_names')
        marker_project=folder/'room-markers.rnp';plan=json.loads((ROOT/'examples/rectangle.json').read_text(encoding='utf8'))
        room=request('apply',project=str(marker_project),operations=plan,new=True);room_uid=room['persistent_refs']['room']
        marker=request('apply',project=str(marker_project),operations=[{'action':'room_marker','id':room_uid,'point':[2345,1678]}])
        assert marker['room_marker_checks'][0]['point']==[2345,1678] and marker['room_marker_checks'][0]['persistence_verified_by_this_reader']
        passed('intrinsic_room_marker_global_xy_saved_readback')
        inspection=request('inspect',project=str(marker_project),kind='Room')
        assert inspection['objects'][0]['uuid']==room_uid and inspection['objects'][0]['room_marker_mm']==[2345,1678]
        passed('independent_reopen_room_marker_readback')
        before=fingerprint(marker_project)
        try:request('apply',project=str(marker_project),operations=[{'action':'room_marker','id':room['persistent_refs']['wall_south'],'point':[1000,1000]}])
        except RuntimeError as error:assert 'genuine native Room' in str(error)
        else:raise AssertionError('Wall accepted as Room marker')
        assert fingerprint(marker_project)==before;passed('non_room_marker_rejected_original_unchanged')
        rows=bounded_constructor_probe(folder/'constructor-limits.rnp')
        (folder/'native-constructor-probes.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
        assert len(rows)==10 and not any(r['created'] for r in rows)
        passed('native_building_and_drawing_factories_reject_annotation_types',probes=10)
        report['status']='passed'
    except Exception as error:report['status']='failed';report['error']=str(error);raise
    finally:
        (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        (ROOT/'runtime/latest-levels-annotations.json').write_text(json.dumps({'evidence_directory':str(folder),'report':report},ensure_ascii=False,indent=2),encoding='utf8')
        print('LEVELS RESULT',report['status'],len(report['checks']),'CHECKS',folder,flush=True)


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--constructor-probe':print(json.dumps(constructor_probe(Path(sys.argv[2]))))
    else:run()
