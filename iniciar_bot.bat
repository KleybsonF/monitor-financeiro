@echo off
title Bot Financeiro - Monitor de Instabilidade
cd /d "%~dp0"
echo ======================================================
echo           BOT FINANCEIRO - STATUS DE BANCOS
echo ======================================================
echo.
python bot.py
if %errorlevel% neq 0 (
    echo.
    echo O bot encerrou com erro ou foi interrompido.
    pause
)
