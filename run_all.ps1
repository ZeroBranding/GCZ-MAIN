<#
.SYNOPSIS
    Starts all essential services for the German Code Zero AI project in the correct order.
#>

Write-Host "--- Starting All Services ---" -ForegroundColor Cyan

# 1. Start ComfyUI in the background
Write-Host "`n[Step 1/3] Starting ComfyUI Service in the background..." -ForegroundColor Yellow
Start-Process powershell -WindowStyle Hidden -ArgumentList "-Command", ".\runbooks\run_comfyui.ps1"
Start-Sleep -Seconds 5 # Give it a moment to initialize

# 2. Start Email Poller in the background
Write-Host "`n[Step 2/3] Starting Email Poller Service in the background..." -ForegroundColor Yellow
Start-Process powershell -WindowStyle Minimized -ArgumentList "-NoExit", "-Command", ".\runbooks\run_email_poller.ps1"
Start-Sleep -Seconds 5 # Give it a moment to initialize

# 3. Start Telegram Bot in the foreground
Write-Host "`n[Step 3/3] Starting Telegram Bot in the foreground..." -ForegroundColor Yellow
Write-Host "This terminal will now be occupied by the Telegram Bot. Press CTRL+C to stop."
& .\runbooks\run_telegram.ps1

Write-Host "`n--- All services are shutting down. ---" -ForegroundColor Cyan
