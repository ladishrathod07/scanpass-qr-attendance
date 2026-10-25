@echo off
title Smart QR Attendance - Standalone OpenCV Scanner
color 0B

echo =====================================================================
echo    Launching Real-Time OpenCV Live Webcam Scanner
echo =====================================================================
echo.
echo Press 'q' or 'ESC' inside the camera window to quit.
echo Press 'c' to toggle mode (Classroom Attendance vs Library Entry).
echo.

.venv\Scripts\python scanner.py

pause
