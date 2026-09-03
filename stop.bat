@echo off
title Stock Watchlist Hub - Stopping
color 0C

echo =======================================================================
echo       STOCK WATCHLIST HUB - SHUTDOWN (PORT 8060)
echo =======================================================================
echo.

echo [1/2] Terminating processes listening on Port 8060...

for /f "tokens=5" %%P in ('netstat -aon ^| findstr ":8060" ^| findstr "LISTENING"') do (
    if not "%%P"=="0" (
        echo Killing Process ID: %%P...
        taskkill /F /T /PID %%P >nul 2>&1
    )
)

echo [2/2] Running backup port verification...
powershell -NoProfile -Command "$pids = (Get-NetTCPConnection -LocalPort 8060 -State Listen -ErrorAction SilentlyContinue).OwningProcess; if ($pids) { foreach ($i in $pids) { if ($i -gt 0) { Stop-Process -Id $i -Force -ErrorAction SilentlyContinue } } }" >nul 2>&1

echo.
echo =======================================================================
echo   Stock Watchlist Hub server on Port 8060 is successfully stopped.
echo =======================================================================
echo.
ping 127.0.0.1 -n 3 >nul
exit /b 0
