<#
.SYNOPSIS
    Starts the standalone email polling service.
    This script should be run in the background to continuously monitor for new emails.
#>

# --- Load .env file manually ---
$envPath = Join-Path -Path $PSScriptRoot -ChildPath '..\.env'
if (Test-Path $envPath) {
    Get-Content $envPath | ForEach-Object {
        if ($_ -match "^\s*([\w.-]+)\s*=\s*(.*)") {
            $key = $matches[1]
            $value = $matches[2].Trim('"')
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
            Write-Host "Loaded env var: $key"
        }
    }
} else {
    Write-Warning ".env file not found. The service might fail."
}


# Ensure the virtual environment is activated to find the correct python and packages
$VenvPath = Join-Path -Path $PSScriptRoot -ChildPath '..\.venv\Scripts\Activate.ps1'
if (-not (Test-Path $VenvPath)) {
    Write-Error "Virtual environment not found. Please run the main setup script first."
    exit 1
}
. $VenvPath

Write-Host "Starting the Email Poller Service with loaded env vars..."
# Redirect all output streams (stdout and stderr) to a log file
python.exe -m services.email_poller *>> logs/poller.log
