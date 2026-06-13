@echo off
REM ===========================================================
REM  WALL-E 桌面宠物 安装脚本
REM  支持：快速复制 exe / MSI 安装向导
REM ===========================================================
setlocal enabledelayedexpansion
chcp 65001 >nul

cd /d "%~dp0"

set "EXE=dist\WALL-E.exe"
set "MSI=dist\WALL-E.msi"
set "INSTALL_DIR=%LOCALAPPDATA%\Programs\WALL-E"

if not exist "%EXE%" (
    echo [错误] 未找到 %EXE%
    echo 请先运行 build.bat 完成打包，再执行本安装脚本。
    pause
    exit /b 1
)

set "MODE=copy"
if exist "%MSI%" (
    echo 检测到 MSI 安装包，请选择安装方式：
    echo   [1] 快速安装 — 复制 exe 到用户目录（默认）
    echo   [2] MSI 向导 — 图形化安装（含桌面快捷方式）
    set /p CHOICE=请输入 1 或 2：
    if "!CHOICE!"=="2" set "MODE=msi"
)

if /i "!MODE!"=="msi" (
    echo [MSI] 启动安装向导...
    start /wait msiexec /i "%~dp0%MSI%"
    if errorlevel 1 (
        echo [错误] MSI 安装未完成。
        pause
        exit /b 1
    )
    echo 提示：MSI 安装目录内附带「操作手册.md」
    goto :after_files
)

echo [1/4] 安装到 %INSTALL_DIR%
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
copy /Y "%EXE%" "%INSTALL_DIR%\WALL-E.exe" >nul
if exist "assets\walle.ico" copy /Y "assets\walle.ico" "%INSTALL_DIR%\walle.ico" >nul

echo [2/4] 复制操作手册
if exist "操作手册.md" copy /Y "操作手册.md" "%INSTALL_DIR%\操作手册.md" >nul
if exist "USER_GUIDE.md" copy /Y "USER_GUIDE.md" "%INSTALL_DIR%\USER_GUIDE.md" >nul

echo [3/4] 创建桌面快捷方式
set "DESKTOP=%USERPROFILE%\Desktop"
powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%DESKTOP%\WALL-E Assistant.lnk');" ^
  "$s.TargetPath='%INSTALL_DIR%\WALL-E.exe';" ^
  "$s.WorkingDirectory='%INSTALL_DIR%';" ^
  "$s.IconLocation='%INSTALL_DIR%\WALL-E.exe,0';" ^
  "$s.Description='WALL-E Assistant';" ^
  "$s.Save()"

echo [4/4] 是否设置开机自启动？(Y/N)
set /p AUTO=请输入选择：
if /i "!AUTO!"=="Y" (
    set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
    powershell -NoProfile -Command ^
      "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('!STARTUP!\WALL-E Assistant.lnk');" ^
      "$s.TargetPath='%INSTALL_DIR%\WALL-E.exe';" ^
      "$s.WorkingDirectory='%INSTALL_DIR%';" ^
      "$s.Save()"
    echo 已设置开机自启动。
) else (
    echo 已跳过开机自启动设置。
)

:after_files
echo.
echo ============================================================
echo  安装完成！
echo    启动：双击桌面「WALL-E Assistant」
echo    卸载：运行 uninstall.bat
echo    语言：控制台 - 番茄钟 - 界面语言（中/英）
echo    手册：%INSTALL_DIR%\操作手册.md / USER_GUIDE.md
echo ============================================================
pause
endlocal
