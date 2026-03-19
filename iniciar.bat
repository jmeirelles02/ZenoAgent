@echo off
start /b python zeno_core.py
timeout /t 3 /nobreak >nul
cd zeno-ui
npm run tauri dev