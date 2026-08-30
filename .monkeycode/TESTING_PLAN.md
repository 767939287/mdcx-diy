# 爬虫与网络能力本机测试计划

> 目的：在本机（Windows/真实网络/住宅 IP）验证当前注册爬虫有效性、代理需求、外置 CF 服务过 CF 能力，并覆盖所有**云端 devbox 做不了**的功能项。
> 背景：devbox 出口受限（探测 FAIL 多为环境网络限制非真实失效）、无 Docker、无 GUI、无住宅 IP，以下项只能本机验证。
> 用法：按清单逐项执行，结果填入表格，完成后可把表格发回。

## 0. 环境准备

```bash
git clone https://github.com/cdlongbow/mdcx-diy.git
cd mdcx-diy
uv sync --locked          # 装依赖（需 Python >= 3.13）
```

- 命令行单刮：`uv run crawl --site <site> -n <番号>`
- GUI 检测网络：设置 → 网络 → 「开始检测」按钮。

---

## 第 1 部分：云端做不了、必须本机验证的项

> 以下项 devbox 无显示器/无真实网络/无 Docker/无住宅 IP，完全无法验证，优先级最高。

### 1.1 GUI 启动与基本交互
- [ ] 双击 `MDCx.exe`（或 `uv run python main.py`）能正常启动，无闪退、无黑色控制台窗口
- [ ] 主界面各 tab（刮削/工具/设置）切换正常，无重影/遮挡
- [ ] 「开始刮削」「停止」按钮工作正常
- [ ] 保存设置后重启，配置能正确保留（重点：网络页各配置项）
- [ ] 高分屏/缩放设置生效

### 1.2 真实刮削全流程（GUI 端到端）
- [ ] 拖入一个视频文件 → 自动识别番号 → 走各站点刮削 → 生成 NFO + 封面 + 整理文件夹
- [ ] 多文件批量刮削（并发、进度显示、剩余任务列表）
- [ ] 断点续刮：中途退出重启，从上次进度继续（`userdata/scrape_state.db`）
- [ ] 失败重试、失败文件移动、失败列表导出
- [ ] 刮削缓存管理：统计/重置/清空（工具页）

### 1.3 文件与媒体处理
- [ ] NFO 生成格式正确（Emby/Kodi 命名、字段完整）
- [ ] 封面/海报/缩略图下载、人脸裁剪、水印添加
- [ ] Amazon 高清封面（有真实图片源时）——条码识别、高清直链
- [ ] 软链接/硬链接创建（跨盘、NAS 场景）
- [ ] 命名模板（Jinja2）效果验证

### 1.4 Emby 集成（需真实 Emby 服务器）
- [ ] Emby 地址 + API 密钥连接
- [ ] 演员管理器：拉取演员列表、匹配头像/简介、批量同步
- [ ] Gfriends/graphis/minnano/本地文件夹多源匹配
- [ ] 演员头像缓存持久化（`userdata/emby_actor_cache/`）

### 1.5 演员库维护（GUI 工具页）
- [ ] 补全中文名/TMDB ID/LibreDMM 链接/别名/minnano 资料
- [ ] 检查用户库、剔除男演员、校验 tmdbid、更新 nfo tmdbid
- [ ] 批量处理进度、分片续跑、停止按钮

### 1.6 代理行为（真实代理环境）
- [ ] 配置可用代理 → 验证「走代理网站」白名单只对这些站走代理，其余直连
- [ ] 开关代理对翻译引擎（Google/Bing）的实际影响

---

## 第 2 部分：爬虫有效性（重点：综合站 / 免 CF 通道 / 高频站）

> 用各站常见番号测，能刮出标题/封面即有效。每站记「成功 / 失败+原因 / 超时」。

### 2.1 综合站（有码+无码，高频兜底）
| 站点 | 测试番号 | 结果 |
|---|---|---|
| javbus | SSNI-804 | |
| javdb | SSNI-804 | |
| javdb_api | SSNI-804 | |
| javdb_app | SSNI-804 | |
| missav | SSNI-804 | |
| missav_api | SSNI-804 | |
| javday | SSNI-804 | |
| javfree | SSNI-804 | |
| airav_cc | SSNI-804 | |
| avsex | SSNI-804 | |
| iqqtv | SSNI-804 | |
| official | SSNI-804 | |

### 2.2 免 CF 通道（重点验证）
| 站点 | 测试番号 | 结果 |
|---|---|---|
| missav_api | SSNI-804 | |
| r18dev | SSNI-804 | |
| javdb_api | SSNI-804 | |

### 2.3 有码信息站
| 站点 | 测试番号 | 结果 |
|---|---|---|
| dmm | SSNI-804 | |
| dmm_api | SSNI-804 | |
| avmoo | SSNI-804 | |
| javlibrary | SSNI-804 | |
| avbase | SSNI-804 | |
| freejavbt | SSNI-804 | |
| lulubar | SSNI-804 | |
| libredmm | SSNI-804 | |

### 2.4 无码站
| 站点 | 测试番号 | 结果 |
|---|---|---|
| avsox | 081826_100 | |
| aventertainments | 081826_100 或 082226-001 | |

### 2.5 FC2 站
| 站点 | 测试番号 | 结果 |
|---|---|---|
| fc2 | FC2-PPV-1014367 | |
| fc2ppvdb | FC2-PPV-1014367 | |

### 2.6 官网系（仅覆盖本厂）
| 站点 | 测试番号 | 结果 |
|---|---|---|
| faleno | （FALENO 系番号，经 official 厂牌子爬虫） | |
| dahlia | （DAHLIA 系番号，经 official 厂牌子爬虫） | |
| prestige | （PRESTIGE 系番号） | |
| mgstage | （MGSTAGE 系番号） | |
| xcity | （XCITY 系番号） | |
| getchu | （GETCHU 系番号） | |
| getchu_dmm | （GETCHU 系番号） | |
| mywife | （MYWIFE 系番号） | |

### 2.7 欧美 / 国产
| 站点 | 测试番号 | 结果 |
|---|---|---|
| theporndb | （欧美番号） | |
| avheat | Men.26.08.17 | |
| madouqu | （国产番号） | |
| madou_club | （麻豆系国产番号） | |

---

## 第 3 部分：代理需求判断

> 对每个「直连失败」的站，分别测：开代理 / 关代理 的差异。
> 默认 `use_proxy=True` 且命中 `proxy_sites` 白名单才走代理。

**重点站**（默认在 proxy_sites 白名单）：javbus、javdb、javlibrary、avsox、avmoo、avheat、xcity、mgstage、dmm 等。

| 站点 | 开代理 | 关代理 | 结论（必须代理?） |
|---|---|---|---|
| javbus | | | |
| javdb | | | |
| javlibrary | | | |
| avsox | | | |
| avmoo | | | |
| avheat | | | |
| xcity | | | |
| mgstage | | | |
| dmm | | | |

---

## 第 4 部分：TRAWL Windows 便携版专项验证（重点）

> TRAWL 便携版是 Windows 端外部 CF 服务的主要载体，必须本机实测。详见 `scripts/windows/USAGE.md`。

### 4.1 便携版启动
- [ ] 便携包已预下载（`trawl-portable-*-windows.zip`），确认版本
- [ ] 解压后运行 `download-bun.bat`（首次需装 Bun 时）
- [ ] 双击 `start-trawl.bat` 启动，预期输出：
  ```
  [api] TRAWL starting on :8191  (pool: 1 browsers)
  [api] session cache connected  (Tier 2 fast-path enabled)
  ```
- [ ] **内置 Redis 生效**：日志含 `Tier 2 fast-path enabled`（Redis 6380 自动拉起）
- [ ] **内置补丁生效**：`trawl-goto-timeout.patch` 应用成功（Tier3/4 超时 30s→90s）
- [ ] 服务监听 `http://localhost:8191`，浏览器池正常（Camoufox 加载）

### 4.2 便携版健康检查
- [ ] `curl http://localhost:8191/health` 或 GUI 检测网络 → 外部 CF 服务项显示正常
- [ ] 重启后 Redis/补丁仍自动生效（幂等）

### 4.3 MDCx 配置（注意：内置 CF 已移除）
GUI 设置 → 网络 → 外部 CF 服务填 `http://127.0.0.1:8191`，后端类型选 `trawl`。
> 不要填 `/v1` 路径（MDCx 适配层检测的是 `/cookies`/`/html`/`/mirror` 端点）。

---

## 第 5 部分：外置 CF 服务过 CF 能力

> 本机有住宅 IP 时最接近真实场景。用 **TRAWL 便携版**（第 4 部分）验证解真实 CF 挑战。
> （本机无 Docker，不测原生 FlareSolverr；若以后有 Docker 可按需补测。）

### 5.1 MDCx 配置
GUI 设置 → 网络 → 外部 CF 服务填 `http://127.0.0.1:8191`，后端类型选 `trawl`。

### 5.2 过 CF 测试目标（真实 CF 挑战站）
| 目标 | 说明 | trawl 结果 |
|---|---|---|
| fc2hub / javten 首页 | 轻挑战 | |
| fc2hub / javten 搜索页 | Turnstile | |
| lulubar | JS 渲染 + 挑战 | |
| f101w.com（javlibrary 镜像） | 标准 CF 挑战 | |

---

## 结果记录（汇总）

| 类别 | 有效数 / 总数 | 失败站及原因 |
|---|---|---|
| 综合站 | /12 | |
| 免 CF 通道 | /3 | |
| 有码信息站 | /8 | |
| 无码 | /2 | |
| FC2 | /2 | |
| 官网系 | /8 | |
| 欧美/国产 | /4 | |
| **爬虫合计** | **/39** | |

| 本机专项 | 通过数 / 总数 | 问题项 |
|---|---|---|
| GUI 启动/交互 | /5 | |
| 真实刮削全流程 | /5 | |
| 文件/媒体处理 | /5 | |
| Emby 集成 | /4 | |
| 演员库维护 | /4 | |
| 代理行为 | /2 | |
| TRAWL 便携版启动/Redis/补丁 | /4 | |

> 结论建议：哪些站确定失效可考虑精简、哪些需代理、外置 CF 服务实际过 CF 能力、本机专项有无问题。
