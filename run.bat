@echo off
title Smart QR Attendance & Library Entry System
color 0A

echo =====================================================================
echo    Smart QR-Based Student Attendance & Library Entry Management System
echo =====================================================================
echo.

IF NOT EXIST ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo Creating virtual environment and installing dependencies...
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
)

echo [INFO] Starting Streamlit Web Application...
echo [INFO] Opening http://localhost:8501 in your default browser...
start http://localhost:8501
.venv\Scripts\streamlit run app.py --server.port 8501

pause
