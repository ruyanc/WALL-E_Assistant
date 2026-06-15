@echo off
REM 在 mobile 目录预览安卓 UI（自动安装依赖并准备 sync 包）
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "PY=..\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo [1/3] 准备 mobile/walle 同步包...
"%PY%" prepare_sync.py
if errorlevel 1 exit /b 1

echo [2/3] 安装 Kivy...
"%PY%" -m pip install -r requirements-mobile.txt -q

echo [3/3] 启动预览...
"%PY%" main.py
endlocal
