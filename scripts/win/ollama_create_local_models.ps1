<#
.SYNOPSIS
    Creates local, specialized models from the Modelfiles in the repository.
#>
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$baseDir = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent
$modelfilesDir = Join-Path -Path $baseDir -ChildPath 'models\ollama\Modelfiles'

if (-not (Test-Path -Path $modelfilesDir -PathType Container)) {
    Write-Error "Directory not found: $modelfilesDir"
    exit 1
}

$modelfiles = Get-ChildItem -Path $modelfilesDir -Filter "*.Modelfile"

Write-Host "--- Starting Local Model Creation from Modelfiles ---" -ForegroundColor Cyan

foreach ($file in $modelfiles) {
    $modelName = $file.BaseName
    $filePath = $file.FullName

    Write-Host "`nCreating model '$modelName' from '$($file.Name)'..." -ForegroundColor Yellow
    try {
        ollama create $modelName -f $filePath
        Write-Host "Successfully created model '$modelName'." -ForegroundColor Green
    } catch {
        Write-Host "Failed to create model '$modelName'. Error: $_" -ForegroundColor Red
        Write-Host "Please ensure the base model specified in the Modelfile is pulled."
        # Continue to the next model
    }
}

Write-Host "`n--- Local Model Creation Finished ---" -ForegroundColor Cyan
Write-Host "Final list of local models:"
ollama list
