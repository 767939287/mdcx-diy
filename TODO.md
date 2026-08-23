# TODO

状态标签：⬜ 未实现 / 🔶 部分实现（已有基础，见括号说明）/ ✅ 已实现

价值·难度标签：**价值**（解决痛点大小）· **难度**（工作量：低<1天 / 中1-5天 / 高>1周）

按价值排序：P1 优先实现 → P2 核心能力 → P3 按需/低频

## P1 优先实现（解决日常痛点，见效快）

### 1. 刮削缓存三项增强 ⬜（`core/scrape_cache.py`）
- **价值：高**　**难度：中**（3-5 天）
- A. **404 负面缓存**：`ScrapeState` 加 `failure_reason`，`NOT_FOUND` 缓存 7 天期内跳过，其他失败仍走重试
- B. **缓存 key 版本化**：表加 `schema_version` 列，解析逻辑修复后递增版本号让旧 done 自动失效
- C. **字段缺失检测**：`list_incomplete(required_fields)` 找"done 但关键字段为空"的片批量重刮（runtime="0" 视为无效）

价值：站点改版期刮到全空片能补刮；404 片不白等重试；解析修复后缓存不失效。

---

### 2. 视频元数据状态机 + 关键帧截图 ⬜
- **价值：中**　**难度：高**（5-7 天）
- 元数据版本号 + 文件指纹（size+mtime）变更检测，schema 升级自动重扫
- 失败按错误码分级 + `next_retry_time` 退避，避免反复重试同一批失败文件
- 关键帧截图：全站无图时 ffmpeg 截帧选最有意义帧作 poster（国产/素人常用）；配置 `video_screenshot_enabled` 默认关，依赖系统 ffmpeg（非 Python 包）

价值：国产/素人片无封面时自动补海报墙。

---

### 3. 演员别名 + 标签声明式配置 ⬜
- **价值：高**　**难度：中**（2-3 天）
- 配置文件写一行 `河北彩花 = 河北彩伽,河北彩花（河北彩伽）`，新刮削自动把别名替换为规范名
- 标签树形映射 + 父级补全 + 冲突检测；Actor Split 正则拆分 `"演员A (别名B)"`
- 写 NFO 前：规范名进 `<actor>`，原始写法保留到 `<actor><aliases>`
- 重名冲突软合并；已有影片不自动重命名；与 #15 联动（别名作 GFriends 候选名来源）

价值：同一人（河北彩伽/河北彩花）分两个演员、带括弧后缀需手动清的问题，写一行配置即统一。

---

## P2 核心能力升级（提升质量与体验，成本适中）

### 4. 字段级多源合并 ⬜
- **价值：中**　**难度：高**（1-2 周）
- 主站点为基准，缺失字段按配置优先级从备用站点补全；字段权重：标题/番号/封面 > 演员/标签 > 剧情/时长/日期
- 配置 `field_merge_enabled`（默认关）

价值：JavBus 有标题没简介、DMM 有简介但封面低清时自动拼出完整记录。

---

### 5. NFO 兼容性增强 🔶（已有 `nfo.py:get_external_id_tag_name` 基础）
- **价值：中**　**难度：中**（3-5 天）
- identifier resolver：`uniqueid[type]` → `<num>` + 无 type → `<{site}id>` 标签映射（→ Website 枚举）
- **可配置字段映射**：每字段多个候选 XML 路径按序取第一个非空
- 演员/标签别名匹配 + 自动创建开关

价值：从 MetaTube/Jellyfin 等换工具已有 NFO 能读进来。

---

### 6. AI 打标签 ⬜（需用户自备 LLM API Key）
- **价值：中**　**难度：高**（3-5 天）
- 路径①：LLM 从标题+简介提取 ≤5 个标签（`AI-` 前缀），走 `USER_LLM_*` 环境变量
- 路径②：多模态从既有标签池选（`json_schema` strict 输出 + 二次校验），只选不造
- 增量重扫（标签池 hash + 资源 hash 变化才重分析）；写入策略 append/replace/only_empty
- 配套标签模型升级（`AIEnabled`/`AIDescription`/`Sort`/`Hot`）

价值：上千部片按剧情/熟女/户外分类自动完成。

---

### 7. NFO 库管理增强 🔶（基础页已上线 v2.0.6+，见 changelog）
- **价值：中**　**难度：中**（约 2.5 天）
- 基础版已有：三栏布局、字段编辑、封面预览、字段级 diff 预览、批量操作、右键菜单（重新刮削/打开目录/删除 NFO）
- 待做：**海报墙缩略图视图**（`QListWidget.setIconMode()` + 可视范围懒加载同目录 `poster.jpg`）/ **仅可播放过滤**（无视频文件的孤儿 NFO）/ **组合筛选**（演员+年份+标签）

不做：SQLite 全量建库、收藏夹/最近看过。

---

### 8. 配置化刮削器引擎 + 调试器 CLI ⬜
- **价值：中**　**难度：高**（1-2 周）
- 声明式配置（JSON/CSS 选择器）：`file_patterns` 番号正则 + `search` + `sites[]`（url 模板 + selectors + post_processors）
- 后处理管道：regexp/split/absolute_url/filename；`fallback_attributes` 备用属性链（src → data-src）
- 多站点失败策略：priority 依次尝试 + 重试退避
- 调试器 CLI：指定站点+番号跑一遍打印字段/图片/日志，无需反复启动 GUI

价值：站点改版后用户写 10 行 JSON 选择器自救。

---

## P3 按需/低频（小改进随时插队，或定位弱相关可不做）

### 9. JavDB App API 端点扩展 ⬜
- **价值：低**　**难度：中**（2-3 天）
- 优先集成磁力列表 `GET /api/v1/movies/{id}/magnets`，排序 `cnsub > hd > size > files_count`
- 配置 `javdb_app_fetch_magnets`（默认关）；复用现有签名/设备参数

价值：刮完直接看到磁力链接。与刮削定位略偏。

---

### 10. JavInfoApi 作为可选元数据源 ⬜（需自托管）
- **价值：低**　**难度：中**（3-5 天）
- 新增爬虫 `javinfoapi.py`，番号查询 + 批量 lookup（一次 100 个）+ 演员模糊匹配
- Emby 演员管理器数据源优先级新增 `javinfoapi`；API 不可用时 fallback 其他站点

价值：老玩家自建 JavInfoApi 后本地秒查。受众窄。

---

### 11. 维护预览 + 字段级 diff ⬜（注意：NFO 库管理的字段级 diff 是单文件编辑场景，非本项的全局维护预览）
- **价值：中**　**难度：高**（1-2 周）
- dry-run 预览模式：先算变更展示 diff，确认后执行
- 预设模式：`read_local` / `refresh_data` / `organize_files`；与 #12 联动

价值：批量整理前先看到"哪些会被重命名/改写"再执行。

---

### 12. 操作历史与批量回滚 ⬜
- **价值：中**　**难度：高**（1-2 周）
- 新增 `core/history.py` SQLite 记录 `file_move`/`file_rename`/`nfo_write`/`image_download`/`image_overwrite`
- 批量操作 batch_id 关联，回滚逆向操作；与 #11 联动

价值：批量整理搞乱目录结构一键回滚。

---

### 13. missav 爬虫指纹降级策略 ✅（已实现）
- **价值：低**　**难度：低**（0.5 天）
- 实现：默认指纹池新增 `safari17_2_ios`；`web_async.py` 检测到 CF 挑战页（403/503 + challenge 标记）时强制轮换连接池指纹重试。实测 missav.ai 桌面 Chrome 403 → Safari 手机指纹 200

---

### 14. MOVIE_NUMBER_PATTERNS 专用规则补全 🔶（9 前缀已完成）
- **价值：低**　**难度：低**（1 天）
- ✅ 已完成：`9` 前缀规则（`9ssis01` → `SSIS-001`，编号补零到 3 位，配 7 个测试用例）
- ⬜ 待做：其余（LAF/MISM/MKBD/CWPBD/SM/MCDV）通用规则可兜底，仅在匹配不理想时补充

---

### 15. GFriends 候选名列表匹配 🔶（单名函数 `gfriends_find_actor(gfriends_index, name)` 已存在）
- **价值：中**　**难度：低**（1-2 天）
- 待做：接口改为接受 `names: list[str]` 依次 NFKC 归一化匹配，首个命中即返回；`ActorInfo` 加 `aliases: list[str]`（来源：JavDB / keyword 列 / #3 声明式别名）

---

### 16. 深度链接（`mdcx://` 自定义协议）⬜
- **价值：低**　**难度：中**（1-2 天）
- 协议：`mdcx://scrape?code=ABC-123`、`mdcx://import?path=...`
- 注册：Windows 注册表 / macOS Info.plist / Linux .desktop；已运行时 IPC 传递 URL

价值：TG 群发链接点击直接唤起 mdcx 开刮。

---

### 17. per-scraper 代理配置继承 ⬜
- **价值：中**　**难度：中**（2-3 天）
- `ProxyProfile` 多 profile；`SiteConfig.proxy`: None=继承全局 / `"direct"`=不用 / 其他=指定 profile
- UI：设置 → 代理管理

价值：JavDB 要日本节点、DMM 要别的代理，每站独立配。

---

### 18. 刮削结果自动备份 ⬜（低优先级）
- **价值：低**　**难度：中**（1-2 天）
- 定时 + 变更计数双触发，队列化防重入；拷贝限速；zip 保留最近 N 份

价值：误删 NFO/磁盘故障能找回。与刮削定位弱相关。

---

### 19. 视频指纹去重 ⬜（低优先级）
- **价值：低**　**难度：高**（3-5 天）
- 10 固定位置抽帧 + 64 位 pHash，时长分桶剪枝 + 汉明距离阈值，传递闭包聚类

价值：同一资源的不同压制/改名副本找出来合并。定位偏媒体库，可不做。

---

### 20. amazon 搜索 URL 双重 quote_plus ✅（已实测确认正确，无需改动）
- **价值：低**　**难度：低**（验证类）
- 已实测：`core/amazon.py:1032` 的双重 `quote_plus` 是正确且必要的——Amazon 对 returnUrl 解一层得到内层 `/s?k=`，跳转时 k 值再解一层；单次编码会导致跳转失败直接去首页。当前代码不改。
