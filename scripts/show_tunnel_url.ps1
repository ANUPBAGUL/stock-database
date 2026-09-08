# Retrieves public ngrok URL from local ngrok agent API and launches browser
$maxRetries = 10
$tunnelUrl = $null

for ($i = 0; $i -lt $maxRetries; $i++) {
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

if ($tunnelUrl) {
    Write-Host "=======================================================================" -ForegroundColor Cyan
    Write-Host "             STOCK WATCHLIST HUB & NGROK TUNNEL ONLINE                 " -ForegroundColor Green
    Write-Host "=======================================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  [Local URL]:   http://localhost:8060" -ForegroundColor Yellow
    Write-Host "  [Public URL]:  $tunnelUrl" -ForegroundColor Green
    Write-Host "  [Web Inspect]: http://127.0.0.1:4040" -ForegroundColor Gray
    Write-Host ""
    Write-Host "=======================================================================" -ForegroundColor Cyan
    Start-Process $tunnelUrl
} else {
    Write-Host "[!] Hub server is running at http://localhost:8060" -ForegroundColor Yellow
    Write-Host "[!] Ngrok tunnel is still initializing. Check http://127.0.0.1:4040." -ForegroundColor Yellow
    Start-Process "http://localhost:8060"
}
