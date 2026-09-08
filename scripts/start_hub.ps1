$ErrorActionPreference = "SilentlyContinue"
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host "       STARTING STOCK WATCHLIST HUB & NGROK LIVE TUNNEL" -ForegroundColor Cyan
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host ""

$baseDir = Split-Path -Parent $PSScriptRoot
Set-Location $baseDir

# 1. Check if server on port 8060 is already running
$conn = Get-NetTCPConnection -LocalPort 8060 -ErrorAction SilentlyContinue
if ($conn) {
    Write-Host "[i] Hub server is already running on port 8060 (PID: $($conn[0].OwningProcess))." -ForegroundColor Yellow
} else {
    Write-Host "[*] Starting Python Hub Server (port 8060)..." -ForegroundColor Green
    Start-Process -FilePath "python" -ArgumentList "scripts\launch_app.py" -WorkingDirectory $baseDir
    Start-Sleep -Seconds 4
}

# 2. Check if ngrok is already running
$ngrokProc = Get-Process -Name "ngrok" -ErrorAction SilentlyContinue
if ($ngrokProc) {
    Write-Host "[i] ngrok tunnel is already active (PID: $($ngrokProc.Id))." -ForegroundColor Yellow
} else {
    Write-Host "[*] Starting ngrok tunnel on port 8060..." -ForegroundColor Green
    Start-Process -FilePath "ngrok" -ArgumentList "http 8060 --log=stdout" -WorkingDirectory $baseDir
    Start-Sleep -Seconds 3
}

# 3. Fetch public URL
Write-Host ""
Write-Host "[*] Fetching public HTTPS tunnel URL..." -ForegroundColor Gray
$tunnelUrl = $null
for ($i = 0; $i -lt 10; $i++) {
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -ErrorAction Stop
        if ($res.tunnels -and $res.tunnels.Count -gt 0) {
            $tunnelUrl = $res.tunnels[0].public_url
            break
        }
    } catch {
        Start-Sleep -Milliseconds 600
    }
}

Write-Host ""
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host "             STOCK WATCHLIST HUB & NGROK TUNNEL ONLINE" -ForegroundColor Green
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host "  [Local URL]:    http://localhost:8060" -ForegroundColor Yellow
if ($tunnelUrl) {
    Write-Host "  [Public URL]:   $tunnelUrl" -ForegroundColor Green
    Write-Host "  [Web Inspect]:  http://127.0.0.1:4040" -ForegroundColor Gray
    Start-Process $tunnelUrl
} else {
    Write-Host "  [Public URL]:   Initializing... check http://127.0.0.1:4040" -ForegroundColor Yellow
    Start-Process "http://localhost:8060"
}
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Hub Server and ngrok are running in background." -ForegroundColor White
Write-Host "To shut down, run stop_hub.bat" -ForegroundColor Gray
