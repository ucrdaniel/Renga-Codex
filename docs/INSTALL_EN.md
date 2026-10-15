# Windows installation

Version 0.2 adds `bridge_create_levels_project`: create a NEW native model with
explicit level elevations and an optional orthogonal native Axis grid through
official IFC import/export. Refresh the MCP catalogue after upgrading (21 tools).
Import and export must be available in the installed Renga edition/license.
The operation refuses existing targets and does not merge into an existing
model. Intermediate own IFC files remain in the dedicated write root. See
[operation plans](OPERATION_PLANS.md) for the exact JSON contract. `room_marker`
moves the Room's intrinsic marker in global XY millimeters; it is separate from
creating a standalone Tag or associative dimension.

Renga–Codex Bridge is an independent local MCP server. Codex interprets a task
and calls tools; the bridge performs its advertised operations through the
official Renga COM API. It does not require a separate AI service or an extra
OpenAI API key. Consult [CAPABILITIES.md](CAPABILITIES.md) for actual tested
coverage and versions.

## Prerequisites installed by the user

- Windows x64 and Python 3.11 or later, x64. The local reference environment uses
  Python 3.12. CI coverage on other versions proves non-Renga tests only.
- An independently installed and licensed Renga with registered COM API.
- A compatible [Renga SDK](https://rengabim.com/sdk/), unpacked outside the public
  repository. Its root must contain `tlb/RengaCOMAPI.tlb` and
  `C++/Include/Renga/EntityTypes.h`, `Parameters.h`, `Quantities.h`.
- Codex; automatic registration additionally requires the `codex` CLI on PATH.

The script does not download/install Renga, the SDK, Python or Codex, alter
licensing, or blindly register Renga as an administrator.

## Install

Open PowerShell in your checkout. Use a dedicated disposable directory for BIM
writes, separate from production projects.

```powershell
git clone https://github.com/ucrdaniel/Renga-Codex.git Renga-Codex-Bridge
Set-Location .\Renga-Codex-Bridge
.\scripts\install.ps1 -SdkPath 'C:\RengaSDK'
```

If automatic Python discovery fails, specify it:

```powershell
.\scripts\install.ps1 -PythonExe 'C:\Python312\python.exe' `
    -SdkPath 'C:\RengaSDK' -WriteRoot 'C:\Renga-tests\bridge'
```

The default approved BIM directory is `runtime/test-projects` inside the
checkout. Set `-WriteRoot` or `RENGA_BRIDGE_WRITE_ROOT` to use a different
disposable directory. Additional Codex workspace instructions can impose a
narrower boundary. Reading a saved project does not authorize editing it.

If local policy blocks PowerShell scripts, run this reviewed script once in a
separate process without changing permanent execution policy:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 `
    -SdkPath 'C:\RengaSDK'
```

The installer validates Windows, Python and SDK structure, creates `.venv`,
installs this package/dependencies, runs `pip check`, and invokes `doctor`.
The diagnostic creates a separate bridge-owned COM process and reports the
actual installed Renga version; it does not open a user project or mutate BIM.

Before `codex mcp add`, an existing `config.toml` is copied to `runtime/backups`
and its SHA-256 is compared. Keep these backups private because configuration
can contain secrets. Other MCP entries are preserved. An unrelated existing
entry with the same name causes a refusal; choose `-ServerName` or explicitly
use `-ReplaceExistingRegistration`. Use `-SkipCodex` to install without changing
Codex configuration.

## Connect Codex

The registered stdio server is named `renga-codex-bridge`. Its launch command
uses this checkout's Python. SDK/write-root variables are supplied to the MCP
process; the script does not create persistent user-wide environment variables.

Reconnect MCP or start a new Codex chat. Ask Codex to check the bridge status
and report genuinely verified capabilities. A successful COM doctor and config
read-back do not prove that an already-open chat refreshed its tool catalogue.

If the CLI becomes available later, back up `config.toml` yourself, then run the
registration command printed by the installer. Without the CLI, this manual
configuration is supported after backing up the existing file and replacing
the sample paths:

```toml
[mcp_servers.renga-codex-bridge]
command = 'C:\Renga-Codex-Bridge\.venv\Scripts\python.exe'
args = ["-m", "renga_codex_bridge.mcp_server"]
startup_timeout_sec = 30
tool_timeout_sec = 240

[mcp_servers.renga-codex-bridge.env]
RENGA_SDK_PATH = 'C:\RengaSDK'
RENGA_BRIDGE_WRITE_ROOT = 'C:\Renga-tests\bridge'
PYTHONUTF8 = "1"
PYTHONIOENCODING = "utf-8"
```

The file is `$CODEX_HOME/config.toml` when `CODEX_HOME` is set, otherwise
`%USERPROFILE%/.codex/config.toml`. Registration and stdio configuration are
documented in the [official Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

## Verify and create a first test model

From the checkout:

```powershell
$env:RENGA_SDK_PATH = 'C:\RengaSDK'
$env:RENGA_BRIDGE_WRITE_ROOT = 'C:\Renga-tests\bridge'
.\.venv\Scripts\renga-bridge.exe doctor
.\.venv\Scripts\python.exe -m pip check
```

For development, install test dependencies and run the non-Renga suite:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[test]'
.\.venv\Scripts\python.exe -m pytest -m 'not integration' -q
```

The actual COM/MCP end-to-end scenario is opt-in; use the command and evidence
description in [README](../README.md). It must create a new disposable file,
modify it, save, close, reopen and compare real saved values. Use a unique file
name. Mock/unit success is not evidence of functioning Renga automation.

Give Codex explicit millimeter dimensions, a new path inside the approved root,
and a request to save a JSON operation plan and verify after reopening. Before
requesting a complete window assembly, inspect and choose an existing style:
the default style can represent an aperture only.

## Troubleshooting, relocation and removal

| Problem | Action |
|---|---|
| Missing SDK | Supply the SDK root, not its `Docs`, `Net` or `tlb` subdirectory |
| COM registration / Renga launch failure | Check a normal Renga launch and repair installation using vendor guidance |
| Copied Python environment | Rerun the installer; an invalid `.venv` is preserved in a local backup directory |
| Tools missing from the chat | Check `codex mcp get renga-codex-bridge`, then reconnect the client |
| Write denied | Use the disposable write directory and check permissions/workspace restrictions |
| Timeout / crash | Inspect logs, the saved file and backup before retrying; never kill an unrelated Renga process |

After moving a checkout, rerun installation with updated absolute paths.
Virtual environments and local MCP registrations are not portable.

```powershell
.\scripts\uninstall.ps1
```

Uninstall removes only the MCP entry whose command still matches this checkout,
after backing up configuration. It preserves Renga, SDK, other settings, source,
`.venv`, models, logs and backups. If `CODEX_HOME` changed or the entry now points
to a different command, it refuses removal. For a manually registered entry,
inspect its command before running `codex mcp remove`.
