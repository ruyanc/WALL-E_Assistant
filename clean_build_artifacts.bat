@echo off
REM ===========================================================
REM  WALL-E 一键清理构建缓存与中间产物
REM  保留 dist\ 下的安装包 (WALL-E.exe / .msi / .dmg)
REM  用法: clean_build_artifacts.bat [silent]
REM ===========================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "SILENT=0"
if /i "%~1"=="silent" set "SILENT=1"

echo ============================================================
echo  WALL-E 清理构建缓存
echo  将删除: build、.buildozer、bin、__pycache__、生成图标等
echo  将保留: dist\WALL-E.exe / .msi / .dmg
echo ============================================================
echo.

call :rm_dir "build"
call :rm_dir_ps "mobile\.buildozer"
call :rm_dir "mobile\.gradle"
call :rm_dir "mobile\bin"
call :rm_dir "mobile\.venv-android"
call :rm_dir "mobile\walle"
call :rm_dir "tools\wix"
call :rm_dir "usr"
call :rm_dir ".pytest_cache"
call :rm_dir ".mypy_cache"
call :rm_dir ".ruff_cache"
call :rm_dir "htmlcov"

if exist "dist\WALL-E.app" (
    echo [删除] dist\WALL-E.app
    rd /s /q "dist\WALL-E.app"
)

call :rm_file "assets\walle.ico"
call :rm_file "assets\walle.png"
call :rm_file "mobile\assets\icon.png"
call :rm_file "mobile\assets\presplash.png"
call :rm_file "mobile\assets\fonts\walle_ui.ttf"
call :rm_file "mobile\assets\fonts\walle_ui_bold.ttf"
call :rm_dir "mobile\assets\fonts"

call :rm_file "scripts\eye_diag_log.txt"
call :rm_file "scripts\eye_backing_test.png"
call :rm_file "scripts\eye_verify_out.png"
call :rm_file "scripts\eye_diag_out.png"
call :rm_file ".coverage"
call :rm_file "coverage.xml"

echo [清理] Python __pycache__ / .pyc / egg-info ...
powershell -NoProfile -Command "$ErrorActionPreference='SilentlyContinue'; function Skip([string]$p){ $p -match '\\.(git|venv|buildozer)(\\|$)' -or $p -match '\\tools\\wix\\' }; Get-ChildItem -Path 'walle','mobile','scripts' -Recurse -Force -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue | Where-Object { -not (Skip $_.FullName) } | Remove-Item -Recurse -Force; Get-ChildItem -Path 'walle','mobile','scripts' -Recurse -Force -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in '.pyc','.pyo' -and -not (Skip $_.FullName) } | Remove-Item -Force; Get-ChildItem -Path '.' -Depth 2 -Force -Directory -Filter '*.egg-info' -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force; Get-ChildItem -Path 'scripts' -Recurse -Force -File -Filter '*_out.png' -ErrorAction SilentlyContinue | Remove-Item -Force"

echo.
echo ============================================================
echo  清理完成。
echo  重新构建桌面端 - build.bat
echo  重新构建安卓   - mobile\BUILD_ANDROID.md
echo  移动端预览     - build_android.bat
echo ============================================================
if not "%SILENT%"=="1" pause
endlocal
exit /b 0

:rm_dir
if exist "%~1" (
    echo [删除] %~1\
    rd /s /q "%~1"
)
exit /b 0

:rm_dir_ps
if exist "%~1" (
    echo [删除] %~1\
    powershell -NoProfile -Command "$ErrorActionPreference='SilentlyContinue'; Remove-Item -LiteralPath '%~1' -Recurse -Force"
)
exit /b 0

:rm_file
if exist "%~1" (
    echo [删除] %~1
    del /f /q "%~1"
)
exit /b 0
