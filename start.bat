@echo off
echo Launching FastAPI app from PowerShell...
powershell -ExecutionPolicy Bypass -File start.ps1
start http://localhost:8000/docs
pause
