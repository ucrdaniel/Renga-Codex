"""Public command routing contracts without a worker or native session."""
import asyncio
import json
import sys
import uuid

import pytest

from renga_codex_bridge import cli, worker


UID = str(uuid.UUID(int=1))


@pytest.mark.parametrize('command,module,function,argument',[
    ('update_window_styles','resource_edits','update_window_styles','changes'),
    ('update_existing_properties','existing_properties','update_existing_properties','changes'),
    ('append_sheet_schedules','sheet_additions','append_sheet_schedules','additions'),
    ('append_sheet_views','sheet_views','append_sheet_views','additions'),
])
def test_worker_dispatches_new_commands_without_opening_session(monkeypatch,command,module,function,argument):
    import importlib
    implementation=importlib.import_module('renga_codex_bridge.'+module)
    calls=[]
    monkeypatch.setattr(implementation,function,lambda *a,**kw:calls.append((a,kw)) or {'status':'mock-route-only'})
    monkeypatch.setattr(worker,'Session',lambda *a,**kw:pytest.fail('No generic/native Session should open'))
    arguments={'project':'test.rnp',argument:[{'route':'only'}]}
    if command=='update_window_styles':arguments['expected_project_sha256']='f'*64
    if command=='update_existing_properties':arguments['cell_checks']=[]
    assert worker.execute(command,arguments)=={'status':'mock-route-only'}
    assert calls[0][0][:2]==('test.rnp',[{'route':'only'}])
    if command=='update_window_styles':assert calls[0][0][2]=='f'*64
    if command=='update_existing_properties':assert calls[0][1]=={'cell_checks':[]}


@pytest.mark.parametrize('command,argument',[
    ('update_window_styles','changes'),('update_existing_properties','changes'),
    ('append_sheet_schedules','additions'),('append_sheet_views','additions')])
def test_cli_loads_saved_list_into_correct_worker_argument(monkeypatch,tmp_path,capsys,command,argument):
    plan=tmp_path/'plan.json';plan.write_text('[{"saved":"request"}]',encoding='utf-8-sig')
    args=['renga-bridge',command,'--project','test.rnp','--plan',str(plan)]
    if command=='update_window_styles':args+=['--expected-project-sha256','a'*64]
    if command=='update_existing_properties':
        checks=tmp_path/'checks.json';checks.write_text('[]',encoding='utf8')
        args+=['--cell-checks',str(checks)]
    calls=[]
    monkeypatch.setattr(sys,'argv',args)
    monkeypatch.setattr(cli,'run_worker',lambda command,arguments,**kw:calls.append((command,arguments)) or {'status':'route'})
    cli.main()
    assert json.loads(capsys.readouterr().out)=={'status':'route'}
    actual_command,arguments=calls[0]
    assert actual_command==command and arguments[argument]==[{'saved':'request'}]
    assert 'operations' not in arguments
    if command!='update_existing_properties':assert 'cell_checks' not in arguments
    if command=='update_window_styles':assert arguments['expected_project_sha256']=='a'*64
    if command=='update_existing_properties':assert arguments['cell_checks']==[]


@pytest.mark.parametrize('extra',[['--expected-project-sha256','a'*64],['--cell-checks','unused.json']])
def test_new_cli_options_cannot_be_silently_ignored_by_other_commands(monkeypatch,extra):
    monkeypatch.setattr(sys,'argv',['renga-bridge','doctor',*extra])
    monkeypatch.setattr(cli,'run_worker',lambda *a,**kw:pytest.fail('Invalid option must not start worker'))
    with pytest.raises(SystemExit) as error:cli.main()
    assert error.value.code==2


@pytest.mark.parametrize('function,rows,argument,command',[
    ('bridge_update_window_styles',[{'resource_uuid':UID,'expected_name':'Window','parameters':{'FrameDepth':50}}],'changes','update_window_styles'),
    ('bridge_update_existing_properties',[{'kind':'Drawing','uuid':UID,'property_guid':UID,'property_name':'Author','value':'A'}],'changes','update_existing_properties'),
    ('bridge_append_sheet_schedules',[{'drawing_uuid':UID,'schedule_id':1,'available_bounds_mm':[0,10,0,10]}],'additions','append_sheet_schedules'),
    ('bridge_append_sheet_views',[{'drawing_uuid':UID,'kind':'model','source_entity_id':1,'scale_id':2,'origin_mm':[0,0]}],'additions','append_sheet_views'),
])
def test_mcp_passes_plain_request_to_serial_worker(monkeypatch,function,rows,argument,command):
    from renga_codex_bridge import mcp_server as m
    calls=[]
    async def run(name,**kwargs):calls.append((name,kwargs));return {'status':'route'}
    monkeypatch.setattr(m,'run',run)
    result=asyncio.run(getattr(m,function)('test.rnp',**{argument:rows}))
    assert result=={'status':'route'} and calls[0][0]==command
    assert calls[0][1][argument]==rows
    assert calls[0][1]['project']=='test.rnp'


@pytest.mark.parametrize('function,argument',[
    ('bridge_update_window_styles','changes'),('bridge_update_existing_properties','changes'),
    ('bridge_append_sheet_schedules','additions'),('bridge_append_sheet_views','additions')])
def test_mcp_invalid_batch_never_launches_native_worker(monkeypatch,function,argument):
    from renga_codex_bridge import mcp_server as m
    async def forbidden(*a,**kw):pytest.fail('Invalid batch must not start native worker')
    monkeypatch.setattr(m,'run',forbidden)
    with pytest.raises(ValueError):asyncio.run(getattr(m,function)('test.rnp',**{argument:[]}))
