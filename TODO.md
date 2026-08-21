# TODO

## 待办

### 1. 深度链接（`mdcx://` 自定义协议）

**目标**：从浏览器点击链接直接唤起 mdcx，跳转到番号刮削页。

**实现要点**：
- 协议格式：`mdcx://scrape?code=ABC-123`（刮削）、`mdcx://import?path=...`（导入，可选）
- 注册：Windows 注册表 `HKCU\Software\Classes\mdcx`、macOS Info.plist、Linux .desktop MimeType
- `main.py` 解析 URL 参数跳转页面；已运行时通过 IPC（socket/命名管道）传递 URL

**成本**：1-2 天
**参考**：javm `javm://download?url=...&title=...`

---

### 2. JavInfoApi 作为可选元数据源 + Emby 数据源扩展

**目标**：支持自托管 JavInfoApi（r18.dev 数据库转储：185 万视频/10 万演员）作为结构化 API 源，替代在线 API 逐个请求。

**实现要点**：
- 新增爬虫 `mdcx/crawlers/javinfoapi.py`，继承 `BaseCrawler`
- 配置：`api_url`（默认 `http://localhost:18080`）、可选 `admin_token`
- 接口：番号查询 `GET /api/v1/videos/search?dvd_id=`、批量 `POST /api/v1/videos/lookup`（一次 100 个）、演员模糊匹配 `GET /api/v1/actresses?q=`
- Emby 扩展：演员管理器数据源优先级新增 `javinfoapi`，头像走 `image_url` 下载缓存
- API 不可用时 fallback 其他站点

**成本**：3-5 天
**参考**：https://github.com/cdlongbow/JavInfoApi — API.md

---

### 3. 字段级多源合并

**目标**：多站点结果按字段完整度评分取最优，缺失字段从备用站点补全，替代"首个成功即用"。

**实现要点**：
- 主站点结果为基准，缺失字段触发备用站点补全（按配置优先级），全字段完整则不补全
- 字段权重：标题/番号/封面 > 演员/标签 > 剧情/时长/日期
- 配置项 `field_merge_enabled`（默认关闭）

**成本**：1-2 周
**参考**：JavInfoApi supplement 分层设计；yamdc Category Chain 搜索链

---

### 4. 演员别名 + 标签声明式配置

**目标**：配置文件写一行即可统一演员名和标签，新刮削自动将别名替换为规范名。标签支持树形映射 + 父级补全。

**实现要点**：
- 配置格式（config.ini `[actor_aliases]` 或独立 JSON）：`河北彩花 = 河北彩伽,河北彩花（河北彩伽）`
- 写 NFO 前：别名 → 规范名进 `<actor>`，原始写法保留到 `<actor><aliases>` 用于头像/资料查询
- 标签树形映射（yamdc）：`{name, alias[], children[]}`，命中子标签自动补全父标签路径，冲突检测 + 去重排序
- Actor Split（yamdc）：正则从 `"演员A (别名B)"` 自动拆分
- 显示优先级（local-javlibrary）：规范名 > NFO 原始名；别名参与头像/资料匹配支持简繁体转换（复用 zhconv）
- 重名冲突软合并（local-javlibrary）：与其他演员规范名冲突时提示合并，统一影片与别名，不回写已有 NFO
- 已有影片不自动重命名；与 #10 联动：别名配置作为 GFriends 候选名来源

**成本**：2-3 天
**参考**：MDCz `personSync.actorAliases` TOML；yamdc `tag_mapper.go`；local-javlibrary 演员「显示名+曾用名+软合并」

---

### 5. 维护预览 + 字段级 diff

**目标**：刮削/整理/刷新执行前预览每条变更的字段级 diff，逐字段选择保留新旧值后确认执行。

**实现要点**：
- dry-run 预览模式：先算变更展示 diff，确认后执行
- Qt 表格/树形展示，支持批量选择
- 预设模式：`read_local` / `refresh_data` / `organize_files`
- 与 `scrape_cache.py` 集成 + #11 操作历史联动

**成本**：1-2 周
**参考**：MDCz `maintenancePreviewItem` DTO

---

### 6. 外部 NFO 标识解析器

**目标**：读取其他工具（MDCx 原版/MetaTube/Jellyfin）生成的 NFO 时，表驱动解析番号和来源标识，来源未知也能正常读取。

**实现要点**：
- `nfo.py` 新增 identifier resolver：标准 `uniqueid[type]` → `<num>` + 无 type → `<{site}id>` 标签映射（→ mdcx Website 枚举）
- 来源未知时 `website` 为空，仍可进入读取本地/资源发现/文件整理流程
- 不从文件名/目录名推断番号

**成本**：2-3 天
**参考**：MDCz `nfoSnapshot.ts`；mdcx `nfo.py:get_external_id_tag_name`

---

### 7. JavDB App API 端点扩展

**目标**：用 javapi 逆向的 37 个端点文档扩展 javdb_app 爬虫（现仅用 3 个）。

**实现要点**：
- 优先集成磁力列表：`GET /api/v1/movies/{id}/magnets`（cnsub/hd/files_count），排序参考 javdb-cli：`cnsub > hd > size > files_count`
- 所有端点共享现有签名 + 设备参数，复用 `_request_api`
- 配置项 `javdb_app_fetch_magnets`（默认关闭）
- 导演/厂牌/系列详情端点价值低暂不做；`MovieDetail` 用 `extra="ignore"` 丢弃了 id 字段，需要时去掉

**成本**：2-3 天
**参考**：https://github.com/ANDonekey/javapi；https://github.com/FlanChanXwO/javdb-cli

---

### 8. missav 爬虫指纹降级策略

**目标**：域名轮询全失败时，尝试 `curl_cffi` 的 `safari17_2_ios` 指纹作为绕过 CF 的最后手段。

**实现要点**：
- 默认指纹池加入 `safari17_2_ios`，或 missav 重写 session 创建指定指纹
- 仅在默认指纹被 CF 拦截（403/503 + challenge markers）时降级

**成本**：半天
**参考**：unofficial-api-for-missav；curl_cffi impersonate 文档

---

### 9. yamdc 架构借鉴

**目标**：选择性引入 yamdc（已归档，Go 刮削工具）的三个设计。

| 设计 | 成本 | 说明 |
|------|------|------|
| AI Tagger | 1-2 天 | 从标题+简介用 AI 提取最多 5 个标签，`AI-` 前缀加入 Genres；LLM 走 `USER_LLM_*` 环境变量 |
| 声明式番号清洗 ruleset | 3-5 天 | 6 阶段清洗流水线（normalizer→rewrite→suffix→noise→matcher→postprocess）+ Explain 调试 |
| Category Chain | 3-5 天 | 爬虫配置按分类拆链（all/fc2/jvr 等），命中分类走专用链否则 fallback |

Plugin Bundle 不做（Python 类迁移成本高收益低）。

**参考**：https://github.com/xxxsen/yamdc（已归档）；https://github.com/cdlongbow/yamdc-plugin

---

### 10. GFriends 候选名列表匹配

**目标**：`gfriends_find_actor` 接受候选名列表（规范名+别名+罗马音）依次匹配，提高头像命中率。

**实现要点**：
- 接口改为接受 `names: list[str]`，依次 NFKC 归一化匹配，首个命中即返回
- `ActorInfo` 增加 `aliases: list[str]`，来源：JavDB / 本地演员库 keyword 列 / #4 声明式别名

**成本**：1-2 天
**参考**：sakuramediabe `GfriendsAvatarJavdbProvider`

---

### 11. 操作历史与批量回滚

**目标**：记录每次操作的文件变更，支持按批次回滚。

**实现要点**：
- 新增 `core/history.py`，SQLite 记录操作日志（复用现有基础设施）
- 操作类型：`file_move`/`file_rename`/`nfo_write`/`image_download`/`image_overwrite`
- 批量操作生成 batch_id 关联；回滚逆向移动/重命名，NFO/图片写入前备份恢复
- 工具栏「历史记录」按钮：批次列表 + 回滚；与 #5 维护预览联动
- 吸收 #18 NFO 库管理的操作历史需求

**成本**：1-2 周
**参考**：javinizer-go `internal/history/`

---

### 12. per-scraper 代理配置继承

**目标**：每个爬虫可独立配代理：继承全局 / 直连 / 指定 profile 三态。

**实现要点**：
- `ProxyProfile` dataclass（url/username/password）多 profile
- `SiteConfig.proxy`: None=继承全局，`"direct"`=不用，其他=指定 profile
- UI：设置 → 代理管理，profile 列表 + 每爬虫选择

**成本**：2-3 天
**参考**：javinizer-go `ResolveScraperProxy` 三模式解析

---

### 13. MOVIE_NUMBER_PATTERNS 专用规则补全（低优先级）

**目标**：补全 sakuramediabe 番号规则中 mdcx 缺失的部分。

**实现要点**：
- 价值较高：`9` 前缀规则（如 `9ssis01`），当前完全无法识别
- 其余（LAF/MISM/MKBD/CWPBD/SM/MCDV）通用规则可兜底，仅在匹配不理想时补充
- 每条规则配测试用例验证不与现有规则冲突

**成本**：1 天
**参考**：sakuramediabe `movie_numbers.py`

---

### 14/15/17. 刮削缓存三项增强（合并条目）

三项均改 `core/scrape_cache.py`，一起做可共用测试基建。

#### A. 404 负面缓存（原 #14，JavBoss 借鉴）

404 是确定性失败，重试无意义。缓存负面状态设 TTL（7 天），期内跳过。

- `ScrapeState` 新增 `failure_reason`（复用 `FailureReason` 枚举），`set_failed` 写入
- `should_skip`：`failed` + `NOT_FOUND` + 未过 TTL → 跳过；其他失败仍走 `MAX_RETRY_COUNT`
- UI「刮削缓存管理」显示负面缓存数量；读取模式不受影响

#### B. 缓存 key 版本化（原 #15，JavBoss 借鉴）

crawler 解析逻辑修复后，旧 done 记录自动失效，无需手动清缓存。

- 新增 `SCRAPE_CACHE_SCHEMA_VERSION = "v2"` 常量；表加 `schema_version` 列（ALTER TABLE 迁移）
- `set_done` 写版本号，`set_failed` 不写；`should_skip` 版本不匹配 → 返回 False
- 后续改解析逻辑只需递增版本号

#### C. 字段缺失检测（原 #17，OpenAver 借鉴）

检测 done 但关键字段为空的影片，批量重刮。站点改版期间刮到的影片可能批量缺字段。

- 新增 `list_incomplete(required_fields)`：遍历 done 记录检查字段有效性（runtime="0" 视为无效）
- UI 工具页「字段缺失影片」面板：列表 + 批量重新入队

**成本**：合计 3-5 天
**参考**：JavBoss `internal/jav/cache.go`；OpenAver `needs_update()`

---

### 16. 视频截图工具（长期规划）

**目标**：所有站点都抓不到封面时（国产/素人常见），ffmpeg 截取关键帧作 thumb/poster。

**实现要点**：
- `core/video_screenshot.py`：截取视频 25%/50%/75% 帧，最大帧作 poster，其余作 extrafanart 候选
- 仅在所有站点未返回图时触发；依赖系统 ffmpeg（检测可用性，非 Python 包）
- 配置：`video_screenshot_enabled`（默认关）、ffmpeg path、并发 worker 数、大文件（>10GB）跳过
- 截图后走相同加水印/命名/移动流程

**成本**：3-5 天
**参考**：JavBoss `screenshot_manager.go` — ffmpeg/mpv 8 worker 并发截图

---

### 19. NFO 库管理增强（local-javlibrary 借鉴）

**目标**：给 NFO 库管理页（已完成，见 changelog v2.0.6+）补上海报墙浏览体验和更强的筛选能力。

**实现要点**：
- **缩略图视图（海报墙）**：「文字/缩略图」切换，`QListWidget.setIconMode()` + 异步加载同目录 `poster.jpg` 缩略图（复用 `PreviewImageLoader` 异步模式；切到缩略图模式才按可视范围懒加载）
- **仅显示可播放**：复选框过滤无视频文件的孤儿 NFO（扫描时顺便探测标记 `Qt.UserRole+2`）
- **多条件组合筛选**：单文本框扩展为 演员 + 年份范围 + 标签 组合筛选，保留关键词框作快速入口

**不做**：SQLite 全量建库（万级以下 rglob 够用）、收藏夹/最近看过（需播放数据，稀释刮削工具定位）

**成本**：缩略图 1 天 + 可播放过滤 0.5 天 + 组合筛选 1 天
**参考**：local-javlibrary 视图切换/分类筛选
