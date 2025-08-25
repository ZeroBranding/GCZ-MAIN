<#
.SYNOPSIS
Runs the main agent with a given prompt.
#>

param (
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Prompt
)

Write-Host "--- Running GCZ Agent ---"

# Assuming a virtual environment exists at .venv
$VenvPath = ".\\venv\\Scripts\\Activate.ps1"

if (-not (Test-Path $VenvPath)) {
    Write-Host "Virtual environment not found at '$VenvPath'."
    Write-Host "Please create it first. Example: python -m venv .venv"
    exit 1
}

Write-Host "Activating virtual environment..."
& $VenvPath

Write-Host "Running agent with prompt: '$Prompt'"
python -m agent.agent --prompt "$Prompt"

Write-Host "Agent execution finished."
