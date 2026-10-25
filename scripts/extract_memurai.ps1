[CmdletBinding()]
param(
    [string]$MsiPath = ".tools\Memurai-Developer-v4.1.2.msi",
    [string]$TargetPath = ".tools\memurai-portable"
)
$ErrorActionPreference = "Stop"
$msi = (Resolve-Path -LiteralPath $MsiPath).Path
$target = [IO.Path]::GetFullPath((Join-Path (Get-Location) $TargetPath))
New-Item -ItemType Directory -Force -Path $target | Out-Null
$arguments = @("/a", $msi, "/qn", "TARGETDIR=$target")
$process = Start-Process -FilePath "msiexec.exe" -ArgumentList $arguments -Wait -PassThru -WindowStyle Hidden
if ($process.ExitCode -ne 0) {
    throw "Memurai administrative extraction failed with exit code $($process.ExitCode)"
}
Get-ChildItem -LiteralPath $target -Recurse -Filter "*.exe" | Select-Object -ExpandProperty FullName
