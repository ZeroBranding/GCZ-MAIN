<#
.SYNOPSIS
Helper script to manage the ComfyUI service.
This script provides commands to start and stop the ComfyUI server but does not autostart it.
#>

function Start-ComfyUI {
    Write-Host "Starting ComfyUI..."
    $baseDir = Split-Path -Path $PSScriptRoot -Parent
    $comfyUIDir = Join-Path -Path $baseDir -ChildPath "external\ComfyUI"

    if (-not (Test-Path $comfyUIDir)) {
        Write-Error "ComfyUI directory not found at $comfyUIDir. Please run the setup scripts."
        return
    }

    # Ensure logs directory exists
    $logDir = Join-Path -Path $baseDir -ChildPath "logs"
    if (-not (Test-Path $logDir)) {
        New-Item -Path $logDir -ItemType Directory | Out-Null
    }
    $logFile = Join-Path -Path $logDir -ChildPath "comfyui.log"

    # Set working directory and start the process
    Push-Location -Path $comfyUIDir

    $process = Start-Process "python.exe" -ArgumentList "main.py" -PassThru -RedirectStandardOutput $logFile -RedirectStandardError $logFile -WindowStyle Hidden

    Pop-Location

    if ($process) {
        Write-Host "ComfyUI process started with PID $($process.Id). Logs are being written to $logFile"
    } else {
        Write-Error "Failed to start ComfyUI process."
    }
}

function Stop-ComfyUI {
    Write-Host "Stopping ComfyUI..."
    Write-Host "Please manually close the terminal window where ComfyUI is running."
    Write-Host "Alternatively, find the process listening on port 8188 and terminate it."
    # Example: Get-Process -Id (Get-NetTCPConnection -LocalPort 8188).OwningProcess | Stop-Process -Force
}

# --- Main Logic ---
param (
    [string]$Action
)

switch ($Action) {
    "start" {
        Start-ComfyUI
    }
    "stop" {
        Stop-ComfyUI
    }
    default {
        Write-Host "Usage: .\\run_comfyui.ps1 [start|stop]"
        Write-Host "Example: .\\run_comfyui.ps1 start"
    }
}
