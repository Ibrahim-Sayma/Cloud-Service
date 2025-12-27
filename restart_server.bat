@echo off
echo ===============================================
echo    Fixing 404 Error - Cleaning and Restarting
echo ===============================================
echo.

cd /d "%~dp0backend"

echo [1/4] Cleaning Python cache...
if exist __pycache__ rmdir /s /q __pycache__
if exist routers\__pycache__ rmdir /s /q routers\__pycache__
if exist services\__pycache__ rmdir /s /q services\__pycache__
if exist jobs\__pycache__ rmdir /s /q jobs\__pycache__
echo ✅ Cache cleaned!
echo.

echo [2/4] Testing imports...
py test_import.py
echo.

echo [3/4] Starting server...
echo ⚠️  Watch the startup logs for registered routes!
echo.
echo Press Ctrl+C to stop the server when done
echo.
pause

py -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
