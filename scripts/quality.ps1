<#
.SYNOPSIS
    Project Atlas — local quality gate.

.DESCRIPTION
    Runs the same checks as the `quality` job in .github/workflows/ci.yml, in
    the same order, so that a green run here means a green run there. Any
    divergence between this file and that workflow is a bug in one of them.

.PARAMETER Fix
    Apply Ruff's safe fixes and Black's formatting instead of only checking.

.EXAMPLE
    scripts\quality.ps1

.EXAMPLE
    scripts\quality.ps1 -Fix
#>
[CmdletBinding()]
param(
    [switch] $Fix
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Set-Location (Join-Path $PSScriptRoot '..')

if (-not (Get-Command poetry -ErrorAction SilentlyContinue)) {
    Write-Error 'poetry not found on PATH - see README.md, section Development Setup'
    exit 127
}

function Invoke-Step {
    param(
        [Parameter(Mandatory)] [string]   $Name,
        [Parameter(Mandatory)] [string[]] $Command
    )

    Write-Host ''
    Write-Host "==> $Name" -ForegroundColor Cyan

    # Native exit codes are the signal here; $LASTEXITCODE is checked directly
    # because PowerShell does not raise on a non-zero exit from an executable.
    & poetry @Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host ''
        Write-Host "$Name failed (exit $LASTEXITCODE)." -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

if ($Fix) {
    Invoke-Step -Name 'Ruff (fixing)'     -Command @('run', 'ruff', 'check', '--fix', '.')
    Invoke-Step -Name 'Black (formatting)' -Command @('run', 'black', '.')
}
else {
    Invoke-Step -Name 'Ruff'  -Command @('run', 'ruff', 'check', '.')
    Invoke-Step -Name 'Black' -Command @('run', 'black', '--check', '--diff', '.')
}

Invoke-Step -Name 'MyPy'   -Command @('run', 'mypy', '.')
Invoke-Step -Name 'Pytest' -Command @('run', 'pytest')

Write-Host ''
Write-Host 'Quality gate passed.' -ForegroundColor Green
