@echo off
title Install PostgreSQL Drivers for SETS AI Watcher
echo ====================================================================
echo   Installing Python PostgreSQL Drivers (psycopg2-binary & pg8000)
echo ====================================================================
set PYTHON_EXE="C:\Users\ZakariyaAbdulBari\AppData\Local\Programs\Python\Python312\python.exe"
if exist %PYTHON_EXE% (
    %PYTHON_EXE% -m pip install psycopg2-binary pg8000
) else (
    pip install psycopg2-binary pg8000
)
echo Done! You can now connect to any Local or Free Cloud PostgreSQL database.
pause

