<#
.SYNOPSIS
    Creates 4-bit quantized versions of specified large models to save disk space and VRAM.
#>
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Models to consider for quantization. The script will check if they exist first.
$modelsToQuantize = @{
    "qwen2:7b-instruct"      = "qwen2:7b-instruct-q4"
    "llama3.1:8b-instruct"   = "llama3.1:8b-instruct-q4"
    "gemma2:9b-instruct"     = "gemma2:9b-instruct-q4"
    "phi3:medium"            = "phi3:medium-q4"
    "deepseek-coder:6.7b"    = "deepseek-coder:6.7b-q4"
    "codegemma:7b"           = "codegemma:7b-q4"
}

Write-Host "--- Starting Ollama Model Quantization ---" -ForegroundColor Cyan

# Get a list of currently installed models
$installedModels = (ollama list | Select-Object -Skip 1 | ForEach-Object { $_.Split(' ')[0] })

foreach ($sourceModel in $modelsToQuantize.Keys) {
    if ($installedModels -contains $sourceModel) {
        $targetModel = $modelsToQuantize[$sourceModel]
        Write-Host "`nQuantizing model: $sourceModel to $targetModel..." -ForegroundColor Yellow
        try {
            ollama create $targetModel --quantize q4 -f (ollama show --modelfile $sourceModel)
            Write-Host "Successfully created quantized model $targetModel." -ForegroundColor Green
            Write-Host "You may want to remove the original model to save space: ollama rm $sourceModel" -ForegroundColor Magenta
        } catch {
            Write-Host "Failed to quantize $sourceModel. Error: $_" -ForegroundColor Red
        }
    } else {
        Write-Host "`nSkipping quantization for $sourceModel (not found locally)." -ForegroundColor Gray
    }
}

Write-Host "`n--- Model Quantization Finished ---" -ForegroundColor Cyan
Write-Host "Final list of local models:"
ollama list
