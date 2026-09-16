# GuardAIN - Central Police Cyber Cell Portal
# Start Script for Windows PowerShell

Write-Host "`n" -ForegroundColor White
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "   GuardAIN - Cyber Cell Portal" -ForegroundColor Cyan
Write-Host "   Starting Services..." -ForegroundColor Cyan
Write-Host "======================================`n" -ForegroundColor Cyan

# Check if Python is installed
Write-Host "Checking Python installation..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Python not found. Please install Python 3.10+" -ForegroundColor Red
    Write-Host "Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit
}

Write-Host "✅ Python found: $pythonVersion`n" -ForegroundColor Green

# Create virtual environment if it doesn't exist
if (-not (Test-Path ".venv")) {
    Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "✅ Virtual environment created`n" -ForegroundColor Green
} else {
    Write-Host "✅ Virtual environment exists`n" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "🔌 Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "📥 Installing dependencies..." -ForegroundColor Yellow
pip install -q -r backend\requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to install dependencies" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit
}

Write-Host "✅ Dependencies installed`n" -ForegroundColor Green

# Start the API server
Write-Host "🚀 Starting GuardAIN API Server...`n" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "   📊 Admin Portal: http://localhost:8080" -ForegroundColor Cyan
Write-Host "   🔐 Username: admin" -ForegroundColor Cyan
Write-Host "   🔐 Password: admin@26" -ForegroundColor Cyan
Write-Host "======================================`n" -ForegroundColor Cyan

Write-Host "Starting Uvicorn server..." -ForegroundColor Yellow
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8080 --reload

Write-Host "`n`nServer stopped. Press Enter to exit..." -ForegroundColor Yellow
Read-Host
