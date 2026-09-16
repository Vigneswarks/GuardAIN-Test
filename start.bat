@echo off
REM GuardAIN - Central Police Cyber Cell Portal
REM Start Script for Windows

echo.
echo ======================================
echo   GuardAIN - Cyber Cell Portal
echo   Starting Services...
echo ======================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

echo ✅ Python found
echo.

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo 📦 Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install dependencies
echo 📥 Installing dependencies...
pip install -q -r backend\requirements.txt

if %errorlevel% neq 0 (
    echo ❌ Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo ✅ Dependencies installed
echo.

REM Start the API server
echo 🚀 Starting GuardAIN API Server...
echo.
echo ======================================
echo   📊 Admin Portal: http://localhost:8080
echo   🔐 Username: admin
echo   🔐 Password: admin@26
echo ======================================
echo.

python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8080 --reload

pause
