"""Real installed-Renga test suite. Every file is disposable and locally retained.

No vendor samples, private fixtures or Computer Use are executed. Public evidence
contains aggregate outcomes, not user paths, BIM files or SDK-generated artifacts.
"""
from pathlib import Path
from datetime import datetime,timezone
import json
import os
import sys
import subprocess
import uuid
import shutil
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from renga_codex_bridge.config import settings
from renga_codex_bridge.safety import fingerprint
from renga_codex_bridge.session import Session
from renga_codex_bridge.model import inventory,placement
from renga_codex_bridge.documentation import snapshot
from renga_codex_bridge.runner import run_worker

def run():
    if sys.platform!='win32':raise RuntimeError('Actual Renga integration requires Windows')
    folder=settings().write_root/('run-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));folder.mkdir(parents=True)
    report={'schema_version':1,'bridge_version':'0.2.0','python':sys.version.split()[0],
            'platform':'Windows x64','computer_use_calls':0,'checks':[],'limitations':[]}
    def passed(name,**values):
        report['checks'].append({'check':name,'status':'passed',**values});print('PASS',name,flush=True)
    def request(command,**arguments):
        value=run_worker(command,arguments,timeout=300)
        (folder/('response-'+command+'-'+uuid.uuid4().hex+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
        return value
    def choose(collection,needle=None):
        entries=catalog[collection]['entries']
        if needle:
            match=next((v for v in entries if needle.replace('А','A')==v['name'].replace('А','A')),None)
            if match:return match['id']
            raise RuntimeError('Required catalog name not found: '+collection+' / '+needle)
        if not entries:raise RuntimeError('Native catalog is empty: '+collection)
        return entries[0]['id']
    try:
        doctor=request('doctor');report['renga_version']=doctor['version'];report['sdk_api']='2.50'
        assert doctor['isolated'] and doctor['apartment']=='STA';passed('owned_sta_connection')
        project=folder/'model.rnp'
        plan=json.loads((ROOT/'examples/rectangle.json').read_text(encoding='utf8'))
        result=request('apply',project=str(project),operations=plan,new=True)
        refs=result['persistent_refs'];assert result['status']=='saved_reopened_verified'
        passed('create_wall_floor_manual_room_save_close_reopen')
        metadata=request('inspect',project=str(project),limit=1000)['objects']
        assert all('uuid' in row for row in metadata)
        assert any(p['enumeration_texts'] for row in metadata for p in row['parameters'].values())
        assert any(p['has_value'] is False for row in metadata for p in row['parameters'].values())
        passed('full_parameter_ids_definitions_enums_has_value')
        assert next(row for row in metadata if row['type']=='Floor')['quantities']['NetVolume']['unit']=='m3'
        passed('native_quantities_area_length_volume_units')
        catalog=request('catalogs',project=str(project))
        assert catalog['WindowStyles']['entries'] and catalog['DoorStyles']['entries'];passed('native_style_material_documentation_catalogs')
        level=next(row for row in metadata if row['type']=='Level')
        window_style=choose('WindowStyles');door_style=choose('DoorStyles')
        modifications=[{'action':'set_parameter','id':refs['wall_south'],'name':'WallHeight','value':3300},
            {'action':'set_parameter','id':refs['wall_south'],'name':'WallThickness','value':240},
            {'action':'property','id':refs['room'],'guid':'{94B01F97-3D89-4AB6-8775-70E1C6BC329F}',
             'name':'Bridge test assignment','value':'TEST-01'},
            {'action':'create','ref':'window','kind':'Window','host':refs['wall_south'],'origin':[1500,0,900],
             'parameters':{'WindowStyleId':window_style,'WindowWidth':1200,'WindowHeight':1400}},
            {'action':'create','ref':'door','kind':'Door','host':refs['wall_south'],'origin':[4000,0,0],
             'parameters':{'DoorStyleId':door_style,'DoorWidth':900,'DoorHeight':2100}},
            {'action':'create','ref':'level','kind':'Level','parameters':{'LevelName':'API test level'}}]
        change=request('apply',project=str(project),operations=modifications)
        refs.update(change['persistent_refs']);passed('edit_parameters_string_property_full_door_window_level_zero_reopen')
        with Session(project) as native:
            wall=native.model.GetObjects().GetById(next(v['id'] for v in inventory(native) if v['uuid']==refs['wall_south']))
            dependents=set(wall.QueryInterface(native.r.IHostObject).GetDependentObjectIds())
            assert change['refs']['window'] in dependents and change['refs']['door'] in dependents
            window=native.model.GetObjects().GetById(change['refs']['window']);point=window.QueryInterface(native.r.ILevelObject).GetPlacement().Origin
            assert abs(point.X-1500)<0.01 and abs(point.Y)<0.01
        passed('hosted_fillings_native_host_and_xy_offset')
        request('apply',project=str(project),operations=[{'action':'room_region','id':refs['room'],'point':[3000,2000]}])
        verified=request('verify',project=str(project),expected_areas={refs['floor']:24.0},collision_types=['Element'])
        assert verified['status']=='passed' and len(verified['checks'])>=3;passed('room_region_and_independent_native_mesh_areas',area_checks=len(verified['checks']))
        before=fingerprint(project)
        try:request('apply',project=str(project),operations=[{'action':'set_parameter','id':refs['wall_south'],'name':'WallHeight','value':9999},
                                                           {'action':'set_parameter','id':refs['wall_south'],'name':'ObjectName','value':'rollback'}])
        except RuntimeError:assert fingerprint(project)==before;passed('undo_rollback_preserves_disk_file')
        else:raise AssertionError('Readonly field was accepted')
        try:request('apply',project=str(project),operations=[],new=True)
        except RuntimeError:assert fingerprint(project)==before;passed('new_cannot_overwrite_existing_file')
        else:raise AssertionError('new overwrite accepted')
        outside=folder.parent.parent/'forbidden-outside.rnp'
        try:request('apply',project=str(outside),operations=[],new=True)
        except RuntimeError:assert not outside.exists();passed('write_root_escape_refused')
        else:raise AssertionError('Outside write root accepted')
        disposable=folder/'delete.rnp';shutil.copy2(project,disposable)
        deletion=request('apply',project=str(disposable),operations=[{'action':'delete','id':refs['window']}])
        assert refs['window'] not in {v['uuid'] for v in deletion['objects']};passed('delete_native_object_reopen')
        copy=request('copy',project=str(project),output=str(folder/'copy.rnp'));assert copy['source_unchanged'];passed('project_copy_reopen')
        save_as=request('save_as',project=str(project),output=str(folder/'save-as.rnp'));assert save_as['source_unchanged'];passed('native_save_as_persistent_uuid_roundtrip')
        preview=request('preview_copy',project=str(project),output=str(folder/'preview.rnp'),
                        operations=[{'action':'set_parameter','id':refs['wall_south'],'name':'WallHeight','value':3450}])
        assert preview['source_unchanged'] and fingerprint(project)==before;passed('proposed_changes_on_disposable_copy')
        moving=folder/'moving.rnp';shutil.copy2(project,moving)
        request('apply',project=str(moving),operations=[{'action':'move','id':refs['floor'],'delta':[1000,0,0]}])
        with Session(moving) as native:
            obj=next(native.model.GetObjects().GetByIndex(i) for i in range(native.model.GetObjects().Count) if native.model.GetObjects().GetByIndex(i).UniqueIdS.strip('{}').lower()==refs['floor'])
            assert abs(placement(native,obj)['origin'][0]-1000)<0.01
        passed('typed_placement_move_saved_readback')
        try:request('apply',project=str(project),operations=[{'action':'create','kind':'Level','origin':[0,0,3000]}])
        except RuntimeError:passed('nonzero_level_constructor_rejected')
        else:raise AssertionError('Ignored elevation accepted')
        metadata=request('set_project_info',project=str(project),values={'Code':'BRIDGE-TEST','Name':'API acceptance','Stage':'TEST','Description':'Synthetic disposable project'})
        assert metadata['status']=='saved_reopened_verified';passed('project_info_four_fields_uuid_native_roundtrip')
        drawing_specs=[{'parameters':{'EntityName':f'API plan {n}','PageFormatId':choose('PageFormatStyles','A3'),
             'PageOrientation':2,'LayoutStyleId':choose('LayoutStyles'),'TopicId':choose('Topics','АР')},
            'level_id':level['id'],'scale_id':choose('Scales','1:100'),'section_mm':1500,
            'title':f'API plan {n} (1:100)','schedule_id':choose('Schedules')} for n in (1,2)]
        drawings=request('documents',project=str(project),drawings=drawing_specs)
        assert len(drawings['created_uuids'])==2;passed('two_native_drawings_linked_views_schedules_text_reopen')
        pdf=request('pdf',project=str(project),output=str(folder/'plans.pdf'),drawing_uuids=drawings['created_uuids'])
        from pypdf import PdfReader
        pages=PdfReader(pdf['output']).pages;assert len(pages)==2
        assert all(float(page.mediabox.width)>float(page.mediabox.height) for page in pages)
        assert all(abs(float(page.mediabox.width)-420/25.4*72)<2 for page in pages)
        assert all(abs(float(page.mediabox.height)-297/25.4*72)<2 for page in pages)
        assert all('API plan' in page.extract_text() for page in pages)
        passed('native_two_page_pdf_a3_landscape',pages=2)
        ifc=request('ifc',project=str(project),output=str(folder/'model.ifc'))
        assert ifc['bytes']>1000;passed('native_ifc4_export')
        try:
            render_result=request('render',project=str(project),output=str(folder/'render.png'),entity_id=level['id'])
            assert Path(render_result['output']).stat().st_size>1000
            passed('native_view_render_without_computer_use')
        except RuntimeError as exc:
            report['limitations'].append({'feature':'native_view_render','status':'NOT_VERIFIED','reason':str(exc)})
            print('NOT_VERIFIED native_view_render',str(exc),flush=True)
        report['status']='passed';report['project_sha256']=fingerprint(project)
    except Exception as exc:
        report['status']='failed';report['error']=str(exc);traceback.print_exc()
    finally:
        (folder/'live-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        (ROOT/'runtime').mkdir(exist_ok=True)
        (ROOT/'runtime/latest-live.json').write_text(json.dumps({'evidence_directory':str(folder),'report':report},ensure_ascii=False,indent=2),encoding='utf8')
        print('LIVE RESULT',report['status'],len(report['checks']),'CHECKS',str(folder),flush=True)
    if report['status']!='passed':raise SystemExit(1)
    return report

if __name__=='__main__':run()
