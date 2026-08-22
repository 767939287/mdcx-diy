# TODO

## 待办（按价值排序：P1 优先实现 → P2 核心能力 → P3 按需/低频）

## P1 优先实现（解决日常痛点，见效快）

### 1. 刮削缓存三项增强（合并条目）

三项均改 `core/scrape_cache.py`，一起做可共用测试基建。

#### A. 404 负面缓存（JavBoss 借鉴）

404 是确定性失败，重试无意义。缓存负面状态设 TTL（7 天），期内跳过。

- `ScrapeState` 新增 `failure_reason`（复用 `FailureReason` 枚举），`set_failed` 写入
- `should_skip`：`failed` + `NOT_FOUND` + 未过 TTL → 跳过；其他失败仍走 `MAX_RETRY_COUNT`
- UI「刮削缓存管理」显示负面缓存数量；读取模式不受影响

#### B. 缓存 key 版本化（JavBoss 借鉴）

crawler 解析逻辑修复后，旧 done 记录自动失效，无需手动清缓存。

- 新增 `SCRAPE_CACHE_SCHEMA_VERSION = "v2"` 常量；表加 `schema_version` 列（ALTER TABLE 迁移）
- `set_done` 写版本号，`set_failed` 不写；`should_skip` 版本不匹配 → 返回 False
- 后续改解析逻辑只需递增版本号

#### C. 字段缺失检测（OpenAver 借鉴）

检测 done 但关键字段为空的影片，批量重刮。站点改版期间刮到的影片可能批量缺字段。

- 新增 `list_incomplete(required_fields)`：遍历 done 记录检查字段有效性（runtime="0" 视为无效）
- UI 工具页「字段缺失影片」面板：列表 + 批量重新入队

**价值场景**：站点改版期刮到"完成但全空"的片，现在无法知道也无法补刮；404 片反复白等重试；爬虫解析修复后旧缓存不失效。
**成本**：合计 3-5 天
**参考**：JavBoss `internal/jav/cache.go`；OpenAver `needs_update()`

---

### 2. 视频元数据状态机 + 关键帧截图（CM Collectors 借鉴）

**目标**：ffprobe 元数据采集工程化（版本号+文件指纹变更检测+失败退避+空闲回填）+ 全站无封面时关键帧截图兜底。

**实现要点**：
- 元数据版本号 + 文件指纹（size+mtime）变更检测：文件变了才重探，schema 升级自动重扫
- 失败按错误码分级（文件缺失/解码失败/无效元数据）+ `next_retry_time` 退避，避免反复重试同一批失败文件；`stale` 状态服务中断后恢复
- 优先级队列 + 空闲回填：距上次交互超阈值才启动低优先级批量补齐，不抢用户资源；可恢复批量任务（scope selected/all + run mode missing/failed/failed_force）
- 关键帧截图：所有站点未返回图时（国产/素人常见）ffmpeg 截帧，多帧抽取后挑选"最有意义帧"（level 参数质量筛选）作 poster，其余作 extrafanart 候选；依赖系统 ffmpeg（检测可用性，非 Python 包）
- 配置：`video_screenshot_enabled`（默认关）、ffmpeg path、并发 worker 数、大文件（>10GB）跳过；截图后走相同加水印/命名/移动流程

**价值场景**：国产/素人片搜不到封面永远灰图，关键帧截图自动补海报墙；ffprobe 失败片反复拖累整个刮削队列。
**成本**：5-7 天
**参考**：cm_collectors_3 `videoMetadata.processors.go` + `keyframe.processorsFFmpeg.go`；JavBoss `screenshot_manager.go`

---

### 3. 演员别名 + 标签声明式配置

**目标**：配置文件写一行即可统一演员名和标签，新刮削自动将别名替换为规范名。标签支持树形映射 + 父级补全。

**实现要点**：
- 配置格式（config.ini `[actor_aliases]` 或独立 JSON）：`河北彩花 = 河北彩伽,河北彩花（河北彩伽）`
- 写 NFO 前：别名 → 规范名进 `<actor>`，原始写法保留到 `<actor><aliases>` 用于头像/资料查询
- 标签树形映射（yamdc）：`{name, alias[], children[]}`，命中子标签自动补全父标签路径，冲突检测 + 去重排序
- Actor Split（yamdc）：正则从 `"演员A (别名B)"` 自动拆分
- 显示优先级（local-javlibrary）：规范名 > NFO 原始名；别名参与头像/资料匹配支持简繁体转换（复用 zhconv）
- 重名冲突软合并（local-javlibrary）：与其他演员规范名冲突时提示合并，统一影片与别名，不回写已有 NFO
- 已有影片不自动重命名；与 #15 联动：别名配置作为 GFriends 候选名来源

**价值场景**：同一个人（河北彩伽/河北彩花）在库里分成两个演员；演员名带括弧后缀每次手动清；写一行配置新刮削自动统一。
**成本**：2-3 天
**参考**：MDCz `personSync.actorAliases` TOML；yamdc `tag_mapper.go`；local-javlibrary 演员「显示名+曾用名+软合并」

---

## P2 核心能力升级（提升质量与体验，成本适中）

### 4. 字段级多源合并

**目标**：多站点结果按字段完整度评分取最优，缺失字段从备用站点补全，替代"首个成功即用"。

**实现要点**：
- 主站点结果为基准，缺失字段触发备用站点补全（按配置优先级），全字段完整则不补全
- 字段权重：标题/番号/封面 > 演员/标签 > 剧情/时长/日期
- 配置项 `field_merge_enabled`（默认关闭）

**价值场景**：JavBus 有标题没简介、DMM 有简介但封面低清，现在只能二选一，多源合并自动拼出完整记录。
**成本**：1-2 周
**参考**：JavInfoApi supplement 分层设计；yamdc Category Chain 搜索链

---

### 5. NFO 兼容性增强（外部标识解析 + 可配置字段映射）

**目标**：兼容异构 NFO 来源——表驱动解析番号/来源标识 + 可配置字段映射，替代硬编码。

**实现要点**：
- identifier resolver：标准 `uniqueid[type]` → `<num>` + 无 type → `<{site}id>` 标签映射（→ mdcx Website 枚举）；来源未知时 `website` 为空，仍可进入读取本地/资源发现/文件整理流程
- 字段映射可配置：每字段多个候选 XML 路径（title/issueNumber/date/score/abstract/tags/performerNames），按顺序取第一个非空
- 演员/标签支持别名匹配 + 自动创建开关（TagAutoCreate/PerformerAutoCreate）
- 不从文件名/目录名推断番号

**价值场景**：从 MetaTube/Jellyfin 等其他工具换到 mdcx，已有 NFO 读不进来只能全部重刮；兼容后直接进库。
**成本**：3-5 天
**参考**：MDCz `nfoSnapshot.ts`；mdcx `nfo.py:get_external_id_tag_name`；cm_collectors_3 `importData.processors.go`（Config_ScanDisk_Nfo）

---

### 6. AI 打标签（yamdc + CM Collectors 借鉴）

**目标**：用 AI 给影片打标签，两条路径互补——① 标题+简介文本提取（AI- 前缀）；② 多模态封闭标签池选择（只从既有标签选，不创建新标签）。配套标签模型升级。

**实现要点**：
- 提取路径：LLM 从标题+简介提取最多 5 个标签，`AI-` 前缀加入 Genres；LLM 走 `USER_LLM_*` 环境变量
- 池选路径：标签池=info_database 标签库；prompt 携带标签池（按分类分组，带语义说明）强约束只选 tagId；`json_schema` strict 输出 `{tags:[{tagId,confidence,reason}]}`，服务不支持回退 text 解析；结果侧二次校验过滤非法 ID
- 多帧截图分批送多模态模型（三重上限），跨批聚合评分 `max*0.5 + avg*0.3 + 批次数占比*0.2`，单批误判不主导
- 增量重扫：标签池版本 hash + 资源集合 hash 记录，变了才重分析，省 token
- 写入策略：append（保留人工标签）/ replace / only_empty
- 标签模型升级打底：标签加 `AIEnabled`/`AIDescription`/`Sort`/`Hot`/批量计数，与标签池打通

**价值场景**：上千部片按剧情/熟女/户外分类，手动打完要几天；AI 自动从封面和简介选标签且只从既有标签池选，不会乱造标签。局限：需用户自备 LLM API Key。
**成本**：3-5 天
**参考**：yamdc `tag_mapper.go`；cm_collectors_3 `processors/aiTag.processors.go` + `processorsAI/tagPrompt.go`

---

### 7. NFO 库管理增强（local-javlibrary 借鉴）

**目标**：给 NFO 库管理页（已完成，见 changelog v2.0.6+）补上海报墙浏览体验和更强的筛选能力。

**实现要点**：
- **缩略图视图（海报墙）**：「文字/缩略图」切换，`QListWidget.setIconMode()` + 异步加载同目录 `poster.jpg` 缩略图（复用 `PreviewImageLoader` 异步模式；切到缩略图模式才按可视范围懒加载）
- **仅显示可播放**：复选框过滤无视频文件的孤儿 NFO（扫描时顺便探测标记 `Qt.UserRole+2`）
- **多条件组合筛选**：单文本框扩展为 演员 + 年份范围 + 标签 组合筛选，保留关键词框作快速入口

**不做**：SQLite 全量建库（万级以下 rglob 够用）、收藏夹/最近看过（需播放数据，稀释刮削工具定位）

**价值场景**：NFO 库管理页现在是纯文字列表认不出片子，海报墙像 Emby 一样直观；孤儿 NFO 一键筛掉。
**成本**：缩略图 1 天 + 可播放过滤 0.5 天 + 组合筛选 1 天
**参考**：local-javlibrary 视图切换/分类筛选

---

### 8. 配置化刮削器引擎 + 刮削调试器 CLI（CM Collectors 借鉴）

**目标**：JSON/CSS 选择器配置的刮削器作为 Python 爬虫之外的新类型，降低自配站点成本；配套无 UI 调试沙盒加速站点适配开发。

**实现要点**：
- 声明式配置：`file_patterns` 番号正则 + `search`（搜索页→详情页链接重定向）+ `sites[]`（url 模板 + priority 排序 + selectors 字段→CSS 映射 + post_processors）
- 后处理管道：regexp（捕获组）/ split / absolute_url（相对转绝对）/ filename；`fallback_attributes` 备用属性链（懒加载图先试 src 再 data-src）
- 元数据有效性判定：配置中定义了 selector 的字段至少一个非空，防错误页/空页当成功
- 多站点失败策略：按 priority 依次尝试 + 重试递增退避，全部失败才换下一配置
- 图片防盗链思路：在页面上下文加载图片取 base64（天然带 cookie/referer），封面被防盗链时可参考
- 调试器 CLI：指定站点+番号跑一遍，打印字段/图片/日志，可保存 NFO；单文件与批量、并发控制、无头浏览器开关（类似 `mdcx/cmd/crawl.py` 但面向调试）

**价值场景**：站点改版后无人维护时，用户自己写 10 行 JSON 选择器适配即可自救，不等作者发新版本；调试器命令行立即看字段命中情况，不用反复启动 GUI。
**成本**：1-2 周
**参考**：cm_collectors_3 `scraper/*.json` + `api/cm_scraper/` + `cm_collectors_scraper_debugger/`

---

## P3 按需/低频（小改进随时插队，或定位弱相关可不做）

### 9. JavDB App API 端点扩展

**目标**：用 javapi 逆向的 37 个端点文档扩展 javdb_app 爬虫（现仅用 3 个）。

**实现要点**：
- 优先集成磁力列表：`GET /api/v1/movies/{id}/magnets`（cnsub/hd/files_count），排序参考 javdb-cli：`cnsub > hd > size > files_count`
- 所有端点共享现有签名 + 设备参数，复用 `_request_api`
- 配置项 `javdb_app_fetch_magnets`（默认关闭）
- 导演/厂牌/系列详情端点价值低暂不做；`MovieDetail` 用 `extra="ignore"` 丢弃了 id 字段，需要时去掉

**价值场景**：刮完想在结果里直接看到磁力链接，不用去 JavDB 网页手搜。与刮削定位略偏，实现便宜。
**成本**：2-3 天
**参考**：https://github.com/ANDonekey/javapi；https://github.com/FlanChanXwO/javdb-cli

---

### 10. JavInfoApi 作为可选元数据源 + Emby 数据源扩展

**目标**：支持自托管 JavInfoApi（r18.dev 数据库转储：185 万视频/10 万演员）作为结构化 API 源，替代在线 API 逐个请求。

**实现要点**：
- 新增爬虫 `mdcx/crawlers/javinfoapi.py`，继承 `BaseCrawler`
- 配置：`api_url`（默认 `http://localhost:18080`）、可选 `admin_token`
- 接口：番号查询 `GET /api/v1/videos/search?dvd_id=`、批量 `POST /api/v1/videos/lookup`（一次 100 个）、演员模糊匹配 `GET /api/v1/actresses?q=`
- Emby 扩展：演员管理器数据源优先级新增 `javinfoapi`，头像走 `image_url` 下载缓存
- API 不可用时 fallback 其他站点

**价值场景**：老玩家自建 JavInfoApi 服务后，刮削优先从本地 API 秒查而非逐个在线请求。受众窄（需自托管），效率高。
**成本**：3-5 天
**参考**：https://github.com/cdlongbow/JavInfoApi — API.md

---

### 11. 维护预览 + 字段级 diff

**目标**：刮削/整理/刷新执行前预览每条变更的字段级 diff，逐字段选择保留新旧值后确认执行。

**实现要点**：
- dry-run 预览模式：先算变更展示 diff，确认后执行
- Qt 表格/树形展示，支持批量选择
- 预设模式：`read_local` / `refresh_data` / `organize_files`
- 与 `scrape_cache.py` 集成 + #12 操作历史联动

**价值场景**：批量整理 200 部片子前先看到"哪些会被重命名、哪些 NFO 会被改写"，确认无误再执行，防误操作。安全感功能，见效慢但长期体验价值高。
**成本**：1-2 周
**参考**：MDCz `maintenancePreviewItem` DTO

---

### 12. 操作历史与批量回滚

**目标**：记录每次操作的文件变更，支持按批次回滚。

**实现要点**：
- 新增 `core/history.py`，SQLite 记录操作日志（复用现有基础设施）
- 操作类型：`file_move`/`file_rename`/`nfo_write`/`image_download`/`image_overwrite`
- 批量操作生成 batch_id 关联；回滚逆向移动/重命名，NFO/图片写入前备份恢复
- 工具栏「历史记录」按钮：批次列表 + 回滚；与 #11 维护预览联动
- 吸收 NFO 库管理的操作历史需求

**价值场景**：昨晚批量整理把目录结构搞乱了，一键回滚恢复原样。建议与 #11 搭配做。
**成本**：1-2 周
**参考**：javinizer-go `internal/history/`

---

### 13. missav 爬虫指纹降级策略

**目标**：域名轮询全失败时，尝试 `curl_cffi` 的 `safari17_2_ios` 指纹作为绕过 CF 的最后手段。

**实现要点**：
- 默认指纹池加入 `safari17_2_ios`，或 missav 重写 session 创建指定指纹
- 仅在默认指纹被 CF 拦截（403/503 + challenge markers）时降级

**价值场景**：missav 被 CF 拦时换手机浏览器指纹再试一次，命中即恢复刮削。
**成本**：半天
**参考**：unofficial-api-for-missav；curl_cffi impersonate 文档

---

### 14. MOVIE_NUMBER_PATTERNS 专用规则补全（低优先级）

**目标**：补全 sakuramediabe 番号规则中 mdcx 缺失的部分。

**实现要点**：
- 价值较高：`9` 前缀规则（如 `9ssis01`），当前完全无法识别
- 其余（LAF/MISM/MKBD/CWPBD/SM/MCDV）通用规则可兜底，仅在匹配不理想时补充
- 每条规则配测试用例验证不与现有规则冲突

**价值场景**：`9ssis01` 这类番号现在完全认不出来，补一条规则即可识别。
**成本**：1 天
**参考**：sakuramediabe `movie_numbers.py`

---

### 15. GFriends 候选名列表匹配

**目标**：`gfriends_find_actor` 接受候选名列表（规范名+别名+罗马音）依次匹配，提高头像命中率。

**实现要点**：
- 接口改为接受 `names: list[str]`，依次 NFKC 归一化匹配，首个命中即返回
- `ActorInfo` 增加 `aliases: list[str]`，来源：JavDB / 本地演员库 keyword 列 / #3 声明式别名

**价值场景**：库里存的是中文别名、头像库只有罗马音，传候选名列表多试几次提高命中。
**成本**：1-2 天
**参考**：sakuramediabe `GfriendsAvatarJavdbProvider`

---

### 16. 深度链接（`mdcx://` 自定义协议）

**目标**：从浏览器点击链接直接唤起 mdcx，跳转到番号刮削页。

**实现要点**：
- 协议格式：`mdcx://scrape?code=ABC-123`（刮削）、`mdcx://import?path=...`（导入，可选）
- 注册：Windows 注册表 `HKCU\Software\Classes\mdcx`、macOS Info.plist、Linux .desktop MimeType
- `main.py` 解析 URL 参数跳转页面；已运行时通过 IPC（socket/命名管道）传递 URL

**价值场景**：TG 群里有人发 `mdcx://scrape?code=ABC-123`，点击直接唤起 mdcx 开刮。
**成本**：1-2 天
**参考**：javm `javm://download?url=...&title=...`

---

### 17. per-scraper 代理配置继承

**目标**：每个爬虫可独立配代理：继承全局 / 直连 / 指定 profile 三态。

**实现要点**：
- `ProxyProfile` dataclass（url/username/password）多 profile
- `SiteConfig.proxy`: None=继承全局，`"direct"`=不用，其他=指定 profile
- UI：设置 → 代理管理，profile 列表 + 每爬虫选择

**价值场景**：JavDB 要日本节点、DMM 要别的代理，现在只能全局一个代理，此功能每站独立配。
**成本**：2-3 天
**参考**：javinizer-go `ResolveScraperProxy` 三模式解析

---

### 18. 刮削结果自动备份（CM Collectors 借鉴，低优先级）

**目标**：NFO/图片/配置变更后自动备份，防误操作或磁盘故障丢失刮削成果。

**实现要点**：
- 双触发：定时（IntervalHours）+ 变更计数累计超阈值触发，队列化防重入
- 拷贝限速（每批 10ms 停顿）防止备份占满 I/O 影响刮削/播放
- zip 备份保留最近 N 份，运行 TTL 30 分钟

**价值场景**：误删 NFO 或磁盘故障时能找回刮削成果。与刮削定位弱相关，低优先。
**成本**：1-2 天
**参考**：cm_collectors_3 `processors/autoBackup.processors.go`

---

### 19. 视频指纹去重（CM Collectors 借鉴，低优先级）

**目标**：检测同一部作品的不同压制/改名副本，刮削前查重避免重复入库。

**实现要点**：
- 10 个固定位置（5%..95%）抽帧 + 64 位 pHash
- 时长分桶剪枝 O(n²) + 匹配模式分级（minimal/loose/high/全十帧）+ 汉明距离阈值
- 传递闭包式聚类成组，返回组平均相似度
- mdcx 定位刮削工具，价值有限，仅在需要"刮削前查重"时实施

**价值场景**：库里 10 部片其实是同一资源的不同压制版（改过名），指纹查重找出来合并。定位偏媒体库，mdcx 是刮削工具，可不做。
**成本**：3-5 天
**参考**：cm_collectors_3 `processors/videoFingerprint.processors.go`

---

### 20. amazon 搜索 URL 双重 quote_plus 待真实请求验证

**背景**：`core/amazon.py:1032` 的 `search_amazon` 对标题做了双重 `quote_plus`（`quote_plus(quote_plus(title.replace("&", " ")))`）拼进 `returnUrl=/s?k=`。

**待确认**：Amazon 是否会对 `returnUrl` 参数二次解码，导致当前双重编码反而是正确的；还是只需单次编码即可。

**验证方式**：用真实请求对比单次/双重编码下的搜索结果命中率；或直接查 returnUrl 参数解码行为。
**标记**：需真实请求验证，暂缓处理，非阻塞。
