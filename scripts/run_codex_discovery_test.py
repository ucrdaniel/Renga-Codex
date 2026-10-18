"""Inspect this MCP server through the *running* Codex Desktop backend.

Uses ``codex app-server proxy`` and the installed CLI's JSON-RPC schema; it
never starts a Codex agent, thread, model turn, daemon or separate AI service.
Default: initialize + filtered discovery only. --reload queues a global MCP
configuration refresh (the protocol has no per-server reload filter); use it
after native commands have finished. Tool execution is explicit and opt-in.
--isolated-app-server instead starts temporary Codex protocol instrumentation
over stdio. Its evidence concerns a fresh backend, never the running Desktop.

Protocol reference: https://learn.chatgpt.com/docs/app-server
Generate local schema with:
  codex app-server generate-json-schema --out runtime/codex-schema --experimental
Generated schema and private reports stay under ignored runtime/.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time

EXPECTED_TOOLS = {
    "bridge_status", "bridge_inspect", "bridge_apply_plan", "bridge_validate_plan",
    "bridge_preview_on_copy", "bridge_geometry", "bridge_verify", "bridge_catalogs",
    "bridge_create_drawings", "bridge_inspect_drawings", "bridge_export_pdf",
    "bridge_export_ifc", "bridge_render_view", "bridge_copy_project", "bridge_save_as",
    "bridge_project_info", "bridge_set_project_info", "bridge_rectangle_plan",
    "bridge_facade_spacing", "bridge_capabilities", "bridge_create_levels_project",
    "bridge_inspect_resources", "bridge_author_resources", "bridge_create_presentations",
    "bridge_inspect_filling_panels", "bridge_inspect_sheet_metadata", "bridge_update_sheet_metadata",
    "bridge_update_sheet_contents",
    "bridge_update_window_styles", "bridge_update_existing_properties",
    "bridge_append_sheet_schedules", "bridge_append_sheet_views",
}


class RpcError(RuntimeError):
    pass


class DesktopProxy:
    def __init__(self, codex: str, *, sock: str | None = None, timeout: float = 45, isolated=False):
        command = [codex, "app-server", "--stdio"] if isolated else [codex, "app-server", "proxy"]
        if sock:
            if isolated:
                raise ValueError("--sock cannot be used with an isolated stdio backend")
            command += ["--sock", sock]
        self.timeout = timeout
        self.messages = queue.Queue()
        self.request_id = 0
        self.notification_methods = set()
        self.stderr_lines = 0
        self.proxy_error_category = None
        self.proxy_os_error = None
        self.process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf8", errors="replace", bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        self.stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self.stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self.stdout_thread.start()
        self.stderr_thread.start()

    def _read_stdout(self):
        try:
            for line in self.process.stdout:
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    self.messages.put({"_protocol_error": "Proxy stdout was not newline-delimited JSON"})
                    continue
                self.messages.put(message)
        finally:
            self.messages.put({"_eof": True})

    def _drain_stderr(self):
        # Avoid collecting arbitrary Desktop diagnostics with private settings.
        for line in self.process.stderr:
            self.stderr_lines += 1
            if "failed to connect" in line.casefold() and "socket" in line.casefold():
                self.proxy_error_category = "control_socket_unavailable"
            match = re.search(r"\(os error (\d+)\)", line)
            if match:
                self.proxy_os_error = int(match.group(1))

    def send(self, message):
        self.process.stdin.write(json.dumps(message, ensure_ascii=False, allow_nan=False) + "\n")
        self.process.stdin.flush()

    def notify(self, method, params=None):
        message = {"method": method}
        if params is not None:
            message["params"] = params
        self.send(message)

    def request(self, method, params=None):
        self.request_id += 1
        request_id = self.request_id
        message = {"id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        self.send(message)
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Codex Desktop request timed out: " + method)
            try:
                response = self.messages.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError("Codex Desktop request timed out: " + method) from exc
            if not isinstance(response, dict):
                raise RpcError("Malformed Codex Desktop protocol response")
            if response.get("_eof"):
                raise RpcError("Desktop proxy disconnected; verify that the local app-server control socket is available")
            if "_protocol_error" in response:
                raise RpcError(response["_protocol_error"])
            if "method" in response:
                self.notification_methods.add(response["method"])
                if "id" in response:
                    # No automatic approvals, elicitation, credential exchange
                    # or side-effecting server request handling in this probe.
                    self.send({"id": response["id"], "error": {
                        "code": -32601, "message": "Discovery probe does not execute or approve server requests",
                    }})
                continue
            if response.get("id") != request_id:
                raise RpcError("Unexpected JSON-RPC response ID")
            if "error" in response:
                error = response["error"]
                raise RpcError(f"{method}: {error.get('code')} {error.get('message')}")
            if "result" not in response:
                raise RpcError("JSON-RPC response has neither result nor error")
            return response["result"]

    def close(self):
        # Closing/killing this proxy cannot terminate the running Desktop daemon.
        if self.process.stdin:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=3)
        self.stdout_thread.join(timeout=1)
        self.stderr_thread.join(timeout=1)


def discover_server(proxy: DesktopProxy, server_name: str, thread_id: str | None):
    params = {"serverName": server_name, "detail": "toolsAndAuthOnly", "limit": 20}
    if thread_id:
        params["threadId"] = thread_id
    rows = []
    while True:
        response = proxy.request("mcpServerStatus/list", params)
        if not isinstance(response, dict) or not isinstance(response.get("data"), list):
            raise RpcError("Unexpected MCP discovery response shape")
        for row in response["data"]:
            if row.get("name") != server_name:
                raise RpcError("Server filter returned an unrelated server; refusing to collect its data")
            rows.append(row)
        cursor = response.get("nextCursor")
        if not cursor:
            break
        params["cursor"] = cursor
    if len(rows) != 1:
        raise RpcError("Expected exactly one configured bridge MCP server; configuration may need reload")
    return rows[0]


def report_discovery(server: dict, *, thread_scoped: bool):
    tools = server.get("tools")
    if not isinstance(tools, dict):
        raise RpcError("Native Codex server status has no tool catalogue object")
    names = {tool.get("name") for tool in tools.values() if isinstance(tool, dict)}
    if None in names:
        raise RpcError("Malformed tool definition in Codex catalogue")
    missing = EXPECTED_TOOLS - names
    connected = server.get("runtimeStatus") == "connected"
    return {
        "server_name": server["name"], "tool_names": sorted(names), "tool_count": len(names),
        "expected_tool_count": len(EXPECTED_TOOLS), "missing_expected_tools": sorted(missing),
        "runtime_status": server.get("runtimeStatus"), "tools_error": server.get("toolsError"),
        "auth_status": server.get("authStatus"),
        "thread_scoped": thread_scoped, "thread_connection_confirmed": connected and thread_scoped,
        "catalogue_discovered": not missing and server.get("toolsError") is None,
    }


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", help="Installed Codex CLI executable; default PATH lookup")
    parser.add_argument("--sock", help="Existing app-server control socket; never starts a daemon")
    parser.add_argument("--isolated-app-server", action="store_true", help="Temporary Codex stdio protocol instrumentation; catalogue scope is a fresh backend, NOT the running Desktop")
    parser.add_argument("--server-name", default="renga-codex-bridge")
    parser.add_argument("--thread-id", default=os.environ.get("CODEX_THREAD_ID"))
    parser.add_argument("--reload", action="store_true", help="Queue the protocol's GLOBAL MCP configuration refresh; run after native requests finish")
    parser.add_argument("--call-tool", help="Explicit opt-in tool call on the existing thread, e.g. bridge_status; can invoke native COM")
    parser.add_argument("--arguments-json", default="{}", help="JSON object for the explicitly selected tool")
    parser.add_argument("--timeout", type=float, help="Per-RPC deadline, 1..300 seconds; default 45 for discovery, 240 for an explicit tool call")
    parser.add_argument("--output", type=Path, default=root / "runtime" / "codex-discovery-latest.json")
    args = parser.parse_args()
    rpc_timeout = args.timeout if args.timeout is not None else (240 if args.call_tool else 45)
    if not math.isfinite(rpc_timeout) or not 1 <= rpc_timeout <= 300:
        parser.error("--timeout must be finite and between 1 and 300 seconds")
    codex = args.codex or shutil.which("codex")
    if not codex:
        parser.error("Installed Codex CLI not found; pass --codex")
    if args.isolated_app_server and args.sock:
        parser.error("--isolated-app-server and --sock cannot be combined")
    if args.call_tool and (not args.thread_id or not args.call_tool.startswith("bridge_")):
        parser.error("Tool call requires an existing --thread-id and an explicit bridge_ tool")
    try:
        tool_arguments = json.loads(args.arguments_json)
    except json.JSONDecodeError:
        parser.error("--arguments-json must be valid JSON")
    if not isinstance(tool_arguments, dict):
        parser.error("--arguments-json must be an object")
    # A fresh backend does not load/resume the user's Desktop thread. Global
    # filtered discovery creates no thread and makes no model request.
    discovery_thread_id = None if args.isolated_app_server else args.thread_id
    scope = "isolated_codex_protocol_backend" if args.isolated_app_server else "existing_codex_desktop_backend"
    report = {
        "time_utc": datetime.now(timezone.utc).isoformat(), "status": "not_verified",
        "transport": "codex app-server --stdio" if args.isolated_app_server else "codex app-server proxy to existing local backend",
        "scope": scope, "existing_desktop_verified": False,
        "configuration_reload_requested": args.reload, "tool_call_requested": args.call_tool,
        "new_threads_created": 0, "model_turns_started": 0, "computer_use_calls": 0,
        "native_com_requested": bool(args.call_tool),
    }
    proxy = None
    exit_code = 1
    try:
        proxy = DesktopProxy(codex, sock=args.sock, timeout=rpc_timeout, isolated=args.isolated_app_server)
        initialized = proxy.request("initialize", {
            "clientInfo": {"name": "renga_bridge_discovery", "title": "Renga Bridge discovery probe", "version": "0.2.0"},
            "capabilities": {"experimentalApi": True},
        })
        proxy.notify("initialized", {})
        # Keep only platform metadata; never collect auth/config/Codex home.
        report["backend"] = {key: initialized.get(key) for key in ("platformFamily", "platformOs", "userAgent")}
        report["existing_desktop_verified"] = not args.isolated_app_server
        if args.reload:
            proxy.request("config/mcpServer/reload")
            report["configuration_reload_acknowledged"] = True
        server = discover_server(proxy, args.server_name, discovery_thread_id)
        discovery = report_discovery(server, thread_scoped=bool(discovery_thread_id))
        report.update(discovery)
        if not discovery["catalogue_discovered"]:
            raise RpcError("Codex did not discover the complete expected bridge tool catalogue")
        report["status"] = "codex_isolated_backend_catalogue_discovered" if args.isolated_app_server else "codex_desktop_catalogue_discovered"
        if discovery["thread_connection_confirmed"]:
            report["status"] = "codex_desktop_thread_discovery_verified"
        if args.call_tool:
            if args.call_tool not in discovery["tool_names"]:
                raise RpcError("Requested tool was not discovered on this server")
            result = proxy.request("mcpServer/tool/call", {
                "server": args.server_name, "threadId": args.thread_id,
                "tool": args.call_tool, "arguments": tool_arguments,
            })
            report["tool_call_result"] = result  # Private runtime report only.
            if result.get("isError"):
                raise RpcError("Explicit Codex MCP tool call returned an error")
            report["status"] = "codex_isolated_backend_tool_call_verified" if args.isolated_app_server else "codex_desktop_tool_call_verified"
        exit_code = 0
    except (OSError, RpcError, TimeoutError, ValueError) as exc:
        report["error"] = str(exc)
    finally:
        if proxy is not None:
            report["notification_methods_seen"] = sorted(proxy.notification_methods)
            proxy.close()
            report["proxy_stderr_line_count"] = proxy.stderr_lines
            report["proxy_error_category"] = proxy.proxy_error_category
            report["proxy_os_error"] = proxy.proxy_os_error
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf8")
    print(json.dumps({"status": report["status"], "tool_count": report.get("tool_count"),
                      "thread_connection_confirmed": report.get("thread_connection_confirmed"),
                      "tool_call_requested": args.call_tool, "report": str(args.output),
                      "error": report.get("error")}, ensure_ascii=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
