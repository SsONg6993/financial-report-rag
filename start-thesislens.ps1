[CmdletBinding()]
param([switch]$NoBrowser)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "scripts\ThesisLens.Runtime.psm1") -Force
try {
    Start-ThesisLens -NoBrowser:$NoBrowser
} catch {
    Write-Error $_.Exception.Message
    Write-Host "Run .\status-thesislens.ps1 for safe diagnostics." -ForegroundColor Yellow
    exit 1
}
