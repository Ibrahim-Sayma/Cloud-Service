@echo off
cd /d "%~dp0"
echo Installing dependencies...
py -m pip install -r backend/requirements.txt

set PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python312\Scripts

echo Starting Backend Server...
cd backend
start "Backend Server" py -m uvicorn main:app --reload
cd ..

echo Opening Frontend...
start chrome "%~dp0frontend\index.html"

echo Project is running!
pause
