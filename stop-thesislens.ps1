[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "scripts\ThesisLens.Runtime.psm1") -Force
Stop-ThesisLens
