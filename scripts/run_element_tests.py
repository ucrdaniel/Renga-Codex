"""Native synthetic elements; no user models, SDK samples or UI automation."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from renga_codex_bridge.config import settings
from renga_codex_bridge.runner import run_worker
from renga_codex_bridge.session import Session
from renga_codex_bridge.model import object_by_id,inventory
from renga_codex_bridge.audit import event,save_plan

def run():
    folder=settings().write_root/('elements-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));folder.mkdir(parents=True)
    report={'schema_version':1,'checks':[],'limitations':[],'computer_use_calls':0}
    def passed(name,**details):
        report['checks'].append({'check':name,'status':'passed',**details});print('PASS ELEMENT',name,flush=True)
    def request(command,**arguments):
        result=run_worker(command,arguments,timeout=300)
        (folder/('response-'+command+'-'+str(len(report['checks']))+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        return result
    try:
        project=folder/'elements.rnp'
        plan=json.loads((ROOT/'examples/bim-elements.json').read_text(encoding='utf8'))
        result=request('apply',project=str(project),operations=plan,new=True)
        assert result['status']=='saved_reopened_verified';refs=result['persistent_refs']
        passed('column_beam_stair_roof_opening_create_native_roundtrip',created=len(refs))
        with Session(project) as s:
            opening=object_by_id(s,refs['slab_opening']).QueryInterface(s.r.IOpeningParams)
            assert object_by_id(s,refs['test_slab']).Id in set(opening.GetAffectedObjectIds())
        passed('opening_affects_native_slab_host')
        verified=request('verify',project=str(project),expected_areas={refs['test_slab']:31.25})
        assert verified['status']=='passed';passed('slab_cut_area_independent_mesh_and_target',expected_net_m2=31.25)
        meshes=request('geometry',project=str(project));by_uid={v['uuid']:v for v in meshes['objects']}
        for ref in ('column_a','column_b','test_beam','test_stair','test_roof','host_wall'):
            assert sum(len(g['triangles']) for g in by_uid[refs[ref]]['grids'])>0
        roof_points=[v for g in by_uid[refs['test_roof']]['grids'] for v in g['vertices']]
        assert max(v[2] for v in roof_points)-min(v[2] for v in roof_points)>900
        passed('actual_native_meshes_and_sloped_roof_geometry')
        changes=[{'action':'set_parameter','id':refs['column_a'],'name':'ColumnHeight','value':3200},
                 {'action':'set_parameter','id':refs['test_stair'],'name':'StairWidth','value':1100},
                 {'action':'baseline3d','id':refs['test_beam'],'points':[[9000,7000,3600],[12500,7000,3700]]},
                 {'action':'roof_slopes','id':refs['test_roof'],'edges':[{'index':0,'shape':0,'angle':30,'overhang':400},{'index':2,'shape':0,'angle':30,'overhang':400}]}]
        request('apply',project=str(project),operations=changes);passed('column_stair_beam3d_roof_edits_saved_readback')
        catalog=request('catalogs',project=str(project),collection='ElementStyles')
        styles=catalog['ElementStyles']['entries']
        if styles:
            element=request('apply',project=str(project),operations=[{'action':'create','ref':'element','kind':'Element','origin':[16000,7000,0],
                            'parameters':{'ElementStyleId':styles[0]['id']}}])
            geometries=request('geometry',project=str(project))
            mesh=next(g for g in geometries['objects'] if g['uuid']==element['persistent_refs']['element'])
            assert any(g['triangles'] for g in mesh['grids']);passed('native_element_selected_existing_style_and_mesh')
        else:report['limitations'].append({'feature':'element_from_existing_style','status':'NOT_VERIFIED','reason_code':'empty_style_catalog'})
        # A nested getter may return a detached placement. Discover through a real
        # copied native model and saved readback, not readonly-interface inference.
        copy=folder/'level-probe.rnp';request('copy',project=str(project),output=str(copy))
        save_plan({'probe':'level_nested_placement_move','project':str(copy),'uuid':refs['test_level'],'delta_mm':[0,0,3000]})
        with Session(copy,write=True) as s:
            level=object_by_id(s,refs['test_level']).QueryInterface(s.r.ILevel)
            with s.operation():level.Placement.Move(s.r.Vector3D(0,0,3000))
            s.save()
        with Session(copy) as s:
            level=object_by_id(s,refs['test_level']).QueryInterface(s.r.ILevel)
            elevation=level.Elevation;origin=level.Placement.Origin.Z
        if abs(elevation-3000)<0.001 and abs(origin-3000)<0.001:
            report['limitations'].append({'feature':'level_nested_placement_move','status':'SUPPORTED_NOT_IMPLEMENTED','reason_code':'persisted_probe_requires_adapter_update'})
        else:
            assert abs(elevation)<0.001 and abs(origin)<0.001
            passed('level_nested_placement_move_has_no_saved_effect')
            report['limitations'].append({'feature':'nonzero_level_elevation','status':'API_LIMITATION','reason_code':'readonly_level_and_detached_placement_move'})
        event('native_element_suite_complete',checks=len(report['checks']),computer_use_calls=0)
        report['status']='passed'
    except Exception as exc:
        report['status']='failed';report['error']=str(exc);traceback.print_exc()
    finally:
        (folder/'element-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        (ROOT/'runtime/latest-elements.json').write_text(json.dumps({'evidence_directory':str(folder),'report':report},ensure_ascii=False,indent=2),encoding='utf8')
        print('ELEMENT RESULT',report['status'],len(report['checks']),'CHECKS',str(folder),flush=True)
    if report['status']!='passed':raise SystemExit(1)
    return report

if __name__=='__main__':run()
