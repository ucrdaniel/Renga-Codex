"""Exercise actual installer probe arguments in Windows PowerShell 5.1 only.

The installer body is parsed, never run: no pip, SDK, COM or Codex changes.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell native-argument regression")
def test_valid_x64_python_passes_both_installer_probes_under_windows_powershell(tmp_path):
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    if not powershell.is_file():
        pytest.skip("Windows PowerShell 5.1 unavailable")
    installer = Path(__file__).resolve().parents[2] / "scripts/install.ps1"
    probe = tmp_path / "probe.ps1"
    probe.write_text(r"""
param([string]$InstallerPath, [string]$PythonPath)
$parseErrors=$null
$tokens=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($InstallerPath,[ref]$tokens,[ref]$parseErrors)
if ($parseErrors.Count) { throw 'Installer AST contains parse errors' }
$function=$ast.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Invoke-Probe'},$true)
. ([scriptblock]::Create($function.Extent.Text))
$codes=@($ast.FindAll({param($node)
    $node -is [System.Management.Automation.Language.StringConstantExpressionAst] -and
    $node.Value.StartsWith('import sys') -and $node.Value.Contains('assert sys.version_info')
},$true))
if ($codes.Count -ne 2) { throw 'Expected both actual installer Python version/architecture probes' }
$exits=@(foreach ($code in $codes) {
    $result=Invoke-Probe -Executable $PythonPath -Arguments @('-c',$code.Value)
    $result.ExitCode
})
[pscustomobject]@{version=$PSVersionTable.PSVersion.Major; exits=$exits; count=$codes.Count} | ConvertTo-Json -Compress
""", encoding="ascii")
    result = subprocess.run(
        [str(powershell), "-NoProfile", "-NonInteractive", "-File", str(probe),
         "-InstallerPath", str(installer), "-PythonPath", sys.executable],
        capture_output=True, text=True, encoding="utf8", timeout=30, check=True,
    )
    report = json.loads(result.stdout)
    assert report == {"version": 5, "exits": [0, 0], "count": 2}
