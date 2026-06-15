# 若本机未装 WiX Toolset，下载 wix314 二进制到 tools\wix（仅首次）
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $root "tools\wix"

function Find-Candle([string]$dir) {
    if (-not (Test-Path $dir)) { return $null }
    foreach ($rel in @("bin\candle.exe", "candle.exe")) {
        $path = Join-Path $dir $rel
        if (Test-Path $path) { return $path }
    }
    return $null
}

$candle = Find-Candle $dest
if ($candle) {
    Write-Host "[WiX] 已缓存: $candle"
    exit 0
}

$zip = Join-Path $env:TEMP "wix314-binaries.zip"
$url = "https://github.com/wixtoolset/wix3/releases/download/wix3141rtm/wix314-binaries.zip"
Write-Host "[WiX] 首次下载 $url ..."
Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
New-Item -ItemType Directory -Path $dest -Force | Out-Null
Expand-Archive -Path $zip -DestinationPath $dest -Force
Remove-Item $zip -Force

$candle = Find-Candle $dest
if (-not $candle) {
    Write-Error "[WiX] 解压后未找到 candle.exe，请检查 $dest"
}
Write-Host "[WiX] 已解压到 $dest"
