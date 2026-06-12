@echo off
REM ===========================================================
REM  WALL-E 桌面宠物 安装脚本
REM  将程序安装到用户目录，并创建桌面快捷方式（可选开机自启）
REM ===========================================================
setlocal enabledelayedexpansion
chcp 65001 >nul

cd /d "%~dp0"

set "EXE=dist\WALL-E.exe"
if not exist "%EXE%" (
    echo [错误] 未找到 dist\WALL-E.exe
    echo 请先运行 build.bat 完成打包，再执行本安装脚本。
    pause
    exit /b 1
)

set "INSTALL_DIR=%LOCALAPPDATA%\Programs\WALL-E"
echo [1/3] 安装到 %INSTALL_DIR%
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
copy /Y "%EXE%" "%INSTALL_DIR%\WALL-E.exe" >nul
if exist "assets\walle.ico" copy /Y "assets\walle.ico" "%INSTALL_DIR%\walle.ico" >nul

echo [2/3] 创建桌面快捷方式
set "DESKTOP=%USERPROFILE%\Desktop"
powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%DESKTOP%\WALL-E 桌面宠物.lnk');" ^
  "$s.TargetPath='%INSTALL_DIR%\WALL-E.exe';" ^
  "$s.WorkingDirectory='%INSTALL_DIR%';" ^
  "$s.IconLocation='%INSTALL_DIR%\WALL-E.exe,0';" ^
  "$s.Description='WALL-E 桌面宠物';" ^
  "$s.Save()"

echo [3/3] 是否设置开机自启动？(Y/N)
set /p AUTO=请输入选择：
if /i "!AUTO!"=="Y" (
    set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
    powershell -NoProfile -Command ^
      "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('!STARTUP!\WALL-E 桌面宠物.lnk');" ^
      "$s.TargetPath='%INSTALL_DIR%\WALL-E.exe';" ^
      "$s.WorkingDirectory='%INSTALL_DIR%';" ^
      "$s.Save()"
    echo 已设置开机自启动。
) else (
    echo 已跳过开机自启动设置。
)

echo.
echo ============================================================
echo  安装完成！双击桌面上的「WALL-E 桌面宠物」即可启动。
echo  卸载请运行 uninstall.bat
echo ============================================================
pause
endlocal
