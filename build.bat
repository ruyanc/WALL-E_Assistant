@echo off
REM ===========================================================
REM  WALL-E 桌面宠物 一键打包脚本（Windows）
REM  生成 dist\WALL-E.exe 单文件可执行程序
REM ===========================================================
setlocal

cd /d "%~dp0"

echo [1/4] 准备 Python 虚拟环境...
if not exist ".venv\Scripts\python.exe" (
    echo   未找到 .venv，正在创建...
    where py >nul 2>nul && (py -3 -m venv .venv) || (python -m venv .venv)
)

set PY=.venv\Scripts\python.exe

echo [2/4] 安装依赖...
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r requirements-dev.txt

echo [3/4] 生成应用图标...
"%PY%" make_icon.py

echo [4/4] 使用 PyInstaller 打包...
"%PY%" -m PyInstaller --noconfirm --clean WALL-E.spec

echo.
echo ============================================================
echo  打包完成！可执行文件位于： dist\WALL-E.exe
echo  双击即可运行，瓦力会出现在桌面右下角。
echo ============================================================
pause
endlocal
