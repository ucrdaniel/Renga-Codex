"""One request per process: all native calls execute on this process's STA."""
import sys
sys.coinit_flags=2
import json
import shutil
from pathlib import Path
from collections import Counter
from .session import Session
from .model import inventory
from .operations import apply_plan
from .validation import validate_plan
from .geometry import extract,verify
from .catalogs import catalogs
from .documentation import snapshot,create_plans,export_pdf,export_ifc,render
from .safety import checked_path,fingerprint
from .audit import event
from .ownership import register_worker_identity
from .project_info import read_project_info,edit_project_info

def execute(command,arguments):
    if command=='author_resources':
        from .resources import author_resources
        return author_resources(arguments['project'],arguments['resources'])
    if command=='presentations':
        from .presentation import create_presentations
        return create_presentations(arguments['project'],arguments['drawings'])
    if command=='create_levels':
        from .level_projects import create_levels_project
        return create_levels_project(arguments['project'],arguments['levels'],arguments.get('grid'))
    if command=='validate':return validate_plan(arguments['operations'])
    if command=='apply':return apply_plan(arguments['project'],arguments['operations'],new=arguments.get('new',False))
    if command=='documents':return create_plans(arguments['project'],arguments['drawings'])
    if command=='set_project_info':return edit_project_info(arguments['project'],arguments['values'])
    if command=='update_sheets':
        from .sheet_metadata import update_sheet_metadata
        return update_sheet_metadata(arguments['project'],arguments['changes'])
    if command=='update_sheet_contents':
        from .presentation_edits import update_sheet_contents
        return update_sheet_contents(arguments['project'],arguments['changes'])
    if command in {'copy','preview_copy'}:
        source=checked_path(arguments['project']);target=checked_path(arguments['output'],write=True,new=True)
        if source.suffix.lower()!='.rnp' or target.suffix.lower()!='.rnp':raise ValueError('Native project extension .rnp required')
        sha=fingerprint(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        result=apply_plan(target,arguments.get('operations',[])) if command=='preview_copy' else None
        if fingerprint(source)!=sha:raise RuntimeError('Source changed during copy')
        with Session(target) as s:
            objects=inventory(s)
        event('project_copy_reopened_verified',source=str(source),target=str(target),objects=len(objects),computer_use_calls=0)
        return {'status':'copy_reopened_verified','source_unchanged':True,'output':str(target),'objects':objects,'applied_result':result,'computer_use_calls':0}
    if command=='doctor':
        with Session() as s:return {'version':s.app.VersionS,'product':s.app.ProductName,'com':True,'isolated':True,'apartment':'STA','computer_use_calls':0}
    with Session(arguments['project']) as s:
        if command=='project_info':return read_project_info(s)
        if command=='inspect':
            rows=inventory(s,details=arguments.get('details',True))
            if arguments.get('kind'):rows=[v for v in rows if v['type']==arguments['kind']]
            offset=arguments.get('offset',0);limit=arguments.get('limit',100)
            if offset<0 or not 1<=limit<=2000:raise ValueError('Invalid pagination')
            return {'objects':rows[offset:offset+limit],'total':len(rows),'offset':offset,'limit':limit}
        if command=='geometry':return extract(s)
        if command=='verify':return verify(s,arguments.get('expected_areas'),arguments.get('collision_types'),arguments.get('expected_filling_hosts'))
        if command=='catalogs':return catalogs(s,arguments.get('collection'))
        if command=='resources':
            from .resources import inspect_resources
            return inspect_resources(s,arguments.get('collections'))
        if command=='filling_panels':
            from .filling_panels import inspect_filling_panels
            return inspect_filling_panels(s,arguments.get('identifiers'))
        if command=='sheet_metadata':
            from .sheet_metadata import snapshot_sheet_metadata
            drawings=snapshot_sheet_metadata(s)
            return {'drawings':drawings,'computer_use_calls':0,
                    'scope':'native_sheet_metadata_and_title_block_getters',
                    'title_block_readback_complete':all(d['title_block_readback']['status']=='read' for d in drawings),
                    'title_block_cell_authoring':False,'visual_layout_verified':False}
        if command=='drawings':return snapshot(s)
        if command=='ifc':return export_ifc(s,arguments['output'])
        if command=='pdf':return export_pdf(s,arguments['output'],arguments.get('drawing_uuids'))
        if command=='render':return render(s,arguments['output'],arguments.get('entity_id'),arguments.get('width',1024),arguments.get('height',768),camera_orientation=arguments.get('camera_orientation'))
        if command=='save_as':
            target=checked_path(arguments['output'],write=True,new=True);before=fingerprint(s.path);old={v['uuid'] for v in inventory(s)}
            target.parent.mkdir(parents=True,exist_ok=True);s.check(s.project.SaveAs(str(target),0,False),'SaveAs')
            if fingerprint(s.path)!=before:raise RuntimeError('SaveAs changed source')
            s.check(s.app.CloseProject(False),'CloseProject SaveAs');s.check(s.app.OpenProject(str(target)),'OpenProject SaveAs')
            s.project=s.app.Project;s.model=s.project.Model;actual=inventory(s)
            if {v['uuid'] for v in actual}!=old:raise RuntimeError('SaveAs lost persistent identities')
            event('save_as_reopened_verified',source=str(s.path),output=str(target),sha256=fingerprint(target),computer_use_calls=0)
            return {'status':'save_as_reopened_verified','output':str(target),'objects':actual,'source_unchanged':True,'computer_use_calls':0}
        raise ValueError('Unknown worker command')

def main():
    try:
        request=json.load(sys.stdin);register_worker_identity()
        result=execute(request['command'],request.get('arguments',{}))
        print(json.dumps({'result':result},ensure_ascii=False,allow_nan=False))
    except Exception as exc:
        event('worker_error',status='error',error=str(exc),exception_type=type(exc).__name__)
        print(json.dumps({'error':str(exc),'exception_type':type(exc).__name__},ensure_ascii=False),file=sys.stderr);sys.exit(1)

if __name__=='__main__':main()
