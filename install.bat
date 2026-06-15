@echo off
REM ===========================================================
REM  WALL-E 桌面宠物 安装脚本
REM  支持：快速复制 exe / MSI 安装向导
REM  用法：
REM    install.bat          交互式安装
REM    install.bat silent   静默安装（复制 exe，跳过自启动，不暂停）
REM    install.bat msi      使用 MSI 向导安装
REM ===========================================================
setlocal enabledelayedexpansion
chcp 65001 >nul

cd /d "%~dp0"

set "EXE=dist\WALL-E.exe"
set "MSI=dist\WALL-E.msi"
set "INSTALL_DIR=%LOCALAPPDATA%\Programs\WALL-E"
set "SILENT=0"
set "MODE=copy"
set "UPGRADE=0"

if /i "%~1"=="silent" set "SILENT=1"
if /i "%~1"=="msi" set "MODE=msi"

if not exist "%EXE%" (
    echo [错误] 未找到 %EXE%
    echo 请先运行 build.bat 完成打包，再执行本安装脚本。
    if not "%SILENT%"=="1" pause
    exit /b 1
)

if exist "%INSTALL_DIR%\WALL-E.exe" set "UPGRADE=1"

if "%UPGRADE%"=="1" (
    echo [升级] 检测到已安装版本，将自动覆盖...
    taskkill /F /IM WALL-E.exe >nul 2>&1
    timeout /t 1 /nobreak >nul
    if /i not "%MODE%"=="msi" set "SILENT=1"
)

if "%SILENT%"=="0" if "%UPGRADE%"=="0" if /i not "%MODE%"=="msi" if exist "%MSI%" (
    echo 检测到 MSI 安装包，请选择安装方式：
    echo   [1] 快速安装 — 复制 exe 到用户目录，默认
    echo   [2] MSI 向导 — 图形化安装，含桌面快捷方式
    set /p CHOICE=请输入 1 或 2：
    if "!CHOICE!"=="2" set "MODE=msi"
)

if /i "!MODE!"=="msi" (
    echo [MSI] 启动安装...
    if "%UPGRADE%"=="1" (
        start /wait msiexec /i "%~dp0%MSI%" /passive
    ) else (
        start /wait msiexec /i "%~dp0%MSI%"
    )
    if errorlevel 1 (
        echo [错误] MSI 安装未完成。
        if not "%SILENT%"=="1" pause
        exit /b 1
    )
    echo 提示：MSI 安装目录内附带「操作手册.md」
    goto :after_files
)

echo [1/4] 安装到 %INSTALL_DIR%
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
copy /Y "%EXE%" "%INSTALL_DIR%\WALL-E.exe" >nul
if exist "assets\walle.ico" copy /Y "assets\walle.ico" "%INSTALL_DIR%\walle.ico" >nul

echo [2/5] 复制文档与同步配置模板
if exist "操作手册.md" copy /Y "操作手册.md" "%INSTALL_DIR%\操作手册.md" >nul
if exist "USER_GUIDE.md" copy /Y "USER_GUIDE.md" "%INSTALL_DIR%\USER_GUIDE.md" >nul
if exist "sync_config.example.json" copy /Y "sync_config.example.json" "%INSTALL_DIR%\sync_config.example.json" >nul
if exist "sync_config.example.json" (
    set "PY=.venv\Scripts\python.exe"
    if not exist "!PY!" set "PY=python"
    "!PY!" -c "import json,pathlib; src=pathlib.Path('sync_config.example.json'); dst=pathlib.Path(r'%INSTALL_DIR%')/'sync_config.json'; data=json.loads(src.read_text(encoding='utf-8-sig')); dst.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')" 2>nul
    if errorlevel 1 copy /Y "sync_config.example.json" "%INSTALL_DIR%\sync_config.json" >nul
)
if exist "GUIDE\sync\CLOUDBASE_SETUP.md" copy /Y "GUIDE\sync\CLOUDBASE_SETUP.md" "%INSTALL_DIR%\CLOUDBASE_SETUP.md" >nul

set "DATA_DIR=%APPDATA%\WALL-E"
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%DATA_DIR%\sync_config.json" (
    if exist "sync_config.example.json" (
        set "PY=.venv\Scripts\python.exe"
        if not exist "!PY!" set "PY=python"
        "!PY!" -c "import json,pathlib; src=pathlib.Path('sync_config.example.json'); dst=pathlib.Path(r'%DATA_DIR%')/'sync_config.json'; data=json.loads(src.read_text(encoding='utf-8-sig')); dst.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')" 2>nul
        if errorlevel 1 copy /Y "sync_config.example.json" "%DATA_DIR%\sync_config.json" >nul
    )
    echo   已生成默认同步配置：%DATA_DIR%\sync_config.json
    echo   请编辑 cloudbase_env_id 为授权码。
) else (
    echo   保留已有同步配置：%DATA_DIR%\sync_config.json
)

echo [3/5] 创建桌面快捷方式
set "DESKTOP=%USERPROFILE%\Desktop"
if exist "%INSTALL_DIR%\walle.ico" (
    set "ICON_LOC=%INSTALL_DIR%\walle.ico,0"
) else (
    set "ICON_LOC=%INSTALL_DIR%\WALL-E.exe,0"
)
powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%DESKTOP%\WALL-E Assistant.lnk');" ^
  "$s.TargetPath='%INSTALL_DIR%\WALL-E.exe';" ^
  "$s.WorkingDirectory='%INSTALL_DIR%';" ^
  "$s.IconLocation='%ICON_LOC%';" ^
  "$s.Description='WALL-E Assistant';" ^
  "$s.Save()"

if "%SILENT%"=="1" (
    echo [4/5] 静默模式：跳过开机自启动
    goto :after_files
)

echo [4/5] 是否设置开机自启动？ Y/N
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
echo  WALL-E install complete
echo  EXE: %INSTALL_DIR%\WALL-E.exe
echo  Desktop shortcut: WALL-E Assistant
echo  Uninstall: uninstall.bat
echo  Account: password / SMS / register in Control Panel
echo  Sync: enter auth code in Account tab, save to sync_config.json
echo ============================================================
if not "%SILENT%"=="1" pause
endlocal
