@echo off
title Smart QR Attendance & Library System (JavaScript Web App)
color 0B

echo =====================================================================
echo    Smart QR Attendance & Library Entry - Modern JavaScript Web Portal
echo =====================================================================
echo.

IF NOT EXIST ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Creating environment...
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
)

echo [INFO] Starting FastAPI & JavaScript Web App Server...
echo [INFO] Launching http://localhost:8000 in your browser...

start http://localhost:8000
.venv\Scripts\python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload

pause
