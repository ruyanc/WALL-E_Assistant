@echo off
REM 准备安卓资源并在本机用 Kivy 试跑（打 APK 请在 WSL 中见 mobile\BUILD_ANDROID.md）
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo [1/4] 复制动画资源到 mobile\assets ...
"%PY%" mobile\prepare_assets.py
if errorlevel 1 exit /b 1

echo [2/4] 复制 walle/sync 到 mobile\walle ...
"%PY%" mobile\prepare_sync.py
if errorlevel 1 exit /b 1

echo [3/4] 安装 Kivy 与移动端依赖...
"%PY%" -m pip install -r mobile\requirements-mobile.txt -q

echo [4/4] 启动移动端预览（关闭窗口即退出）...
"%PY%" mobile\main.py
endlocal
