[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$taskRuntime = Join-Path $taskRoot 'runtime'
$taskMarker = Join-Path $taskRuntime 'installation.local.json'
function Invoke-Probe {
    param([string]$Executable, [string[]]$Arguments)
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & $Executable @Arguments 2>$null
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    return [PSCustomObject]@{ ExitCode = $code; Output = @($output) }
}
foreach ($taskLocalPath in @($taskRuntime, (Join-Path $taskRuntime 'backups'))) {
    if (Test-Path -LiteralPath $taskLocalPath) {
        if ((Get-Item -LiteralPath $taskLocalPath).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw ('Refusing a linked runtime path: ' + $taskLocalPath)
        }
    }
}
if (-not (Test-Path -LiteralPath $taskMarker -PathType Leaf)) {
    throw 'This checkout has no installation record. Nothing was changed; inspect Codex MCP entries manually.'
}
$taskInstallation = Get-Content -LiteralPath $taskMarker -Raw | ConvertFrom-Json
$taskExpectedPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
if ($taskInstallation.repository -ne $taskRoot -or
    $taskInstallation.python -ne $taskExpectedPython -or
    $taskInstallation.module -ne 'renga_codex_bridge.mcp_server' -or
    $taskInstallation.server_name -notmatch '^[a-zA-Z0-9_-]+$') {
    throw 'Installation record does not match this checkout. Refusing to remove any configuration.'
}
$taskCodex = Get-Command 'codex' -CommandType Application -ErrorAction SilentlyContinue
if (-not $taskCodex) {
    throw ('Codex CLI is unavailable. With the CLI restored, run this script again. Only remove the MCP entry ' + $taskInstallation.server_name + ' after confirming it points to ' + $taskExpectedPython + '.')
}
$taskCurrentHome = if ($env:CODEX_HOME) { [IO.Path]::GetFullPath($env:CODEX_HOME) }
                   else { Join-Path $env:USERPROFILE '.codex' }
$taskCurrentConfig = Join-Path $taskCurrentHome 'config.toml'
if ($taskCurrentConfig -ne $taskInstallation.codex_config) {
    throw 'CODEX_HOME changed since installation. Restore the original home before uninstalling; no configuration was changed.'
}
$taskEntryProbe = Invoke-Probe $taskCodex.Source @('mcp', 'get', $taskInstallation.server_name, '--json')
if ($taskEntryProbe.ExitCode -ne 0) {
    Write-Host 'The recorded MCP entry is already absent. No configuration was changed.'
} else {
    $taskEntry = ($taskEntryProbe.Output -join [Environment]::NewLine) | ConvertFrom-Json
    if ($taskEntry.transport.PSObject.Properties.Name -notcontains 'command' -or
        $taskEntry.transport.PSObject.Properties.Name -notcontains 'args' -or
        $taskEntry.transport.command -ne $taskExpectedPython -or
        (@($taskEntry.transport.args) -join '|') -ne '-m|renga_codex_bridge.mcp_server') {
        throw 'The MCP entry now belongs to another command. Refusing to remove it.'
    }
    if (Test-Path -LiteralPath $taskCurrentConfig) {
        $taskBackupFolder = Join-Path $taskRuntime 'backups'
        New-Item -ItemType Directory -Path $taskBackupFolder -Force | Out-Null
        $taskStamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ')
        $taskBackup = Join-Path $taskBackupFolder ('codex-config-uninstall-' + $taskStamp + '.toml')
        if (Test-Path -LiteralPath $taskBackup) { throw 'Backup target already exists.' }
        Copy-Item -LiteralPath $taskCurrentConfig -Destination $taskBackup
        if ((Get-FileHash -LiteralPath $taskCurrentConfig -Algorithm SHA256).Hash -ne
            (Get-FileHash -LiteralPath $taskBackup -Algorithm SHA256).Hash) {
            throw 'Configuration backup hash mismatch.'
        }
        Write-Host ('Codex configuration backup: ' + $taskBackup)
    }
    & $taskCodex.Source mcp remove $taskInstallation.server_name
    if ($LASTEXITCODE -ne 0) { throw 'Codex MCP removal failed; inspect config and the preserved backup.' }
    $taskRemovedProbe = Invoke-Probe $taskCodex.Source @('mcp', 'get', $taskInstallation.server_name, '--json')
    if ($taskRemovedProbe.ExitCode -eq 0) { throw 'The MCP entry is still registered after removal.' }
    Write-Host 'The MCP entry belonging to this checkout was removed.'
}

Write-Host 'Renga, SDK, other Codex entries, repository, virtual environment, logs, backups and BIM files were preserved.'
Write-Host 'The installer did not create user-wide environment variables; there are none to unregister.'
Write-Host 'Reconnect Codex to stop using the removed entry. Remove this checkout/environment yourself only after stopping its processes and preserving needed files.'
