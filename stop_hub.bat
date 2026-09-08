@echo off
title Stock Watchlist Hub - Shutdown
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_hub.ps1"
ping 127.0.0.1 -n 3 >nul
