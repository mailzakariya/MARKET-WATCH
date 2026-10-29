@echo off
title SETS AI Lead Watcher (www.sets4us.com)
echo ====================================================================
echo   Starting SETS AI Lead Watcher for www.sets4us.com
echo   Regions : UAE, KSA, India
echo   Services: Energy Audit, Sustainability Audit, BMS, CMS, ESG
echo ====================================================================

set PYTHON_EXE="C:\Users\ZakariyaAbdulBari\AppData\Local\Programs\Python\Python312\python.exe"
if exist %PYTHON_EXE% (
    %PYTHON_EXE% "%~dp0app.py" --port 8080 --open
) else (
    python "%~dp0app.py" --port 8080 --open
)
pause

