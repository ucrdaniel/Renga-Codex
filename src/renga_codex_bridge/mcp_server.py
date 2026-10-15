"""Serial stdio MCP frontend. COM stays in disposable STA workers."""
import asyncio
import json
import sys
import os
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from .planning import rectangle_plan,facade_spacing
from .validation import validate_plan
from .audit import event
from .ownership import create_ownership_lease,command_timeout_seconds,cleanup_after_timeout

server=MCPServer('Renga Codex Bridge')
gate=asyncio.Lock()

async def run(command,**arguments):
    async with gate:
        limit=command_timeout_seconds()
        lease=create_ownership_lease()
        process=await asyncio.create_subprocess_exec(sys.executable,'-m','renga_codex_bridge.worker',
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,
            env={**os.environ,**lease.environment(),'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'})
        try:identity=lease.observe_worker(process.pid)
        except BaseException:
            process.kill();await asyncio.wait_for(process.wait(),timeout=5);raise
        try:
            out,err=await asyncio.wait_for(process.communicate(json.dumps({'command':command,'arguments':arguments},ensure_ascii=False).encode('utf8')),timeout=limit)
        except (asyncio.TimeoutError,asyncio.CancelledError) as exc:
            if process.returncode is None:process.kill()
            try:await asyncio.wait_for(process.wait(),timeout=5)
            except asyncio.TimeoutError:pass
            cleanup=cleanup_after_timeout(lease,identity)
            event('worker_timeout',status='error',command=command,cleanup=cleanup,outcome='unknown')
            if isinstance(exc,asyncio.CancelledError):raise
            raise ToolError('Native worker timed out; outcome is unknown. Inspect local logs/backups before retrying.')
        if process.returncode:raise ToolError(err.decode('utf8',errors='replace'))
        return json.loads(out.decode('utf8'))['result']

@server.tool()
async def bridge_status()->dict:
    """Probe installed Renga in a new owned STA process; never attach to the user's session."""
    return await run('doctor')

@server.tool()
async def bridge_inspect(project:str,kind:str|None=None,offset:int=0,limit:int=100,details:bool=True)->dict:
    """Read saved native UUIDs, parameters/definitions, quantities. Numeric IDs can change on SaveAs."""
    return await run('inspect',project=project,kind=kind,offset=offset,limit=limit,details=details)

@server.tool()
async def bridge_apply_plan(project:str,operations:list[dict],new:bool=False)->dict:
    """Create/edit models only under configured write root. Backup, undo transaction, save/reopen and requested-value checks included. Coordinates mm."""
    return await run('apply',project=project,operations=operations,new=new)

@server.tool()
async def bridge_create_levels_project(project:str,levels:list[dict],grid:dict|None=None)->dict:
    """Create a NEW native .rnp with levels at explicit elevation_mm and optional orthogonal Axis grid via official IFC import. Verify saved native identities/heights and fresh exported grid coordinates; remove own carriers. Does not modify existing level elevations."""
    return await run('create_levels',project=project,levels=levels,grid=grid)

@server.tool()
def bridge_validate_plan(operations:list[dict])->dict:
    """Validate plan structure without native mutation. This is NOT a native solver preview."""
    return validate_plan(operations)

@server.tool()
async def bridge_preview_on_copy(project:str,output:str,operations:list[dict])->dict:
    """Apply proposed edits to a NEW disposable native copy, preserving the saved source file."""
    return await run('preview_copy',project=project,output=output,operations=operations)

@server.tool()
async def bridge_geometry(project:str)->dict:
    """Extract genuine native mesh vertices/triangles in millimeters."""
    return await run('geometry',project=project)

@server.tool()
async def bridge_verify(project:str,expected_areas:dict|None=None,collision_types:list[str]|None=None)->dict:
    """Compare native room/floor areas with triangle calculations and explicit targets; conservative AABB candidates only."""
    return await run('verify',project=project,expected_areas=expected_areas,collision_types=collision_types)

@server.tool()
async def bridge_catalogs(project:str,collection:str|None=None)->dict:
    """Inspect existing native styles/materials/scales/layouts/schedules before selecting actual IDs."""
    return await run('catalogs',project=project,collection=collection)

@server.tool()
async def bridge_create_drawings(project:str,drawings:list[dict])->dict:
    """Create actual drawings with embedded level views and optional existing native schedules/text titles; no fake dimensions or tags."""
    return await run('documents',project=project,drawings=drawings)

@server.tool()
async def bridge_inspect_drawings(project:str)->list:
    """Read native drawing parameters and object persistent identities."""
    return await run('drawings',project=project)

@server.tool()
async def bridge_export_pdf(project:str,output:str,drawing_uuids:list[str]|None=None)->dict:
    """Export native drawings to one PDF using Renga API; requires a NEW output path inside write root."""
    return await run('pdf',project=project,output=output,drawing_uuids=drawing_uuids)

@server.tool()
async def bridge_export_ifc(project:str,output:str)->dict:
    """Export IFC4 using Renga API to a new protected output path."""
    return await run('ifc',project=project,output=output)

@server.tool()
async def bridge_render_view(project:str,output:str,entity_id:int|None=None,width:int=1024,height:int=768)->dict:
    """Render a native view through IScreenshotService; no mouse, keyboard or Computer Use calls."""
    return await run('render',project=project,output=output,entity_id=entity_id,width=width,height=height)

@server.tool()
async def bridge_copy_project(project:str,output:str)->dict:
    """Copy saved native project to a NEW writable destination and open the copy in an isolated process."""
    return await run('copy',project=project,output=output)

@server.tool()
async def bridge_save_as(project:str,output:str)->dict:
    """Native SaveAs to a NEW protected destination; source disk file unchanged, UUIDs checked after reopen."""
    return await run('save_as',project=project,output=output)

@server.tool()
async def bridge_project_info(project:str)->dict:
    """Read actual native project Code/Name/Stage/Description and persistent project UUID."""
    return await run('project_info',project=project)

@server.tool()
async def bridge_set_project_info(project:str,values:dict)->dict:
    """Back up, edit four native project metadata fields, save and verify after reopen; resource undo is not guaranteed."""
    return await run('set_project_info',project=project,values=values)

@server.tool()
def bridge_rectangle_plan(width:float=6000,depth:float=4000,height:float=3000,thickness:float=200)->list:
    """Prepare an explicit generic four-wall/room/floor operation plan. Does not mutate Renga."""
    return rectangle_plan(width,depth,height,thickness)

@server.tool()
def bridge_facade_spacing(length:float,width:float,count:int,end_pier:float=600,min_pier:float=600)->dict:
    """Calculate explicit window offsets and piers in millimeters without mutating a model."""
    return facade_spacing(length,width,count,end_pier,min_pier)

@server.tool()
def bridge_capabilities()->dict:
    """Return release scope; research and actual local integration evidence are distinguished."""
    from .capabilities import capabilities
    return capabilities()

def main():server.run(transport='stdio')
if __name__=='__main__':main()
