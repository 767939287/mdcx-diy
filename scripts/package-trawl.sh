#!/bin/bash
# TRAWL Windows 便携版打包脚本
# 用法: bash package-trawl.sh [版本]

set -e

VERSION="${1:-1.4.0}"
OUTPUT_DIR="./trawl-portable-${VERSION}-windows"
BUN_VERSION="1.3.9"

echo "=== TRAWL Windows 便携版打包 ==="
echo "版本: $VERSION"
echo "输出: $OUTPUT_DIR/"

# 创建输出目录
mkdir -p "$OUTPUT_DIR"
cd "$OUTPUT_DIR"

# 1. 下载 Bun (Windows 版本)
echo "[1/5] 下载 Bun..."
BUN_ZIP="bun-win-x64.zip"
curl -sL "https://github.com/oven-sh/bun/releases/download/bun-v${BUN_VERSION}/bun-windows-x64.zip" -o "$BUN_ZIP"
if [ ! -f "$BUN_ZIP" ] || [ ! -s "$BUN_ZIP" ]; then
    echo "Bun 下载失败，尝试备用链接..."
    curl -sL "https://github.com/nicolo-ribaudo/bun/releases/download/bun-v${BUN_VERSION}/bun-windows-x64.zip" -o "$BUN_ZIP"
fi
unzip -q "$BUN_ZIP" -d bun
rm "$BUN_ZIP"

# 2. 克隆 trawl 源码
echo "[2/5] 克隆 trawl 源码..."
git clone --depth 1 --branch v"$VERSION" https://github.com/germondai/trawl.git src
cd src

# 3. 安装依赖
echo "[3/5] 安装依赖..."
../../../bun/bun install --frozen-lockfile

# 4. 构建
echo "[4/5] 构建..."
bun run build 2>/dev/null || echo "构建失败，尝试直接运行..."

# 5. 打包便携版
echo "[5/5] 打包便携版..."
cd ..

# 复制必要文件
cp -r src/apps/api/dist dist 2>/dev/null || true
cp src/.env.example .env 2>/dev/null || true

# 创建启动脚本
cat > start-trawl.bat << 'EOF'
@echo off
chcp 65001 >nul
echo ========================================
echo   TRAWL - Cloudflare Bypass Service
echo   Windows Portable Edition
echo ========================================
echo.
echo Starting TRAWL API server...
echo.

cd /d "%~dp0"
set REDIS_URL=
set MITM_PROXY_ENABLED=false

echo [INFO] 服务启动中，请稍候...
echo [INFO] API 地址: http://localhost:8191
echo [INFO] 健康检查: http://localhost:8191/health
echo.
echo [提示] 按 Ctrl+C 停止服务
echo.

bun run src/apps/api/src/index.ts

pause
EOF

# 创建说明文档
cat > README.txt << 'EOF'
========================================
  TRAWL Windows 便携版
========================================

【功能】
  绕过 Cloudflare、Akamai、Imperva 等 WAF 防护
  支持 CF Turnstile、reCAPTCHA、hCaptcha 等验证码

【快速开始】
  1. 双击 "start-trawl.bat" 启动服务
  2. 等待 10-15 秒（浏览器预热）
  3. 确认浏览器: http://localhost:8191/health

【配置 MDCx】
  设置 → 网络:
    外部 CF 服务: http://localhost:8191
    后端类型: trawl（默认；原生 FlareSolverr 选 flaresolverr）

【API 端点】
  - http://localhost:8191/        首页
  - http://localhost:8191/health  健康检查
  - http://localhost:8191/v1      FlareSolverr 兼容
  - http://localhost:8191/scrape  原生 API

【故障排查】
  Q: 启动失败？
  A: 确保已安装 Bun (scripts/bun/)
  
  Q: 浏览器启动慢？
  A: 首次启动需下载 Camoufox (~300MB)，请耐心等待
  
  Q: 端口被占用？
  A: 编辑 .env，修改 PORT=8191 为其他端口

【技术栈】
  - 运行时: Bun 1.3.9
  - 框架: Elysia (TypeScript)
  - 浏览器: Camoufox ( patched Firefox )
  - 缓存: 内存 (无需 Redis)

【来源】
  原版项目: https://github.com/germondai/trawl
  许可: AGPL-3.0

========================================
EOF

# 打包成 zip
echo ""
echo "打包成 zip..."
cd ..
zip -r "trawl-portable-${VERSION}-windows.zip" "$OUTPUT_DIR" -x "*.git*" 2>/dev/null || \
    tar czf "trawl-portable-${VERSION}-windows.tar.gz" "$OUTPUT_DIR"

echo ""
echo "=== 完成 ==="
echo "便携版位置: $(pwd)/trawl-portable-${VERSION}-windows.zip"
echo ""
echo "分发方式:"
echo "  1. 上传 zip 到网盘/GitHub Releases"
echo "  2. 用户下载后解压，双击 start-trawl.bat 运行"
echo "  3. 配置 MDCx 的 cf_bypass_url"
