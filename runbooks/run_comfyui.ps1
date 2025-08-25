<#
.SYNOPSIS
Helper script to manage the ComfyUI service.
This script provides commands to start and stop the ComfyUI server but does not autostart it.
#>

function Start-ComfyUI {
    Write-Host "Starting ComfyUI..."
    Write-Host "Please run the following command in a new terminal:"
    Write-Host "powershell -File .\\scripts\\win\\comfyui_directml.ps1"
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
