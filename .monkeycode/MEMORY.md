# 用户指令记忆

本文件只记录长期有效的行为规范、构建发布流程、排错方法和环境约束。项目实现细节以代码、测试和文档为准。

## 协作与质量

- Date: 2026-08-29
- Category: 工作流协作
- Instructions:
  - 简体中文回复；面向小白说明按"现象和影响 → 原因 → 可执行步骤"组织；日期时间一律用北京时间 (UTC+8) 表述并显式注明，避免歧义。
  - 改动前说明内容与原因；用户明确要求提交/推送后才执行，绝不擅自操作。直接在当前分支操作。
  - 每次代码改动后跑 `uv run quick-check`；提交前跑 `uv run check --skip-hook-install` 并确认退出码。仅改 `docs/*.md` 或本文件时只需 `git diff --check`。**全绿判定必须"退出码 + 显式 grep 错误行"双确认**：`grep -E "\.py:[0-9]+: error|Found [0-9]+ error"` 无输出才算过——H2 提交时 mypy 错误行被 `tail` 截断、退出码 grep 又漏检，误判全绿推上去 CI 连挂三次（2026-08-30 教训）。`scripts/` 下的脚本同样在 check 范围内（ruff format/check），写完临时脚本入库前必须先格式化。
  - 提交前必看 `git status` 全部未跟踪文件：程序运行时残留与脚本中间产物（如 `_failed.json`、`amazon_asin_manual_review_*.xlsx`）不得 `git add -A` 入库，应先 `.gitignore` 排除再单独清理（2026-08-27 误提交后补救的教训）。
  - 不装 pre-commit；提交前更新 `docs/changelog.md` 当前版本条目并合并同类。**版本号归属用户**：不得擅自新开版本号段落（如 v2.0.8），条目一律追加进当前进行中的版本小节（2026-08-28 用户指正）。
  - 站点/爬虫/配置改动须同步检查：UI 文案（启动文字 main_window.py、.ui）、README、`docs/*.md`、爬虫总数（`crawler_names()` 长度）、**`config/migrations.py` 旧值清洗**。删站点漏写迁移的后果是旧配置 pydantic 校验整体失败 → 配置被写入 `_failed.json` 且界面回写被跳过，用户表现为"保存不生效"（2026-08 删 15 站漏迁移，一个月后才由议题 #55 带出）。
  - 文档/UI 中写死数字或清单前必须先 grep 代码核实，禁止凭记忆。高频漂移锚点（2026-08 核查实证）：默认网站源顺序（`config/models.py` ↔ `resources/config/default_config.json`，`test_config_conversion.py::test_config_default_site_priorities_follow_current_frontend_defaults` 锁定，改注释勿动枚举）、代理域名列表（`Config.proxy_sites`）、命名变量表（`core/naming/fields.py::FIELD_DESCRIPTIONS`）、设置 Tab 名（tabWidget.setTabText）、水印行为（`MarkType` 徽标+角落轮转，无文字水印）、字段优先级数（`manual.py::REDUCED_FIELDS`）、演员库列（`resources.py::DB_HEADERS`）、指纹池（`network_fingerprint.py`，默认 7/Amazon 6，无令牌桶限流）、主窗口行数（`wc -l controllers/main_window/*.py`）。
  - **长时间运行任务的标准做法**（2026-08-28 用户强调）：① 一律用 `background_terminal_create` 建后台终端执行，不许用普通 bash；② 必须实现断点续传（checkpoint state 持久化到磁盘，重启后从断点续跑）；③ 分批处理，批间落盘；④ 用外层 wrapper 每 50 分钟自动重启进程（规避云环境超时杀进程）；⑤ 执行期间监测进度，定期主动汇报，用户询问时能立即给出。**判进度看 state/批次产物文件，别看后台终端日志**——wrapper 外挂 `tail` 管道时子进程 stdout 全缓冲，日志可能长时间 0 字节造成"卡死"假象（libredmm 抓取实测：state 与 batch 正常推进而终端日志空）；进度落盘文件（progress json）按小间隔写，供随时汇报。

## GitHub 议题处理

- Date: 2026-08-29
- Category: 环境配置
- Instructions:
  - `gh` 自带 token 已失效（`monkeycode-ai[bot]` invalid）。正确姿势：从 git credential helper 取 token 传 `GH_TOKEN` 走 `gh api` —— `TOKEN=$(printf "protocol=https\nhost=github.com\n\n" | git credential fill | sed -n 's/^password=//p')`，再 `GH_TOKEN="$TOKEN" gh api repos/<owner>/<repo>/issues/<n>`。`gh api user` 会 403（integration 无该权限）但仓库议题读写正常，不要据此判定 token 不可用。凭据值禁止回显到聊天或落盘。
  - 读议题正文/评论优先 `gh api`。退化到抓 GitHub 网页 HTML 时，评论正文要从内联 JSON 的 `"body"` 字段提取（`comment-body markdown-body` 类名已不存在）；未认证直连 `api.github.com` 会撞 IP 级 rate limit。
  - 回帖用 `gh api ... -F body=@文件` 传 Markdown 文件（**注意：必须用 `-F`**，不是 `-f`；`-f` 是 raw-field 会原样发送，`@/tmp/xxx.md` 会作为字面值发送而不是读文件内容——真机踩过，议题里出现 `@/tmp/...` 字面值而非正文，see #56 两次）。
  - **BUG 规避传统**：发送回帖后检查 `gh api --jq '.body' | head -1` 验证首行有内容不为 `@/...` 路径，才水准可信。
  - 关闭议题的判断标准：修复完整且用户明确要求才 `-f state=closed -f state_reason=completed`。根因未完全查清时保留 open，回帖如实写明"已修的部分解释了什么、解释不了什么"，并给出需报告人补充的具体信息（日志文件、进程内存数值、复现操作序列、特征文件是否存在）与已排除的假设清单，避免对方往错方向猜。不硬套一个原因去凑完整叙事。
  - **CI 失败排查**：`gh api repos/<owner>/<repo>/actions/runs?per_page=N` 列运行 → `runs/{id}/jobs` 用 jq `select(.conclusion=="failure")` 定位失败 job → `actions/jobs/{job_id}/logs` 拉全量日志后 grep `\.py:[0-9]+: error`（直接在线 grep 常拿空，先落盘再 grep 稳）。注意失败的 run 有重跑后同 head_sha 会新旧两条记录，看最新一条。

## 排查与本地验证

- Date: 2026-08-29
- Category: 排错调试
- Instructions:
  - **仓库根 `config.json` 是脏配置**（含已删站点值），`manager.load()` 遇校验失败会走 except 分支保留旧配置、不调 `_replace_config`。拿它写验证脚本会看到"一切正常"的假象。验证配置加载/网络栈相关行为须用 `Config()` 默认配置写临时文件再指 `manager.path`。
  - 泄漏/累积类问题先写最小复现脚本量化再下结论：统计 `gc.get_objects()` 中目标类存活数、事件循环 `asyncio.all_tasks()` 未完成数，跑 N 轮看是否线性增长。必须做对照实验区分"每次操作都泄漏"与"泄漏一次后被钉住"（议题 #55 靠对照确认单纯点保存无害，必须先有一次停止刮削造成的租约泄漏）。
  - **行为修复一律"先写复现测试跑红 → 修 → 绿"**，缺一步都不算完成。修复后再做一轮反向审查（边界、调用点语义分类），2026-08-29 实证：C2 修完后未先红跑，审查才发现水印流程（`.[MARK].jpg` 落位）每次重刮留 `_conflict` 垃圾——31 个 `move_file_async` 调用点须分"素材移动（冲突保留，默认）"与"临时落位（覆盖期望，显式 `overwrite=True`）"两类，12 处落位点易漏。pytest-asyncio 是 strict 模式：async 测试文件顶部须 `pytestmark = pytest.mark.asyncio`，缺了报 "not natively supported"。
  - 结构约束类修复（要求某调用必须在/不在某条件分支内）用 AST 哨兵测试锁定位置，行为测试覆盖不到。写完必须拿**修复前的代码片段**反向喂哨兵确认能判定失败，否则哨兵可能恒真（先例：`tests/test_actor_mapping_decoupled.py`、`tests/test_issue55_memory_leak.py`）。
  - conftest 用 dummy 模块替换了 `mdcx.config.manager`、`mdcx.config.resources`、`mdcx.signals`，测试内无法 import 这些模块的真实类；需要检查其源码结构时直接读文件做 AST 解析。**写独立验证脚本时须在 import mdcx 前手工注入同样的 dummy**（`types.ModuleType` + `manager`/`resources`/`signal` 属性），否则 ImportError。
  - 用 subagent 做大范围根因排查时，要求它输出"已排除的假设清单 + 每条排除理由"，比只给可疑点更有价值——可直接写进议题回帖，也能防止自己重复走同一条死路。**subagent 标注"已验证"的结论同样不可直接采信**（2026-08-29 实证：22 项宣称 11 项编造/夸大——引用了不存在的方法 `_return_session`、死锁模型把两个独立线程池当成一个、描述了不存在的 API 签名）。自己修复前必须用独立复现脚本重现每一条，"半数编造"的审查报告曾导致整批修复被撤销重做（4fc9546→6a47ec2）。
  - 大范围多文件改动后撤回用 `git revert --no-commit <多个提交>` 合并成单个撤销提交，历史可追溯且不强推。

## 并发与网络库行为（实测实证）

- Date: 2026-08-29
- Category: 排错调试
- Instructions:
  - **curl_cffi 0.16 流式响应关闭语义**：`aclose()` 只 await 内部接收任务、会把剩余响应体全部拉完（实测提前放弃 4MB 响应仍阻塞 3.5s 拉满全量）；同步 `close()` 设 quit_now 立即中止（0.00s）。**中止流后该 session 的 `close()` 会抛库内 TypeError**（`curl_multi_remove_handle` 遇 `curl._curl=None`），但同一 session 的后续请求复用完全正常——真项目里 session 由连接池长期持有且 `_close_sessions` 有 suppress，故应"close 优先中止流"，session 关闭异常按噪声处理。涉及网络层关闭/清理行为改动前先看 `web_async.py::_close_response` 的注释与 `tests/test_stream_close_aborts.py`。
  - **asyncio 线程池归属事实**：全局 `AsyncBackgroundExecutor`（`mdcx/utils/__init__.py`）的后台事件循环有**独立的** default executor（线程名 `asyncio_0`），与主 loop 的 default executor（跑 `asyncio.to_thread` 的池）是两个池。判断"executor.run 嵌套 to_thread 会不会死锁"必须先实测两个池是否同一个——线程池隔离时不构成循环等待（2026-08-29 实证：subagent 宣称的裁剪死锁因此不成立，8 并发全过）。
  - **LogBuffer 任务树归因**（2026-08-29 引入）：写入按 `_ROOT` contextvar 归因落键，`create_task` 子协程自动继承、`to_thread` 线程内可见（ctx.run 语义）；兄弟任务在 `process_one_file` 入口 `new_root()` 切断继承。新增并发诊断日志时**不要**再按 task_id 做全局隔离/聚合的假设，改走 root 归因；不要回退到"get() 拼全局 all_buffers"的旧模式（会复现跨影片错误污染，`tests/test_log_buffer_tree.py` 锁定）。


## UI 开发与排错

- Date: 2026-08-26
- Category: UI 开发与排查
- Instructions:
  - 改 UI 先改 `.ui`（唯一权威源），再 pyuic 重生成 MDCx.py、`ruff format`、`tests/test_ui_structure.py`；禁手工改生成的 MDCx.py。
  - 主窗口全局绝对定位、无布局管理器：长文本 QLabel 用 wordWrap 并查 sizeHint，固定高度底部留约 60px 余量；scroll 内容走 CustomScrollArea.sync_content_min_height；新增顶层悬浮控件须纳入 resizeEvent 手动几何同步。
  - QComboBox 显示文本如要加装饰性后缀（如站点区域标签"（日本IP限定）"）：`addItem(icon, 文本含后缀, UserRole 纯值)`，所有消费点统一从 `currentData()/itemData(UserRole)` 取值，不能只改 DisplayRole 后缀留文本旧逻辑；信号 handler（如 `textActivated`/`currentTextChanged`）只收到文本时须 `split("（")[0]` 剥后缀。改动必查：所有 currentText/itemText/currentData 调用点、信号连接点、AllItems.index 匹配点。
  - 打包前逐页切 stackedWidget 审计边界溢出（scripts/check_ui_layout.py、tests/test_ui_geometry.py、test_main_window_startup.py）。
  - Qt 同名 API 重载签名不同（如 QLayout/QSplitter 的 setStretchFactor），改前先确认目标类签名；测试桩显式枚举属性方法，不用 __getattr__ 通配（生产代码可能依赖 AttributeError 降级）。
  - Onefile 无控制台异常用 faulthandler + crash/ 日志定位；GUI 日志走 signal_qt.show_log_text。
  - 删代码前检查赋值点、读取点、装饰器注册、延迟 import、动态工厂，删后重扫死 import 与零引用。

  - **议题 #62/#66 Qt 绝对定位 UI 缩放经验**（2026-08-30 实践）：`setGeometry()` 只改组件位置/尺寸，但**不触发子组件 resizeEvent**——须用 `widget.resize(w, h)` 让 Qt 消息传播 resize。tab container (QTabWidget/QStackedWidget) 的子页（page）resize 后，内部 scrollArea 仍保持设计器固定几何且不同步；修复时先 resize 容器自身再同步子组件（scrollArea），避免 setGeometry 不传递缩放的情况。offscreen 验证方法：构造 MyMAinWindow，调 resize(1920, 1080) 再 processEvents，检查每个 tab 的 CustomScrollArea 是否跟随变化；测试脚本里读源码验证记得 `open(..., encoding="utf-8")`（Windows 默认 charmap 会炸）。
  - **QStackedWidget resizeEvent 同步技巧**：stackedWidget 是嵌套 QTabWidget 的顶级容器，resize 时主动遍历所有 page 手动同步每个 page 内的 scrollArea/tabWidget 几何；这种工作无 layout 容器时， resize 子组件的尺寸需要通过 resize/setGeometry 处理，避免遍历 all children。子级 % 改动后，子级的 fixed-position scrollArea 会得到 resize（resizeEvent）不回传——必须由父级调用未活动页面 resize、scrollArea 等 child 一样 resize。
  - **议题 #68 休眠页修复模式（2026-08-30，提交 feae221）**：`QStackedWidget` 只把**当前可见页** resize 到自身尺寸，休眠页永远停在设计尺寸——"先缩放窗口再切页"时内部控件全按陈旧尺寸布局。修复模式（沿用 #66）：`currentChanged` 连接 `_sync_page_layouts`，同步函数先统一 resize 所有 stacked pages 再算内部几何（顺序敏感：基于 `page.width()/height()` 的计算必须发生在 page resize 之后）。同批修复：`show_hide_logs` 类硬编码 `resize(790, 418)` 会覆盖动态同步结果，一律改走统一同步函数；隐藏子控件时剩余控件要接管全部分区（日志下栏隐藏→上栏铺满整页）。
  - **PyQt6 测试 qFatal abort 排查经验（2026-08-30 实证）**：pytest 中 PyQt6 槽函数抛未捕获异常（如 AttributeError）会触发 Qt `qt_assert` 原生 abort（Fatal Python error: Aborted，栈里只有 QMessageLogger/qFatal 而无 Python 行号）——先检查 `QTimer.timeout` 槽与 conftest dummy 桩缺方法（当时 `_DummySignals` 缺 `get_log()` 使 `show_detail_log` 每次事件循环 abort）。防御：① 新增 Qt 窗口测试的 fixture 构造完立即停全部 QTimer（隔离无关副作用）；② 几何断言不需要 `window.show()`，隐藏窗口下 widget 几何同样有效且省去样式/资源路径副作用；③ conftest dummy 桩加方法时同步更新此文件注释。矩阵测试沉淀 `tests/test_window_state_matrix.py`（边框模式×尺寸×日志展开×切页 6 项）。
## 站点与网络

- Date: 2026-08-27
- Category: 排错调试
- Instructions:
  - 各站探测番号与收录依据见爬虫类注释；javdb 仅搜 FC2 需要 Cookie。
  - 站点 API 坑：missav_api Recombee 仅 POST；DMM Affiliate v3 ItemList 必需 site/service/floor 且 keyword 用 content_id 形态（ssis00200）；madouqu 域名发布页动态维护（web.py::get_madouqu_domains，24h 缓存）；madou_club 番号无横杠；parsel Selector.get() 遇纯 JSON 返回 dict，JSON 爬虫解析须兼容 str/dict/Selector 三态。
  - 已删 15 站（2026-08）：cnmdb/hdouban/mdtv/love6/kin8/giga/cableav/7mmtv/hscangku/fc2club/fc2hub（失效或 CF 成本高）+ jav321/fantastica（重复）+ dahlia/faleno（降级为 official 厂牌子爬虫）。恢复从 git 历史找回并重建枚举/注册/默认源。
  - 无码官网五站由 official_uncensored.py 统一路由，勿重复开发；均被墙需代理；其中 1pondo/pacopacomama/10musume 首页有反 bot 壳，但 dyn/phpauto movie_details JSON API 直通（official_uncensored.py::json_base_url 见 spec）。
  - 被墙站测试：`uv run python -m scripts.dev_proxy start|status|test <url>|stop`，起后等 10-20 秒测速再用；日本 IP 限制站（faleno/giga-web/mywife/mgstage）用 `--port 7891 --regions "jp|日本"` 起纯日节点。
  - devbox 环境限制：超时属云端限制≠站点死亡；getchu/iqqtv/madou_club/missav/xcity 需代理；avbase/javdb 等在免费代理下不稳是云端问题，用户本地多可直连；高频批量测试触发 CF IP 拉黑，失败换时段重试；连通性验证必须 curl_cffi impersonate 指纹；批量探测须校验 data.title 为真实字符串防假阳性。

## Windows 打包与发布

- Date: 2026-08-24
- Category: 环境配置
- Instructions:
  - 函数内延迟导入须同步加入 scripts/build.py 的 --hidden-import/--collect-all；改依赖/构建脚本/Release 工作流时逐项核对。
  - EXCLUDED_MODULES 中的 rich/typer 等只供构建或 CLI，GUI 运行期不得引用；Windows curl_cffi.libs 需显式 --add-binary。
  - Release Tag 纯数字 YYYYMMDD（check_version 做 int()），双平台构建显式传 Tag；scripts/*.py 顶部的 `# ruff: noqa: E402` 与探测 import 的 `# noqa: F401` 须保留。

## 并发与数据

- Date: 2026-08-24
- Category: 构建方法
- Instructions:
  - 文件间批量用 asyncio.wait(FIRST_COMPLETED) 滑动窗口，文件内多站点用 gather；网络请求不跨 executor loop 复用。
  - 后台协程统一 utils/qt_thread.py::run_in_background，不直接碰 QWidget，结果经 Qt signal 回主线程；新增后跑 scripts/check_thread_safety.py。
  - 出厂模板在 resources/userdata/，运行时数据在 manager.data_folder/userdata/ 勿混淆；devbox 代理 127.0.0.1:7890 可能无进程，排查网络临时关闭代理而不改产品默认配置。

## 日亚 ASIN 数据库校正

- Date: 2026-08-28
- Category: 排错调试
- Instructions:
  - amazon_asin_database.xlsx 是 ASIN-番号映射库，**以 ASIN 为唯一可信锚点**（ASIN 唯一，番号可由多个搜索误挂到同一 ASIN）。冲突形态：同一 ASIN 挂多个番号且各行标题相同。
  - **冲突裁决梯队**（已实测校准，2026-08-30 修订）：① `_cover_similarity` 图像相似度以 **DMM 官方图为裁判**最可信——竖版 ps 直接用、横版 pl（800×499 套图）必须 `_cut_thumb_right_image` 裁右半再比；② javdb/javbus 的 cover_url 是重压处理图，与 DMM 原图相似度仅 0.5~0.7，**不可作严格裁判**，只可作低置信参考（放宽阈值 score≥0.60 且不计入匹配率）；③ 标题文本比对不可用。**注意 `_cover_similarity` 返回三元组 (score, hash_sim, hist_sim)，生产软校验判定是三阈值同时满足：score≥0.82 AND hash≥0.86 AND hist≥0.70**——写验证脚本时当单值用会全部误判（2026-08-30 实测踩坑）。脚本沉淀 `scripts/clean_asin_db_conflicts.py`。
  - **裁判图源优先级**（2026-08-30 实测修订，旧 thejavdb 链已废弃——生产 `web.py::_load_dmm_official_reference` 早已改用 DMM 高清直链）：① **DMM 直链**（`dmm_direct.build_aws_poster_candidates/cover_candidates`，含学习表前缀）严格判定主力，60 条抽查中 50/60；② **libredmm** `/movies/{番号小写带横杠}` 页面给真实 DMM 大图 URL（pl ~150KB 中清 + ps ~12KB 低清），对下架老片一击全中（补判 10/10），**价值在 cid 真值发现而非高清图源**；③ r18dev/javbus 兜底实测零出场可不留。libredmm 缺点：部分地区需代理，故优先把它**归纳成静态枚举知识**而非运行时依赖。
  - **DMM cid 结构规律**（2026-08-30 从 libredmm 真实 cid 实证修订，修正"content_id 一律 5 位补零"的旧认知）：cid = `{前缀}{系列}{数字}{变体?}`，四要素——① 前缀按系列映射（lid→24、mild→84、hmd→143、hmpd→41、yst→540、amz→28、sprd→18、mdtm/mkmp→84，现有静态表 `_PREFIX_GROUPS`/`_COMMON_PREFIXES` 缺大量老片系列）；② **数字形态双态**：5 位补零（digital 新片）与 3 位原样（mono 老片，n≥100）**同系列可并存**（mild: 00953 与 781 都真）；③ **双路径**：`pics.dmm.co.jp/digital/video/{cid}/` 与 `/mono/movie/adult/{cid}/` 各占约半，枚举须双路径都试；④ 变体后缀（如 84mdtm388dod 的 dod 企划）**无需枚举**——不带后缀的 84mdtm388ps 同样存在。四层补全后 10 条下架老片直链 10/10 命中。
  - **libredmm 全站数据源与归纳集成（2026-08-30 完成并集成，提交 e0c98b7）**：`/movies?page=N` 每页 30 条按字母序、**列表页缩略图 src 直接含完整 DMM cid URL**（`<a href="/movies/番号"><img src="...cid...ps.jpg"/>` 同元素），翻页即批量取「番号↔cid」；番号与 cid 字母部分不要求一致（厂牌自定义编号，如 000_339↔n_630aps176）。全量抓取 23472 页 588,532 对（脚本 `crawl_libredmm_full.py` 与 161 批产物在 /tmp/opencode/），归纳三轮迭代：① combo 结构（prefix×cid_series 全枚举解前缀截断歧义，VRKM→v+rkm）；② 数字位数集合（存在 pad6 如 `5642hodv010006`，硬编码 3/5 位不够）；③ other 阈值放宽 50%（重编号条目落白名单），最终 9627 系列 96.5% 直构命中。**集成时拦下的系统性风险（最重要教训）**：libredmm 同名番号被 mono 老厂牌占据（SSIS-001 在其记录中是老厂牌 `k9ssis001` 而非 s1 的 `ssis00001`），IPX/SONE/MIDV/CAWD 等 8 个高频系列直接注入会全部污染候选顺序——安全过滤仅保留 digital 路径 + 数字一致 + 无变体 + 弃用与生产静态表（`_PREFIX_GROUPS`/`_SPECIAL_THRESHOLDS`/`_EXTRA_PREFIXES`）冲突系列与全部 mono 数据，最终 6613 规则系列 + 10507 白名单落地 `resources/userdata/dmm_cid_routes.json`（1.1MB 随包），`dmm_direct` 惰性加载，`test_high_frequency_series_first_candidate_unchanged` 等 12 项测试锁定。**外部归纳数据接入生产前必须先在高频样本上做候选顺序回归——覆盖率数字（96.5%）会掩盖顺序污染**。后续增量：上游每周新增番号可定期重跑归纳刷新种子；学习表与种子并行无冲突。
  - 「一 ASIN 挂多个不同分集番号」多数是合集商品（BEST 8時間 类），各番号单集封面 ≠ 合集封面，图像法也救不了，属不可自动裁决类；all_match（同分 >0.82）才是"同一商品多番号发行"的正常情况。
  - 环境限制：DMM/fanza 地区锁（日本外 302 到 not-available-in-your-region），devbox 无法直连；日亚 dp 页 devbox 直连 404（amazon.co.jp 需代理/日本节点）；封面 OCR（tesseract eng）对日系封面效果差不可作依据。DMM 站点页面会下架但 CDN 图床不删对象（URE-018 网页端已下架，awsimgsrc/pics.dmm 的 ure00018 图仍 200），下架番号的参考图始终可按番号直构 cid 去碰。
  - DMM 图床占位图坑：pics.dmm.co.jp 对无效 cid 返回 200 + ~2.7KB 甚至 142B 垃圾体，单凭 check_url 的 200 会通过；真实封面再小也 ≥10KB。已在 `base/web.py::_validate_dmm_image_url` 加 <4096B 拒收。
  - tenhow.net 图床：图片按 ASIN 命名 `images/{ASIN}.jpg`（大图）+ icon_/s_ 前缀小图；条目 DOM 内 ASIN 图与 DMM cid 绑定，经 13 个冲突 ASIN 对 libredmm 实测 13/13 正确。**双向价值**：正向按 ASIN 免代理直接取图（T0 优先，404 再回退 Amazon）；反向凡页面条目里的图文件名都是可入库 ASIN，全站爬一遍即一次 ASIN 增量发现。2026-08-28 重爬全站收敛 **1903 页 / 36441 ASIN**（无冲突），结果在 `/tmp/opencode/tenhow_index_full.json`、页面缓存 `/tmp/opencode/tenhow_pages/`；旧索引 8126 条严重不全（旧脚本每批 50 页无新链接即整体退出，只抓 250/1903 页）已作废。另有 ~5388 条目只有 ASIN 无 cid，未来可用封面图像比对反查番号补库。
  - cid→番号清洗规则（与仓库 `_parse_number`/DMM 官方约定对齐）：cid 形态 `^(\d*)([a-z]+)(\d+)([a-z])?$` = 可选厂商数字前缀 + 系列字母 + 数字（content_id 5 位补零）+ 可选变体字母。番号 = `系列字母大写 + f"{int(数字):03d}"`（去前导零但至少 3 位：24ped00030→PED-030、13gvg00564→GVG-564、onsg00064→ONSG-064，**绝不**缩成 PED-30，旧库 tenhow 行此类错误写法待修）；末尾变体字母（b/c/f/r 等）视为同番号变体归并；去重比对一律用 (系列字母, int(数字)) 做 key 以兼容去零/补零两种存量写法；不匹配该形态的 cid 进「待人工」sheet 不猜番号。
   - 批量导入外部数据到 xlsx 前必须走 `save_asin_to_excel` 这类含去重逻辑的入口函数；直接 `ws.append` 会绕过同番号去重产生成批重复行（教训：tenhow 8094 行导入产生 699 完全重复行）。错配行处置规则：不删、不丢番号，移到「待修正」sheet 附原因保留待补，主表只留裁决通过的。
   - **HTTP 4xx 错误定位顺序**（议题 #56 教训）：先看【客户端实际发了什么】（headers/body/URL 构造完整？、条件分支是否被误判覆盖），再想服务端权限/角色/版本。同一函数内 `if _is_jellyfin_server(): 加鉴权 else: None` 的条件分支看似无害，对 Emby 就是"否"把鉴权头置 None → POST 全量 401——这类"条件头构造"在同函数多个调用点改一处漏一处的错误常见（`_is_jellyfin_server` 当时同名双调用点，一处修了另一处留）。**写回帖前先核对所有调用点的硬编码分支**，不要在未读完整数据路径的情况下把责任推给用户的服务端配置。
