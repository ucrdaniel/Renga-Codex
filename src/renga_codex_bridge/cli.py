import argparse
import json
import subprocess
import sys
from pathlib import Path
from .runner import run_worker

def main():
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf8')
    parser=argparse.ArgumentParser(description='API-first local Renga MCP bridge, no GUI automation')
    parser.add_argument('command',choices=['doctor','inspect','apply','validate','geometry','verify','catalogs','resources','author_resources','presentations','documents','drawings','sheet_metadata','update_sheets','update_sheet_contents','update_window_styles','update_existing_properties','append_sheet_schedules','append_sheet_views','filling_panels','ifc','pdf','render','copy','preview_copy','save_as','project_info','set_project_info','create_levels'])
    parser.add_argument('--project');parser.add_argument('--plan');parser.add_argument('--output');parser.add_argument('--collection')
    parser.add_argument('--new',action='store_true');parser.add_argument('--json',action='store_true',help='JSON is also the default output')
    parser.add_argument('--limit',type=int,default=100)
    parser.add_argument('--camera-orientation',choices=['front','back','left','right'],help='render: whole-building parallel main-camera PNG; not a sheet elevation')
    parser.add_argument('--timeout',type=float,help='Native worker timeout in seconds (default 180, range 1..3600)')
    parser.add_argument('--expected-project-sha256',help='update_window_styles: complete inspected project digest, checked again after native open')
    parser.add_argument('--cell-checks',help='update_existing_properties: optional JSON array of explicit before/after title-block assertions')
    args=parser.parse_args()
    if args.expected_project_sha256 is not None and args.command!='update_window_styles':parser.error('--expected-project-sha256 applies only to update_window_styles')
    if args.cell_checks is not None and args.command!='update_existing_properties':parser.error('--cell-checks applies only to update_existing_properties')
    arguments={k:v for k,v in vars(args).items() if k not in {'command','json','plan','timeout','cell_checks'} and v is not None}
    if args.plan:
        plan=json.loads(Path(args.plan).read_text(encoding='utf-8-sig'))
        arguments['drawings' if args.command in {'documents','presentations'} else 'values' if args.command=='set_project_info' else 'levels' if args.command=='create_levels' else 'resources' if args.command=='author_resources' else 'changes' if args.command in {'update_sheets','update_sheet_contents','update_window_styles','update_existing_properties'} else 'additions' if args.command in {'append_sheet_schedules','append_sheet_views'} else 'identifiers' if args.command=='filling_panels' else 'operations']=plan
        if args.command=='create_levels' and isinstance(plan,dict):
            arguments['levels']=plan['levels'];arguments['grid']=plan.get('grid')
    if args.cell_checks:
        arguments['cell_checks']=json.loads(Path(args.cell_checks).read_text(encoding='utf-8-sig'))
    try:result=run_worker(args.command,arguments,timeout=args.timeout)
    except Exception as exc:
        print(json.dumps({'error':str(exc),'exception_type':type(exc).__name__},ensure_ascii=False),file=sys.stderr);sys.exit(1)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
