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
    Write-Host "[X] Python not found. Please install Python 3.10+" -ForegroundColor Red
    Write-Host "Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit
}

Write-Host "[OK] Python found: $pythonVersion`n" -ForegroundColor Green

# Create virtual environment if it doesn't exist
if (-not (Test-Path ".venv")) {
    Write-Host "[*] Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "[OK] Virtual environment created`n" -ForegroundColor Green
} else {
    Write-Host "[OK] Virtual environment exists`n" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "[*] Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "[*] Installing dependencies..." -ForegroundColor Yellow
pip install -q -r backend\requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Failed to install dependencies" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit
}

Write-Host "[OK] Dependencies installed`n" -ForegroundColor Green

# Start the API server
Write-Host "Starting GuardAIN API Server...`n" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "   Admin Portal: http://localhost:8080" -ForegroundColor Cyan
Write-Host "   PWA: http://localhost:8080/pwa/" -ForegroundColor Cyan
Write-Host "   Username: admin" -ForegroundColor Cyan
Write-Host "   Password: admin@26" -ForegroundColor Cyan
Write-Host "======================================`n" -ForegroundColor Cyan

$lanAddresses = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
    Select-Object -ExpandProperty IPAddress -Unique
foreach ($lanAddress in $lanAddresses) {
    Write-Host "   Other laptops: http://${lanAddress}:8080/" -ForegroundColor Magenta
}

Write-Host "Starting Uvicorn server..." -ForegroundColor Yellow
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8080 --reload

Write-Host "`n`nServer stopped. Press Enter to exit..." -ForegroundColor Yellow
Read-Host