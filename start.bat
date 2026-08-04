@echo off
title Guyu Jianzhen

set ROOT=D:\liuJade
set NPM=%ROOT%\desktop\.nodeenv\Scripts\npm.cmd
set NPX=%ROOT%\desktop\.nodeenv\Scripts\npx.cmd
set NODE=%ROOT%\desktop\.nodeenv\Scripts\node.exe

echo ============================================
echo   Gu Yu Jian Zhen - Starting...
echo ============================================
echo.

if not exist "%NODE%" (
    echo [ERROR] Node.js not found: %NODE%
    pause
    exit /b 1
)

if not exist "%NPX%" (
    echo [ERROR] npx not found: %NPX%
    pause
    exit /b 1
)

echo [1/2] API server on port 8720...
start "Guyu-API" /MIN cmd /c "cd /d %ROOT%\inference && python -m uvicorn src.api.server:app --host 127.0.0.1 --port 8720"

echo [2/2] Frontend on port 5173...
start "Guyu-Web" /MIN cmd /c "set PATH=%ROOT%\desktop\.nodeenv\Scripts;%%PATH%% && cd /d %ROOT%\desktop && %NPX% vite --host"

timeout /t 4 /nobreak >nul

start http://localhost:5173

echo.
echo ============================================
echo   Frontend : http://localhost:5173
echo   API Docs : http://localhost:8720/docs
echo ============================================
echo.
echo Close this window to stop all servers.
pause >nul

taskkill /FI "WINDOWTITLE eq Guyu*" /F >nul 2>&1
