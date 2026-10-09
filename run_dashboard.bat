@echo off
echo ========================================================
echo  AegisEdge Industrial AI Vision & Safety Dashboard
echo  Raspberry Pi 5 / Edge Worker Gateway
echo ========================================================
echo.
python -m uvicorn server:app --host 0.0.0.0 --port 8000
pause
