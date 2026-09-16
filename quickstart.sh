#!/bin/bash
# GuardAIN - Quick Start Guide
# This script helps you get started quickly

echo ""
echo "========================================="
echo "  GuardAIN - Cyber Cell Portal"
echo "  Quick Start Setup"
echo "========================================="
echo ""

# Check Python
echo "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python 3.10+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✅ Python $PYTHON_VERSION found"
echo ""

# Create virtual environment
echo "Setting up virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment exists"
fi

# Activate
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r backend/requirements.txt
if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

echo ""
echo "========================================="
echo "  Ready to Start!"
echo "========================================="
echo ""
echo "Run the server with:"
echo "  python -m uvicorn backend.app.main:app --reload"
echo ""
echo "Then open: http://localhost:8080"
echo "Login with: admin / admin@26"
echo ""
