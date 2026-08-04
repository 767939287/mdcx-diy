# 用户指令记忆

本文件记录了用户的指令、偏好和教导，用于在未来的交互中提供参考。

## 格式

### 用户指令条目
用户指令条目应遵循以下格式：

[用户指令摘要]
- Date: [YYYY-MM-DD]
- Context: [提及的场景或时间]
- Instructions:
  - [用户教导或指示的内容，逐行描述]

### 项目知识条目
Agent 在任务执行过程中发现的条目应遵循以下格式：

[项目知识摘要]
- Date: [YYYY-MM-DD]
- Context: Agent 在执行 [具体任务描述] 时发现
- Category: [运维部署|构建方法|测试方法|排错调试|工作流协作|环境配置]
- Instructions:
  - [具体的知识点，逐行描述]

## 去重策略
- 添加新条目前，检查是否存在相似或相同的指令
- 若发现重复，跳过新条目或与已有条目合并
- 合并时，更新上下文或日期信息
- 这有助于避免冗余条目，保持记忆文件整洁

## 条目

[面向小白的细致指导风格]
- Date: 2026-06-08
- Context: 用户希望我以编程能手、审核、修改和补全代码专家的方式长期协作
- Instructions:
  - 默认从全方位、多角度、深层次的角度审查和改进代码。
  - 面向小白解释问题，给出细致、可执行、易落地的建议。
  - 在发现风险、缺陷、遗漏时主动指出，并尽量给出修复方案和进行验证。

[提交推送工作流]
- Date: 2026-07-18 (合并 2026-08-03)
- Context: 用户要求每次改动代码和提交推送前必须征得同意，且推送前自动运行测试
- Category: 工作流协作
- Instructions:
  - 所有代码改动（新建文件、修改代码、删除文件等）必须先向用户说明改动内容和原因，获得同意后再执行。
  - 提交推送前必须先向用户说明要提交什么、推送到哪里，获得同意后再执行 `git add` + `git commit` + `git push`。
  - 本指令优先级高于此前所有"自动执行"类指令，改动代码和提交推送这两件事必须先问后做。
  - 用户同意推送后，`git push` 前必须自动运行 `uv run check --skip-hook-install`（ruff format --check + ruff check + mypy mdcx/ + pytest --tb=short -m "not network" -x + check_actor_db）。失败则修复后再推，不要强行推送。

[每次新会话自动安装 pre-commit 钩子]
- Date: 2026-07-17
- Context: 用户希望每次新会话开始时自动安装 pre-commit 钩子，无需手动执行
- Instructions:
  - 每次新会话开始时，自动执行 `pre-commit install` 命令安装 git hooks。
  - 如果 pre-commit 工具未安装，先执行 `pip install pre-commit --break-system-packages` 安装。
  - 安装完成后确认 `.git/hooks/pre-commit` 文件存在且可执行。

[环境 Python 版本升级到 >= 3.13.4]
- Date: 2026-07-17 (更新 2026-08-04)
- Context: 项目要求 Python >= 3.13.4（使用 type parameter defaults 语法），但沙箱环境默认只有 Python 3.11，无法运行测试和导入项目。2026-08-04 环境重置后工具链已变化。
- Category: 环境配置
- Instructions:
  - 项目只能 `uv run` 执行测试（`pytest tests/ --tb=short -m "not network"`），因为 sandbox 默认 python3 是 3.11，无法解析 3.12+ 的 `class Rename[TRaw = str, TNew = TRaw]` 语法。
  - 环境重置后 `/opt/python3.13` 与预置 `uv` 均不存在，按以下恢复：`pip install --break-system-packages uv` 安装 uv 到 `/usr/local/bin/uv`，再执行 `uv sync`（自动下载合适的 Python 并创建 `.venv`，2026-08-04 实际装到 python3.14，pytest/ruff 均可用）。
  - 跑 pytest 前若报 `ImportError: libglib-2.0.so.0 / libGL.so.1 / libEGL.so.1 / libfontconfig.so.1` 缺失，说明 PyQt6 系统库没装，执行：`DEBIAN_FRONTEND=noninteractive apt-get install -y libglib2.0-0 libgl1 libegl1 libopengl0 libfontconfig1 libqt6gui6 libqt6widgets6 libqt6core6 libqt6network6 libqt6xml6`。
  - 依赖安装后可以运行 `uv run pytest tests/ --tb=short -m "not network"` 验证。

[Windows exe 打包依赖约束]
- Date: 2026-08-03
- Context: 用户提醒后续修改需兼容 Windows 单 exe 打包发布场景（用户以单 exe 文件运行）
- Category: 环境配置
- Instructions:
  - 代码变更优先使用 Python 标准库，不主动引入新三方依赖。
  - 新增文件持久化路径应使用 `resources`/`userdata` 现有目录习惯，避免新增外部库。
  - 变更涉及打包入口或运行时依赖时，先确认打包脚本与 PyInstaller 打包配置仍能在 Windows 下正常启动。
  - 改动代码后，必须检查对单 exe 打包是否安全，按以下清单核对：
    - 新增/改动运行时 import 的模块，若属延迟导入（函数内 import）须确认已加入 `scripts/build.py` 的 `--hidden-import` 或 `--collect-all`，否则 exe 运行时报 `ModuleNotFoundError`。
    - 新引入三方依赖（如 aiohttp/aiofiles/lxml）若在 hidden-import 的模块顶层 import，PyInstaller 静态分析会自动收集；必要时补充 `--collect-all`。
    - 被 `EXCLUDED_MODULES` 排除的若干包（rich/typer/playwright 等）绝不能被 GUI 运行期代码引用，否则 exe 运行崩溃；排除前确认无运行期引用。
    - 检查 `.github/workflows/build-windows.yml` 与 `release.yml` 中的打包流程、hidden-import、chromium 缓存过期键（版本更新时 bump 缓存 key 末尾 vN）是否仍有意义。
  - 已知：排除 rich/typer 后，唯一使用它们的是独立 CLI 调试脚本 `mdcx/cmd/crawl.py`，它无 GUI 入口引用、不被打包，排除安全。

[UI 改动注意事项]
- Date: 2026-08-03（2026-08-04 更新）
- Context: 用户在多次调整工具页 UI（新增/重排 groupBox、增删按钮）时提出的约束；2026-08-04 在增高 actor_db groupBox 时补充
- Category: 环境配置
- Instructions:
  - UI 布局定义在 `mdcx/views/MDCx.ui`，改完后必须用 pyuic6 重编译生成 `MDCx.py`，命令：`/workspace/.venv/bin/python3 -m PyQt6.uic.pyuic mdcx/views/MDCx.ui -o mdcx/views/MDCx.py`，否则改动不生效。
  - 调整布局后必须验证 `import mdcx.views.MDCx` 可正常导入（UI 里有中文/多行 tooltip，编译易出错）。
  - 注意 tab/groupBox 重叠、遮挡问题：所有 groupBox 在 `page_tool` 的滚动区 `scrollAreaWidgetContents_gongju` 内是绝对定位（x/y/width/height），重排顺序要同时更新各 groupBox 的 y 坐标和滚动区 widget 高度（最后一块底部留 20px 边距），否则底部内容被遮挡。
  - **UI 结构有自动化测试**（`tests/test_ui_structure.py`，已挂入 `uv run check` 与 CI）：解析 `MDCx.ui` 检查 groupBox 同父容器不重叠/无负间距/不超滚动区、用户控件 objectName 唯一、`MDCx.py` 与 `MDCx.ui` 重编译同步。改 UI 后跑 `uv run check` 或 `uv run pytest tests/test_ui_structure.py -q` 即可自动验证，无需手写 Qt offscreen 几何检查脚本。
  - 增高某一 groupBox 后，必须连锁把**其下方所有兄弟 groupBox** 的 y 同步 +delta，并同步增高滚动区 widget 高度，最后做 Qt offscreen 几何验证确认两两无重叠。踩坑：曾只检查与紧邻下方 group 的空隙、漏了中间一个 group，导致 110px 重叠；下方 group 不止紧邻的那一个。
  - `MDCx.py` 虽由 pyuic 生成，但仓库版曾被另行整理格式。**规范流程**：改动一律先改 `MDCx.ui`，再用 `/workspace/.venv/bin/python3 -m PyQt6.uic.pyuic mdcx/views/MDCx.ui -o mdcx/views/MDCx.py` 重编译，最后 `uv run ruff format mdcx/views/MDCx.py` 对齐格式（可把 diff 从数千行压到几十行）。**不要手工修改 MDCx.py**——有 `tests/test_ui_structure.py::test_mdcx_py_in_sync_with_ui` 在 CI 把关，手工改 `.py` 不同步 `.ui` 会红。
  - **重编译会回退 MDCx.py 的手工文案**：pyuic6 用 `MDCx.ui` 里的旧文案覆盖 MDCx.py 中可能手工更新过的文本（曾遇到项目主页 `mdcx-diy` 链接、graphis 描述等被回退）。根治方式是把新文案**回写 `MDCx.ui` 源文件**，让 `.ui` 成为唯一权威源。另注意 pyuic6 会把输入路径写进头部注释，同步对比测试必须用相对路径编译。
  - 用 `findChildren` 做几何重叠/溢出检查时，comboBox 的 popup 内部子部件（QListView/QScrollBar/qt_scrollarea_viewport 等，坐标为 0,0/100x30/640x480）会误报为"重叠/溢出"，需排除这些 Qt 内部件；长文本 label 的显示完整性用 `fontMetrics().boundingRect(0,0,w,1e6,flags,text).height()` 与控件高度对比，横向用 `horizontalAdvance`。
  - 新增按钮后必须检查三处一致：`MDCx.ui`（定义）、`MDCx.py`（编译产物）、`mdcx/controllers/main_window/init.py`（信号接线：clicked 槽 + setText 防重入信号）。三条链路缺一按钮不生效或运行崩。
  - 按钮防重入模式：参见下方 `[executor.submit 与跨线程 Qt 安全]` 条目，使用 `executor.submit(run())` 而非 `executor.submit(asyncio.run, ...)`，且协程内不可直接 `setEnabled()`，必须通过 pyqtSignal 主线程恢复。
  - 删除旧按钮后要清理失联的 delegate/实现死代码，避免引用已删除控件导致 AttributeError。

[Onefile 环境调试要点：静默退出与日志通道]
- Date: 2026-08-03
- Context: 4 个按钮点击后程序直接退出（无提示、无事件查看器记录），用户反复打包定位不到；另一按钮点击后无输出误以为卡死
- Category: 排错调试
- Instructions:
  - PyInstaller onefile + `-w`（无控制台）环境下，Python 普通的 TypeError/AttributeError 异常会被静默吞掉——`sys.__stderr__` 不存在，`print()` 到空 stdout，`main()` 的 `except` 分支输出丢失，PyQt 信号槽异常调用 `sys.excepthook` 默认也输出到 stderr。最终表现是"程序直接退出"，被误判为 C 扩展 segfault。
  - 标准诊断三件套必须在 main.py 启动时注册：`faulthandler.enable()` 抓 C 层崩溃堆栈、`sys.excepthook` 写文件抓 Python 异常、`sys.stdout`/`sys.stderr` 重定向到文件抓 print 输出。日志文件写进 `MAIN_PATH/crash/` 目录（正常运行时无文件生成）。
  - 事件查看器没有崩溃记录本身就是关键线索——说明不是系统级 segfault（WER 会记录），而是程序正常退出（Python 异常导致 `sys.exit`）。
  - 另一个易混淆场景：工具内部日志走 `LogBuffer.log().write()`（只存内存），不走 `signal_qt.show_log_text`（GUI+文件）。用户看到"开始扫描"后无后续输出，以为卡死，实则是工具已跑完但日志通道不通。修复：所有工具内部日志输出必须走 `signal_qt.show_log_text`。检查项目其他只写 LogBuffer 不写 GUI 通道的代码。

[executor.submit 与跨线程 Qt 安全]
- Date: 2026-08-03
- Context: 修复演员库工具按钮时发现两处同类 bug：`executor.submit(asyncio.run, run())` 传参错误，以及协程内直接 `btn.setEnabled()` 跨线程操作 QWidget
- Category: 工作流协作
- Instructions:
  - `AsyncBackgroundExecutor.submit(coro)` 只接受单个协程对象，`executor.submit(asyncio.run, run())` 会报 `TypeError: takes 2 positional arguments but 3 were given`。正确写法：`executor.submit(run())`。`main_window.py` 的 `_run_actor_db_tool` 等和 `tool_handlers.py` 的 cover_backfill 两处同源 bug 曾因此修复。
  - 协程在 executor 后台线程事件循环执行，`btn.setEnabled()` / `setText()` 直接操作 QWidget 跨线程不安全。必须用 pyqtSignal 发到主线程执行。正确模式：按钮点击时主线程 setEnabled(False) + emit "运行中"，协程 finally 里发射 `pyqtSignal.emit()`（线程安全），主线程槽负责恢复 setEnabled(True) + setText。参见 `main_window.py:_run_actor_db_tool`/`_on_actor_db_finished`。
  - `tool_handlers.py` 里的函数是模块级函数（通过 `main_window.py` `from .tool_handlers import ...; pushButton_xxx_clicked(self)` 调用），`self._open_actor_db_file` 不会自动可用——必须确保方法存在在 `MyMAinWindow` 上，或完全不用 `self.xxx`。

[刮削并发架构参考]
- Date: 2026-08-03
- Context: 探索 actor_db_tool 并发提速时发现刮削已有成熟的滑动窗口并发
- Category: 构建方法
- Instructions:
  - 正常刮削（`scraper.py`）已经是两层并发：文件间用 `_run_tasks_with_limit`（滑动窗口，`asyncio.wait(..., FIRST_COMPLETED)` 渐进式调度，并发数 = 配置项 `thread_number`）；文件内用 `_call_crawlers` 的 `asyncio.gather` 多站点并发抓取。
  - 不要误以为刮削是串行的。慢可能是单站点超时拖慢整个文件，而非并发不足。
  - actor_db_tool 的可复用并发模式已从 `Semaphore+gather` 升级为滑动窗口（`mdcx/tools/actor_db_tool.py`），与刮削同构。后续新增异步批量处理工具时，优先采用滑动窗口模式而非 `Semaphore+gather`。
  - 滑动窗口优势：内存峰值低（不会同时存在全部协程对象）、取消响应快（最多等当前批次完成）、渐进式调度（大列表不会一次性创建海量协程）。

[演员/用户态数据双库结构与 AVdb 同步]
- Date: 2026-08-04
- Context: 为演员库引入 AVdb 演员映射同步并入库时，梳理清楚本地 actor 数据的分发与读写路径
- Category: 运维部署
- Instructions:
  - **两层 actor 库**：出厂模板 `resources/userdata/actor_database.xlsx`（git 跟踪，作为分发默认库，新用户首次启动复制到运行时目录）；运行时实际读写库 `manager.data_folder/userdata/actor_database.xlsx`（在 `mdcx/core/tmdb_actor.py:_get_db_path`），该目录默认被 git 忽略——改运行时库不会出现在 `git status`。用户态开发环境里 `manager.data_folder` 指向 `/workspace`，因此运行时库是 `/workspace/userdata/`，与出厂模板 `resources/userdata/` 是两份。
  - **改库要分清目标**：要「给用户实际用」改运行时库即可；要「进 git 作为新装默认」改出厂模板并提交。出厂模板已升级为 9 列全量 AVdb 合并库（25436 条，`COL_BIRTH_DATE=7`/`COL_BIO=8`，出生日期 `YYYY-MM-DD`/简介中文）。
  - **AVdb 同步幂等**：`sync_from_avdb(source, value)` 可反复跑——匹配后只填空缺、不覆盖本地已有值，第二次同源同步 `created=0`。匹配顺序 tmdbid 冲突并入 → jp → zh_cn → keyword（均 casefold）。keyword 合并做 casefold 去重保留首次写法。
  - **get_actor_data(name)**（`resources.py`）按名反查本地库，返回 `birth_date`/`bio`/`has_name`，非空即有、空即缺；是 Emby 补全等下游复用的统一查询入口。
  - **Emby 演员信息补全本地优先**：`emby_actor_info._process_actor_async` 在 wiki/minnano/ActressDB 兜底前先用 `get_actor_data` 查本地库，命中且简介非空即跳过外部来源，本地简介空才退回外部（生日仍取本地）；返回标志 bit3(值 8) 表示本地命中。

[openpyxl 删除行后 max_row 虚高与空行残留坑]
- Date: 2026-08-04
- Context: 重建出厂 actor_database.xlsx 清理空行时，`ws.delete_rows` 后 `max_row` 不变、空行"删不干净"，反复出现诡异现象
- Category: 排错调试
- Instructions:
  - **症状**：对历史遗留的老 xlsx（多次 openpyxl 增删改后），`ws.delete_rows` 逐行删空后重新加载，`max_row` 仍是旧值、空行依旧存在，即使 `diff` 对比磁盘文件确认已删。根因是行样式/格式残留导致 openpyxl 内部行号状态错乱，`delete_rows` 不清理样式。
  - **可靠方案**：不要试图用 `delete_rows` 清理大库空行。直接重建工作簿——读出全部非空行（`iter_rows` 过滤 `row[0] is None`），`Workbook()` 新建、`append` 表头+数据、重新设置样式/auto_filter/freeze_panes，再保存。重建后 `max_row` 精确等于数据行+1。
  - **删除数据行**（如 `clean_male_actors` 删男优）在**干净重建后的库**上正常，不会产生空行残留；历史脏库上才会踩坑。所以清洗逻辑本身没问题，库质量才是关键。
  - `check_actor_db` 会遍历 `min_row=2` 到 `max_row` 检查 jp 为空——空行残留会直接导致校验失败（报大量"jp 为空"），是发现此问题的主要手段。

[男优名单清洗方法论与双通道清洗]
- Date: 2026-08-04
- Context: 用 avdanyuwiki 作品数据提取男优名单接入 `filter_male` 与 `clean_male_actors`，审查中发现名单噪声多、易混入女优
- Category: 构建方法
- Instructions:
  - **数据源**：`resources/userdata/male_actors.txt`（625 个男优）从 avdanyuwiki 作品 JSON（`*_avdanyuwiki.com.json`）的 `actor` 字段提取；生成脚本 `scripts/build_male_actor_list.py` 可复现，文档 `docs/male_actor_list.md`。JSON 由用户浏览器油猴脚本 `avdanyuwiki-extract-1.0.user.js` 生成，字段含 banko/title/actress/actor/date/director/maker/tag。
  - **actor 字段噪声大**：含标签词（主観/完全主観/素人/覆面/モザイク/触手）、括号注释（`主観（トニー大木）`）、多个名字空格连接（`田淵正浩 日高涼`）、合并名（`森林原人桜井ちんたろう`）、`×`已故标记、`？`噪声。清洗必须：括号内外拆解、超长(>8)剔除、标签黑名单、去后缀。
  - **女优混入是最大风险**：レズ片/SILK 女女片会把女优填进 actor 字段（如 `友田彩也香`）。用 actress 字段交叉验证——某名 actress 出现次数 ≥ actor×0.5，或 actor≤3 但 actress>0，判定女优剔除。原则：**宁漏勿误删**。
  - **双通道清洗**：`clean_male_actors` = 名单精确匹配（删无 tmdbid 及 TMDB gender=0 的男优）+ TMDB gender=2 校验。TMDB 局限性：gender=0 的男优（如加藤鷹）TMDB 标不出、永远清不掉，靠名单补。名单命中后不再重复请求 TMDB。`sync_from_avdb` filter_male 同理先名单后 TMDB，且名单过滤不依赖 TMDB key。
  - **低成本两字名**（如テツ）容易误杀，用 AVdb actor-mapping.xml 权威收录交叉验证——仅在 AVdb 有映射的低频两字名才保留。
