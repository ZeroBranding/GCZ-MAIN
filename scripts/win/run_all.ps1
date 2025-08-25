<#
.SYNOPSIS
    Runs the full setup and verification process for the project.
    Executes cloning, post-installation, and diagnostics in sequence.
#>
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$cloneScript = Join-Path -Path $scriptDir -ChildPath 'clone_all.ps1'
$postInstallScript = Join-Path -Path $scriptDir -ChildPath 'post_install.ps1'
$doctorScript = Join-Path -Path $scriptDir -ChildPath 'doctor.ps1'

Write-Host "--- Starting Full Setup and Verification ---" -ForegroundColor Cyan

try {
    Write-Host "`n[Step 1/3] Running clone_all.ps1..." -ForegroundColor Yellow
    & $cloneScript
    if ($LASTEXITCODE -ne 0) { throw "clone_all.ps1 failed." }

    Write-Host "`n[Step 2/3] Running post_install.ps1..." -ForegroundColor Yellow
    & $postInstallScript
    if ($LASTEXITCODE -ne 0) { throw "post_install.ps1 failed." }

    Write-Host "`n[Step 3/3] Running doctor.ps1..." -ForegroundColor Yellow
    & $doctorScript
    if ($LASTEXITCODE -ne 0) { throw "doctor.ps1 failed." }

    Write-Host "`n--- Full Setup and Verification Completed Successfully ---" -ForegroundColor Green
} catch {
    Write-Host "`n--- SCRIPT EXECUTION FAILED ---" -ForegroundColor Red
    Write-Host "An error occurred: $_"
    exit 1
}

exit 0
