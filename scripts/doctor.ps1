<#
GuardAIN readiness checker. This does not install software or change cloud
settings; it shows exactly what is available on this laptop.
#>
[CmdletBinding()]
param([string]$ApiUrl = "")

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Show-Check([string]$name, [scriptblock]$check) {
    try {
        $result = & $check
        Write-Host "[OK] $name" -ForegroundColor Green
        if ($result) { Write-Host "     $result" -ForegroundColor DarkGray }
        return $true
    } catch {
        Write-Host "[NEEDS ACTION] $name - $($_.Exception.Message)" -ForegroundColor Yellow
        return $false
    }
}

Write-Host "`nGuardAIN setup check" -ForegroundColor Cyan
$pythonOk = Show-Check "Python" { (python --version 2>&1 | Select-Object -First 1) }
$dockerOk = Show-Check "Docker Desktop / Docker engine" { (docker version --format '{{.Server.Version}}' 2>$null) }
Show-Check "Required project files" {
    foreach ($file in @("Dockerfile", "docker-compose.yml", "backend/app/main.py", "extension/manifest.json", "admin_portal/index.html")) {
        if (-not (Test-Path $file)) { throw "Missing $file" }
    }
    "Project files found"
} | Out-Null

if ($ApiUrl) {
    if ($ApiUrl -notmatch '^https://') { throw "ApiUrl must start with https://" }
    Show-Check "Cloud API health" {
        $health = Invoke-RestMethod "$($ApiUrl.TrimEnd('/'))/health" -TimeoutSec 15
        "database=$($health.database), redis=$($health.redis), engine=$($health.inference.engine)"
    } | Out-Null
    Show-Check "Cloud API readiness" {
        (Invoke-RestMethod "$($ApiUrl.TrimEnd('/'))/ready" -TimeoutSec 15).status
    } | Out-Null
}

Write-Host "`nNext local command:" -ForegroundColor Cyan
if ($dockerOk) {
    Write-Host "  docker compose up --build" -ForegroundColor White
} elseif ($pythonOk) {
    Write-Host "  .\start.ps1" -ForegroundColor White
} else {
    Write-Host "  Install Python 3.11+ or Docker Desktop, then run this script again." -ForegroundColor White
}
