# TRAWL Windows 便携版使用指南

## 快速开始

### 1. 下载

从 [Releases](https://github.com/cdlongbow/mdcx-diy/releases) 下载最新版本的 `trawl-portable-*-windows.zip`

### 2. 解压

```powershell
# 建议解压到 Program Files 或用户目录
Expand-Archive -Path "trawl-portable-1.4.0-windows.zip" -DestinationPath "C:\Tools\"
cd C:\Tools\trawl-portable-1.4.0-windows
```

### 3. 启动

双击 `start-trawl.bat`

**首次启动**会：
- 检查 Bun 运行时（如有需要运行 `download-bun.bat`）
- 检查 Camoufox 浏览器（从 `.cache/camoufox` 加载）
- 启动服务，监听 `http://localhost:8191`

**预期输出**：
```
[api] TRAWL starting on :8191  (pool: 1 browsers)
[api] session cache connected  (Tier 2 fast-path enabled)
```

## 配置 MDCx

1. 打开 MDCx → 设置 → 网络
2. **取消勾选** "启用内置 CF Bypass"
3. 在 "TRAWL 服务" 输入框中填写 TRAWL 服务地址：`http://localhost:8191`
4. 保存设置

> **注意**：请填写 TRAWL 的**根地址**（如 `http://localhost:8191`），**不要**填写 `/v1` 路径。
> MDCx 会在本地自动拉起协议适配层，把内部请求翻译成 TRAWL 的 `/scrape` 接口，
> 填 `/v1` 反而会导致健康检查失败（MDCx 检测的是 `/cookies`/`/html`/`/mirror` 端点）。

## API 端点

| 地址 | 说明 |
|------|------|
| `http://localhost:8191/` | 首页 |
| `http://localhost:8191/health` | 健康检查 |
| `http://localhost:8191/v1` | FlareSolverr 兼容 API |
| `http://localhost:8191/scrape` | 原生 API |

### 测试示例

```bash
# 健康检查
curl http://localhost:8191/health

# 测试 Cloudflare 绕过
curl -X POST http://localhost:8191/v1 `
  -H 'Content-Type: application/json' `
  -d '{"cmd":"request.get","url":"https://lulubar.co","maxTimeout":60000}'
```

## 常见问题

### Q: 启动失败，提示 "Bun not found"？
A: 运行 `download-bun.bat` 下载 Bun 运行时

### Q: 启动失败，提示 "Camoufox not found"？
A: 
1. 检查 `.cache/camoufox` 目录是否存在
2. 如不存在，手动下载：
   ```powershell
   bunx camoufox-js fetch
   ```

### Q: 端口 8191 被占用？
A: 编辑 `.env` 文件，修改：
```
PORT=8192
```
然后更新 MDCx 配置为 `http://localhost:8192/v1`

### Q: 启动慢（>2分钟）？
A: 正常。首次启动需：
- 加载 Camoufox 浏览器 (~30s)
- 预热浏览器池 (~30s)
- 建立 Redis 连接 (~5s)

### Q: 内存占用高？
A: 编辑 `.env`，减少浏览器池：
```
BROWSER_POOL_SIZE=1
```

## 目录结构

```
trawl-portable-1.4.0-windows/
├── start-trawl.bat          # 启动脚本
├── download-bun.bat         # Bun 下载脚本
├── README.md                # 本说明
├── .env                     # 配置文件
├── .env.example             # 配置示例
├── bun/                     # Bun 运行时 (~50MB)
├── .cache/
│   └── camoufox/            # Camoufox 浏览器 (~663MB)
├── src/                     # TRAWL 源码
└── node_modules/            # 依赖
```

## 系统要求

- **OS**: Windows 10/11 (x64 或 ARM64)
- **RAM**: 2GB 可用内存
- **Disk**: 1GB 空间
- **Network**: 稳定连接（首次需下载浏览器）

## 更新版本

1. 下载新版本 zip
2. 备份 `.env` 配置
3. 解压覆盖原目录
4. 恢复 `.env` 配置

## 许可

- TRAWL: AGPL-3.0
- Bun: MIT
- Camoufox: MIT

---

原版项目: https://github.com/germondai/trawl
打包维护: https://github.com/cdlongbow/mdcx-diy
