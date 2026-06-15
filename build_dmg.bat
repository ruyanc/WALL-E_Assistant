@echo off
REM 仅重新封装 DMG（需已有 dist\WALL-E.app，且须在 macOS 上执行）
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist "dist\WALL-E.app" (
  echo [错误] 未找到 dist\WALL-E.app，请先运行 build_mac.sh 完整打包
  pause
  exit /b 1
)

where bash >nul 2>nul
if %ERRORLEVEL% neq 0 (
  echo [错误] 需要 bash；在 Mac 上运行: bash scripts/build_dmg.sh
  pause
  exit /b 1
)

bash -lc "uname -s" 2>nul | findstr /i "Darwin" >nul
if %ERRORLEVEL% neq 0 (
  echo [错误] DMG 封装只能在 macOS 上运行 scripts/build_dmg.sh
  echo 请运行 build_mac.bat 查看完整说明
  pause
  exit /b 1
)

bash scripts/build_dmg.sh
echo.
echo DMG 已更新: dist\WALL-E.dmg
if /i not "%1"=="silent" pause
endlocal
