[CmdletBinding()]
param([switch]$Json)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "scripts\ThesisLens.Runtime.psm1") -Force
$status = Get-ThesisLensStatus
if ($Json) {
    $status | ConvertTo-Json -Depth 4
    exit 0
}
Write-Host "ThesisLens local status" -ForegroundColor Cyan
Write-Host "  Backend:      $($status.backend)"
Write-Host "  Build:        $($status.backend_build)"
Write-Host "  Expected:     $($status.expected_build)"
Write-Host "  Market Pulse: $($status.market_pulse)"
Write-Host "  General AI:   $($status.general_ai) ($($status.configured_model))"
Write-Host "  Database:     $($status.database)"
Write-Host "  Frontend:     $($status.frontend)"
Write-Host "  Managed PIDs are shown only when process ownership can be verified."
