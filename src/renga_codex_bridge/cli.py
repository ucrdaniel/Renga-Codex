import argparse
import json
import subprocess
import sys
from pathlib import Path
from .runner import run_worker

def main():
    parser=argparse.ArgumentParser(description='API-first local Renga MCP bridge, no GUI automation')
    parser.add_argument('command',choices=['doctor','inspect','apply','validate','geometry','verify','catalogs','documents','drawings','ifc','pdf','render','copy','preview_copy','save_as','project_info','set_project_info'])
    parser.add_argument('--project');parser.add_argument('--plan');parser.add_argument('--output');parser.add_argument('--collection')
    parser.add_argument('--new',action='store_true');parser.add_argument('--json',action='store_true',help='JSON is also the default output')
    parser.add_argument('--limit',type=int,default=100)
    parser.add_argument('--timeout',type=float,help='Native worker timeout in seconds (default 180, range 1..3600)')
    args=parser.parse_args();arguments={k:v for k,v in vars(args).items() if k not in {'command','json','plan','timeout'} and v is not None}
    if args.plan:
        plan=json.loads(Path(args.plan).read_text(encoding='utf-8-sig'))
        arguments['drawings' if args.command=='documents' else 'values' if args.command=='set_project_info' else 'operations']=plan
    try:result=run_worker(args.command,arguments,timeout=args.timeout)
    except Exception as exc:
        print(json.dumps({'error':str(exc),'exception_type':type(exc).__name__},ensure_ascii=False),file=sys.stderr);sys.exit(1)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
