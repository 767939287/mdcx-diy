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

:: 应用 MDCx 兼容补丁（提升 Tier3/4 页面加载超时上限，改善挑战页稳定性）
if exist "trawl-goto-timeout.patch" (
    cd /d "%~dp0src"
    git apply --check ..\trawl-goto-timeout.patch >nul 2>&1
    if not errorlevel 1 (
        echo [INFO] 应用 TRAWL goto 超时补丁...
        git apply ..\trawl-goto-timeout.patch
        if errorlevel 1 (
            echo [WARN] 补丁应用失败，继续以原版运行
        )
    )
    cd /d "%~dp0"
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
set MITM_PROXY_ENABLED=false
set PORT=8191
:: 浏览器池默认 2（稳定性/内存折中，用户可改 .env 的 BROWSER_POOL_SIZE）
set BROWSER_POOL_SIZE=2
:: 让 camoufox-js 直接使用便携包内自带的 Camoufox 浏览器，避免在线下载
set CAMOUFOX_INSTALL_DIR=%~dp0.cache\camoufox

:: 内置 Redis：便携包自带，自动启动用于 TRAWL 会话缓存（Tier 2 fast-path）
set REDIS_URL=
if exist "%~dp0redis\redis-server.exe" (
    echo [INFO] 检测到内置 Redis，正在启动...
    start "TRAWL-Redis" /min "%~dp0redis\redis-server.exe" --port 6380 --save "" --appendonly no
    if not errorlevel 1 (
        set REDIS_URL=redis://127.0.0.1:6380
        echo [INFO] Redis 已启动，TRAWL 会话缓存已启用
    )
)

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
