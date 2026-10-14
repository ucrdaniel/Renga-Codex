"""A real stdio MCP client, not mocks or direct adapter calls."""
import asyncio
from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from renga_codex_bridge.config import settings
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

async def run():
    folder=settings().write_root/('mcp-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    folder.mkdir(parents=True)
    report={'schema_version':1,'transport':'MCP stdio','checks':[],'computer_use_calls':0}
    parameters=StdioServerParameters(command=sys.executable,args=['-m','renga_codex_bridge.mcp_server'],env=dict(os.environ))
    def passed(name,**details):
        report['checks'].append({'check':name,'status':'passed',**details});print('PASS MCP',name,flush=True)
    try:
        async with stdio_client(parameters) as streams:
            async with ClientSession(*streams,read_timeout_seconds=timedelta(seconds=360)) as client:
                await client.initialize();passed('initialize_protocol')
                tools=(await client.list_tools()).tools
                assert len(tools)>=18;passed('discover_tools',count=len(tools),names=[tool.name for tool in tools])
                async def call(name,**arguments):
                    result=await client.call_tool(name,arguments)
                    if result.isError:raise RuntimeError(str(result.content))
                    if result.structuredContent is not None:
                        value=result.structuredContent
                        if isinstance(value,dict) and set(value)=={'result'}:value=value['result']
                    else:value=json.loads(''.join(block.text for block in result.content if hasattr(block,'text')))
                    (folder/('response-'+str(len(report['checks']))+'-'+name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
                    return value
                doctor=await call('bridge_status');assert doctor['com'] and doctor['isolated'];report['renga_version']=doctor['version'];passed('owned_renga_connection')
                plan=await call('bridge_rectangle_plan',width=8000,depth=5000,height=3000,thickness=200)
                validated=await call('bridge_validate_plan',operations=plan);assert validated['valid'];passed('plan_and_structural_validation')
                piers=await call('bridge_facade_spacing',length=8000,width=1200,count=3);assert len(piers['offsets_mm'])==3;passed('window_pier_calculation')
                project=folder/'mcp-model.rnp'
                result=await call('bridge_apply_plan',project=str(project),operations=plan,new=True)
                assert result['status']=='saved_reopened_verified';refs=result['persistent_refs'];passed('create_bim_save_close_reopen')
                inventory=await call('bridge_inspect',project=str(project),limit=1000)
                assert len(inventory['objects'])>=7;passed('read_persisted_model')
                info=await call('bridge_set_project_info',project=str(project),values={'Code':'MCP-TEST','Name':'MCP acceptance','Stage':'TEST','Description':'Synthetic MCP model'})
                assert info['status']=='saved_reopened_verified'
                assert (await call('bridge_project_info',project=str(project)))['Code']=='MCP-TEST';passed('native_project_metadata_roundtrip')
                catalog=await call('bridge_catalogs',project=str(project))
                south=refs['wall0']
                change=await call('bridge_apply_plan',project=str(project),operations=[
                    {'action':'set_parameter','id':south,'name':'WallHeight','value':3400},
                    {'action':'create','ref':'full_window','kind':'Window','host':south,'origin':[2000,0,1000],
                     'parameters':{'WindowStyleId':catalog['WindowStyles']['entries'][0]['id'],'WindowWidth':1400,'WindowHeight':1500}},
                    {'action':'create','ref':'full_door','kind':'Door','host':south,'origin':[6000,0,0],
                     'parameters':{'DoorStyleId':catalog['DoorStyles']['entries'][0]['id'],'DoorWidth':1000,'DoorHeight':2200}}])
                assert change['status']=='saved_reopened_verified';passed('edit_wall_create_styled_fillings_saved_readback')
                meshes=await call('bridge_geometry',project=str(project));assert meshes['unit']=='mm' and len(meshes['objects'])>=6;passed('read_native_meshes')
                verified=await call('bridge_verify',project=str(project),expected_areas={refs['floor']:40})
                assert verified['status']=='passed';passed('area_target_and_native_mesh_check',area_checks=len(verified['checks']))
                level=next(row['id'] for row in change['objects'] if row['type']=='Level')
                def choose(collection,needle):
                    entries=catalog[collection]['entries'];return next(v['id'] for v in entries if needle in v['name'])
                drawings=[{'parameters':{'EntityName':f'MCP API plan {n}','PageFormatId':choose('PageFormatStyles','A3'),
                           'PageOrientation':2,'LayoutStyleId':catalog['LayoutStyles']['entries'][0]['id']},
                           'level_id':level,'scale_id':choose('Scales','1:100'),'title':f'MCP API plan {n}',
                           'schedule_id':catalog['Schedules']['entries'][0]['id']} for n in (1,2)]
                sheets=await call('bridge_create_drawings',project=str(project),drawings=drawings)
                assert len(sheets['created_uuids'])==2;passed('native_drawings_views_schedule_text_roundtrip')
                assert len(await call('bridge_inspect_drawings',project=str(project)))>=2;passed('read_saved_native_drawings')
                pdf=await call('bridge_export_pdf',project=str(project),output=str(folder/'mcp-plans.pdf'),drawing_uuids=sheets['created_uuids'])
                from pypdf import PdfReader
                pages=PdfReader(pdf['output']).pages;assert len(pages)==2
                assert all('MCP API plan' in page.extract_text() for page in pages);passed('native_pdf_two_pages_content',pages=2)
                ifc=await call('bridge_export_ifc',project=str(project),output=str(folder/'mcp-model.ifc'));assert ifc['bytes']>1000;passed('native_ifc4_export')
                preview=await call('bridge_preview_on_copy',project=str(project),output=str(folder/'mcp-preview.rnp'),
                    operations=[{'action':'set_parameter','id':south,'name':'WallHeight','value':3500}])
                assert preview['source_unchanged'];passed('preview_copy_preserves_source')
                copied=await call('bridge_copy_project',project=str(project),output=str(folder/'mcp-copy.rnp'));assert copied['source_unchanged'];passed('protected_copy')
                saved=await call('bridge_save_as',project=str(project),output=str(folder/'mcp-save-as.rnp'));assert saved['source_unchanged'];passed('native_save_as')
                denied=await client.call_tool('bridge_apply_plan',{'project':str(folder.parent.parent/'mcp-forbidden.rnp'),'operations':[],'new':True})
                assert denied.isError;passed('mcp_denies_outside_write_root')
                capabilities=await call('bridge_capabilities');assert capabilities['api_first'];passed('declared_capabilities')
                report['status']='passed'
    except Exception as exc:
        report['status']='failed';report['error']=str(exc);raise
    finally:
        (folder/'mcp-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        (ROOT/'runtime/latest-mcp.json').write_text(json.dumps({'evidence_directory':str(folder),'report':report},ensure_ascii=False,indent=2),encoding='utf8')
        print('MCP RESULT',report['status'],len(report['checks']),'CHECKS',str(folder),flush=True)
    return report

if __name__=='__main__':asyncio.run(run())
