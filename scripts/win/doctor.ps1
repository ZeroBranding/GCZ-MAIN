<#
.SYNOPSIS
    Diagnoses the local environment to ensure it's ready for running the project.
    Checks .env file, port availability, directory permissions, and hardware.
#>
param()

$ErrorActionPreference = 'SilentlyContinue'
Set-StrictMode -Version Latest

$baseDir = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent
$envFile = Join-Path -Path $baseDir -ChildPath '.env'

$results = @()
$overallStatus = 0 # 0 for PASS, 1 for FAIL

# --- Helper Functions ---
function Add-Result {
    param([string]$Check, [bool]$Success, [string]$Message)
    global:results += [PSCustomObject]@{
        Check   = $Check
        Status  = if ($Success) { "PASS" } else { "FAIL" }
        Message = $Message
    }
    if (-not $Success) {
        $global:overallStatus = 1
    }
}

# --- Checks ---

# 1. .env file existence
if (Test-Path $envFile) {
    Add-Result -Check ".env File" -Success $true -Message "File exists at $envFile"
    
    # 2. .env file required keys
    $envContent = Get-Content $envFile -Raw
    $requiredKeys = @(
        'OLLAMA_BASE_URL', # Note: Using OLLAMA_BASE_URL as per .env.template
        'TELEGRAM_BOT_TOKEN',
        'INSTAGRAM_USERNAME',
        'INSTAGRAM_PASSWORD',
        'YOUTUBE_API_KEY' # Note: Checking for API key instead of secrets file path
    )

    foreach ($key in $requiredKeys) {
        if ($envContent -match "^\s*$key\s*=\s*.(.+)") {
            Add-Result -Check ".env Key: $key" -Success $true -Message "Key is present and not empty."
        } else {
            Add-Result -Check ".env Key: $key" -Success $false -Message "Key is missing or empty."
        }
    }
} else {
    Add-Result -Check ".env File" -Success $false -Message "File not found. Please copy .env.template to .env and fill it out."
}

# 3. Port availability
$portsToCheck = @(7860, 11434, 8000, 8080)
foreach ($port in $portsToCheck) {
    $tcpConnection = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($null -eq $tcpConnection) {
        Add-Result -Check "Port $port" -Success $true -Message "Port is free."
    } else {
        Add-Result -Check "Port $port" -Success $false -Message "Port is in use by process with ID $($tcpConnection.OwningProcess)."
    }
}

# 4. Directory writability
$dirsToCheck = @(
    (Join-Path -Path $baseDir -ChildPath 'artifacts'),
    (Join-Path -Path $baseDir -ChildPath 'external'),
    (Join-Path -Path $baseDir -ChildPath 'models')
)
foreach ($dir in $dirsToCheck) {
    $tempFile = Join-Path -Path $dir -ChildPath "write_test_$(New-Guid).tmp"
    try {
        "test" | Out-File -FilePath $tempFile -Encoding ascii
        Remove-Item $tempFile -Force
        Add-Result -Check "Directory Write: $dir" -Success $true -Message "Directory is writable."
    } catch {
        Add-Result -Check "Directory Write: $dir" -Success $false -Message "Directory is not writable. Check permissions."
    }
}

# 5. GPU Information
try {
    $gpu = Get-CimInstance -ClassName Win32_VideoController
    if ($gpu) {
        $gpuName = $gpu.Name
        $gpuDriver = $gpu.DriverVersion
        Add-Result -Check "GPU Info" -Success $true -Message "$gpuName (Driver: $gpuDriver)"
    } else {
         Add-Result -Check "GPU Info" -Success $false -Message "Could not retrieve GPU information via WMI."
    }
} catch {
    Add-Result -Check "GPU Info" -Success $false -Message "Failed to query WMI for GPU info. Error: $_"
}


# --- Output ---
Write-Host "`n--- System Doctor Results ---" -ForegroundColor Cyan
$results | Format-Table -AutoSize

if ($overallStatus -eq 0) {
    Write-Host "`nOverall Status: PASS" -ForegroundColor Green
    Write-Host "Your system appears to be configured correctly."
} else {
    Write-Host "`nOverall Status: FAIL" -ForegroundColor Red
    Write-Host "Please address the issues listed above."
}

exit $overallStatus
