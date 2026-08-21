# TODO

## 待办

### 1. 深度链接（`mdcx://` 自定义协议）

**目标**：从浏览器或其他应用点击链接直接唤起 mdcx，跳转到番号刮削页。

**实现要点**：
- 协议格式：`mdcx://scrape?code=ABC-123`（刮削）、`mdcx://import?path=...`（导入，可选扩展）
- 注册：Windows 注册表 `HKCU\Software\Classes\mdcx`、macOS Info.plist、Linux .desktop MimeType
- `main.py` 接收 URL 参数解析 query string 跳转页面；已运行时通过 IPC（socket/命名管道）传递 URL

**成本**：1-2 天 / 200 行
**参考**：javm `javm://download?url=...&title=...`

---

### 2. JavInfoApi 作为可选元数据源 + Emby 数据源扩展

**目标**：支持用户自托管 JavInfoApi 作为结构化 API 元数据源，同时扩展 Emby 演员管理器数据源。

**背景**：JavInfoApi 基于 r18.dev 数据库转储（185 万视频 / 10 万演员），提供番号精确查询、批量查找、演员作品列表等 REST API。mdcx 现有 `r18dev.py` 走在线 API 逐个请求受网络/CF 限制。

**实现要点**：
- 新增爬虫 `mdcx/crawlers/javinfoapi.py`，继承 `BaseCrawler`
- 配置项：`api_url`（默认 `http://localhost:18080`）、可选 `admin_token`
- 番号查询 `GET /api/v1/videos/search?dvd_id=ABC-123`，批量 `POST /api/v1/videos/lookup`（一次 100 个）
- 字段映射：`content_id`/`dvd_id`/`title_en`/`title_ja`/`release_date`/`runtime_mins`/`jacket_full_url`/`actresses`/`maker`/`label`/`series`/`categories`
- Emby 扩展：`emby_actor_manager.py` 数据源优先级新增 `javinfoapi` 选项，`GET /api/v1/actresses?q=<name>` 模糊匹配，头像走 `image_url` 下载缓存
- API 不可用时 fallback 到其他站点

**成本**：3-5 天（爬虫 + 配置 + 字段映射 + 批量优化 + Emby 挂载 + 测试）
**参考**：https://github.com/cdlongbow/JavInfoApi — API.md 完整接口文档

---

### 3. 字段级多源合并

**目标**：刮削时多站点结果不再"首个成功即用"，而是按字段完整度评分取最优，缺失字段从备用站点补全。

**实现要点**：
- 主站点抓取结果作为基准，缺失字段触发备用站点补全（按已配置优先级）
- 字段权重：标题/番号/封面 > 演员/标签 > 剧情/时长/日期
- 配置项 `field_merge_enabled`（默认关闭，保持现有行为）
- 仅在缺失字段时触发额外请求，全字段完整则不补全
- 测试：单站点完整 / 多站点互补 / 全站点缺失

**成本**：1-2 周（scraper 合并逻辑重构 + 字段权重配置 + 测试）
**参考**：JavInfoApi supplement 层 `source_*` → `supplement_*` → `resolved_*` 分层设计；yamdc Category Chain 搜索链

---

### 4. 演员别名 + 标签声明式配置

**目标**：用户在配置文件中写一行即可统一演员名称和标签，新刮削自动将别名替换为规范名。标签支持树形映射 + 父级补全。

**背景**：mdcx 现有别名管理在 `actor_database.xlsx`（`actor_db_tool.py`），数据库驱动门槛高。MDCz 用 TOML 配置段一行一个演员组，小白可用。yamdc 的 `tag_mapper.go` 提供树形 JSON 结构支持别名映射 + 父级补全。

**实现要点**：
- 配置格式（config.ini `[actor_aliases]` 段或独立 JSON）：
  ```
  [actor_aliases]
  河北彩花 = 河北彩伽,河北彩花（河北彩伽）
  三上悠亚 = 鬼頭桃菜,鬼头桃菜
  ```
- 刮削写 NFO 前做名称替换：别名 → 规范名输出到 `<actor>`，原始写法保留到 `<actor><aliases>` 用于头像/资料查询
- 标签树形映射（yamdc `tag_mapper.go`）：`{name, alias[], children[]}`，别名 → 标准，命中子标签自动补全父标签路径，冲突检测 + 去重排序
- Actor Split（yamdc）：正则 `\s*(.+?)\s*\(\s*(.+?)\s*\)` 从 `"演员A (别名B)"` 自动拆分
- 已有影片不自动重命名
- 与 #10（GFriends 候选名）联动：别名配置直接作为候选名来源

**成本**：2-3 天（配置解析 + 替换逻辑 + 标签树 + 测试）
**参考**：MDCz `personSync.actorAliases` TOML；yamdc `tag_mapper.go` / `actor_split_handler.go`；mdcx `actor_db_tool.py` 别名同步逻辑

---

### 5. 维护预览 + 字段级 diff

**目标**：刮削/整理/刷新操作执行前预览每条变更的字段级 diff，用户逐字段选择保留新旧值后再确认执行。

**实现要点**：
- 新增 dry-run 预览模式：先计算变更展示 diff，用户确认后执行
- 字段级 diff：标题/演员/标签/封面/剧情等逐字段对比新旧值
- 用户可逐字段选择保留旧值或采用新值
- 预设模式：`read_local`（只读本地 NFO）、`refresh_data`（联网刷新）、`organize_files`（文件整理）
- UI：Qt 表格/树形控件展示 diff，支持批量选择
- 与 `scrape_cache.py` 集成 + #11 操作历史联动

**成本**：1-2 周（diff 引擎 + Qt 预览 UI + 逐字段选择 + 测试）
**参考**：MDCz `maintenancePreviewItem` DTO + `fieldDiffs` 字段级对比

---

### 6. 外部 NFO 标识解析器

**目标**：读取其他工具（MDCx 原版/MetaTube/Jellyfin）生成的 NFO 时，表驱动解析番号和来源网站标识，来源未知也能正常读取。

**实现要点**：
- `nfo.py` 新增 identifier resolver，表驱动解析
- 优先级：标准 `uniqueid[type]` → `<num>` + 无 type `uniqueid` → `<{site}id>` 标签映射（`javbusid`/`javdbid`/`dmmid`/`fc2id` 等 → mdcx Website 枚举）
- 来源未知时 `website` 为空，仍可进入读取本地/资源发现/文件整理流程
- 不从文件名/目录名推断番号
- 测试：MDCx/MetaTube/Jellyfin NFO fixture + round-trip

**成本**：2-3 天
**参考**：MDCz `nfoSnapshot.ts` identifier resolver；mdcx `nfo.py:get_external_id_tag_name` 已有标签生成逻辑

---

### 7. JavDB App API 端点扩展

**目标**：利用 javapi 仓库逆向的完整 JavDB App API 文档，扩展 mdcx javdb_app 爬虫数据覆盖面。

**背景**：`javdb_app.py` 目前仅用 3 个端点（`/api/v2/search`、`/api/v4/movies/{id}`、`/api/v1/actors/{id}`）。javapi 仓库提供了 37 个公开端点文档，签名常量已验证一致。

**实现要点**：
- 优先集成磁力列表：`GET /api/v1/movies/{id}/magnets`（含 cnsub/hd/files_count 字段），详情页磁力不全时补充
- 磁力排序参考 javdb-cli：`cnsub > hd > size > files_count`
- 导演/厂牌/系列详情端点价值低（详情页已返回 name），`MovieDetail` 当前用 `extra="ignore"` 丢弃了 id 字段，将来需要时去掉 ignore
- 所有端点共享现有签名 + 设备参数，复用 `_request_api`
- 配置项 `javdb_app_fetch_magnets`（默认关闭）

**成本**：2-3 天
**参考**：https://github.com/ANDonekey/javapi — `JavDB API/` 完整端点文档；https://github.com/FlanChanXwO/javdb-cli — Go SDK 磁力搜索/排序

---

### 8. missav 爬虫指纹降级策略

**目标**：当 missav 域名轮询全部失败时，尝试 `curl_cffi` 的 `safari17_2_ios` 指纹作为最后手段绕过 Cloudflare。

**背景**：实测 `missav.ai` 用默认指纹池 3 轮全 200，但未来 CF 加强防护时 `safari17_2_ios` 可能成为备用手段。

**实现要点**：
- `AsyncWebClient._new_curl_session` 默认指纹池加入 `safari17_2_ios`，或 missav 爬虫重写 session 创建指定指纹
- 仅在默认指纹被 CF 拦截（403/503 + challenge markers）时降级
- 注意 iOS 指纹 TLS ClientHello 与桌面不同，可能影响部分站点 TLS 检测

**成本**：半天
**参考**：https://github.com/EchterAlsFake/unofficial-api-for-missav；curl_cffi impersonate 文档

---

### 9. yamdc 架构借鉴

**目标**：参考已归档的 yamdc（xxxsen/yamdc，Go 影片元数据刮削工具）架构设计，选择性引入对 mdcx 有实际价值的模式。

**背景**：yamdc 已于 2026-08-07 归档，但其架构有多处值得借鉴。配套 cdlongbow/yamdc-plugin 包含 19 个爬虫的声明式 YAML 定义。

**可借鉴的设计**：

| 设计 | 价值 | 说明 |
|------|------|------|
| AI Tagger Handler | 中 | 从标题+简介用 AI 提取 2-3 字标签（最多 5 个），`AI-` 前缀加入 Genres；mdcx 目前无 AI 能力 |
| 声明式番号清洗 ruleset | 中 | 6 阶段清洗（normalizer→rewrite→suffix→noise→matcher→postprocess）+ Explain 调试 |
| Processor Pipeline 注册表 | 中 | handler 独立注册 + 配置驱动启用/排序 |
| Category Chain 搜索链 | 中 | 按分类走不同爬虫链（all/fc2/jvr/cospuri/md），命中分类走专用链 |
| Plugin Bundle 外部分发 | 低 | mdcx 爬虫是 Python 类，迁移成本高收益低 |

**实现要点**：
- AI 标签提取（可选，需用户自行配置 LLM）：prompt 限制最多 5 个标签，遵循 no-read-llm-env 规则用 `USER_LLM_*` 环境变量
- 声明式番号清洗：ruleset 配置文件驱动，6 阶段流水线 + Explain 调试输出
- Category Chain：爬虫配置按分类拆链，命中分类走专用链否则 fallback 到 `all`

**成本**：AI 标签 1-2 天 / 番号清洗 3-5 天 / Category Chain 3-5 天
**参考**：https://github.com/xxxsen/yamdc（已归档）；https://github.com/cdlongbow/yamdc-plugin（19 爬虫 YAML）

---

### 10. GFriends 候选名列表匹配

**目标**：`gfriends_find_actor` 接受演员候选名列表（规范名 + 别名 + 罗马音），依次尝试匹配，提高头像命中率。

**实现要点**：
- `gfriends_find_actor` 接受 `names: list[str]`，依次 NFKC 归一化匹配，首个命中即返回
- `ActorInfo` 增加 `aliases: list[str]` 字段，在 `search_actor_info` 中填充
- 别名来源：JavDB `fetch_javdb_actor_info` / 本地演员库 keyword 列 / #4 声明式别名配置

**成本**：1-2 天
**参考**：sakuramediabe `GfriendsAvatarJavdbProvider` 传入 `actor.name + alias_names`

---

### 11. 操作历史与批量回滚

**目标**：记录每次刮削/整理操作的文件变更，支持按批次回滚。

**背景**：mdcx 当前无操作历史和回滚机制，批量刮削后发现问题只能手动逐个恢复。

**实现要点**：
- 新增 `core/history.py`，用 SQLite 记录操作日志（复用 mdcx 现有 SQLite 基础设施）
- 操作类型：`file_move`/`file_rename`/`nfo_write`/`image_download`/`image_overwrite`
- 每次批量操作生成 batch_id，所有操作记录关联
- 回滚：逆向移动/重命名，NFO/图片恢复旧内容（写入前备份）
- UI：工具栏新增"历史记录"按钮，展示批次列表 + 回滚
- 与 #5 维护预览联动

**成本**：1-2 周（SQLite 表结构 + 操作记录注入点 + 回滚逻辑 + UI）
**参考**：javinizer-go `internal/history/` 目录

---

### 12. per-scraper 代理配置继承

**目标**：每个爬虫可独立配置代理，支持继承全局默认或显式指定 profile。

**实现要点**：
- 新增 `ProxyProfile` dataclass（url/username/password），支持多 profile
- `SiteConfig` 增加 `proxy: Optional[str]`（None=继承全局，`"direct"`=不用，其他=指定 profile）
- 三态解析：爬虫请求时按语义解析代理配置
- UI：设置 → 代理管理，新增 profile 列表 + 每个爬虫代理选择

**成本**：2-3 天
**参考**：javinizer-go `internal/scraperconfig/` `ResolveScraperProxy` 三模式解析

---

### 13. MOVIE_NUMBER_PATTERNS 专用规则补全（低优先级）

**目标**：补全 sakuramediabe `MOVIE_NUMBER_PATTERNS` 中 mdcx 缺失的专用番号规则。

**实现要点**：
- 9 前缀规则价值较高：`9` 开头 + 字母 + 数字组合（如 `9ssis01`），当前完全无法识别
- 其他专用规则（LAF/MISM/MKBD/CWPBD/SM/MCDV）价值低，通用规则可兜底，仅在匹配不理想时补充
- 每条规则配测试用例验证不与现有规则冲突

**成本**：1 天
**参考**：`/tmp/sakuramediabe/src/common/movie_numbers.py` `MOVIE_NUMBER_PATTERNS`

---

### 14. 404 负面缓存（JavBoss 借鉴）

**目标**：站点返回 404（确认无此番号）时缓存"负面"状态，设定 TTL 期间不再重复请求同一番号，减少无效请求。

**背景**：mdcx 当前 `ScrapeStateCache` 只记录 `done`/`failed`，`failed` 会按 `MAX_RETRY_COUNT=3` 重试。但 404 是确定性失败（站点确实没有这个番号），重试无意义，应像 JavBoss 那样缓存 404 结果并设 TTL（7 天），TTL 过期前直接跳过。

**实现要点**：
- `ScrapeState` 新增 `failure_reason` 字段（复用 `FailureReason` 枚举：`NOT_FOUND`/`BLOCKED`/`TIMEOUT`/`PARSE_ERROR`/`UNKNOWN`）
- `set_failed` 写入 `failure_reason`
- `should_skip` 检查：`status=failed` + `failure_reason=NOT_FOUND` + 未过 TTL → 跳过
- 404 TTL 默认 7 天，其他失败仍走现有 `MAX_RETRY_COUNT` 重试逻辑
- UI 工具页「刮削缓存管理」面板显示负面缓存数量
- 读取模式不受负面缓存影响（始终处理全部选中文件）

**成本**：1-2 天
**参考**：JavBoss `internal/jav/cache.go` — 404 缓存 7 天 TTL，成功缓存 90 天

---

### 15. 缓存 key 版本化（JavBoss 借鉴）

**目标**：crawler 解析逻辑变更后，旧 `scrape_state.db` 中的 "done" 记录自动失效，无需用户手动清缓存即可重新刮削。

**背景**：mdcx `ScrapeStateCache` 按 `file_path` + `mtime` 判断是否跳过，无版本概念。修复了某个 crawler 的解析 bug 后，旧 "done" 记录仍会跳过，用户必须到工具页手动重置缓存才能看到修复效果。JavBoss 每个 provider 有独立版本号，解析逻辑改了升版本号 → 旧缓存自动失效。

**实现要点**：
- `core/scrape_cache.py` 新增 `SCRAPE_CACHE_SCHEMA_VERSION = "v2"` 常量
- `scrape_state` 表新增 `schema_version TEXT NOT NULL DEFAULT ''` 列（`open()` 中 ALTER TABLE 迁移）
- `ScrapeState` dataclass 新增 `schema_version: str = ""` 字段
- `set_done` 写入当前版本号；`set_failed` 不写版本号（失败记录不受版本影响）
- `should_skip` 增加版本检查：`state.schema_version != SCRAPE_CACHE_SCHEMA_VERSION` → 返回 False（需重刮）
- 旧记录 `schema_version=""` 与 `"v2"` 不匹配，升级后首次刮削自动重刮全部
- 后续改 crawler 解析逻辑时，开发者只需递增版本号即可让用户缓存自动失效

**成本**：半天
**参考**：JavBoss `internal/jav/cache.go` `lookupJavCacheKeyVersionByProvider` map

---

### 16. 视频截图工具（JavBoss 借鉴，长期规划）

**目标**：为没有封面的视频自动截取关键帧作为 thumb/poster，替代空白占位。

**背景**：部分小众番号（尤其国产/素人）在所有站点都抓不到封面图，最终 NFO 的 thumb/poster 字段为空。JavBoss 用 ffmpeg/mpv 8 worker 并发截图，从视频中提取多帧选最佳作为封面。

**实现要点**：
- 新增 `core/video_screenshot.py`，调用 ffmpeg 截取视频 25%/50%/75% 位置的帧
- 选择最大文件大小的帧作为 poster，其余作为 extrafanart 候选
- 仅在所有站点均未返回 thumb/poster 时触发
- 依赖系统 ffmpeg（非 Python 包），需检测可用性
- 配置项 `video_screenshot_enabled`（默认关闭）、`video_screenshot_ffmpeg_path`
- 性能控制：并发 worker 数量可配置，大文件跳过（>10GB）
- 与现有图片下载流程整合：截图后走相同的加水印/命名/移动逻辑

**成本**：3-5 天（ffmpeg 集成 + 帧选择算法 + 配置 UI + 测试）
**参考**：JavBoss `internal/jav/screenshot_manager.go` — ffmpeg/mpv 8 worker 并发截图

---

### 17. 刮削成功但字段缺失检测（OpenAver 借鉴）

**目标**：检测已标记 done 但关键字段为空的影片，列出缺失字段供用户批量重刮。

**背景**：mdcx `ScrapeStateCache` 只有 `should_skip`（done 跳过）、`should_retry`（failed 重试）、`list_pending`（列失败文件）。一旦标记 done 就永远跳过，即使只刮到番号+标题、演员/日期/标签全空。站点改版期间某段时间刮到的影片可能批量缺字段，用户只能手动逐个强制重刮。

**实现要点**：
- `ScrapeStateCache` 新增 `list_incomplete(required_fields: list[str]) -> list[tuple[Path, list[str]]]`
- 遍历 `summary_json` 非空的 done 记录，检查每个字段是否有有效值（runtime="0" 视为无效）
- 返回 `(file_path, missing_fields)` 列表
- UI 工具页新增「字段缺失影片」面板，展示列表 + 批量重新入队刮削
- 复用 `FailureReason` 枚举区分「来源没有」和「未抓到」

**成本**：1-2 天
**参考**：OpenAver `core/nfo_updater.py:needs_update()` — 检查 title/date/actor/genre/maker/director/duration 缺失


