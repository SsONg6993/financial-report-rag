import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "ThesisLens.Runtime.psm1"


def powershell(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_runtime_scripts_parse_and_never_default_to_force_kill():
    source = MODULE.read_text(encoding="utf-8")
    assert "Stop-Process -Id $pid -Force" not in source
    assert "taskkill /F" not in source
    result = powershell(
        "$errors=$null;$tokens=$null;"
        "[System.Management.Automation.Language.Parser]::ParseFile("
        f"'{MODULE}',[ref]$tokens,[ref]$errors)|Out-Null;"
        "if($errors.Count){$errors|% Message;exit 1}"
    )
    assert result.returncode == 0, result.stderr + result.stdout


def test_backend_listener_decisions_are_safe_and_version_aware():
    script = f"""
Import-Module '{MODULE}' -Force
$module = Get-Module ThesisLens.Runtime
$result = & $module {{
  @(
    Get-BackendListenerDecision $null $null 'new' $false
    Get-BackendListenerDecision 100 ([pscustomobject]@{{service='ThesisLens Backend';build_commit='new'}}) 'new' $false
    Get-BackendListenerDecision 100 ([pscustomobject]@{{service='ThesisLens Backend';build_commit='old'}}) 'new' $true
    Get-BackendListenerDecision 100 ([pscustomobject]@{{status='ok'}}) 'new' $false
    Get-BackendListenerDecision 100 $null 'new' $false
  )
}}
$result | ConvertTo-Json -Compress
"""
    result = powershell(script)
    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads(result.stdout.strip()) == [
        "start",
        "reuse",
        "replace",
        "refuse",
        "refuse",
    ]


def test_status_command_does_not_print_environment_secrets():
    source = (ROOT / "status-thesislens.ps1").read_text(encoding="utf-8")
    assert "TELEGRAM" not in source
    assert "TYPESAFE_API_KEY" not in source
    assert "Get-ChildItem Env:" not in source
