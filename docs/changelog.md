# Changelog

## 未发布

### 功能

- **missav 爬虫 3 域名轮询**：missav 支持 `missav.ai`/`missav.ws`/`missav.live` 三域名自动轮询，请求失败时自动切换镜像重试（404 不轮询直接返回）；missav.ai 排第一（当前网络环境最稳定）。默认代理站点列表加入 `missav.live`。`missav_api` 不需要轮询（走 Recombee API + fourhoi 图床，无 CF 无镜像）
- **NFO 库管理页面（左侧导航新页）**：借鉴 NFO.Editor 的目录浏览+批量编辑理念，在左侧导航树新增「NFO库管理」按钮（工具与设置之间），`stackedWidget` 新增 `page_nfo_library`（index 6）。三栏布局：左栏 `QListWidget` 列出选定目录下所有 `.nfo` 文件（支持多选+筛选），中栏 `QFormLayout` 字段编辑表单（番号/标题/演员/发行日/年份/时长/导演/制作商/发行商/系列/评分/简介/标签/封面URL/海报URL 共 15 字段），右栏封面预览（poster 200×280 + thumb 200×120）+ 裁剪按钮。目录扫描递归 `rglob`，列表项存 NFO 路径于 `UserRole+1`。单条读取复用 `core/nfo.py:get_nfo_data`，保存复用 `write_nfo(update=True)`，均走 `executor.submit` 后台执行 + `pyqtSignal` 回主线程更新 UI（避免重蹈 `save_nfo_info` 的 `executor.run` 主线程阻塞）。封面预览从 NFO 同目录加载本地图片（`{番号}-poster.jpg`/`poster.jpg`/`{番号}-thumb.jpg`/`thumb.jpg`），不走网络。裁剪封面复用 `cut_window`。批量操作：左栏列表下方 `QGroupBox` 含替换演员名/加标签/删标签/统一系列名 4 个操作 + 批量保存按钮，每项配输入框，选中多条后一键执行，后台逐条读取-修改-写回，状态实时显示。**字段级 diff 预览**：加载 NFO 时深拷贝原始数据作为基准，点保存时对比表单与基准的 15 个字段，无改动提示后返回，有改动弹窗显示「字段名 + 旧值 → 新值」，确认后才写盘。**列表右键菜单**：重新刮削（找同目录同名视频加入 `Flags.again_dic` 队列，单个选中可修改番号）/ 打开所在目录（`open_file_thread` 定位到文件）/ 删除 NFO（Warning 确认框 → `delete_file_sync` → 从列表移除并更新计数）。新增 `controllers/main_window/nfo_library.py`（controller），`main_window.py` 加 `nfo_lib_data_loaded`/`nfo_lib_save_done`/`nfo_lib_batch_done` 三个信号 + 16 个包装方法，`init.py` 接线 11 个按钮信号 + 3 个信号槽连接
- **字段 skip 哨兵（字段级跳过抓取）**：新增 `FieldConfig.skip`/`FieldPriorityConfig.skip` 字段，勾选后该字段不从任何来源抓取。`file_crawler.py` 预收集阶段和字段处理阶段两处检查 skip 标志，命中则跳过抓取并记录日志。字段优先级对话框（`FieldPriorityDialog`）每个字段行新增「跳过」复选框，勾选后禁用对应网站列表；全部重置/清空时同步清除 skip 状态。`set_field_skip()` 方法设置后清空并重建 `type_field_configs` 确保 skip 立即传播到 type 级配置
- **NFO 合并策略（5 种 MergeStrategy）**：新增 `NfoMergeStrategy` 枚举（`prefer_scraper`/`prefer_nfo`/`merge_arrays`/`keep_existing`/`fill_empty`），`write_nfo()` 写入前按策略读取现有 NFO 并合并。`core/nfo_merger.py` 合并引擎区分标量字段（17 个）和数组字段（5 个），关键字段（number/title）双重保护，合并结果带溯源标记。UI 在主界面「读取模式」区域（「允许更新 nfo 文件」复选框下方）新增「NFO合并策略」下拉框，5 项按枚举顺序排列，`load_config`/`save_config` 双向同步
- **DMM 官方图源兜底**（借鉴 AVACA 图源直构思想）：站点图源全部失败时，按番号直构 DMM 官方 CDN（awsimgsrc）高清封面兜底，自动学习厂牌前缀。`crawlers/dmm_direct.py` 新增 `find_valid_dmm_cover`（复用 `check_url` GET 验证 + `_is_dmm_hd_image` 分辨率过滤），`core/web.py` 的 `thumb_download` 失败分支插入兜底，成功后 fanart/poster 走既有复制/裁剪链路。新增 `dmm_prefix_learn.py` 前缀学习表：从刮削过程观察到的真实 DMM URL（`upgrade_dmm_cover` 命中 + dmm 爬虫验证过的图）提取 series→prefix 证据，状态机管理（≥2 个不同番号验证成功转正 verified、连续失败 ≥3 次隔离 quarantined、新证据解除隔离重走验证），持久化到 `userdata/dmm_prefix_learned.json`（原子写）。`generate_cid_candidates` 应用顺序：学习表 verified → 静态前缀表 → 学习表 provisional → 常见前缀盲试。新增配置项 `dmm_fallback_enabled`（默认开，设置页「下载高清图」组）与 `find_valid_dmm_cover` 测试、学习表 9 项测试
- **图片下载大小上限**：`AsyncWebClient.download` 新增 `max_bytes` 参数（Content-Length 预检 + 未知大小 content 事后校验双重防护），图片链路（`download_file_with_filepath`/`download_content_with_filepath`/`download_dmm_extrafanart_with_filepath`）统一传 50MB 上限，防异常大文件拖死磁盘；trailer 等大文件链路不传保持不限。新增 4 项 `download` max_bytes 测试

### 重构

- **dmm_api 爬虫底层替换为 DMM 官方 Affiliate API**：原 `dmm_api` 爬虫实际走 `api.thejavdb.net`（JavDB 第三方 API），名不副实。现将 `dmm_api` 底层实现替换为 DMM 官方 Affiliate API（`api.dmm.com/affiliate/v3/ItemList`），枚举值 `dmm_api` 不变，老用户配置零迁移、无感知。新爬虫直连 DMM 官方 API（无需日本节点），单请求获取完整元数据（标题/演员/厂牌/标签/系列/导演/日期/时长/评分/封面/剧照），并从 HTML5 player 页面提取预告片直链（复用 DmmCrawler 预告片质量分级系统，自动选最优画质）。NetworkConfig 新增 `dmm_api_id`/`dmm_affiliate_id` 配置项，留空使用内置默认值开箱即用，正式使用建议自行注册获取
- **新增 thejavdb_api 爬虫**：保留原有 thejavdb.net API 数据源为独立爬虫 `thejavdb_api`（`crawlers/thejavdb_api.py`），枚举值 `thejavdb_api`，默认未启用，需手动添加到网站列表。修复原 `dmm_api` 未设置 `ctx.number_00`/`ctx.number_no_00` 导致 DMM 高清封面升级（AWS CDN `pl.jpg`）部分失效的问题
- **爬虫文件去 `_new` 后缀**：`dmm_new` → `dmm`、`javdb_new` → `javdb`、`avbase_new` → `avbase`，消除"有旧版"的误导。纯文件重命名 + import 路径更新，无功能变更
- **JavDB App 爬虫类名统一**：`javdb_app.py` 的 `JavdbAPICrawler` → `JavdbAppCrawler`，与文件名一致且避免与 `javdb_api.py` 的 `JavdbApiCrawler` 同名冲突
- **love6.py 死代码清理**：删除未调用的 `get_extrafanart` 函数（从 lulubar.py 复制粘贴遗留，拼接了错误的 `lulubar.net` 域名）
- **JavDB App 签名简化 + 设备参数补全**：`javdb_app.py` 签名算法从运行时 base64 解密（`_decrypt` + `_ENCRYPTED_PART1/2` + `_SECRET`）改为直接硬编码已验证的 prefix/suffix 常量（与 javdb-cli 项目交叉验证值一致），消除 `base64`/`json` 模块依赖；`_build_api_params` 补全 `system_version`/`device_model`/`device_name`/`device_uuid` 四个设备标识参数（与真实 JavDB App 请求一致），降低被风控的概率
- **移植 sakuramediabe 4 项改进**：① `remove_disturb` 域名干扰预处理——番号清洗时去除附带域名（如 `ABC-123.example.com` → `ABC-123`），去除后为空则保留原值防止整个文件名被吃掉；② jsdelivr CDN 加速——`Content`/`Filetree` 资源 URL 从 github.com 改为 jsdelivr CDN（版本检测保持 github.com）；③ NFKC 归一化匹配——演员名等匹配时先做 NFKC 归一化消除全半角差异（不预构建索引）；④ stale cache 降级——缓存过期时不直接报错而是降级使用旧数据（不替换版本检测逻辑）
- **Emby 演员管理器入口移到左侧导航**：工具页顶部的 90px「Emby 演员管理」入口 groupBox 删除（下方 8 个 groupBox 连锁上移 90px，滚动区高度同步收缩），改为左侧导航树新增「Emby演员管理」按钮（工具按钮下方，点击弹出原独立对话框，行为不变）。同步清理 init.py 旧按钮 clicked/setText 连接与 main_window.py 失联信号定义，文档更新为「左侧导航 Emby演员管理」

### 修复

- **Emby 同步失败不再标记为已同步**：`emby_actor_manager_ui.py` 的 `_on_sync_finished` 原本无差别清掉全部 `need_update_*` 标记并刷新状态，失败演员也被标成已同步。现改为在 `_on_sync_actor_done`（per-actor 信号）里按演员名反查后仅对成功者调用 `_apply_sync_success` 清标记，失败演员保留待同步状态可在下次重试
- **Emby 过滤器补齐 backdrop**：`emby_actor_manager_ui.py` 下拉框新增「缺背景」过滤模式（缺 backdrop 但有头像的演员不再只在全部里可见）；「待同步」模式条件补上 `need_update_backdrop`，漏掉待同步背景图的演员现在会出现在过滤结果中
- **crawl CLI 测试消除 coroutine 警告**：`tests/test_crawl_cli.py` 的 `_FakeExecutor.submit` 接收 `task(c)` 协程后从不消费导致「coroutine never awaited」RuntimeWarning，fake 现对协程调用 `close()` 模拟真实 executor 的调度语义
- **Gfriends 同步改后台线程**：`tool_handlers.py` 的 `pushButton_sync_gfriends_clicked` 不再同步调用 `do_sync`（内部 `git pull` 最长 5 分钟）阻塞 UI 主线程，改为 `executor.submit` + `asyncio.to_thread` 后台执行，通过新增的 `_gfriends_signals.done`（pyqtSignal）回主线程恢复按钮、提示结果并刷新更新时间
- **Emby 演员名双击反查**：`emby_actor_manager_ui.py` 的 `_on_table_double_clicked` 改用 `table.item(row, 1).text()` 取演员名后到 `self._actors` 反查数据，不再用过滤后的视觉行索引 `filtered[row]`，修复列表经过筛选后双击错位/越界的问题
- **Emby 图片上传去掉 base64**：`emby_shared.py` 移除 `base64.b64encode(content)` 与 `import base64`，直接发送原始图片字节流，修复 Emby 收到的图片因二次编码损坏、无法识别的问题
- **minnano 缓存 key 统一为字符串**：`minnano_crawler.py` 缓存行从数字 `COL_*` key 改为字符串 key（新增 `CACHE_FIELD_KEYS` 常量），`save_cache_row` 新建/追加统一按番号去重更新，`load_cache` 加载前清空内存表，修复缓存读/写 key 错位导致的信息漏填（新爬取结果也受影响）
- **nfo criticrating 读取修复**：`core/nfo.py` 第二处评分 xpath 从重复的 `//rating/text()` 改为 `//criticrating/text()`，并加 `int/10` 转换与 ValueError 兜底，修复 criticrating 永远读不到、NFO 重写后评分丢失的问题
- **dmm 番号匹配修复前导零与连字符**：`dmm_api.py` 的 `_match_score` 归一化去除非字母数字后比较，编号段分别 `int` 比较（`ABC-012` 与 `ABC-12` 能匹配），并新增回归测试
- **javdb 两位数评分 + 镜像轮询修复**：`javdb_api.py`/`javdb.py` 评分正则 `\d{1}\.\d+` → `\d{1,2}\.\d+`（支持 10.0 等）；`javdb_api.py` 重写 `_try_mirrors` 显式遍历 `_MIRRORS` 且每轮设置 `self.base_url`，修复 `base_url` getter 缓存旧成功镜像导致失败镜像被永久锁定的问题
- **fc2 无修正判定修正**：`fc2.py` 在清洗「無修正」标签前保存原始 `tag`，正确判定无码（原逻辑标签清洗后永远判为有码）
- **prestige 爬虫字段缺失防护**：`prestige.py` 演员/媒体/标签/标题/简介/时长等字段改用 `.get` + 默认值，站点接口结构变化时不再抛 KeyError
- **dmm release 截断为日期 + 预告片质量正则兼容数字序号**：`dmm/__init__.py` 的 `startDeliveryAt`/`startPublicAt` 截取前 10 位为日期（去掉 `T20:00:00Z` 尾缀）；`_trailer_quality_rank` 第一正则序号段 `[a-z]` 放宽为 `[a-z]|\d{1,2}`，修复 `{cid}_hhb_1.mp4` 等带数字序号 URL 评不到质量等级的问题
- **javdb_app year 推导修复**：`javdb_app.py` 的 year 从 `release[:4]` 推导不再依赖 runtime 字段存在与否
- **fanart 下载失败不再静默忽略**：`core/scraper.py` `_download_images` 消费 `fanart_task.result()`，fanart 复制失败时返回失败
- **强杀线程加超时保护**：`utils/__init__.py` 的 `_async_raise` 去掉 `while res == 1` 自旋（改为单次注入 + res>1 回滚），`kill_a_thread` 改为限时循环（默认 10 秒）；`main_window.py` 的 `_kill_threads` 外层加 12 秒忙等上限，防止线程无法退出时主进程无限空转
- **dmm_prefix_learn 加载失败禁落盘**：`dmm_prefix_learn.py` 学习表加载失败（`_load_failed`）时 `_persist` 直接返回，防止空表 + 单条新记录覆盖历史学习结果
- **Emby 演员管理器 3 项 P0 修复**：① 连接参数生效——`_on_connect_result` 成功后把 UI 填写的地址/密钥写回全局配置（`manager._replace_config` + `save`），此前仅存于对话框实例导致后续取列表/同步实际使用旧配置；② 头像/背景改为直接覆盖上传——`sync_actor` 不再先 DELETE 再 POST（删除成功但上传失败会丢失旧头像），头像直接 POST 覆盖 `Images/Primary`，背景覆盖 `Images/Backdrop/0`；③ 缓存文件名清洗——新增 `_safe_filename` 替换演员名中的 Windows 非法字符（`\ / : * ? " < > |` 等），`from_gfriends`/`from_graphis`/`from_minnano_image` 三处缓存文件统一走安全名，避免含特殊字符演员名下载/读写失败
- **Emby 演员管理器 3 项 P1 优化**：① `sync_batch` 并发同步——原逐个串行同步（大列表极慢），现拆出 `_sync_actor_async` 协程 + `asyncio.Semaphore(SYNC_CONCURRENCY=4)` 并发批量执行，回调均在后台 loop 线程顺序触发（Qt 信号线程安全）；② 取列表带 fields 一次拿全——`get_emby_actor_list` Emby 分支补 `fields=Overview,Taglines,ProductionYear,PremiereDate,ProductionLocations,ProviderIds,Genres,Tags`，`fetch_all_actors` 第二遍检测列表项已含详情字段时直接复用，不再逐人 `fetch_actor_detail`（省 N 次 HTTP）；③ 失败演员重试——`_on_sync_actor_done` 失败时记录演员名，同步完成后自动刷新（3 秒）重建 ActorInfo 前把失败演员旧对象合并进刷新结果（保留 `need_update_*` 与本地新数据，仅更新服务器侧状态），失败项可再次点「开始全部更新同步」直接重试

- **读取模式不再受断点续刮缓存干扰**：断点续刮（ScrapeStateCache）的跳过逻辑与状态写入原本不区分刮削模式，读取模式（`main_mode==4`）下大量已刮削文件被 `should_skip` 过滤不可见，且读取一次后因标记 done 下次读不到。修复为读取模式跳过 `should_skip` 过滤全部文件入队，成功/失败路径不写 `set_done`/`set_failed`，始终处理全部选中文件
- **打包脚本补齐 v2.0.6 新增延迟导入模块**：`scripts/build.py` 的 hidden-import 列表补上 `mdcx.crawlers.dmm_prefix_learn`（DMM 厂牌前缀学习表，被 `dmm_direct.py`/`dmm/__init__.py` 函数内延迟导入）与 `mdcx.core.nfo_merger`（NFO 合并策略引擎，被 `nfo.py` 写入前函数内延迟导入）。这两模块 PyInstaller 静态分析收集不到，不显式打包会在 exe 运行期报 ModuleNotFoundError（与 `qt_thread` 同因）
- **文档与代码同步**：站点数量统一更新为实际注册数 48（README 徽章 Sites-47→48、FEATURES 标题「全部 47 个爬虫」、DEVELOPMENT、UI 帮助文档「当前 47 个」），FEATURES 补上遗漏的 thejavdb_api 爬虫行并标「仅能有码」；dmm_api 数据源描述从误写的「JavDB v1 API」改为「DMM 官方 Affiliate API」；免 CF 通道清单由 3 条补为 4 条（+thejavdb_api）；DMM 兜底描述统一补前缀学习机制（覆盖 USER_GUIDE/FEATURES/UI 帮助文档）；UI 帮助文档与 FEATURES 补 NFO 合并策略（5 种 MergeStrategy）、FEATURES 与 CONFIGURATION 补字段 skip 哨兵说明；CONFIGURATION 走代理网站默认白名单补 missav.live
- **演员数据库日文异体字简体化**：`actor_db_tool.py` 新增日文新字体/异体字→简体映射表（87 字，覆盖 亜→亚、桜→樱、沢→泽、恵→惠、瀬→濑 等），在 zhconv 繁简转换后额外应用；修复 `fill_zh_javdb` 和 TMDB 翻译模式中因 zhconv 不识别日文汉字导致中文名保留日文原字的问题。一次性修复脚本对现有 xlsx 修复 4569 条中文名 + 2561 条繁体名
- **演员数据库异常数据清理**：清理 2 条中文名/繁体名包含拉丁字母前缀的异常记录（`Aiko SUZUHARA - 鈴原愛子`、`Chihiro SHIRASAKI - 白崎千尋`）
- **copytree same-file 防护**：新增 `safe_copytree`/`safe_copytree_async`（`utils/file.py`），在 `shutil.copytree` 前检查 src==dst，命中则直接返回。修复用户把 `extrafanart_folder` 配成 `"extrafanart"` 时，外层 `rmtree(dst)` 先删源目录再 `copytree` 导致 extrafanart 剧照数据丢失的问题。`base/image.py`（`extrafanart_copy2`/`extrafanart_extras_copy`/批量补图）和 `base/video.py`（`add_del_extras`）4 处裸 `shutil.copytree` 已替换
- **程序退出改优雅退出**：`main_window.py` `exit_app` 不再 `os._exit(0)` 强杀进程（跳过 Python/atexit/Qt 资源清理，PyInstaller bootloader 也收不到正常退出信号），改为 `QApplication.quit()` 让 `app.exec()` 自然返回、主流程正常清理后退出（executor 后台线程为 daemon，不会挂起退出）
- **ComputedLease 释放改非阻塞**：`config/manager.py` `ComputedLease.__exit__` 不再主线程 `executor.run(computed.release())` 阻塞等待，改为 `executor.submit` 后台释放并消费结果（release 通常为 O(1) 计数递减，仅关闭请求时才清理连接池），保存配置等路径不再卡 UI
- **TMDB 演员库并发覆盖写防护**：`core/tmdb_actor.py` `fetch_actor_tmdb_ids` 的预加载 workbook → await 查询 → 落盘跨 await 点，多影片并发刮削时后落盘者覆盖先前写入行。新增模块级 `asyncio.Lock` 串行化整个读改写批次（独立路径 `update_actor_db_row` 原有 `_actor_db_write_lock` 已全程保护）
- **标记文件路径校验**：`config/manager.py` `__init__` 读取 MARK_FILE 内容后校验空值/空字节，无效时回退默认配置路径，防止标记文件被破坏时 `Path("")` 指向当前目录或 NUL 字节触发启动崩溃
- **软链接原身路径解析不再阻塞事件循环**：`core/file.py` 软链接分支的同步 `Path.resolve()` 改为 `asyncio.to_thread(os.path.realpath)`，避免网络路径解析卡住整个异步循环
- **女优信息库并发访问加锁**：`actress_db.py` 单例 SQLite 连接（`check_same_thread=False`）的 `init_db` 与查询用模块级 `threading.Lock` 串行化，消除多线程并发读写同一连接的隐患

### 工程质量

- 新增 `tests/crawlers/test_dmm_api.py` 回归测试（`test_content_id_leading_zeros_match` 前导零匹配、`test_product_id_with_hyphen_match` 连字符编号匹配）；`tests/test_minnano_lookup.py` 缓存 row 数据同步改为字符串 key；`tests/test_jellyfin_actor_api.py` 图片上传测试断言同步改为原始字节 body（`test_upload_actor_photo_uses_raw_image_body_for_emby`/`_jellyfin`，与 Emby/Jellyfin 图片上传 API 二进制 body 规范一致）；`tests/test_tool_handlers.py` Gfriends 同步测试适配后台化（offscreen QApplication + processEvents 轮询等待异步回调）

## v2.0.6 (2026-08-19)

### 修复

- **Bing 翻译引擎不可用修复**：`mdcx/base/translate.py` 将翻译页面与 API 端点从 `www.bing.com` 改为 `cn.bing.com`。`www.bing.com` 当前对爬虫式翻译接口返回 `HTTP 200` 但响应体为空（`Content-Length: 0`），疑似地区/风控限制；`cn.bing.com` 同样免 Key 免配置，参数提取逻辑（IG/key/token/path/IID）保持不变，实测中文、英文、日文互译全部正常

### 功能

- **JavDB 中文名补全**：演员数据管理工具新增「JavDB 中文名」按钮（`fill_zh_javdb` 模式），对 `actor_database.xlsx` 中「中文名为空」或「中文名 == 日文原名」的条目（约 15000 行未做中文化的含汉字姓名 + 11 行完全空名），通过 JavDB 移动端 API 查询演员详情的 `name_zht`/`name` 字段，拿到正式中文名后用 zhconv 转简体写入「中文名」列、繁体写入「繁体名」列；无需 TMDB API Key（按日文原名搜索），与原「补全中文名」（translate，走 TMDB 需 tmdbid）互补不冲突；`javdb_app.py` 新增 `fetch_javdb_actor_info` 函数返回完整 `{name, name_zht, other_name}`，原 `fetch_javdb_aliases` 改为调用该函数后拆分别名（消除重复代码）；支持「起始行/限量」分片续跑，连续失败降并发、连续成功恢复

- **JavLibrary Selenium CF bypass**：新增 `mdcx/cf_bypass/selenium_adapter.py`——当普通 HTTP 请求遇 Cloudflare JS challenge 时，自动 fallback 到 Selenium+Edge headless 获取页面 HTML，通过真实浏览器引擎绕过 CF 挑战；selenium 作为可选依赖首次使用自动安装，driver 由 Selenium Manager 4.6+ 自动匹配；新增 `cf_selenium_bypass` 配置开关（默认开启），无 Edge 环境优雅降级，连续失败 3 次进入 5 分钟冷却
- **JavLibrary DMM 高清封面升级**：javlibrary 爬虫新增 `post_process`，刮削成功后调用 `upgrade_dmm_cover` 将低清/水印封面升级为 DMM 高清版本（pl.jpg/ps.jpg），与 JavBus/JavDB 对齐
- **JavLibrary xpath 兼容 Selenium**：`javlibrary.py` 所有字段 xpath 从 `/table/tr/` 改为 `//`，兼容普通 HTTP（无 tbody）和 Selenium page_source（浏览器自动补全 tbody）两种 HTML 来源
- **IQQTV 域名轮询**：新增镜像 `https://iqqk4.quest`，IQQTV 爬虫接入 `_domains` + `_init_rotator` + `_get_text_with_rotate`，搜索和详情请求失败自动切换镜像域名重试；网络检测自动返回多地址
- **JavDB 演员别名补全**：演员数据管理工具「补全别名」新增 JavDB 数据源（与 TMDB、minnano 并列），通过 JavDB 移动端 API（`/api/v1/actors/{id}`）获取 `other_name` 字段拆分别名，无需 cookie 走签名 API；演员名匹配支持 NFKC 归一化 + zhconv 繁简转换 + 日文异体字统一（亜/亞 等），兼容搜索名与数据库名写法差异；纯假名短名（≤2字）不做子串包含匹配避免误匹配（如「りな」→「新ありな」）；`_split_aliases` 过滤组合名（A・B 格式双人名）；`sync_aliases` 合并去重改为 casefold 大小写不敏感避免重复词
- **别名清洗模式 cleanup_aliases**：`run_actor_db_xlsx` 新增 `cleanup_aliases` 模式，清洗 keyword 列中带括号后缀的别名——去括号保留名字，去括号后与主名或其他别名重复的整条删除（如「佐伯晴香(熟女)」整条删除）；`(注)` 开头的注释说明整条删除；括号在中间的（如「しいなうしお SIR(...)」）整条删除；嵌套括号取括号前名字；出厂库 1494 行已清洗，含括号别名归零
- **剔除男优支持别名匹配 + JavDB 充实名单**：`clean_male_actors` 扫描时增加 keyword 别名列判断，任意别名命中男优名单即标记删除（原仅检查日文原名/中文名）；通过 JavDB gender 字段验证 719 个男优（382 个 gender=1 确认），从 other_name 提取 9 个新别名补充 `male_actors.txt`（鮫島健介、黒田稔彦、赤木陽太、中沢真、中沢栄司、綠汁男、岡田敦斗、卓哥、セツネヒデユキ井口）
- **TRAWL 外部 CF 服务协议适配层**：新增 `mdcx/cf_bypass/trawl_adapter.py`——TRAWL（FlareSolverr 风格，POST /v1）与 mdcx 所需的 cf_bypasser 协议（/cookies /mirror /html）不兼容，直接填 /v1 无法工作，适配层暴露三端点并内部调用 TRAWL `/scrape` 原生 API（/v1 的 solution.headers 为空，拿不到状态码/响应头/二进制），支持 x-hostname/x-proxy/x-bypass-cache 控制头与 Set-Cookie 还原；`TrawlAdapterServer` 随机端口 + uvicorn 启动，配置 `cf_bypass_trawl_url` 后由 AsyncWebClient 自动拉起
- **适配层支持 FlareSolverr 后端**：`_call_trawl` 重构为统一 `_call_backend`，按后端类型分流——trawl 走 `/scrape` 原生 API、flaresolverr 走 POST /v1（cmd=request.get/post），三端点共用归一化响应；新增 `cf_bypass_trawl_backend` 配置（默认 trawl）；UI 外部 CF 服务行加后端类型下拉框；network_check 健康检查按后端选端点
- **TRAWL 稳定性优化**：适配层不再把 bypassCookieCache/x-bypass-cache 映射为 TRAWL skipHttp，恢复 Tier1 直连快速路径（已解 cookie 的域名直连命中）；新增 `trawl-goto-timeout.patch`（Tier3/4 页面加载超时 30s→90s），start-trawl.bat 与 package-trawl.yml 在 clone 后自动应用
- **TRAWL 便携版内置 Redis 并自动跟随上游版本**：package-trawl.yml version 输入可空（默认 latest，git ls-remote 取最新 tag），新增 Redis 8.10.1 打入包内；start-trawl.bat 自动启动内置 Redis（端口 6380）启用 Tier2 会话缓存，浏览器池默认 2；check-trawl-update.yml CURRENT 改从本仓库 trawl-* release tag 提取
- **域名轮询并修正站点域名**：新增 `mdcx/utils/domain_rotate.py`（DomainRotator 轮询切换 + rebuild_url + 用户自定义 URL 优先），爬虫基类接入 `_domains`/`_init_rotator`/`_get_text_with_rotate`，请求失败自动切下一镜像域名；javbus 12 个镜像（默认 dmmsee.cyou）、freejavbt（freejavbt22.cc）、7mmtv（7mmtv.sx）、xcity（tc.xcity.jp）；javday 默认域名 .tv → .app（实测 .tv 不可达）
- **javlibrary 动态获取最新直连地址**：新增 `get_javlibrary_domain()`，抓取 github.com/javlibcom 主页 `rel="nofollow me"` 链接提取最新地址（当前 f101w.com），带 1 天缓存，失败回退已知镜像逐个探测；javlibrary 爬虫未指定 base_url 且未配 custom_url 时 `_run` 开头动态获取
- **新增 avmoo / avheat 爬虫**：avmoo（有码，jav.data 命名空间）、avheat（欧美，wav.data 命名空间）。这两个站点与 avsox 同属 tellme.pw AIO 平台，已改为 Vue SPA + JSON API，页面 HTML 只是壳，数据全部走 API：search（POST JSON 数组 body）+ getMovie（movieId）两步。新增共享基类 `AioSiteCrawler` 封装统一流程
- **avsox 爬虫改为 API 方式**：旧 HTML 解析（#waterfall）因站点改版已失效，改用 javu.data 命名空间的 API 流程并补充简介字段
- **tellme.pw 动态地址统一获取**：新增 `get_aio_domain()` 从 `tellme.pw/{site}` 导航页解析 `__AIO_SITE_URLS__`，带 1 天缓存、三站互相兜底，修复 avsox 旧地址源（tellme.pw/avsox 已 403）
- **检测网络适配动态域名/镜像/API 类爬虫**：新增 `check_urls()` 支持镜像与动态域名站点多地址检测（主站 + 镜像）；重写 `_run` 的 API 类爬虫（avmoo/avheat/avsox/missav_api）改走真实刮削探测，不再误报"无法自动探测"；javlibrary 检测改用动态直连地址，不再打已失效的 javlibrary.com；avsox/avheat 指定各自探针番号
- **移除内置 CF Bypass 服务**：删除 cloakbrowser + cf_bypasser 内置服务（local_server.py），过 CF 统一走外部服务（TRAWL `/scrape` 或 FlareSolverr `/v1`）；移除 `cf_bypass_auto` 配置与 UI 开关，移除 Chromium 下载/预热/随包逻辑，打包体积与运行内存显著减小
- **站点定位说明**：为全部 47 个爬虫新增 `description` 定位说明（综合站/免 CF 通道/仅覆盖本厂/类型），站点下拉框与优先级弹窗列表项悬停展示 tooltip，帮助选站时快速了解站点定位
- **检查演员缺失番号多数据源重写**：「检查演员缺失番号」工具从单一 JAVBus 改为按演员类型分四路数据源——有码（libredmm xlsx href → fuzzy 搜索 → javbus searchstar 兜底）、无码（avsox getFilterMovies → javbus uncensored 兜底）、欧美（avheat getFilterMovies）、国产（iqqtv 演员页 num 分页 + title 提取番号）；演员名支持括号标注类型（如「水菜麗(无码)」「Angela White(欧美)」），不标注默认有码；javbus 使用 12 镜像轮询（与 JavbusCrawler 一致，DomainRotator 自动切换）；新增 `mdcx/tools/actor_sources.py` 封装各数据源的演员定位+番号拉取逻辑；UI 输入框增加 placeholder 与 tooltip 提示

### 重构

- **Amazon 标题匹配函数抽为模块级**：`get_big_pic_by_amazon` 内 11 个嵌套匹配函数（build_number_regex / clean_amazon_title_for_compare / normalize_title_for_compare / calculate_title_confidence / get_media_priority / is_supported_pic_ver / strip_trailing_media_noise / count_actor_group_matches / text_has_target_number / build_expected_titles / get_best_title_confidence）抽为 `mdcx/core/amazon_match.py` 模块级函数，闭包变量改为显式参数，可被批量采集脚本直接 import 复用；用 git HEAD 版本逐函数对比验证行为一致

### 工程质量

- 新增 `tests/crawlers/test_javlibrary.py` xpath 兼容性测试（含/不含 tbody 双场景）、Selenium CF 检测测试、配置关闭降级测试、DMM 封面升级 post_process 测试
- 新增 `tests/crawlers/test_javdb_app.py` 的 `fetch_javdb_aliases` 测试（9 个用例：正常返回别名、name_zht 并入、other_name 为空、搜索无结果、演员未匹配、日文异体字匹配、空输入、名字归一化、匹配逻辑）+ `fetch_javdb_actor_info` 测试（5 个用例：完整字段、null 字段、无匹配、空输入、dataclass 默认值）
- 新增 `tests/crawlers/test_aio_sites.py`（avmoo/avheat/avsox 三站 API 流程与请求格式）与 `tests/core/test_amazon_match.py`（匹配函数单元测试）
- 更新 `tests/test_network_check.py` 的爬虫探测测试（重写 `_run` 爬虫走真实刮削探测）
- 新增 TRAWL 适配层测试（`test_trawl_adapter.py`，含 FlareSolverr 后端 cookies/html/mirror/URL 重建/错误处理）、域名轮询测试（javbus/freejavbt）、javlibrary 动态地址解析与缓存测试

### 文档

- 更新 README / FEATURES / USER_GUIDE / CONFIGURATION / DEVELOPMENT：网站数量 45→47（新增 avmoo/avheat）、CF 说明改为外部服务（TRAWL/FlareSolverr）、移除内置 Bypass 相关描述、更新默认代理站点列表
- 同步 UI 使用说明页（`MDCx.ui` textBrowser_about）与仓库文档：刮削模式从 5 项修正为 4 种实际模式（正常/整理/更新/读取），软链接与调试模式标注为设置项/日志页选项；CF Bypass 补充 Selenium CF Bypass（JavLibrary 专用）与免 CF 通道说明；代理默认列表加入 missav.ws/missav.ai（完整 24 域名）；断点续刮补充「读取模式不受缓存干扰」与「刮削缓存管理」重置方式；工具页演员库维护新增「JavDB 中文名」按钮说明与「刮削缓存管理」条目；FAQ.md 引用修正为实际存在的 USER_GUIDE.md/CONFIGURATION.md/FEATURES.md；README Sites badge 40+→47
- **UI 文字全面修正**：(1) 输入网址弹窗支持网站列表改为从 `WEB_DIC` 动态生成，修复遗漏 missav/avmoo/avheat/cableav/love6/hsck/fc2ppvdb 共 7 个站点；(2) 帮助文档「调试模式」位置从"日志页面"修正为"设置→高级"；(3) CF Bypass tooltip 修正"为空=关闭"误导，补充外部 CF 服务自动启用适配层说明；(4) CF Bypass placeholder 移除已废弃的旧内置服务端口 8000；(5) init.py tooltip "免翻网址"修正为"走代理网站"，路径"设置-代理"统一为"设置→网络"，全量替换 `「设置」-「` 为 `「设置→`

### 修复

- **build-windows 工作流 upload-artifact 版本不存在**：`.github/workflows/build-windows.yml` 使用 `actions/upload-artifact@v7`，该 action 最高版本为 v4，v7 不存在导致构建上传产物步骤失败；改为 v4（与 package-trawl.yml 一致）
- **移除过时的 playwright dev 依赖**：内置 CF Bypass 服务移除后 `playwright` 不再被任何代码引用（仅 `scripts/build.py` 的 `EXCLUDED_MODULES` 排除它），`pyproject.toml` 的 dev group 仍保留且注释写着"构建期下载并随包打入 CF Bypass 所需的 Chromium"；移除 playwright 依赖与 build.py 的 exclude 项，同步更新 uv.lock

- **网络检测取消崩溃**：`run_network_check` 取消时调用不存在的 `asyncio.Task.close()` 抛 AttributeError，改为 `pending.cancel()` 且跳过已完成任务，优雅终止
- **详情页候选浪费**：基类 `_detail` 首个详情 URL 解析为 None 时直接返回，不尝试后续候选；改为解析失败继续尝试下一个
- **dmm 双重重试叠加**：外层重试循环 + 底层 `retry_count=1` 相乘放大请求次数，底层改 `retry_count=0`（外层承担重试）
- **javbus 搜索不走镜像轮换**：`get_real_url` 搜索请求用首个镜像且 us 类型硬编码 `javbus.hair`，改为镜像轮换重试
- **Amazon 高清宽度空隙**：`is_hd_candidate_width` 区间 `[1750,1770)` 误判标准大图，改为 `width >= 600`
- **minnano 标题校验失效**：精确匹配时详情页标题不含演员名仅告警仍返回，改为拒绝该候选继续尝试
- **crawl CLI 代理白名单失效**：`mdcx/cmd/crawl.py` 构造 `AsyncWebClient` 时漏传 `proxy_sites`，导致 `--proxy` 参数实际不生效。两处调用补传 `proxy_sites`，与 GUI 路径一致；新增回归测试
- **crawl CLI 失败仍返回 exit 0**：`_crawl` 与 `_fetch_async` 业务失败时不控制退出码。任一失败抛 `typer.Exit(1)`；新增退出码回归测试
- **javdb_api 搜索 q 参数丢失**：`_fetch_search` 硬编码 `/search?all=1&page=1` 丢弃番号，改为透传 URL 的 path+query；新增回归测试
- **dmm 图片校验 zip(strict=True) 脆弱耦合**：`_sanitize_image_list` 中 `remaining_candidates` 与 `remaining_results` 配对依赖 `asyncio.gather` 默认不返回异常保证长度一致，若协程被取消或 gather 签名改变会抛 ValueError 崩溃。改为非 strict，不足时自动截断
- **TRAWL 便携版路径/补丁打包缺陷**：`start-trawl.bat` 检测的 `bun\bun.exe`/`redis\redis-server.exe` 与实际嵌套路径（`bun\bun-windows-x64\bun.exe`、`redis\Redis-*\redis-server.exe`）不符，导致 Bun/Redis 检测失败静默跳过；`package-trawl.yml` 打包时漏复制 `trawl-goto-timeout.patch`，运行时兜底应用分支永不触发。start-trawl.bat 改用通配查找定位实际 exe 路径（兼容扁平与嵌套两种结构），download-bun.bat 解压后扁平化到 `bun/` 根目录，package-trawl.yml 打包时同步扁平化 Bun/Redis 目录并补复制 patch 文件
- **百度翻译 appid/key 未 strip 导致签名错误**：`_baidu_translate_message` 直接用原始 `baidu_appid`/`baidu_key` 计算签名，用户复制粘贴时可能带入前后空格/换行，导致 MD5 签名不匹配返回 `54001`。DeepL/DeepLX 使用前均 `.strip()`，百度翻译遗漏。修复为使用前 strip appid 和 key，`get_translator_skip_reason` 检测空值时同步 strip

### 清理

- **删除 AVWikiDB 别名查询死代码**：`tmdb_actor.fetch_avwiki_aliases` 全站被 Cloudflare 拦截（403）已不可达，UI 补别名入口早已改走 minnano，该函数无业务调用方（仅测试引用）。删除函数及配套 `_avwiki_rate_limiter`/`_avwiki_session` 模块级对象、`tests/test_avwiki_aliases.py`
- **文件移动冗余分支**：`file.py` "are the same file" 两分支代码相同，合并
- **Gfriends 缓存重复写入**：`emby_actor_manager` 先 wb 写原始字节再原子写展开 JSON，去掉首次写入直接解析展开
- **CF 后退避死分支**：`web_async` `sleep_after_cf_bypass` 恒为 False 的日志分支，删除
- **javdb_api 不可达代码**：`_try_mirrors` return 后不可达的 `_last_page_request_at` 赋值，删除
- **避免使用不支持的状态表情**：UI 中部分状态展示使用了某些环境不支持渲染的 emoji，替换为通用字符避免显示异常
- **Windows 保存配置时黑色控制台窗口一闪而过**：保存/加载配置的日志调用 `platform.platform()`，在 Windows 上会执行 `cmd /c ver` 启动子进程，windowed 打包下每次闪黑色控制台窗口。`consts.py` 新增 `SYSTEM_INFO`（platform.uname()，无子进程，启动时算一次），save_config/load_config 改用之；local_server/trawl_adapter 的 uvicorn 子进程与 sync_gfriends 的 git pull 加 `CREATE_NO_WINDOW`
- **翻译引擎说明文字重影**：v2.0.5 新建的 `label_baidu_hint`（百度提示）被放到 `gridLayout_32` col0（标签列，仅 ~130px），长说明不换行向右溢出进入 col1，被 col1 的 `label_60` 不透明背景遮挡，露出前半截产生重影。改为 `label_baidu_hint` 跨整行（col0-1）+ `setWordWrap(True)`，合并两段文案为一句综合说明，移除/隐藏 `label_60`
- **配置保存 Windows 拒绝访问**：`_write_config_text` 的 `os.replace` 一次失败即抛异常，对 Windows 上常见的瞬时占用（杀软实时扫描 `.tmp`）/只读属性/权限不足零容错，导致「配置保存失败，软件已保持运行」。改为多级回退：重试 6 次（瞬时锁）→ 去只读属性 → 删目标改名 → 直接覆盖写，最后仍失败抛带中文操作指引的 `PermissionError`，所有走 `manager.save()` 的配置/资源文件（不止 `studios.json`）均受益
- **修复 Emby 演员管理器窗口遮挡主窗口 + 按钮无反应（issue #38）**：`open_emby_actor_manager`/`tool_handlers.pushButton_emby_actor_manager_clicked` 由模态 `dialog.exec()` 改为 `dialog.show()` 非模态，并给 `EmbyActorManagerDialog` 加 `WindowMinimizeButtonHint`，窗口可最小化、不再盖死主窗口。修复 GUI 主线程直接 `executor.run()` 同步阻塞（全局单 loop 被长任务占满 + 网络慢时主窗口整个卡死）：`_on_connect`/`_on_fetch` 的 `get_media_folders`/`_on_fetch_finished` 的 `get_gfriends_index` 改 `executor.submit` + 自定义信号回传结果，`ActorDetailDialog` 的加载现有头像/获取头像/获取简介/单演员同步 4 处改后台执行 + `_detail_done` 信号回主线程更新 UI（并消除协程内直接碰 QWidget 的跨线程违规），统一 `_future_result_or` 兜底 Future 异常
### 工程/文档
- 更新默认代理站点列表与使用说明文档
- **DEVELOPMENT/FEATURES 补全近期架构**：DEVELOPMENT 新增镜像域名轮询、API 类爬虫（AioSiteCrawler）、check_urls 网络检测、TRAWL/FlareSolverr 适配层、动态域名、网络检测章节；FEATURES 补网络连通性检测功能点
- **UI 几何回归测试**：新增 `tests/test_ui_geometry.py`，offscreen 实例化 `Ui_MDCx`，遍历所有 `QGridLayout` 并强制激活布局（切换各 tab + 祖先链 setVisible），断言同 layout 内任意两个可见直接子控件包围盒无交集，挡住「同行同列多 item / 跨列长 label 溢出被邻列遮挡」类重影回归（与既有 XML 静态结构测试互补）
- **百度翻译控件收口到 .ui**：`checkBox_baidu`/`label_baidu_appid`/`lineEdit_baidu_appid`/`label_baidu_key`/`lineEdit_baidu_key`/`label_baidu_hint` 从 `main_window.py::_setup_baidu_translate_ui` 运行时注入改为直接写进 `MDCx.ui`（`gridLayout_32` row4-6 + `horizontalLayout_20`），删除动态注入方法与运行时增高逻辑（增高固化到 .ui：`groupBox_trans`/`layoutWidget_2`/`scrollAreaWidgetContents_fanyi` +70、9 个兄弟 groupBox y+70）。`.ui` 成为唯一权威源，几何回归测试从此覆盖这些控件
- **网站优先级按钮收口到 .ui**：`gridLayout_36` 内 6 个刮削类型（有码/无码/素人/FC2/欧美/国产）的「编辑网站」「字段优先级」共 12 个按钮从 `setup_site_priority_ui` 运行时 `_make_inline_button` 创建+`addWidget` 改为直接写进 `MDCx.ui`（row 0/2/4/6/8/10 col 2/3，objectName `pushButton_edit_website_{type}`/`pushButton_priority_website_{type}`），运行时只 `getattr` 赋值 + `connect` 信号 + `apply_site_priority_theme` 上主题样式；删除 `_make_inline_button` 工厂
- **UI 几何回归测试扩展（绝对定位子控件）**：`test_ui_geometry` 新增 `test_absolutely_positioned_children_no_overlap`，检查 `layout() is None` 的父 widget（如 `groupBox_10`、`scrollAreaWidgetContents_wangluo`、`widget_setting`）内绝对定位子控件包围盒不重叠。覆盖三处收口后固化的绝对坐标控件（`label_75`/`label_get_cookie_url`/`label_7`、`groupBox_44`/`groupBox_14` 下移后的位置等），防止增高/下移固化时绝对定位控件互相压叠。排除 `centralwidget`/`page_*`（offscreen 下几何退化或含运行时切换控件）
- **跨线程 Qt 安全收口（阶段 A+B）**：提取 `mdcx/utils/qt_thread.py::run_in_background(button=, coro_factory=, busy_signal=, busy_text=, finished_signal=, finished_arg=, log_prefix=)` 通用工具，固化「防重入 + setEnabled(False) + busy_signal + submit + finally 发 finished_signal + 异常 show_log」正确模式（后台协程只发 `pyqtSignal`，主线程槽恢复 UI）；`_run_actor_db_async` 改为调用它作样板。新增 `scripts/check_thread_safety.py` AST 扫描 `async def` 体内直接操作 QWidget setter（setEnabled/setText/setGeometry 等）的违规，当前 0 违规，作为防回归工具
- **刮削缓存管理 UI**：工具页新增「刮削缓存管理」groupBox，把已有的 SQLite 状态缓存暴露给用户。缓存层 `ScrapeStateCache` 补 3 个 API：`stats()`（SQL 聚合返回 done/failed/failed_exhausted/total 计数 + db 路径/大小）、`list_failed_detail(limit)`（返回失败详情含 error/fail_count）、`delete_state(file_path)`（单文件重置，强制下次重刮）。UI 含统计区（4 计数 + db 路径/大小 + 刷新）、失败列表表格（QTableWidget 5 列）、导出失败列表 CSV（标准库 csv，utf-8-sig 兼容 Excel）、重置选中记录、清空全部缓存（带二次确认）。清缓存只影响是否跳过，不删已生成 NFO，零数据风险
- **性能优化批次**：剩余任务列表改为快照后后台线程写入，避免 1.5 秒 QTimer 在主线程全量写盘；水印源图缓存打开和 RGBA 转换，重复处理时减少磁盘 IO；同番号等待由 1 秒轮询改为 `asyncio.Event` 即时唤醒，并保留停止/超时兜底。ActressDB 改为参数化 SQL；信息映射库加载时建立规范化索引，查询从全表扫描降为 O(1)；刮削状态缓存启用 WAL + `synchronous=NORMAL`，刮削写入按 32 条批量提交并在关闭时 flush；`json_data_dic` 限制为最近 2000 条，防止长批次内存无界增长。新增缓存批提交和内存上限测试，专项 40 个测试通过
- **启动性能：本地数据库延迟加载**：`Resources` 构造阶段移除演员库、信息映射库和相关 XLSX 迁移/合并的同步阻塞，新增 `ResourcesDataLoader` 后台线程、`start_data_loading()` 和 `ensure_data_ready()` 就绪屏障。主窗口基础 UI 初始化后启动资源加载；演员库、信息映射库、翻译和标签优先级入口首次使用时安全等待资源完成，加载异常保留日志和错误传播。资源与翻译专项 74 个测试通过
- **fc2ppvdb Cookie 控件收口到 .ui**：`label_fc2ppvdb_cookie`/`plainTextEdit_cookie_fc2ppvdb`/`horizontalLayout_fc2ppvdb_cookie`（含 `pushButton_check_fc2ppvdb_cookie`+`label_fc2ppvdb_cookie_result`）从 `main_window._setup_fc2ppvdb_cookie_ui` 运行时注入改为直接写进 `MDCx.ui`（`gridLayout_10` row4-5，仿 javdb/javbus 同模式）。运行时增高/下移逻辑一并固化到 .ui：`groupBox_10` height +140、`gridLayoutWidget_10` height→400、`label_75`/`label_get_cookie_url`/`label_7` y+120、`scrollAreaWidgetContents_wangluo` height +140、`groupBox_44`/`groupBox_14` y+140 下移。删除 `_setup_fc2ppvdb_cookie_ui` 方法与调用，清理未用 import
- **启动健康自检**：新增 `mdcx/controllers/main_window/health_check.py`，在窗口启动「显示信息」阶段调用 `run_startup_health_checks()`，只读检查 3 项环境前提并把结果写入网络页日志（`signal_qt.show_net_info`），不弹模态弹窗、不自动改配置：1) 配置目录可写性（写测试文件再删，不可写提示检查权限，呼应此前 `_write_config_text` 多级回退修复）；2) TMDB API Key 是否配置（空则提示演员/封面受限）；3) 代理可达性（`use_proxy=True` 时解析 proxy 取 host:port，`socket.create_connection` 2s 超时探测 TCP 连通，不可达提示确认代理软件已启动或临时禁用）。代理探测走 `threading.Thread(daemon=True)` 后台 + 信号，不阻塞启动；目录/key 检查毫秒级同步。8 个单元测试覆盖三项判定分支

## v2.0.5 (2026-08-15)

### 功能

- **DMM 高清升级探测去重**：`upgrade_dmm_cover` 增加进程内 TTL 缓存（按规范化番号，成功缓存高清 URL、失败缓存 None）+ 同事件循环 in-flight 合并，JavBus / JavDB 三站 / R18.dev 等站点并行刮削同一番号时不再对相同 DMM 候选重复探测（未知系列全 404 场景从每站点 ~20 次请求降为全程一次）
- **DMM 高清图按分辨率放行跳过日亚**：`_should_skip_amazon_for_existing_poster` 对 awsimgsrc DMM 高清图改为按分辨率直接放行（宽≥700），解决 DMM 竖图普遍 <400KB 被字节阈值误判为「不够清晰」而误走日亚搜索的问题；同时 `upgrade_dmm_cover` 增加分辨率校验，过滤 147x200 缩略图占位图，避免把海报覆盖成低清缩略图
- **DMM 放行门槛降至 700**：`POSTER_DMM_MIN_WIDTH` 与 `_DMM_HD_MIN_WIDTH` 由 1024 降到 700，MILK 系列 745x1081 等中尺寸图也能升级为海报并跳过日亚，进一步减少日亚请求；588x800 及 147x200 窄图/缩略图仍被拦截
- **ASIN 数据库写入去重**：`save_asin_to_excel` 写入前按番号去重，同番号已存在时跳过不写，避免重复行
- **ASIN 出厂库增量合并**：新增 `merge_asin_db_from_backup`（仿演员库，出厂库 md5 标记 `.asin_db_merge_marker` 未变跳过；按番号并集合并——新增番号追加、已有字段空缺补全，不覆盖用户已填值、不删行），软件更新后老用户启动时自动把出厂库新增/修正数据合并进用户库
- **ASIN 出厂库更新**：出厂 ASIN 库合并最新数据至 9699 个番号（净新增 4616），按番号（前缀字母 + 数字）排序
- **ASIN 出厂库合并后重排**：`merge_asin_db_from_backup` 合并产生新增行时，合并后按番号（前缀字母 + 数字）整体重排并重新格式化（重建工作簿避免 delete_rows 的 max_row 虚高）；纯字段补全不改变行数与顺序，不重排
- **相似片推荐**：新增 `mdcx/core/similar.py`（借鉴 OpenAver 设计）——基于 tag IDF 加权 Jaccard + 系列/片商/年份/时长/演员组合评分 + MMR 重排的本地离线相似算法，零网络零模型；主界面结果树右键「查看相似片推荐」弹出对话框，双击可跳转
- **SQLite 刮削状态缓存（断点续刮）**：新增 `mdcx/core/scrape_cache.py`（标准库 sqlite3 + WAL），持久化每个源文件的刮削状态（done/failed + mtime + 失败计数），实现断点续刮与失败跨会话重试（上限 3 次，成功清零）；数据库损坏自动回退内存模式；重启后自动跳过已完成且未变化的文件、恢复上次失败未超限文件
- **结果摘要缓存**：`scrape_state` 表新增 `summary_json` 列（旧表自动迁移），刮削成功时存储相似推荐所需字段；相似推荐语料 = 历史成功结果（SQLite）+ 当次刮削结果，重启后仍可基于全历史推荐
- **相似推荐特征扩展**：结果摘要新增 `mosaic`（有码/无码）、`publisher`（发行商）、`directors`（导演）、`score`（评分）四个特征，算法加分项同步扩展——马赛克类型相同 +0.35 / 不同 -0.30（有码无码不再混淆推荐）、发行商一致 +0.15、导演有交集 +0.15、评分接近 +0.05；同时修复召回缺陷：热门标签（IDF=0）不再被排除出候选召回，只影响精排权重，解决「目标片全是常见标签时完全推荐不出结果」的问题
- **CF Bypass 落地域名白名单**：新增配置 `cf_bypass_trusted_hosts`（逗号分隔，支持 `*.example.com` 子域通配），校验 Bypass 服务落地/重定向后的最终域名，防第三方服务被劫持时把恶意页面当数据；设置页新增「Bypass落地白名单」输入框
- **本地 Bypass 服务健康状态机**：新增 `_local_bypass_health`（idle/ready/dead），连续请求失败达阈值（3 次）标记 dead 并解除转发（不再空等假死服务超时），冷却 300s 后自动重试，请求成功自动恢复
- **Emby 演员管理器修复**：修复「连接 Emby」无反应的根因（`ComputedManager` 模块不存在致 ModuleNotFoundError 被静默吞掉）、`_is_jellyfin_server` 恒 False 的判断 bug；修复 `search_actor_info` 键大小写不匹配导致简介/信息抓取完全失效、DELETE 404 被当失败致无头像演员传不上头像；`PreparePreviewThread` 加顶层异常处理并真正 emit error（原 worker 调用不存在的 `self.log` 致线程静默死亡）；并发模型由「10 线程各自 event loop」改为单 loop + `asyncio.Semaphore(10)`；头像/背景上传统一复用 `_upload_actor_photo`；Emby 分支补 `personTypes=Actor` 过滤；`sync_actor` 单演员异常不再中断整批、`update_person_info` 不再用空值覆盖服务器已有字段
- **Emby 演员管理器新功能**：新增「设置」对话框（数据源优先级拖拽排序、演员类型过滤/去重、本地头像目录、Gfriends、使用数据库）；「数据源测试」窗口（按配置优先级逐源验证头像/简介并展示结果，含字段/值信息表与快速设置面板）；演员详情编辑对话框（左栏现有数据、右栏可编辑简介/信息表、快速设置面板、单独同步头像/简介）；快速设置面板（测试/详情窗口内改即自动保存）；「清空缓存文件夹」按钮；底部状态栏（连接/操作状态）；同步完成后 3 秒自动重新获取演员列表
- **Emby 演员管理器健壮性**：头像补全主循环逐演员容错、backdrop 按索引删除、Gfriends commits 解析失败降级、时区偏差修复、缓存文件名防碰撞、`src[jp_name.index()]` 越界防护、按钮状态机修正、Dialog 关闭安全（`closeEvent` 等待线程）、清理死代码（`_avatar_cache`/无效 checkbox/重复 layout 等）
- **爬虫类型分类校准**：按站点性质校准各刮削类型默认网站源——仅能有码（dmm、dmm_api、libredmm、r18dev、avbase、faleno、giga、dahlia、xcity、prestige、mgstage、fantastica、cableav、getchu、getchu_dmm、javlibrary、jav321、freejavbt、lulubar）、无码专属（avsox、kin8）、综合有码+无码（javbus、javdb 系、missav 系、javday、7mmtv、airav_cc、avsex、official、iqqtv）、素人（含 mywife、iqqtv）、FC2（含 javdb 系）、欧美（仅 theporndb）、国产（含 iqqtv、hscangku）；同步默认配置模板与 FEATURES 文档标注；「刮削不到？看这里！」弹窗网站列表改为动态生成（随爬虫注册自动更新）
- **Emby 演员缓存持久化**：演员头像缓存从临时目录（`tempfile.gettempdir()`）改为持久化目录 `userdata/emby_actor_cache/`，与 gfriends.json/minnano_cache.xlsx 一致，重启后可复用缓存避免重复下载

### 修复

- **图片尺寸探测失效**：`_read_stream_size`/`get_imgsize` 对 curl_cffi 同步生成器产出 bytes 误用 `await` 恒抛 TypeError，改为 `aiter_content` 异步迭代；修正测试 mock 与线上行为对齐（此前测试掩盖 bug，Amazon 高清择优/尺寸校验静默失效）
- **GUI 状态卡死**：`_move_file_thread` 移动完成后按钮永久卡禁用（补 `reset_buttons_status` + try/finally）；非刮削状态点「停止演员库维护」后 `signal_qt.stop`/`Flags.stop_requested` 永不复位导致日志静默、下一任务秒停（`_on_actor_db_finished` 复位）
- **停止标志 / 跨线程 Qt**：`_show_version_thread` 移除 worker 线程直接操作 QWidget（`setCursor`/cookie 检查改经 `version_check_done` 信号回主线程）；`network_check` 按钮状态经信号回主线程 + 防重入 + 删重复 setText；`to_cut` 后台线程读 QWidget 改为主线程采集 `mark_list` 传入、`_set_pixmap` 跨线程改 UI 经信号回主线程
- **trailer 旧文件复用**：`deal_old_files` 带文件名时用旧 `file_name` 构造目标路径，与 `trailer_download` 的 `naming_rule` 命名不一致导致旧 trailer 无法复用/孤立文件，新增 `naming_rule` 参数对齐
- **Amazon ASIN 记录丢失**：低清兜底路径 `asyncio.create_task` fire-and-forget（事件循环关闭时 pending task 销毁），改为 `await`
- **爬虫修复**：`get_amazon_data` 删除对恒为 None 的 `html_info` 提取 session 的死逻辑；`get_avsox_domain` 布尔优先级错误（or→and）；`check_url` `max_retries` 1→3 启用真实退避重试；非数字评分 `float()` 崩溃防御；`translate_actor` 空演员名误替换全部演员；missav 冒号格式时长解析（1:30:00）；missav URL slug 非番号格式不覆盖番号；javbus 搜索结果相对路径补全绝对 URL；javdb XPath 作用域逃逸；r18dev dvd_id 补零比较
- **读模式 tmdbid 不落盘**：xlsx 缓存命中 tmdbid 立即回写 `res.actor_tmdb_ids`，修复 `still_missing` 为空时 NFO 缺 tmdbid
- **文件写入原子化**：NFO 与配置保存改为临时文件 + `os.replace` 原子写入（防写入中断损坏），推广到 missing 番号清单、gfriends JSON、actor_db 断点文件、amazon_database 报告等
- **LogBuffer 并发安全**：`write`/`clear` 加锁、`get` 遍历浅拷贝，修复并发 append 时 `list changed size during iteration`
- **死代码清理**：删除 `image.py:get_pixmap`（无调用且读取失败会删除源图）、amazon 4 个未用函数、`parse_fanza_resp`、`save_asin_to_excel` 未实现的 `max_rows` 参数、`query_asin_database` 重复 import 死分支、`Config.from_legacy` `type(timedelta)` 恒 False 等
- **Emby 演员管理器 Event loop is closed**：9 处 `new_event_loop()`+`close()` 改用全局 `executor` 常驻 event loop，避免 curl_cffi AsyncSession 跨 loop 复用报错
- **Emby 演员管理器获取列表无反应**：`QDialogButtonBox.Ok` → `StandardButton.Ok`（PyQt6 6.4+ 扁平枚举已改嵌套）；site_priority_dialog 两处补 `manager.save()` 修复网站优先级拖拽排序后不落盘
- **Emby 演员管理器设置保存不生效**：`EmbyActorSettingsDialog._save` 及两处 `_save_quick_settings` 补 `manager.save()`，修复设置弹窗修改后不写盘
- **Emby 设置弹窗 QListWidget 遍历崩溃**：PyQt6 QListWidget 不可直接 `for item in self.list` 迭代（抛 TypeError），改用 `item(i)` 索引遍历
- **Emby 数据源测试跨线程 UI 崩溃**：`ActorSourceTestDialog` 在后台线程直接操作 QWidget 导致崩溃，改用 `QThread` + 信号回调模式（`ActorSourceTestThread` 发 `result`/`error` 信号回主线程）
- **翻译页 label_60 文字被覆写**：翻译页百度提示文字覆写了 label_60 原有文字导致重影，新建 `label_baidu_hint` 独立显示
- **网络设置 groupBox 重影**：网络设置页 `trusted_hosts` 输入框与超时行 cell 冲突（同一 gridLayout cell 放了两个 widget），`trusted_hosts` 移到 row=10，`groupBox_28` 高度 400→480
- **MDCx.ui 重复 objectName 消除**：4 对重复 objectName（label_81/60/423/424 第二次出现）重命名，消除运行时控件查找歧义
- **label_601 死引用删除**：`main_window.py` 引用不存在的 `label_601`，运行时必崩
- **Courier 字体替换**：117 处 `font:"Courier"` → `font:"Courier New"`，修复中文环境字体名匹配失败导致文字显示为方框

### 工程质量

- **测试增强**：新增 Amazon 跳过逻辑测试（DMM 高清/中尺寸放行、缩略图/窄图拦截、非 DMM 字节阈值保留、Amazon 来源不跳过）；新增 `upgrade_dmm_cover` 缓存行为测试（命中零探测、失败缓存保留原图、并发 in-flight 去重）；更新 JavBus / R18.dev 受影响升级测试
- **ASIN 库测试增强**：新增 4 个测试（同番号去重、批量去重、出厂合并行为、md5 标记跳过）
- **新功能测试增强**：新增相似算法 7 测试、相似对话框 5 测试、`ScrapeStateCache` 15 测试、CF 白名单 6 测试 + 4 集成测试、本地 Bypass 健康状态机 8 测试；修正 `test_media_resource` mock 与线上 curl_cffi 行为对齐
- **打包与 CI 加固**：`build.py` 显式收集 `curl_cffi.libs` 防打包后 TLS 指纹库丢失；`ci.yaml` 补 `check_info_db` 步骤；移除 `libs/` 下 OpenSSL 1.1 死数据；`main.py` stderr 重定向仅 IS_PYINSTALLER 时生效
- **Emby 数据源实现合并**：`emby_actor_manager.py`/`emby_actor_image.py`/`emby_actor_info.py` 三模块间重复的 Gfriends 索引解析、Graphis HTML 解析、信息补全链路合并——`get_gfriends_index` 增强为完整版（版本检测+缓存刷新+展开写回）、抽出 `_parse_graphis_html`/`fill_actor_info_from_sources` 共用函数、`_BIO_TAG_PATTERNS`/`_extract_bio_tags` 统一移至 manager 模块
- **Emby API 共用函数提取**：新建 `emby_shared.py`，移入 5 个共用函数（`_generate_server_url`/`_build_jellyfin_headers`/`_is_jellyfin_server`/`_append_query`/`_upload_actor_photo`），两模块从中导入并 re-export（`# noqa: F401`）保持向后兼容
- **本地头像预扫描索引**：新增 `build_local_avatar_index` 预扫描本地头像目录建立文件名索引，`from_local_avatar` 加 `pre_scanned_index` 参数，N 次逐演员全树遍历降为 1 次预扫描 + N 次字典查找；新增 6 个测试

## v2.0.4 (2026-08-14)

### 功能

- **DMM 官方高清直链**：新增番号→DMM cid 候选构造器 `dmm_direct`（前缀映射表覆盖 110+ 主流系列，含 `h_xxx`/数字特殊前缀与跨厂商附加前缀，用 dmmapi/avbase 实测校准，配套 `dmm-probe` 探测工具）；封面补全所有爬虫失败时走官方直链兜底（竖版 `ps` 高清作海报优先，横版 `pl` 裁剪兜底，无码番号跳过）
- **DMM 高清覆盖九个爬虫**：LibreDMM / R18.dev / JavBus / JavDB 三站 / DMM / DMM API / avbase 刮削时直接把低清/水印图升级为 DMM 官方高清（统一 `upgrade_dmm_cover` + 前缀表候选，check_url 验证，失败回退原图）；开启「Poster 选优」时自动注入 DMM 高清候选按尺寸选优；DMM 图下载失败自动重试一次
- **同番号刮削结果 TTL 缓存**：同批次相同番号文件（多 CD/重复文件）直接复用刮削结果，避免重复请求所有站点，TTL 90 秒 + 容量上限自动淘汰
- **R18.dev 英文标题掩蔽还原**：日文标题缺失时用服务端 `title_en_uncensored` 还原掩蔽字段（`Sex S***e` → `Sex Slave`）
- **补别名/补全功能调整**：补别名来源切换为内置 minnano 爬虫（无 CF 拦截、命中质量高），新增「全量更新」开关与「起始行/限量」分片续跑；新增「minnano 补全」按钮（补缺生日/简介，日文自动翻译）
- **演员库维护工具健壮性**：新增「检查用户库」（扫描格式/结构/数据异常，安全项一键自动修复）与独立停止按钮；联网工具统一滑动窗口并发（TMDB 5 / LibreDMM 2）+ 限量分片 + 断点续跑；LibreDMM 补链接加限流与共享会话
- **info 库重构与同步**：三语言列、五源标签收集、cn 翻译优化；出厂库合并用户库机制（cn 合并键 + md5 marker）；actor 库标签/事务所/生涯日文残留清理与同步；check_actor_db 检查项整合
- **Emby 演员管理器增强**：信息补全与管理器接入本地演员库（最高优先，离线可用）；新增 graphis 头像/背景图来源；跳过逻辑精确化（识别"无维基百科信息"占位符）

### 修复

- **打包与网络**：PyInstaller 补充 minnano 爬虫 hidden-import；默认走代理列表补 `minnano-av.com` 且裸 session 按配置走代理；JavDB 图片域名归一（水印 `tp.spfcas.com` → 无水印 `c0.jdbstatic.com`）
- **Emby 演员管理器**：「仅补缺失演员」不再拉全库、详情并发拉取、删除图按响应状态判定；移植版 import 修复、空响应不再误报失败、缓存导入路径修复
- **演员库维护工具**：新增「更新 nfo tmdbid」与「校验 tmdbid 有效性」按钮；TMDB 演员匹配优化（繁→简转换、adult 权重优先、候选放宽 + 命中变体排序）；actor_db 并发 UX 修复（信号带 task_id、通用模板消重）
- **UI 与布局**：工具页/设置页 groupBox 重叠连锁修复；删除无效单选按钮；MDCx.py 文案漂移回写 MDCx.ui；`validate_crawler_registry` 误报修复
- **网络诊断**：站点超时改用用户配置值；新增"路由"列显示代理/直连
- **安全**：修复 `shell=True` 注入风险、移除 11 处 `?api_key=` 暴露、修复 5 处静默异常 + 下载 URL 白名单
- **minnano 路径 bug**：日文名查找与缓存文件改用运行时用户数据目录（打包后 CWD 失效问题）
- **其他**：爬虫 xpath 防御下沉（10 处）、`update_nfo_tmdb_ids` 类型防御、UI 缩放异常不阻断启动、异常日志通道修复

### 工程质量

- **mypy 严格化**：移除全部 19 项 `disable_error_code`，全项目零抑制通过；`BaseCrawler` 泛型化等修复 43+ 处类型错误，顺带修复 5 个隐藏 bug
- **测试增强**：UI 结构自动化测试、`validate_crawler_registry` 测试、Emby HTTP 测试、actor_db 按钮一致性测试；ruff 自动修复 138 处
- **其他**：单站失败原因结构化分类（`FailureReason`）、死代码清理、`_download_chunk` 返回类型修正

### 文档

- 使用说明 tab 与 README/INSTALL/FEATURES/USER_GUIDE 等更新（仓库链接修复、新功能描述）

## v2.0.3 (2026-08-03)

### 功能

- **演员库维护工具改为直接操作 xlsx**：移除「输入演员名单 / 选择 nfo 目录」输入方式，新增三个独立按钮——补全中文名（按已有 TMDB ID 补中/英繁体翻译）、补全 LibreDMM 链接（补信息链接）、同步别名（用 TMDB 最新 also_known_as 刷新 keyword 列），统一扫描 `actor_database.xlsx`，每个按钮带独立防重入
- **同步别名与刮削共用同一规则**：`run_actor_db_xlsx` 的 `sync_aliases` 改为复用 `_merge_keyword_values`，与刮削写入 actor 库的别名合并逻辑保持一致，永不同步偏差
- **工具页工具排序调整**：按用户偏好重排为 Emby 演员管理 → 演员库维护 → 单文件刮削 → 裁剪图片 → 封面补图 → 软链接助手 → 移动视频字幕 → 检查演员缺失番号
- **打开演员数据库按钮**：演员库维护工具新增「打开演员数据库」按钮，用系统默认程序打开 `actor_database.xlsx` 供查看与手工编辑；文件不存在或打开失败时提示先安装 Excel/WPS 等办公软件
- **并发提速**：演员库维护（补全中文名/链接/同步别名）改为滑动窗口并发模式，TMDB 请求并发 5、LibreDMM 请求并发 2，串行 150s+ 降至约 30s

### 修复

- **单 exe 按钮无提示退出**：修复「打开演员数据库」按钮点击后程序直接退出（根因：`_open_actor_db_file` 误作实例方法调用导致 AttributeError，被 onefile 无控制台吞掉为静默退出）
- **executor.submit 传参错误**：`AsyncBackgroundExecutor.submit()` 只接受单协程参数，`executor.submit(asyncio.run, run())` 写法导致 TypeError。修复 `main_window.py` 的 `_run_actor_db_tool` 及 `tool_handlers.py` 的 cover_backfill 两处同源 bug
- **跨线程 Qt 不安全操作**：`_run_actor_db_tool` 协程内直接 `btn.setEnabled()` 跨线程操作 QWidget。改为 `actor_db_finished` pyqtSignal 主线程恢复，消除潜在 segfault 风险
- **日志通道不通**：`_log_line` 仅写内存 LogBuffer，不显示在 GUI 日志页/文件，用户看到「开始扫描」后无后续输出误以为卡死。改为同时调用 `signal_qt.show_log_text` 实时显示

### 工程质量

- **崩溃转储埋点**：`main.py` 注册 faulthandler + sys.excepthook + stdout/stderr 重定向到 `MAIN_PATH/crash/` 目录， onefile 无控制台环境下的 Python 异常不再被静默吞掉
- **死代码清理**：移除 `init.py` 重复 `setText` 接线、`tool_handlers.py`/`main_window.py` 旧 `pushButton_actor_db_pick_dir/start_clicked` 引用已删除控件的死代码
- **记忆文件写入**：`.monkeycode/MEMORY.md` 记录 9 条经验：onefile 静默退出诊断方法、日志通道一致性、executor.submit 正确用法、跨线程 Qt 安全模式、刮削并发架构参考

## v2.0.2 (2026-08-02)

### 重构

- **工具页槽函数抽取**：将 `main_window.py` 中的 21 个工具/设置页槽函数抽取至独立模块 `tool_handlers.py`，`main_window.py` 从 3539 行减至约 3350 行
- **目录选择模式统一**：新增 `_pick_folder` 公共 helper，9 个目录选择方法统一为一行 delegate 调用
- **删除 2 个废弃 import**：`emby_actor_image`/`emby_actor_info` 改为延迟导入

### 性能

- **行索引缓存**：`update_actor_db_row` 新增 `_ACTOR_DB_ROW_INDEX` 全局索引（jp_name → row_index），消除 O(n²) workbook 全表扫描，三个调用点（actor_db_tool/tmdb_actor/scraper）直接受益
- **读取模式批量落盘**：`scraper.py` 读取模式下演员 TMDB ID 补充改为共享 workbook，集中一次落盘，避免每个演员独立 load/save
- **格式化跳过**：`_format_db_worksheet` 检测表头是否已格式化，首次后跳过边框/字体/列宽设置，每次 save 减少 5 次全表遍历，CI 测试耗时从 20.8s 降至 10.7s

### 工程质量

- **移除 7 个文件的 network 标记**：`test_tmdb_actor.py` 等 7 个文件的 93 个测试全部为纯离线 mock 测试，移除 `pytestmark = pytest.mark.network` 使其进入 CI
- **修复 9 个预存陈旧测试**：`test_network_lifecycle.py` 的 `_FakeLimiter`/`_FakeResponse` mock 修复（添加 async context manager 支持），`test_web_amazon_data.py` 的 mock 路径修正（`mdcx.utils.rate_limit.random`），`test_amazon_database.py` freeze_panes assert 修正
- **新增 14 个测试用例**：行索引缓存 6 个、`_load_actor_db_wb`/`_flush_actor_db_wb` 4 个、目录选择/gfriends 同步 8 个
- CI 离线测试通过数从 **530 提升至 635**（+105），全量 627 passed，4 skipped
- **打包配置补充**：`build.py` 新增 `mdcx.tools.emby_actor_image`/`emby_actor_info`/`sync_gfriends`/`scripts.cover_backfill` 的 hidden-import，排除 6 个开发期包（playwright/setuptools/mypy 等），预估单 exe 体积减少约 200MB

## v2.0.1 (2026-08-01)

### 新增功能

- **演员库维护工具**：工具页新增"演员库维护"功能，可对已有 TMDB ID 的演员批量补全中文/繁体翻译和 LibreDMM 链接，支持输入演员名单或选择 nfo 目录自动收集演员
- **刮削流程精简**：更新模式刮削时不再自动为已有演员补全翻译/LibreDMM 链接（该能力移至独立的"演员库维护"工具），加快刮削速度、减少不必要的网络请求
- **Emby 演员管理器**：工具页新增"Emby 演员管理器"按钮，打开独立对话框，可连接 Emby 服务器获取演员列表、多源匹配头像（Gfriends/minnano-av/本地文件夹）和简介（minnano-av/Wiki/本地数据库），支持批量同步到 Emby
- **Emby 演员管理器 - 选库**：点击"获取演员列表"时弹出媒体库选择对话框，可按需勾选要管理的库
- **Emby 演员管理器 - 表格查看**：演员列表表格展示头像/简介/背景图/影片数状态，支持按缺失情况筛选和搜索
- **封面补图工具**：工具页新增"封面补图"功能，输入番号即可自动刮削并补齐缺失的 `poster.jpg` 和 `thumb.jpg`，复用当前配置的站点优先级、命名、裁切、水印规则，支持批量输入与覆盖已有图片
- **封面补图独立脚本**：`scripts/cover_backfill.py` 支持命令行批量和自定义参数，可在打包外独立运行
- **JIMMY 前缀路由**：`JIMMY-003` 等番号自动路由到 FALENO 官网获取资料
- **失败原因记录**：所有刮削来源均失败时，日志会列出各站点的具体失败原因（超时/搜索未匹配等），便于定位问题

### 改进

- **自动海报选优**：不再将横向海报作为最终 Poster，候选图全为横图时自动改用缩略图右裁切，修复 ABF-371 一类封面未裁剪问题

### 修复

- **Windows 路径超限**：`{{ series }}` 系列名过长导致完整路径超 MAX_PATH(260) 时，自动缩短目录名，修复刮削后文件夹无法打开的问题（#19）
- **中文字幕标签误添加**：共享数据路径中未检查 `nfo_tag_include` 配置，关闭后仍会添加"中文字幕"标签，现已修复（#20）
- **explorer /select 路径未引号**：含空格或特殊字符的路径无法用 `explorer /select` 打开，已修复为加引号调用
- **Emby 4.9 剧照显示**：`extrafanart_extras_copy` 将 .jpg 改为 .mp4 时使用 move 而非 copy，导致 `behind the scenes` 目录下只保留 .mp4，Emby 4.9 无法识别。改为 copy 同时保留 .jpg 和 .mp4（#17）

### 工程质量

- 新增 2 个模块，596 个测试用例（583 通过，13 个为既有环境性网络用例失败，与本次改动无关）
- 无新增第三方依赖，兼容 Windows 打包
- 新增 9 个测试用例：JIMMY 前缀路由测试、失败原因记录测试、海报横向过滤单元测试（7 个覆盖 portrait 选优逻辑）
- 新增演员库维护相关测试用例：nfo 目录收集/去重、空名单、翻译/链接开关控制、翻译与链接补全

## v2.0.0 (2026-07-18)

MDCx v2.0.0 全新出发。

### 新增爬虫

- **R18.dev 爬虫**：新增 `r18dev` 刮削源，走 R18.dev 的 JSON 接口直连，不需要翻墙，番号自动补零适配，支持 dvd_id 和 content_id 两种查询方式
- **JavDB API 爬虫**：新增 `javdb_api` 刮削源，走 JavDB 镜像站 HTML 直连，不用 CF 代理，带演员名简繁转换和异体字修正（筱→篠、穗→穂等），可选镜像站地址
- **MissAV免防护墙爬虫 missav_api**：原MissAV爬虫常被防护墙挡住；现在多了一条免防护墙通道，不用费力绕墙也能直接刮到它的影片信息

### 新增功能

- **界面缩放比例配置**：在"设置 → 界面外观 → 高分屏缩放"设置区域新增缩放比例下拉框，支持"跟随系统"/80%/90%/100%/125%/150%/175%/200% 共 8 档选项（含非整数倍缩放）。选择非默认值时通过 `QT_SCALE_FACTOR` 环境变量（Qt6 原生机制）精确控制界面缩放，解决高分屏字体过大或过小的问题，并可配合暗色模式使用。保存后重启软件生效
- **内置 CF Bypass（零配置）**：新增"启用内置 Bypass"选项，勾选后 MDCx 自动在后台启动本地旁路服务（基于隐身浏览器），无需手动搭建外部服务。
- **新增设置项**：`cf_bypass_auto`（bool，默认 false），与外部 `cf_bypass_url` 互斥，地址为空时方能启用本地服务

### 刮削系统

- **四种刮削模式**：正常模式（全新刮削：扫描→刮数据→下图片→生成NFO→重命名→移动）/ 整理模式（仅归类文件，不下载图片不生成NFO）/ 更新模式（调整已有文件的目录结构）/ 读取模式（维护补刮，4个独立选项自由组合）
- **字段级优先级配置**：每个字段（标题、简介、演员、海报、评分等）可独立配置来源网站顺序和翻译开关，不同刮削类型还可设置不同的字段优先级
- **刮削模式**：支持 info（信息优先）、speed（速度优先）、single（单站快速）三种模式
- **刮削类型独立配置**：有码/无码/FC2/国产/欧美/素人每种类型可分别设置网站源列表
- **马赛克标准化**：自动将各类标签归一化为有码、无码、无码破解、流出、无码流出、国产
- **标签优先级系统**：基于 info_database.xlsx 的标签优先级排序，优先级标签→系列标签→其他标签

### 网络与反爬

- **CF Bypass 双模式**：支持 Mirror 模式（外部 bypass 服务代理请求）与 HTML 模式（调用 bypass 服务 `/html` 端点）
- **域名级独立限流**：每个网站独立令牌桶限流，默认 8 req/s，失败自动退避重试（403/429/500/502/503/504）
- **连接池管理**：三级连接池（HostPool → ConnectionPool → Session），域名级并发控制，Session 热更新，空闲自动回收
- **网络连通性检查**：内置一键测试各网站可达性工具
- **软链接支持**：可选择不移动原文件，创建软链接到目标目录

### 界面与工具

- **暗色/亮色主题切换**：内置完整双主题支持
- **海报裁剪工具**：图形化界面，鼠标拖拽选择裁剪区域，支持 2:3 标准比例
- **缺失文件检测**：检查媒体库中哪些文件缺失
- **成功/失败文件列表**：自动记录处理结果，支持断点续刮
- **多CD分集支持**：多碟片文件自动合并为一条记录
- **额外剧照处理**：自动下载多张剧照并管理副本
- **图片修复**：自动修复下载的图片（尺寸、格式等）
- **24 个命名模板字段**：番号、标题、演员、系列、制作商、分辨率、编码等，Jinja2 条件渲染
- **演员 NFO 生成**：生成 Kodi 兼容的演员信息文件（.actors 目录）
- **内置资源管理**：演员数据库、ASIN 数据库、NFO 信息数据库、字体等资源统一管理

### 配置系统

- **配置自动迁移**：旧版 INI 格式配置文件在加载时自动转换为 JSON 格式
- **配置热切换**：修改配置后自动生效，无需重启
- **敏感字段脱敏**：API Key 等敏感字段在导出时自动替换为 `***`

### 修复

- **网络标签页按钮重叠**：修复了设置页面里网络标签页的控件叠到一起、显示不全的问题，调整了各区域的高度和位置
- **Windows 下启动崩溃**：修复了 Windows 版打开时因 `topLevelItem(1)` 为空导致闪退的问题
- **R18.dev 补零位数**：番号标准化从 3 位补零改为 5 位，跟 R18.dev 数据库实际格式一致
- **fc2cmadb 演员数据爬取修复**：Inertia.js Deferred Props 导致的演员数据缺失问题。修复逻辑改为 Inertia JSON 解析后若 actresses 为空则回退到 HTML table 解析补充，同时增强 Inertia partial reload 请求头（注入 X-Inertia-Version 和 X-XSRF-TOKEN），解决已登录但爬不到演员的问题
- **fc2ppvdb Cookie 检查优化**：域名迁移至 fc2cmadb 后，Cookie 检查不再依赖 `fc2ppvdb_session` 关键字
- **刮削失败标题被日志污染**：修复 `main_window.py:1180` 中刮削失败后标题回退到 `LogBuffer.error().get()` 的问题——该函数会跨任务聚合其他任务的 TMDB 演员处理日志（如 `[演员数据库] 已新增 ... 并写入 tmdbid=...`）作为标题。改为使用文件名兜底
- **刮削过程更稳**：修好了多个任务同时刮时偶尔"串数据"的老毛病，演员信息写入也更省系统资源
- **修好 30 个第三方库的安全隐患**：把软件用到的外部工具库都升级到安全版本，整体更安全

### 改进

- **绕过网站防护墙更稳更快**：后台服务重写，启动不发呆、不卡死；安装包里直接带好隐身浏览器，装完即用，不用额外下载和配置
- **界面缩放优化**：放宽 Windows 窗口最小尺寸限制（从硬锁定 1089x700 改为 QSize(850, 550)），解决 1920x1080 125% 缩放下界面过大且无法缩小的问题

### 工程质量

- **推送前自动跑测试**：新增 pytest 推送前自检，`uv run check` 会自动执行 ruff 格式检查 + ruff 代码规范 + pytest 单元测试，三项全过才能推
- **新增一批测试用例**：R18.dev 14 个测试 + JavDB API 18 个测试，覆盖番号解析、字段映射、搜索匹配等工作

### 其他

- 软件内"使用说明"的内容已更新，过时的信息换成了最新的
- 新增一批自动测试，防止上面的问题以后又冒出来

## v1.4.0 (2026-07-07)

### 新增功能

- **Bing 翻译引擎**：新增 Bing 翻译选项，免费免配置，与 Google 一样自动爬取翻译接口，支持中/英/日互译
- **无码官网爬虫**：official 源扩展支持 Caribbeancom、HEYZO、1Pondo、Pacopacomama、10Musume 五个无码官网，番号自动路由到对应站点
- **official 官网前缀路由**：FNS/FALENO 与 DLDSS/DAHLIA 番号前缀自动委派给对应的子爬虫，扩大官网覆盖范围
- **fc2ppvdb 适配 fc2cmadb**：基础 URL 迁移至 `fc2cmadb.com`，新增 Inertia.js JSON + HTML 双模式解析，不再依赖旧版 fc2ppvdb XHR 接口

### 修复

- **avsex 更新修复**: 兼容 /cn/ 简体中文页面，修复 title/actor/tag/outline/extrafanart XPath 提取
- **iqqtv 标题清理**：去除标题末尾的 `caribbeancom_番号` / `1pondo_番号` 等站点前缀，避免污染无码影片标题
- **fix**: 图片简化命名(poster.jpg)在 skip_reorganize 和不移动文件路径下被忽略

## v1.3.3 (2026-06-23)

### 修复

- **xcity 刮不出中文**：修复了 xcity 刮出来全是英文的问题（加了请求头让网站返回繁体中文，再自动转成简体）
- **多任务同时刮会串数据**：修复了同时刮多个影片时，xcity 的数据会串到别的影片上的问题
- **预置4个默认代理**：amazon.co.jp、m.media-amazon.com、xcity.jp、dmm.co.jp 保障正常刮削 dmm、xcity及下载日亚高清封面

### 日志精简

- **日志去重**：同一行重复的日志不再刷屏了
- **去掉没意义的"(old)"日志**：之前每个文件都会刷"Poster done! (old)"这类消息（意思是"文件已经有了，跳过下载"），现在不显示了，日志减少了将近一半
- **报错提示不再重复弹**：图片下载失败时，"去设置里勾选xxx"的提示只出现一次，不再日志和错误提示各出现一次
- **翻译跳过不再逐行输出**：如果多个翻译引擎都不可用或跳过，现在汇总成一行显示，不再每个引擎占一行

### 日志合并

- **Poster 裁剪日志合并为一行**：以前裁剪海报时先输出"开始处理"，再输出"用了什么策略"，现在合并为一行，信息量不变
- **Poster 直复制缩略图日志合并**：策略说明和完成报告合并为一行

### 开发者工具

- **添加类型检查工具**：新增 pyright 配置，后续开发时能自动发现潜在的类型错误，减少发布后出问题的概率

## v1.3.2 (2026-06-22)

### 功能增强

- **刮削速度优化**：图片下载改成并行模式，缩略图下载完后，海报、剧照等会同时下载，不用排队等了
- **演员 TMDB ID 查询加速**：从 TMDB 查演员信息时，多个演员同时查（以前是排着队一个一个查），补演员改名翻译和网址也合并到一块写入硬盘，减少重复读写

### 界面调整

- **代理设置更清晰了**：原来的"不使用代理"改成了"使用代理"。现在只对你填进去的网站走代理，其他网站默认直连，不会出现代理影响国内网站的尴尬。默认预填了 `amazon.co.jp` 和 `m.media-amazon.com`

### 修复

- **Excel 字体大小不一致**：修复了往演员数据库和 Amazon ASIN 数据库添加新数据时，字体默认变成 12 号，和原来 11 号不统一的问题

## v1.3.1 (2026-06-20)

### 新增功能

- **新爬虫：JavDB APP版接口**：新增 `javdb_app` 刮削源，走的是 JavDB App 的接口，有码/无码/素人/FC2/欧美都能用，配置里对应的分类已默认加上

### 修复

- **欧美影片刮着刮着就超时**：修复了一个代码缩进错误。以前日系番号（如 `SSNI-111`）正常，但欧美番号（如 `Viv-thomas.24.12.20`）因为名字里带点号，程序错误地进入了"等待同番号"的死循环，干等 300 秒后超时报错。现在欧美番号也能正常刮了

### 界面调整

- **可用网站列表刷新**："可用网站"弹窗和"指定网站"下拉框现在和实际注册的爬虫保持一致，移除了已停用的 `avsex`、`love6`
- **无码分类编辑框不再出现有码站**：`javlibrary`、`libredmm`、`dmm_api` 不会再出现在无码的编辑网站对话框里

### 日志优化

- **分隔线不再用满屏 emoji**：以前每个任务开始和结束用 50 个连续 emoji（`👆`×50、`👇`×50）做分隔线，在某些电脑上显示为乱码方框，且日志文件体积巨大。改为 40 个等号 `====`，清爽多了

## v1.3.0 (2026-06-18) 重磅更新

### 新增功能

- 演员日文名更准了：以前填演员表用的是搜索用的中文名，现在改用 TMDB 返回的日文原名（像"三上悠亜"这种）
- 自动补演员网址：刮削完会自动检查哪些演员有 TMDB ID 但没网址，用日文名去 LibreDMM 找到网址填上
- 重磅更新,读取模式下，向已刮削的影片的NFO中补全写入演员tmdbid
- 前提条件：
  - 1.设置网络页面填入TMDB API KEY（没有的要去TMDB申请）
  - 2.设置NFO页面勾选"为演员写入TMDB ID"
  - 3.设置刮削模式为选读取模式，并勾选"允许更新 nfo文件"
  - 4.TMDB上要有这个演员的信息资料
- 注意：如果不想在补全演员tmdbid后，改变nfo中的演员名，请不要勾选设置翻译页面的"使用演员映射表翻译演员"
- 好消息：AVdb的LEO、龙王大佬们在持续补充 TMDB 女优资料中，lsj可以定期用读取模式去获取新增加女优的tmdbid了，不用重新刮削

### 读取模式改进

- **选项更灵活了**：4 个选项现在互不绑定。可以只勾"有 NFO 时更新"不勾"更新 NFO"，就只整理文件不改 NFO；也可以只勾"更新 NFO"不勾"有 NFO 时更新"，就只改 NFO 内容不挪文件

### 修复

- **NFO 里的 `<![CDATA[...]]>`** 改用正规解析，不会再因为内容里恰好有 `]]>` 而出错
- **正则表达式安全**：文件名中的特殊字符会先转义再匹配，不会崩
- **并发请求异常**：演员名查询时如果某个请求出错，不会让整个任务崩溃
- **被悄悄吞掉的错误日志**：演员数据查询中隐蔽的异常现在会写入日志

## v1.2.1 (2026-06-17)

### 修复

- 修复传统窗口模式下（未勾选"隐藏边框"），点击原生标题栏关闭按钮无响应问题
- 修复反序设置导致已有超链接单元格样式标记丢失

### 功能增强

- 完善 LibreDMM 演员链接自动补全功能
- xlsx 冻结窗格从 `A2` 改为 `B2`，同时固定表头行和第1列（番号列），横向滚动时始终可见
- 传统窗口模式下，点击关闭按钮同样遵循 `HIDE_CLOSE` 配置，支持"关闭时隐藏到系统托盘"

### UI 改进

- 更新设置翻译页面提示词，反映 xlsx 数据库格式和 TMDB 自动填充功能

## v1.2.0 (2026-06-16)

### 架构改进

- 将 `_read_actor_db_xlsx` 及列常量从 `tmdb_actor.py` 迁移至 `resources.py`，彻底消除模块初始化阶段的循环导入依赖

### 修复

- **#consts.py** `IS_DOCKER` 改为检测 `/.dockerenv` 文件，避免 Linux 桌面环境误判为 Docker
- **#number.py** `get_number_first_letter("")` 加空字符串保护，防止 `IndexError` 崩溃
- **#tmdb_actor.py** `_tmdb_request()` curl_cffi 分支补上 `follow_redirects` 参数，统一两种 HTTP 后端的重定向行为

### 功能增强

- **#file_crawler.py** `_normalize_release_value()` 增加 `YYYYMMDD` 无分隔符日期格式兼容
- **#tmdb_actor.py** 演员数据库首次发现为 `None` 时自动重试加载（延迟加载兜底），减少不必要的 TMDB API 请求
- **#tmdb_actor.py** 对 `update_actor_db_row()` 增加 `asyncio.Lock()` 防止并发写 xlsx 导致文件损坏
- **#resources.py** `reload_actor_db()` 文件不存在时不再重置 `actor_db` 为 `None`；异常时恢复旧值保留缓存；异常信息同步写入主日志和 traceback 日志

### 代码精简

- **#resources.py** `_get_mark_icon()` 7 处重复的 if-not-isfile-copy 合并为数据驱动循环
- **#number.py** FC2 / HEYZO 番号提取两个几乎相同的 elif 分支合并为一个，区分前缀和最小位数
- **#crawlers/** 12 个爬虫文件各自定义的 `split_csv` 函数统一为 `crawlers/base/types.py` 的共享函数，各文件 import 使用
- **#pyproject.toml** 添加 `[build-system]` 段，符合 PEP 517/518 打包规范

### 线程安全

- **#log_buffer.py** `all_buffers` 字典所有读写操作增加 `threading.Lock` 保护，消除多协程并发时字典损坏风险

## v1.1.0 (2026-06-13)

### 新增功能

- **Minnano-av 演员信息刮削源**
  - 新增 `minnano_crawler.py` 模块，支持从 みんなのAV 网站抓取演员信息
  - 支持中文→日文演员名映射（通过 `actor_database.xlsx` 查找日文原名后再搜索）
  - 实现模糊搜索匹配策略：精确匹配优先，其次多字符公共子串匹配，最后五十音回退搜索
  - 详情页加了标题核对，避免匹配到错误的演员

- **Emby 演员信息增强**
  - 在 Wikipedia 之前优先查询 Minnano-av 数据源，补充 Emby 演员元数据
  - Minnano-av 缓存文件 `minnano_cache.xlsx` 集成，避免重复请求
  - 缓存表头冻结、数据行全边框、URL 超链接，便于用户手动审查

- **Gfriends 头像本地仓库**
  - UI 新增"Gfriends 设置"区域：可以选择本地仓库路径、点按钮更新（拉取最新头像）、显示最后更新时间
  - 有本地仓库时优先从本地读取，不联网；本地没配置时才从 GitHub 网络下载
  - 更新按钮在没选路径或正在更新时禁用，防止误操作
  - 保存配置时，如果本地和网络都没填会弹窗提醒

- **Gfriends 头像升级：AI 修复版优先**
  - 找Gfriends 头像时优先用 `AI-Fix-名字.jpg`（AI 修复增强版），再找普通版

- **搜索链接中文兼容**
  - Graphis、Minnano-av、Wikidata 搜索时，演员名字自动做编码转换，解决日语名字搜索失败的问题

### 配置变更

- 新增 `gfriends_local_path` 配置项：填本地 Gfriends 文件夹路径即可启用本地模式

## v1.0.0 (2026-06-11)

MDCx-DIY 首个正式发布版，基于Hazard804改良的mdcx项目制作，对前辈表示衷心感谢！！！

### 刮削引擎

- 40+ 网站爬虫（有码/无码/FC2/国产/欧美）
- 新增 libredmm 刮削源（可刮削dmm下架影片）
- GenericBaseCrawler 统一框架 + 上下文隔离
- 智能番号识别与自动分类（用户预定义）
- 异步并发架构（asyncio + 渐进式任务调度）
- curl-cffi 浏览器指纹伪装

### TMDB 演员

- 新增 NFO 女优 TMDB ID 功能
- NFO 女优 TMDB ID 写入（需在 NFO 设置勾选 + 填入 API Key）
- 日文原名搜索，日本出生地 + 女性/未指定性别 + 精确名匹配过滤
- 多候选按 popularity 排序取最优，失败不阻塞刮削
- 令牌桶限流器（3.5 req/s，突发 10），并发 3 查询
- TMDB adult 候选自动跳过，搜索候选数优化为 5
- actor_database.xlsx用于nfo增加tmdbid和演员映射功能，反向搜索 + 增量写入，已预置部分女优数据，后续随软件使用动态更新（新演员若TMDB有数据就在表中追加数据，表中演员若TMDB数据更新，表中相关数据会追加）
- 超链接一致性校验与自动修复

### Amazon 高清封面

- ASIN 条码识别 + 三层搜索策略
- 封面 poster 固定 1500 尺寸（平衡质量和大小）
- 新增Amazon ASIN 缓存功能，通过Excel 缓存（amazon_asin_database.xlsx）
- 缓存去重逻辑，保护高置信度数据
- ASIN 缓存Excel随软件使用动态追加（同个影片二次刮削时不用再去Amazon查找，直接用表中数据下载高清封面）

### 数据源迁移

- actor_mapping XML + TMDB 缓存合并为 actor_database.xlsx
- mapping_info.xml 迁移为 info_database.xlsx
- 内置 xlsx 数据库，支持表头冻结，筛选、超链接等，用户可自行编辑或通过超链接审查数据

### 代理与网络

- HTTP/SOCKS5 代理配置
- 新增"不使用代理"网站选择器：40+ 刮削源下拉快速选择，智能域名匹配
- 默认 api.tmdb.org 不走代理

### 元数据与媒体

- NFO 生成器，30+ 字段，兼容 Kodi/Emby/Jellyfin
- 多语言翻译（Google/Bing/百度/DeepL/DeepLX/LLM 六引擎）
- Jinja2 命名模板引擎
- OpenCV 人脸检测智能裁剪
- 海报/背景图/预告片自动获取
- 字幕管理与缺失检测
- Emby/Jellyfin 演员信息补全 + 头像同步

### 界面与工具

- PyQt6 桌面图形界面
- 命令行工具（crawl、gen_enums）
- 构建工具链（build、bump、changelog、check）

### 工程质量

- 70+ 个测试文件覆盖核心模块
- CI：ruff format + ruff check
- Release：macOS DMG + Windows EXE
- 新增29 篇技术文档（架构、模块、API、迁移指南等）
