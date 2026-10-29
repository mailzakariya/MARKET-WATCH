@echo off
title SETS Open-Source WhatsApp Bridge (+918138858961)
echo ====================================================================
echo   Starting SETS Open-Source Free WhatsApp API Bridge (Baileys)
echo   Configured Default Number: +918138858961
echo   QR Code & Status Page    : http://127.0.0.1:3001
echo ====================================================================
cd /d "%~dp0whatsapp_bridge"
if not exist "node_modules" (
    echo Installing open-source WhatsApp bridge dependencies...
    call npm install
)
start "" "http://127.0.0.1:3001"
node server.js
pause

