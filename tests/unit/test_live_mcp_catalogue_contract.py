"""Keep the public native test runner aligned with the real registered tools."""
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from renga_codex_bridge.mcp_server import server


def runner():
    path=Path(__file__).resolve().parents[2]/'scripts'/'run_mcp_tests.py'
    spec=importlib.util.spec_from_file_location('bridge_native_mcp_catalogue_contract',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_native_runner_checks_every_current_registered_tool_without_running_native_tools():
    module=runner()
    tools=asyncio.run(server.list_tools())
    names=module.assert_tool_catalogue(tools)
    assert len(names)==24
    assert {'bridge_inspect_resources','bridge_author_resources','bridge_create_presentations'}<=set(names)


@pytest.mark.parametrize('change',['missing','extra','duplicate'])
def test_wrong_catalogue_fails_before_native_connection(change):
    module=runner()
    tools=[SimpleNamespace(name=name) for name in sorted(module.EXPECTED_TOOLS)]
    if change=='missing':tools=[tool for tool in tools if tool.name!='bridge_author_resources']
    elif change=='extra':tools.append(SimpleNamespace(name='unreviewed_native_tool'))
    else:tools.append(tools[0])
    with pytest.raises(AssertionError,match='Unexpected MCP catalogue'):module.assert_tool_catalogue(tools)


def test_codex_discovery_requires_the_three_additional_tools_too():
    path=Path(__file__).resolve().parents[2]/'scripts'/'run_codex_discovery_test.py'
    spec=importlib.util.spec_from_file_location('bridge_current_codex_discovery_contract',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.EXPECTED_TOOLS==runner().EXPECTED_TOOLS
