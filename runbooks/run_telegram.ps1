<#
.SYNOPSIS
    Starts the main Telegram Bot service.
    This script should be run in the foreground.
#>

# Ensure the virtual environment is activated
$VenvPath = Join-Path -Path $PSScriptRoot -ChildPath '..\.venv\Scripts\Activate.ps1'
if (-not (Test-Path $VenvPath)) {
    Write-Error "Virtual environment not found. Please run the main setup script first."
    exit 1
}
. $VenvPath

Write-Host "Starting the Telegram Bot Service..."
.\.venv\Scripts\python.exe telegram_bot.py
