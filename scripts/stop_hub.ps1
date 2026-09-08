$ErrorActionPreference = "SilentlyContinue"
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host "       SHUTTING DOWN STOCK WATCHLIST HUB & NGROK TUNNEL" -ForegroundColor Cyan
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Stop ngrok
$ngrokProc = Get-Process -Name "ngrok" -ErrorAction SilentlyContinue
if ($ngrokProc) {
    Stop-Process -Name "ngrok" -Force -ErrorAction SilentlyContinue
    Write-Host "[+] Terminated ngrok tunnel processes." -ForegroundColor Green
} else {
    Write-Host "[i] No active ngrok process found." -ForegroundColor Gray
}

# 2. Stop server on port 8060
$conns = Get-NetTCPConnection -LocalPort 8060 -ErrorAction SilentlyContinue
if ($conns) {
    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($p in $pids) {
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
        Write-Host "[+] Terminated Hub Server process (PID: $p)." -ForegroundColor Green
    }
} else {
    Write-Host "[i] No active server found on port 8060." -ForegroundColor Gray
}

Write-Host ""
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host "       SHUTDOWN COMPLETE - ALL PROCESSES STOPPED" -ForegroundColor Green
Write-Host "=======================================================================" -ForegroundColor Cyan
