# Run this script once from an elevated PowerShell window on the central PC.
# It opens only the GuardAIN TCP port in Windows Defender Firewall.
[CmdletBinding()]
param([ValidateRange(1, 65535)][int]$Port = 8080)

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run PowerShell as Administrator, then execute this script again."
}

$ruleName = "GuardAIN Central Portal TCP $Port"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if (-not $existing) {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow `
        -Protocol TCP -LocalPort $Port -Profile Private | Out-Null
}
Write-Host "GuardAIN LAN access enabled on TCP $Port for Private networks."
Write-Host "Keep the server running with --host 0.0.0.0 and use the printed LAN URL."
