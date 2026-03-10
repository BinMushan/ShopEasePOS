@echo off
title ShopEase POS - Setup & Run

echo ============================================
echo   ShopEase POS - Installing & Starting...
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed!
    echo Please download it from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo [1/2] Installing required libraries...
pip install customtkinter fpdf2 --quiet

echo [2/2] Starting ShopEase POS...
echo.
python shopease_pos.py

pause
