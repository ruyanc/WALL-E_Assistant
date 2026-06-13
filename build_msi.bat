@echo off

REM ===========================================================

REM  WALL-E MSI 安装包构建（需先 build.bat 生成 exe）

REM  优先 WiX Toolset（含安装向导）；否则 msilib 回退

REM ===========================================================

setlocal

chcp 65001 >nul

cd /d "%~dp0"



if not exist "dist\WALL-E.exe" (

    echo [错误] 未找到 dist\WALL-E.exe，请先运行 build.bat

    pause

    exit /b 1

)



if not exist "assets\walle.ico" (

    echo [提示] 未找到 assets\walle.ico，正在生成...

    set "PY=.venv\Scripts\python.exe"

    if not exist "%PY%" set "PY=python"

    "%PY%" make_icon.py

)



set "PY=.venv\Scripts\python.exe"

if not exist "%PY%" set "PY=python"



set "WIXBIN="

if exist "%ProgramFiles(x86)%\WiX Toolset v3.14\bin\candle.exe" (

    set "WIXBIN=%ProgramFiles(x86)%\WiX Toolset v3.14\bin"

)

if exist "%ProgramFiles(x86)%\WiX Toolset v3.11\bin\candle.exe" if not defined WIXBIN (

    set "WIXBIN=%ProgramFiles(x86)%\WiX Toolset v3.11\bin"

)

if exist "tools\wix\bin\candle.exe" if not defined WIXBIN (

    set "WIXBIN=%~dp0tools\wix\bin"

)



if not defined WIXBIN (

    echo [WiX] 未检测到 WiX，尝试下载到 tools\wix ...

    powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\ensure_wix.ps1"

    if exist "tools\wix\candle.exe" set "WIXBIN=%~dp0tools\wix"
    if exist "tools\wix\bin\candle.exe" if not defined WIXBIN set "WIXBIN=%~dp0tools\wix\bin"

)



if defined WIXBIN (

    echo [MSI] 使用 WiX: %WIXBIN%

    if not exist "build\msi" mkdir "build\msi"

    "%WIXBIN%\candle.exe" -nologo -out "build\msi\WALL-E.wixobj" "installer\WALL-E.wxs"

    if errorlevel 1 goto :fallback

    "%WIXBIN%\light.exe" -nologo -out "dist\WALL-E.msi" "build\msi\WALL-E.wixobj" -ext WixUIExtension

    if errorlevel 1 goto :fallback

    goto :done

)



:fallback

echo [MSI] WiX 不可用，使用 Python msilib（含安装向导）...

"%PY%" scripts\build_msi.py

if errorlevel 1 (

    echo [错误] MSI 构建失败

    pause

    exit /b 1

)



:done

echo.

echo ============================================================

echo  MSI 安装包： dist\WALL-E.msi

echo ============================================================

if /i not "%1"=="silent" pause

endlocal

