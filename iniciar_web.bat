@echo off
title Dashboard Financeiro - Web Server
cd /d "%~dp0"
echo ======================================================
echo       PAINEL WEB - MONITOR FINANCEIRO 24/7
echo ======================================================
echo.
echo Abrindo servidor web local...
echo Acesse no navegador: http://localhost:8000
echo.
start http://localhost:8000
python -m uvicorn api.index:app --host 0.0.0.0 --port 8000
if %errorlevel% neq 0 (
    echo.
    echo O servidor foi encerrado.
    pause
)
