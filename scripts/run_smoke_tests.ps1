<#
.SYNOPSIS
    Führt Smoke-Tests für alle Systemkomponenten in der korrekten virtuellen Umgebung durch.
#>

Write-Host "=== GermanCodeZero AI Smoke Tests ===" -ForegroundColor Cyan

# Aktiviere die virtuelle Umgebung
Write-Host "Activating Python virtual environment..." -ForegroundColor Yellow
try {
    . .\.venv\Scripts\Activate.ps1
} catch {
    Write-Host "❌ Virtual environment not found. Please run the main setup script." -ForegroundColor Red
    exit 1
}

# Stelle sicher, dass alle Abhängigkeiten installiert sind
Write-Host "Verifying dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# 1. Teste Workflow-Engine
Write-Host "Testing Workflow Engine..." -ForegroundColor Yellow
try {
    python -m pytest tests/smoke/test_workflow_engine.py -v
    if ($LASTEXITCODE -ne 0) { throw "Workflow Engine Tests failed" }
} catch {
    Write-Host "❌ Workflow Engine Tests failed: $_" -ForegroundColor Red
    exit 1
}

# 2. Teste Dokumentenservice
Write-Host "Testing Document Service..." -ForegroundColor Yellow
try {
    python -m pytest tests/smoke/test_document_service.py -v
    if ($LASTEXITCODE -ne 0) { throw "Document Service Tests failed" }
} catch {
    Write-Host "❌ Document Service Tests failed: $_" -ForegroundColor Red
    exit 1
}

# 3. Teste Telegram Integration
Write-Host "Testing Telegram Integration..." -ForegroundColor Yellow
try {
    python -m pytest tests/smoke/test_telegram_integration.py -v
    if ($LASTEXITCODE -ne 0) { throw "Telegram Integration Tests failed" }
} catch {
    Write-Host "❌ Telegram Integration Tests failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Alle Smoke-Tests erfolgreich!" -ForegroundColor Green
