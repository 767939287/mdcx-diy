@echo off
chcp 65001 >nul
title TRAWL - Cloudflare Bypass

echo ========================================
echo   TRAWL - Cloudflare Bypass Service
echo   Windows Portable Edition
echo ========================================
echo.

cd /d "%~dp0"

:: 检查 Bun 是否存在
if not exist "bun\bun.exe" (
    echo [ERROR] 未找到 Bun，请先运行 download-bun.bat
    pause
    exit /b 1
)

:: 检查源码是否存在
if not exist "src" (
    echo [INFO] 首次运行，正在克隆源码...
    git clone --depth 1 https://github.com/germondai/trawl.git src
    if errorlevel 1 (
        echo [ERROR] 克隆失败，请检查网络连接
        pause
        exit /b 1
    )
)

:: 安装依赖（仅首次）
if not exist "src\node_modules" (
    echo [INFO] 正在安装依赖，请稍候...
    "bun\bun.exe" install --frozen-lockfile
    if errorlevel 1 (
        echo [WARN] 依赖安装失败，尝试不使用 frozen lockfile...
        "bun\bun.exe" install
    )
)

:: 设置环境变量
set REDIS_URL=
set MITM_PROXY_ENABLED=false
set PORT=8191

echo.
echo [INFO] 服务启动中...
echo [INFO] API 地址: http://localhost:%PORT%
echo [INFO] 健康检查: http://localhost:%PORT%/health
echo.
echo [提示] 按 Ctrl+C 停止服务
echo.

:: 启动服务
"bun\bun.exe" run src/apps/api/src/index.ts

if errorlevel 1 (
    echo.
    echo [ERROR] 服务启动失败
    pause
)
