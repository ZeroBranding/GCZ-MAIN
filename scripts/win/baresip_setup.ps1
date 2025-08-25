# Baresip Setup Script for Windows
# This script downloads and prepares baresip for use with the project.

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Project root directory
$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent
$ExternalDir = Join-Path $ProjectRoot "external"
$BaresipDir = Join-Path $ExternalDir "baresip"
$BaresipZip = Join-Path $ExternalDir "baresip.zip"
$BaresipUrl = "https://github.com/baresip/baresip/releases/download/v3.7.0/baresip-3.7.0-win32.zip" # Example URL, check for the latest version

# --- Main ---

# 1. Create external directory if it doesn't exist
if (-not (Test-Path $ExternalDir)) {
    Write-Host "Creating external directory at $ExternalDir"
    New-Item -ItemType Directory -Path $ExternalDir | Out-Null
}

# 2. Download baresip
if (-not (Test-Path $BaresipDir)) {
    Write-Host "Downloading baresip from $BaresipUrl..."
    try {
        Invoke-WebRequest -Uri $BaresipUrl -OutFile $BaresipZip
    } catch {
        Write-Error "Failed to download baresip. Please check the URL and your internet connection."
        Write-Error $_.Exception.Message
        exit 1
    }

    Write-Host "Extracting baresip..."
    Expand-Archive -Path $BaresipZip -DestinationPath $BaresipDir -Force

    # Clean up the zip file
    Remove-Item $BaresipZip
    
    # The extracted folder might have a subfolder, e.g., baresip-3.7.0. Move contents up.
    $subfolder = Get-ChildItem -Path $BaresipDir | Where-Object { $_.PSIsContainer } | Select-Object -First 1
    if ($null -ne $subfolder) {
        Get-ChildItem -Path $subfolder.FullName | Move-Item -Destination $BaresipDir -Force
        Remove-Item $subfolder.FullName -Recurse
    }

    Write-Host "Baresip downloaded and extracted to $BaresipDir"
} else {
    Write-Host "Baresip directory already exists. Skipping download."
}

# 3. Create sample configuration
$ConfigDir = Join-Path $ProjectRoot "configs"
$BaresipConfigDir = Join-Path $ConfigDir "baresip"
$AccountsFile = Join-Path $BaresipConfigDir "accounts"

if (-not (Test-Path $BaresipConfigDir)) {
    New-Item -ItemType Directory -Path $BaresipConfigDir | Out-Null
}

if (-not (Test-Path $AccountsFile)) {
    Write-Host "Creating sample baresip accounts file at $AccountsFile"
    $accountsContent = @'
#
# Baresip accounts file
#
# Format: <sip:user:password@host;params>
# Example: <sip:user:secret@sip.example.com>
#
# Replace with your actual SIP account details.
#
<sip:your_user:your_password@your_sip_provider.com>
'@
    $accountsContent | Out-File -FilePath $AccountsFile -Encoding utf8
    Write-Host "Sample accounts file created. Please edit it with your SIP credentials."
} else {
    Write-Host "Baresip accounts file already exists. Skipping creation."
}

Write-Host "Baresip setup complete."
