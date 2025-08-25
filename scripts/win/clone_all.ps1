<#
.SYNOPSIS
    Clones or updates all required external repositories for the German Code Zero AI project.
    This script is idempotent. If a repository already exists, it will be updated via git pull.
#>
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$baseDir = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent
$externalDir = Join-Path -Path $baseDir -ChildPath 'external'

# Helper to ensure a directory exists
function Ensure-Dir {
    param([string]$Path)
    if (-not (Test-Path -Path $Path -PathType Container)) {
        Write-Host "Creating directory: $Path"
        New-Item -Path $Path -ItemType Directory -Force | Out-Null
    }
}

# Repositories to clone
$repos = @{
    'TikTokAutoUploader'    = 'https://github.com/bellingcat/TikTokUploader.git' # Note: Using a popular fork as original is gone.
    'OpenVoice'             = 'https://github.com/myshell-ai/OpenVoice.git'
    'XTTS'                  = 'https://github.com/coqui-ai/TTS.git'
    'SadTalker'             = 'https://github.com/OpenTalker/SadTalker.git'
    'Real-ESRGAN'           = 'https://github.com/xinntao/Real-ESRGAN.git'
    'ComfyUI'               = 'https://github.com/comfyanonymous/ComfyUI.git'
    'ComfyUI-Manager'       = 'https://github.com/ltdrdata/ComfyUI-Manager.git'
    'Wav2Lip'               = 'https://github.com/Rudrabha/Wav2Lip.git'
    'RIFE'                  = 'https://github.com/hzwer/Practical-RIFE.git'
    'mcp-python'            = 'https://github.com/Mause/mcp-python.git'
    'baresip'               = 'https://github.com/baresip/baresip.git'
}

Write-Host "--- Starting Clone/Update Process for External Repositories ---"
Ensure-Dir -Path $externalDir
Push-Location $externalDir

foreach ($repoName in $repos.Keys) {
    $repoUrl = $repos[$repoName]
    $repoDir = Join-Path -Path $externalDir -ChildPath $repoName

    Write-Host ""
    Write-Host "Processing repository: $repoName"

    if (Test-Path -Path $repoDir -PathType Container) {
        Write-Host "Directory exists. Fetching updates..."
        try {
            Push-Location $repoDir
            git fetch --all
            git pull --ff-only
            Pop-Location
            Write-Host "Successfully updated $repoName." -ForegroundColor Green
        } catch {
            Write-Error "Failed to update $repoName. Error: $_"
        }
    } else {
        Write-Host "Directory not found. Cloning repository..."
        try {
            git clone --depth 1 $repoUrl $repoName
            Write-Host "Successfully cloned $repoName." -ForegroundColor Green
        } catch {
            Write-Error "Failed to clone $repoName. Error: $_"
        }
    }
}

# Placeholder for Piper voices
$piperVoicesDir = Join-Path -Path $externalDir -ChildPath 'piper-voices'
Write-Host ""
Write-Host "Ensuring Piper voices placeholder directory exists..."
Ensure-Dir -Path $piperVoicesDir
Write-Host "Directory 'piper-voices' is ready." -ForegroundColor Green


Pop-Location
Write-Host ""
Write-Host "--- External Repositories Process Finished ---" -ForegroundColor Cyan
