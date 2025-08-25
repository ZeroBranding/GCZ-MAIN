<#
.SYNOPSIS
    Pulls a curated list of foundational models from Ollama Hub.
#>
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$modelsToPull = @(
    "qwen2:7b-instruct",
    "llama3.1:8b-instruct",
    "gemma2:9b-instruct",
    "mistral:7b-instruct",
    "phi3:medium",
    "deepseek-coder-v2:lite",
    "deepseek-coder:6.7b",
    "codegemma:7b",
    "llava:7b" # vision model
)

Write-Host "--- Starting Ollama Model Pull Process ---" -ForegroundColor Cyan
Write-Host "This may take a significant amount of time and disk space."

foreach ($model in $modelsToPull) {
    Write-Host "`nPulling model: $model..." -ForegroundColor Yellow
    try {
        ollama pull $model
        Write-Host "Successfully pulled $model." -ForegroundColor Green
    } catch {
        Write-Host "Failed to pull $model. Error: $_" -ForegroundColor Red
        Write-Host "Please ensure Ollama is running and accessible."
        # Continue to the next model
    }
}

Write-Host "`n--- Model Pull Process Finished ---" -ForegroundColor Cyan
Write-Host "Listing all available local models:"
ollama list
