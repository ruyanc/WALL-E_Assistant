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

echo [4/5] 使用 PyInstaller 打包...
"%PY%" -m PyInstaller --noconfirm --clean WALL-E.spec

echo [5/5] 生成 MSI 安装包...
call build_msi.bat silent

echo.
echo ============================================================
echo  打包完成！
echo    exe: dist\WALL-E.exe
echo    msi: dist\WALL-E.msi  （若构建成功）
echo  也可单独运行 build_msi.bat 重新生成 MSI。
echo ============================================================
pause
endlocal
