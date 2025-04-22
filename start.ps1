# start.ps1
Write-Host "Activating virtual environment..."
& "$PSScriptRoot\venv\Scripts\Activate.ps1"

Write-Host "Starting FastAPI with uvicorn..."
uvicorn main:app --reload
