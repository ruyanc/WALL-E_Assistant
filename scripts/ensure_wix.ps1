# 若本机未装 WiX Toolset，下载 wix314 二进制到 tools\wix（仅首次）
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $root "tools\wix"
$candle = Join-Path $dest "bin\candle.exe"

if (Test-Path $candle) { exit 0 }

$zip = Join-Path $env:TEMP "wix314-binaries.zip"
$url = "https://github.com/wixtoolset/wix3/releases/download/wix3141rtm/wix314-binaries.zip"
Write-Host "[WiX] 下载 $url ..."
Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
Expand-Archive -Path $zip -DestinationPath $dest -Force
Remove-Item $zip -Force
Write-Host "[WiX] 已解压到 $dest"
