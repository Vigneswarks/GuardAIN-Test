<#
Sets only the public API origin used by the static Vercel portal. Database and
JWT secrets belong exclusively in the backend host's encrypted environment.
#>
[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$ApiUrl)

$ErrorActionPreference = "Stop"
if ($ApiUrl -notmatch '^https://[A-Za-z0-9.-]+(?::\d+)?$') {
    throw "Enter only a public HTTPS origin, for example https://guardain-api.example.com"
}
$api = $ApiUrl.TrimEnd('/')
Write-Host "Checking $api/health ..." -ForegroundColor Cyan
$health = Invoke-RestMethod "$api/health" -TimeoutSec 20
if ($health.status -ne "online") { throw "API did not report online status" }

$root = Split-Path -Parent $PSScriptRoot
$config = Join-Path $root "admin_portal/config.js"
$content = @"
// Public API origin for the static administrator portal. Never put secrets here.
window.GUARDAIN_API_URL = "$api";
"@
Set-Content -LiteralPath $config -Value $content -Encoding utf8

Write-Host "Portal configuration updated: $config" -ForegroundColor Green
Write-Host "Health: database=$($health.database), redis=$($health.redis), model=$($health.inference.engine)" -ForegroundColor Green
Write-Host "Next: commit this public URL, then redeploy admin_portal on Vercel." -ForegroundColor Yellow
