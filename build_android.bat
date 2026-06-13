@echo off
REM 准备安卓资源并在本机用 Kivy 试跑（打 APK 请在 WSL 中见 mobile\BUILD_ANDROID.md）
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo [1/3] 复制动画资源到 mobile\assets ...
"%PY%" mobile\prepare_assets.py
if errorlevel 1 exit /b 1

echo [2/3] 安装 Kivy（若尚未安装）...
"%PY%" -m pip install "kivy>=2.3,<2.4" -q

echo [3/3] 启动移动端预览（关闭窗口即退出）...
"%PY%" mobile\main.py
endlocal
