<#
.SYNOPSIS
    Starts the main Telegram Bot service.
    This script should be run in the foreground.
#>

# --- Load .env file manually ---
$envPath = Join-Path -Path $PSScriptRoot -ChildPath '..\.env'
if (Test-Path $envPath) {
    Get-Content $envPath | ForEach-Object {
        if ($_ -match "^\s*([\w.-]+)\s*=\s*(.*)") {
            $key = $matches[1]
            $value = $matches[2].Trim('"')
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
            Write-Host "Loaded env var for Bot: $key"
        }
    }
} else {
    Write-Warning ".env file not found. The bot will likely fail."
}

# Ensure the virtual environment is activated
$VenvPath = Join-Path -Path $PSScriptRoot -ChildPath '..\.venv\Scripts\Activate.ps1'
if (-not (Test-Path $VenvPath)) {
    Write-Error "Virtual environment not found. Please run the main setup script first."
    exit 1
}
. $VenvPath

Write-Host "Starting the Telegram Bot Service..."
.\.venv\Scripts\python.exe telegram_bot.py
