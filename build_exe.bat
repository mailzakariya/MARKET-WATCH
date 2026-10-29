@echo off
title Build SETS AI Lead Watcher 64-Bit Windows .EXE & Setup Installer
echo ====================================================================
echo   Building SETS AI Lead Watcher (64-Bit Windows Single .EXE)
echo   and Step-by-Step Setup Wizard (SETS_AI_Watcher_Setup_x64.exe)
echo ====================================================================

set PYTHON_EXE="C:\Users\ZakariyaAbdulBari\AppData\Local\Programs\Python\Python312\python.exe"

echo [1/4] Generating SETS Logo Icon (.ico and .png)...
%PYTHON_EXE% "%~dp0build_icon.py"

echo [2/4] Ensuring PyInstaller and PostgreSQL Driver (pg8000) are installed...
%PYTHON_EXE% -m pip install --upgrade pyinstaller pg8000

echo [3/4] Compiling Single Standalone Application (SETS_AI_Lead_Watcher_x64.exe)...
%PYTHON_EXE% -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "SETS_AI_Lead_Watcher_x64" ^
    --icon "%~dp0assets\sets_logo.ico" ^
    --add-data "%~dp0static;static" ^
    --add-data "%~dp0assets;assets" ^
    --hidden-import "pg8000" ^
    "%~dp0app.py"

echo [4/4] Compiling Step-by-Step 64-Bit Windows Setup Installer (SETS_AI_Watcher_Setup_x64.exe)...
%PYTHON_EXE% -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "SETS_AI_Watcher_Setup_x64" ^
    --icon "%~dp0assets\sets_logo.ico" ^
    --add-binary "%~dp0dist\SETS_AI_Lead_Watcher_x64.exe;." ^
    --add-data "%~dp0assets;assets" ^
    --add-data "%~dp0whatsapp_bridge\package.json;whatsapp_bridge" ^
    --add-data "%~dp0whatsapp_bridge\server.js;whatsapp_bridge" ^
    --add-data "%~dp0start_whatsapp_bridge.bat;." ^
    --add-data "%~dp0setup_postgres.bat;." ^
    --add-data "%~dp0README.md;." ^
    "%~dp0installer_wizard.py"

echo ====================================================================
echo   Build Complete!
echo   1. Standalone 64-Bit App : %~dp0dist\SETS_AI_Lead_Watcher_x64.exe
echo   2. 64-Bit Setup Installer: %~dp0dist\SETS_AI_Watcher_Setup_x64.exe
echo ====================================================================
pause

