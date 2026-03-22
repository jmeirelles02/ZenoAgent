@echo off
start /b python main.py
timeout /t 3 /nobreak >nul
cd zeno-ui
npm run tauri dev