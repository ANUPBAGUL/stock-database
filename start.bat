@echo off
title Stock Watchlist Hub - Starting
color 0A

echo =======================================================================
echo       STOCK WATCHLIST HUB - STARTUP (PORT 8060)
echo =======================================================================
echo.

cd /d "%~dp0"

echo [1/3] Checking for any stale process on Port 8060...
for /f "tokens=5" %%P in ('netstat -aon ^| findstr ":8060" ^| findstr "LISTENING"') do (
    if not "%%P"=="0" (
        echo Stopping old PID: %%P...
        taskkill /F /T /PID %%P >nul 2>&1
    )
)

echo [2/3] Launching Stock Watchlist Hub Server on Port 8060...
start "Stock Watchlist Hub Backend" /B python scripts\launch_app.py

ping 127.0.0.1 -n 3 >nul

echo [3/3] Opening Web Dashboard in default browser...
start http://localhost:8060

echo.
echo =======================================================================
echo   Stock Watchlist Hub is live at: http://localhost:8060
echo   To stop the server at any time, run stop_hub.bat or stop.bat
echo =======================================================================
echo.
pause
