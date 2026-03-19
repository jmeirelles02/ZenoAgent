@echo off
title Zeno System Launcher
color 0B

echo =========================================
echo Iniciando o Nucleo de IA do Zeno...
echo =========================================

start "Zeno Core" cmd /k "python zeno_core.py"

timeout /t 3 /nobreak >nul

echo =========================================
echo Iniciando a Interface Visual Tauri...
echo =========================================

npm run tauri dev