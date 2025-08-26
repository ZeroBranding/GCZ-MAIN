<#
.SYNOPSIS
    Starts all essential services for the German Code Zero AI project in the correct order.
#>

Write-Host "--- Starting All Services ---" -ForegroundColor Cyan

# 1. Start ComfyUI in the background and wait for it to be healthy
Write-Host "`n[Step 1/3] Starting ComfyUI Service in the background..." -ForegroundColor Yellow
Start-Process powershell -WindowStyle Hidden -ArgumentList "-Command", ".\runbooks\run_comfyui.ps1 -Action start"

Write-Host "Waiting for ComfyUI to become available..."
$maxRetries = 10
$retryDelaySeconds = 3
$comfyUIUrl = "http://127.0.0.1:8188/history/1" # An endpoint that should return 404 when server is up
$healthy = $false

foreach ($i in 1..$maxRetries) {
    try {
        $response = Invoke-WebRequest -Uri $comfyUIUrl -Method Get -TimeoutSec 2
        # A response (even an error like 404) means the server is up.
        Write-Host "ComfyUI is up! (Status: $($response.StatusCode))" -ForegroundColor Green
        $healthy = $true
        break
    } catch {
        Write-Host "Attempt $i of $maxRetries: ComfyUI not yet available. Retrying in $retryDelaySeconds seconds..."
        Start-Sleep -Seconds $retryDelaySeconds
    }
}

if (-not $healthy) {
    Write-Error "ComfyUI failed to start within the timeout period. Check logs/comfyui.log for details."
    exit 1
}

# 2. Start Email Poller in the background
Write-Host "`n[Step 2/3] Starting Email Poller Service in the background..." -ForegroundColor Yellow
Start-Process powershell -WindowStyle Minimized -ArgumentList "-NoExit", "-Command", ".\runbooks\run_email_poller.ps1"
Start-Sleep -Seconds 5 # Give it a moment to initialize

# 3. Start Telegram Bot in the foreground
Write-Host "`n[Step 3/3] Starting Telegram Bot in the foreground..." -ForegroundColor Yellow
Write-Host "This terminal will now be occupied by the Telegram Bot. Press CTRL+C to stop."
& .\runbooks\run_telegram.ps1

Write-Host "`n--- All services are shutting down. ---" -ForegroundColor Cyan
