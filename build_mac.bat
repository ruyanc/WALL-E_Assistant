@echo off
REM ===========================================================
REM  WALL-E macOS DMG 打包入口（Windows）
REM  DMG 必须在 macOS 上生成；本脚本提供本机 Mac 检测与云端构建指引
REM ===========================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

for /f "delims=" %%V in ('"%PY%" scripts\read_version.py') do set "APP_VERSION=%%V"

echo.
echo ============================================================
echo  WALL-E macOS DMG 打包  (目标版本 v%APP_VERSION%)
echo ============================================================
echo.
echo  DMG 无法在 Windows 上直接生成（需要 macOS 的 hdiutil 与 .app 构建链）。
echo.

REM 若通过 Git Bash / 远程 Mac SSH 在「类 Unix」环境调用时，尝试交给 build_mac.sh
where bash >nul 2>nul
if %ERRORLEVEL% equ 0 (
  bash -lc "uname -s" 2>nul | findstr /i "Darwin" >nul
  if %ERRORLEVEL% equ 0 (
    echo [检测] 当前为 macOS 环境，调用 build_mac.sh ...
    bash build_mac.sh
    goto :done
  )
)

echo  方式 1 — 在 Mac 本机打包（推荐）：
echo    cd 项目目录
echo    chmod +x build_mac.sh scripts/build_dmg.sh
echo    ./build_mac.sh
echo    产物: dist\WALL-E.dmg 、dist\WALL-E-%APP_VERSION%.dmg
echo.
echo  方式 2 — 无 Mac：用 GitHub Actions 云端构建
echo    需已安装 GitHub CLI 并已 gh auth login
echo    gh workflow run build-macos-dmg.yml
echo    完成后在 GitHub Actions 页面下载 WALL-E-macOS-dmg 产物
echo.

where gh >nul 2>nul
if %ERRORLEVEL% equ 0 (
  set /p "RUN_GH=是否现在触发 GitHub Actions 构建？[Y/N] "
  if /i "%RUN_GH%"=="Y" (
    gh workflow run build-macos-dmg.yml
    if errorlevel 1 (
      echo [错误] 触发失败，请检查 gh 登录与仓库权限
    ) else (
      echo [OK] 已触发 workflow，请在 GitHub Actions 查看进度并下载 DMG
    )
  )
) else (
  echo  [提示] 未检测到 gh CLI，请手动在 GitHub 网页触发 workflow build-macos-dmg
)

:done
echo.
if /i not "%1"=="silent" pause
endlocal
