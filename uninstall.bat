@echo off
REM ===========================================================
REM  WALL-E 桌面宠物 卸载脚本
REM ===========================================================
setlocal
chcp 65001 >nul

echo 正在关闭正在运行的 WALL-E ...
taskkill /IM "WALL-E.exe" /F >nul 2>nul

set "INSTALL_DIR=%LOCALAPPDATA%\Programs\WALL-E"
set "DESKTOP=%USERPROFILE%\Desktop"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

echo 删除程序文件...
if exist "%INSTALL_DIR%" rmdir /S /Q "%INSTALL_DIR%"

echo 删除快捷方式...
if exist "%DESKTOP%\WALL-E 桌面宠物.lnk" del /F /Q "%DESKTOP%\WALL-E 桌面宠物.lnk"
if exist "%STARTUP%\WALL-E 桌面宠物.lnk" del /F /Q "%STARTUP%\WALL-E 桌面宠物.lnk"

echo.
echo 卸载完成。
echo 提示：你的待办与设置仍保存在 %APPDATA%\WALL-E
echo 如需彻底清除，请手动删除该文件夹。
pause
endlocal
