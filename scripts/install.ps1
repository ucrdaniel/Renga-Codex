[CmdletBinding()]
param(
    [string]$PythonExe,
    [string]$SdkPath = $env:RENGA_SDK_PATH,
    [string]$WriteRoot = $env:RENGA_BRIDGE_WRITE_ROOT,
    [ValidatePattern('^[a-zA-Z0-9_-]+$')]
    [string]$ServerName = 'renga-codex-bridge',
    [switch]$SkipCodex,
    [switch]$ReplaceExistingRegistration
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$taskRuntime = Join-Path $taskRoot 'runtime'
$taskVenv = Join-Path $taskRoot '.venv'
$taskVenvPython = Join-Path $taskVenv 'Scripts\python.exe'
$taskMarker = Join-Path $taskRuntime 'installation.local.json'
$taskModule = 'renga_codex_bridge.mcp_server'
$taskStamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ')

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments, [string]$Failure)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw $Failure }
}

function Invoke-Probe {
    param([string]$Executable, [string[]]$Arguments)
    $previousPreference = $ErrorActionPreference
    try {
        # Expected nonzero exits must remain inspectable on Windows PowerShell
        # 5.1, where redirected native stderr can otherwise terminate the script.
        $ErrorActionPreference = 'Continue'
        $output = & $Executable @Arguments 2>$null
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    return [PSCustomObject]@{ ExitCode = $code; Output = @($output) }
}

function Assert-PrivateRuntimePath {
    param([string]$Path)
    $current = [IO.Path]::GetFullPath($Path)
    $prefix = $taskRoot.TrimEnd('\') + '\'
    if (-not $current.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Runtime path must remain inside this checkout.'
    }
    while ($current -ne $taskRoot) {
        if (Test-Path -LiteralPath $current) {
            if ((Get-Item -LiteralPath $current).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw ('Refusing a linked runtime path: ' + $current)
            }
        }
        $current = Split-Path -Parent $current
    }
}

function Backup-CodexConfig {
    param([string]$ConfigPath)
    if (-not (Test-Path -LiteralPath $ConfigPath)) { return $null }
    $folder = Join-Path $taskRuntime 'backups'
    Assert-PrivateRuntimePath $folder
    New-Item -ItemType Directory -Path $folder -Force | Out-Null
    $destination = Join-Path $folder ('codex-config-' + $taskStamp + '.toml')
    if (Test-Path -LiteralPath $destination) { throw 'Configuration backup already exists.' }
    Copy-Item -LiteralPath $ConfigPath -Destination $destination
    if ((Get-FileHash -LiteralPath $ConfigPath -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash) {
        throw 'Codex configuration backup hash mismatch.'
    }
    Write-Host ('Codex configuration backup: ' + $destination)
    return $destination
}

if ([Environment]::OSVersion.Platform -ne 'Win32NT' -or
    -not [Environment]::Is64BitOperatingSystem) {
    throw 'Renga-Codex Bridge requires Windows x64; this installer does not install Renga.'
}
if (-not $SdkPath) {
    throw 'Provide -SdkPath with your separately downloaded Renga SDK root (containing tlb and C++ folders).'
}
$SdkPath = (Resolve-Path -LiteralPath $SdkPath).Path
foreach ($required in @('tlb\RengaCOMAPI.tlb', 'C++\Include\Renga\EntityTypes.h',
                        'C++\Include\Renga\Parameters.h', 'C++\Include\Renga\Quantities.h')) {
    if (-not (Test-Path -LiteralPath (Join-Path $SdkPath $required) -PathType Leaf)) {
        throw ('Incomplete SDK root; missing ' + $required)
    }
}
if (-not $WriteRoot) { $WriteRoot = Join-Path $taskRuntime 'test-projects' }
$WriteRoot = [IO.Path]::GetFullPath($WriteRoot)
if ($WriteRoot.TrimEnd('\') -eq [IO.Path]::GetPathRoot($WriteRoot).TrimEnd('\')) {
    throw 'The BIM write root must be a dedicated test directory, not a drive root.'
}

if (-not $PythonExe) {
    $taskLauncher = Get-Command 'py.exe' -CommandType Application -ErrorAction SilentlyContinue
    if ($taskLauncher) {
        $taskCandidate = Invoke-Probe $taskLauncher.Source @('-3', '-c', 'import sys; print(sys.executable)')
        if ($taskCandidate.ExitCode -eq 0 -and $taskCandidate.Output.Count -eq 1) {
            $PythonExe = [string]$taskCandidate.Output[0]
        }
    }
    if (-not $PythonExe) {
        $taskPythonCommand = Get-Command 'python.exe' -CommandType Application -ErrorAction SilentlyContinue
        if ($taskPythonCommand) { $PythonExe = $taskPythonCommand.Source }
    }
}
if (-not $PythonExe) { throw 'Install Python 3.11+ x64 separately, then pass -PythonExe with its absolute path.' }
$PythonExe = (Resolve-Path -LiteralPath $PythonExe).Path
Invoke-Checked $PythonExe @('-c', 'import sys, struct; assert sys.version_info >= (3, 11), "Python 3.11+ required"; assert struct.calcsize("P") == 8, "Python x64 required"; print(sys.version); print(sys.executable)') 'Python version or architecture check failed.'

Assert-PrivateRuntimePath $taskRuntime
New-Item -ItemType Directory -Path $taskRuntime -Force | Out-Null
New-Item -ItemType Directory -Path $WriteRoot -Force | Out-Null
if (Test-Path -LiteralPath $taskVenv) {
    if ((Get-Item -LiteralPath $taskVenv).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'Refusing a linked virtual environment; create .venv directly inside this checkout.'
    }
    $taskVenvValid = $false
    if (Test-Path -LiteralPath $taskVenvPython) {
        $taskVenvProbe = Invoke-Probe $taskVenvPython @('-c', 'import sys, struct; assert sys.version_info >= (3, 11) and struct.calcsize("P") == 8')
        $taskVenvValid = ($taskVenvProbe.ExitCode -eq 0)
    }
    if (-not $taskVenvValid) {
        $taskArchive = [IO.Path]::GetFullPath((Join-Path $taskRuntime ('backups\venv-' + $taskStamp)))
        Assert-PrivateRuntimePath $taskArchive
        $taskPrefix = $taskRoot.TrimEnd('\') + '\'
        if (-not $taskVenv.StartsWith($taskPrefix, [StringComparison]::OrdinalIgnoreCase) -or
            -not $taskArchive.StartsWith($taskPrefix, [StringComparison]::OrdinalIgnoreCase) -or
            (Test-Path -LiteralPath $taskArchive)) {
            throw 'Virtual-environment backup target failed workspace checks.'
        }
        New-Item -ItemType Directory -Path (Split-Path -Parent $taskArchive) -Force | Out-Null
        Move-Item -LiteralPath $taskVenv -Destination $taskArchive
        Write-Host ('Invalid/copied environment preserved: ' + $taskArchive)
    }
}
if (-not (Test-Path -LiteralPath $taskVenvPython)) {
    Invoke-Checked $PythonExe @('-m', 'venv', $taskVenv) 'Virtual environment creation failed.'
}
Invoke-Checked $taskVenvPython @('-m', 'pip', 'install', '-e', $taskRoot) 'Bridge dependency installation failed.'
Invoke-Checked $taskVenvPython @('-m', 'pip', 'check') 'Dependency consistency check failed.'

# Only the current process and the MCP entry receive these variables. No user-
# wide environment variables or Renga registration/licensing settings are changed.
$env:RENGA_SDK_PATH = $SdkPath
$env:RENGA_BRIDGE_WRITE_ROOT = $WriteRoot
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
Write-Host 'Checking the installed Renga version in a separate owned COM process...'
Invoke-Checked $taskVenvPython @('-m', 'renga_codex_bridge.cli', 'doctor') 'Renga diagnostic failed; no MCP entry was changed. Check SDK path, installed Renga, COM registration and the diagnostic error.'

$taskCodexHome = if ($env:CODEX_HOME) { [IO.Path]::GetFullPath($env:CODEX_HOME) }
                 else { Join-Path $env:USERPROFILE '.codex' }
$taskConfig = Join-Path $taskCodexHome 'config.toml'
$taskCodex = Get-Command 'codex' -CommandType Application -ErrorAction SilentlyContinue
$taskBackup = $null
$taskRegistered = $false
if (-not $SkipCodex -and $taskCodex) {
    $taskExistingProbe = Invoke-Probe $taskCodex.Source @('mcp', 'get', $ServerName, '--json')
    if ($taskExistingProbe.ExitCode -eq 0) {
        $taskExisting = ($taskExistingProbe.Output -join [Environment]::NewLine) | ConvertFrom-Json
        $taskSameCommand = ($taskExisting.transport.PSObject.Properties.Name -contains 'command' -and
            $taskExisting.transport.PSObject.Properties.Name -contains 'args' -and
            $taskExisting.transport.command -eq $taskVenvPython -and
            (@($taskExisting.transport.args) -join '|') -eq ('-m|' + $taskModule))
        if (-not $taskSameCommand -and -not $ReplaceExistingRegistration) {
            throw ('An unrelated Codex MCP entry named ' + $ServerName + ' already exists. Choose -ServerName or explicitly use -ReplaceExistingRegistration. No configuration was changed.')
        }
    }
    $taskBackup = Backup-CodexConfig $taskConfig
    $taskAddArgs = @('mcp', 'add', $ServerName,
        '--env', ('RENGA_SDK_PATH=' + $SdkPath),
        '--env', ('RENGA_BRIDGE_WRITE_ROOT=' + $WriteRoot),
        '--env', 'PYTHONUTF8=1', '--env', 'PYTHONIOENCODING=utf-8',
        '--', $taskVenvPython, '-m', $taskModule)
    Invoke-Checked $taskCodex.Source $taskAddArgs 'Codex MCP registration failed. The backup is preserved; inspect config before restoring it, especially if another process edited it.'
    $taskRegisteredText = & $taskCodex.Source mcp get $ServerName --json
    if ($LASTEXITCODE -ne 0) { throw 'Codex MCP entry could not be read back.' }
    $taskRegisteredEntry = ($taskRegisteredText -join [Environment]::NewLine) | ConvertFrom-Json
    if ($taskRegisteredEntry.transport.command -ne $taskVenvPython -or
        (@($taskRegisteredEntry.transport.args) -join '|') -ne ('-m|' + $taskModule)) {
        throw 'Read-back MCP command did not match this installation.'
    }
    $taskRegistered = $true
} else {
    Write-Host 'Codex configuration was not changed. Register with the following command once codex is on PATH:'
    Write-Host ('codex mcp add ' + $ServerName + ' --env "RENGA_SDK_PATH=' + $SdkPath + '" --env "RENGA_BRIDGE_WRITE_ROOT=' + $WriteRoot + '" --env PYTHONUTF8=1 --env PYTHONIOENCODING=utf-8 -- "' + $taskVenvPython + '" -m ' + $taskModule)
    Write-Host 'Before manual registration, back up your Codex config.toml. See docs/INSTALL_EN.md or docs/INSTALL_RU.md.'
}

@{
    schema_version = 1; installed_utc = $taskStamp; repository = $taskRoot
    python = $taskVenvPython; module = $taskModule; server_name = $ServerName
    sdk_path = $SdkPath; write_root = $WriteRoot; codex_config = $taskConfig
    codex_registered = $taskRegistered; codex_config_backup = $taskBackup
} | ConvertTo-Json | Set-Content -LiteralPath $taskMarker -Encoding UTF8
Write-Host ('Bridge installed. Local installation record: ' + $taskMarker)
Write-Host 'Restart/reconnect your Codex MCP session, then request the bridge status tool. Configuration read-back and COM doctor do not prove that an already-open Codex chat has refreshed its tools.'
