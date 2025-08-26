<#
.SYNOPSIS
    Starts the standalone email polling service.
    This script should be run in the background to continuously monitor for new emails.
#>

# Ensure the virtual environment is activated to find the correct python and packages
$VenvPath = Join-Path -Path $PSScriptRoot -ChildPath '..\.venv\Scripts\Activate.ps1'
if (-not (Test-Path $VenvPath)) {
    Write-Error "Virtual environment not found. Please run the main setup script first."
    exit 1
}
. $VenvPath

Write-Host "Starting the Email Poller Service..."
Write-Host "Python will now load the .env file internally."
# Redirect all output streams (stdout and stderr) to a log file
python.exe -m services.email_poller *>> logs/poller.log
