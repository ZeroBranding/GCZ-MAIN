<#
.SYNOPSIS
    Performs post-installation checks and setup for the project.
    Verifies dependencies, sets up the Python virtual environment, and installs packages.
#>
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$baseDir = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent
$venvDir = Join-Path -Path $baseDir -ChildPath '.venv'
$requirementsFile = Join-Path -Path $baseDir -ChildPath 'requirements.txt'

# --- Dependency Checks ---
Write-Host "--- Running Post-Install Dependency Checks ---" -ForegroundColor Cyan

function Check-Command {
    param([string]$Command, [string]$VersionArgs, [string]$MinVersion, [string]$InstallUrl)
    Write-Host -NoNewline "Checking for $Command... "
    try {
        $versionOutput = Invoke-Expression "$Command $VersionArgs"
        $versionString = ($versionOutput | Select-Object -First 1).ToString()
        $versionMatch = [regex]::Match($versionString, '(\d+\.\d+)').Groups[1].Value
        
        if ([version]$versionMatch -ge [version]$MinVersion) {
            Write-Host "OK ($versionString)" -ForegroundColor Green
            return $true
        } else {
            Write-Host "FAIL (Version $versionMatch is older than required $MinVersion)" -ForegroundColor Yellow
            Write-Host "Please upgrade from: $InstallUrl"
            return $false
        }
    } catch {
        Write-Host "FAIL (Not found)" -ForegroundColor Yellow
        Write-Host "Please install from: $InstallUrl"
        return $false
    }
}

# Python
Check-Command -Command 'python' -VersionArgs '--version' -MinVersion '3.10' -InstallUrl 'https://www.python.org/downloads/'

# Pip
Check-Command -Command 'pip' -VersionArgs '--version' -MinVersion '22.0' -InstallUrl 'https://pip.pypa.io/en/stable/installation/'

# Git
Check-Command -Command 'git' -VersionArgs '--version' -MinVersion '2.30' -InstallUrl 'https://git-scm.com/download/win'

# Node
Check-Command -Command 'node' -VersionArgs '--version' -MinVersion '20.0' -InstallUrl 'https://nodejs.org/'

# PowerShell Execution Policy
Write-Host -NoNewline "Checking PowerShell Execution Policy... "
$policy = Get-ExecutionPolicy
if ($policy -eq 'RemoteSigned' -or $policy -eq 'Unrestricted') {
    Write-Host "OK ($policy)" -ForegroundColor Green
} else {
    Write-Host "FAIL ($policy)" -ForegroundColor Yellow
    Write-Host "Please run: Set-ExecutionPolicy RemoteSigned -Scope CurrentUser"
}

# FFMPEG
Write-Host -NoNewline "Checking for ffmpeg... "
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Host "OK (Found in PATH)" -ForegroundColor Green
} else {
    Write-Host "FAIL (Not found in PATH)" -ForegroundColor Yellow
    Write-Host "Please install from: https://ffmpeg.org/download.html and add to your system PATH."
}

# Visual C++ Redistributable
# A simple check for a common DLL. This is not foolproof.
Write-Host -NoNewline "Checking for Visual C++ Redistributable... "
$vcDllPath = Join-Path -Path $env:SystemRoot -ChildPath 'System32\msvcp140.dll'
if (Test-Path $vcDllPath) {
    Write-Host "OK (Found msvcp140.dll)" -ForegroundColor Green
} else {
    Write-Host "FAIL (msvcp140.dll not found)" -ForegroundColor Yellow
    Write-Host "Please install the latest Visual C++ Redistributable from Microsoft."
}


# --- Python Virtual Environment Setup ---
Write-Host "`n--- Python Virtual Environment Setup ---" -ForegroundColor Cyan

if (-not (Test-Path -Path $venvDir -PathType Container)) {
    Write-Host "Virtual environment not found. Creating at '$venvDir'..."
    python -m venv $venvDir
    Write-Host "Virtual environment created." -ForegroundColor Green
} else {
    Write-Host "Virtual environment already exists."
}

# Install Python requirements
Write-Host "`nInstalling Python requirements from '$($requirementsFile)'..."
try {
    # Determine correct pip executable
    $pipExe = Join-Path -Path $venvDir -ChildPath 'Scripts\pip.exe'
    if (-not (Test-Path $pipExe)) {
        throw "pip.exe not found in venv!"
    }
    & $pipExe install -r $requirementsFile
    Write-Host "Python requirements installed successfully." -ForegroundColor Green
} catch {
    Write-Error "Failed to install Python requirements. Error: $_"
}

# --- Final Steps ---
Write-Host "`n--- Post-Install Complete ---" -ForegroundColor Cyan
Write-Host "Next steps:"
Write-Host "1. Copy '.env.template' to '.env' and fill in your secrets."
Write-Host "2. Run 'scripts\win\doctor.ps1' to verify your setup."
Write-Host "3. Activate the virtual environment with: .\.venv\Scripts\Activate.ps1"
