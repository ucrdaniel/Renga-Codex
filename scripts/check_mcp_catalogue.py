"""Discover the current stdio MCP catalogue and validate schemas; no Renga calls.

This never calls doctor/status, a model reader, a mutation or an export. It
starts only the Python MCP frontend, reads tools/list and calls pure metadata.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from jsonschema import Draft202012Validator
from run_mcp_tests import assert_tool_catalogue


def field(tool,snake,camel):
    return getattr(tool,snake,None) or getattr(tool,camel,None)


async def check():
    report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),
            'transport':'MCP stdio','native_tool_calls':0,'computer_use_calls':0,'pdf_exports':0}
    params=StdioServerParameters(command=sys.executable,args=['-m','renga_codex_bridge.mcp_server'],
        env={**os.environ,'PYTHONPATH':str(ROOT/'src'),'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'})
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer) as session:
            initialized=await session.initialize()
            result=await session.list_tools()
            names=assert_tool_catalogue(result.tools)
            rows=[]
            for tool in result.tools:
                inputs=field(tool,'input_schema','inputSchema')
                outputs=field(tool,'output_schema','outputSchema')
                Draft202012Validator.check_schema(inputs)
                if outputs is not None:Draft202012Validator.check_schema(outputs)
                rows.append({'name':tool.name,'input_schema':inputs,'output_schema':outputs})
            caps=await session.call_tool('bridge_capabilities',{})
            if field(caps,'is_error','isError'):raise AssertionError('Pure capabilities metadata request failed')
            report.update(status='passed',protocol_version=field(initialized,'protocol_version','protocolVersion'),
                          tool_count=len(names),tools=rows,pure_metadata_call='bridge_capabilities',
                          all_advertised_input_output_schemas_valid=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',help='Optional JSON report path; never a BIM/PDF file')
    args=parser.parse_args()
    report=asyncio.run(check())
    if args.output:
        output=Path(args.output)
        if output.exists():raise FileExistsError('Refusing to overwrite an earlier protocol report')
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({key:value for key,value in report.items() if key!='tools'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
