@echo off
setlocal enabledelayedexpansion
title Stock Watchlist Hub - Control Panel

:MENU
cls
echo =======================================================================
echo          STOCK WATCHLIST ^& INTRADAY RADAR - CONTROL PANEL
echo =======================================================================
echo.
echo   [1] TURN ON  - Start Hub Server (Port 8060) + Ngrok Live Tunnel
echo   [2] TURN OFF - Stop Hub Server + Ngrok Tunnel
echo   [3] STATUS   - Check Server, Ngrok Tunnel ^& Show Public URL
echo   [4] OPEN UI  - Open Dashboard in Default Browser
echo   [5] EXIT
echo.
echo =======================================================================
set /p CHOICE="Select an option (1-5): "

if "%CHOICE%"=="1" goto START_ALL
if "%CHOICE%"=="2" goto STOP_ALL
if "%CHOICE%"=="3" goto CHECK_STATUS
if "%CHOICE%"=="4" goto OPEN_BROWSER
if "%CHOICE%"=="5" goto EXIT_SCRIPT

echo [!] Invalid selection. Please choose 1, 2, 3, 4, or 5.
timeout /t 2 >nul
goto MENU

:START_ALL
cls
call "%~dp0start_hub.bat"
goto MENU

:STOP_ALL
cls
call "%~dp0stop_hub.bat"
goto MENU

:CHECK_STATUS
cls
echo =======================================================================
echo                         SYSTEM STATUS CHECK
echo =======================================================================
echo.
set SRV=OFFLINE
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8060" ^| findstr "LISTENING"') do (
    set SRV=ONLINE (PID: %%a)
)
echo  [1] Hub Server (Port 8060): !SRV!

tasklist /FI "IMAGENAME eq ngrok.exe" 2>nul | find /I /N "ngrok.exe" >nul
if "%ERRORLEVEL%"=="0" (
    echo  [2] ngrok Tunnel:           ONLINE
    echo.
    powershell -NoProfile -Command ^
        "$t = try { (Invoke-RestMethod -Uri 'http://127.0.0.1:4040/api/tunnels' -ErrorAction Stop).tunnels[0].public_url } catch { $null };" ^
        "if ($t) { Write-Host ('      Public URL: ' + $t) -ForegroundColor Green } else { Write-Host '      Public URL: Unavailable' -ForegroundColor Yellow }"
) else (
    echo  [2] ngrok Tunnel:           OFFLINE
)
echo.
echo =======================================================================
pause
goto MENU

:OPEN_BROWSER
powershell -NoProfile -Command ^
    "$t = try { (Invoke-RestMethod -Uri 'http://127.0.0.1:4040/api/tunnels' -ErrorAction Stop).tunnels[0].public_url } catch { $null };" ^
    "if ($t) { Start-Process $t } else { Start-Process 'http://localhost:8060' }"
goto MENU

:EXIT_SCRIPT
exit /b 0
