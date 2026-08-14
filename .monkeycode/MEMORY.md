# 用户指令记忆

本文件记录用户的指令、偏好和教导，用于未来交互参考。

## 格式

- **用户指令条目**：`[摘要]` / `- Date` / `- Context` / `- Instructions: 逐行`
- **项目知识条目**：同用户指令 + `- Category: [运维部署|构建方法|测试方法|排错调试|工作流协作|环境配置]`

## 去重策略

添加前先查重；重复则合并（更新 Context/Date），保持文件精简。

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
- Context: 项目要求 Python >= 3.13.4（使用 type parameter defaults 语法），沙箱默认 python3 是 3.11 无法解析
- Category: 环境配置
- Instructions:
  - 测试一律用 `uv run` 执行（`uv run pytest tests/ --tb=short -m "not network"`），sandbox 默认 python3 是 3.11 无法解析 3.12+ 语法。
  - 环境重置后恢复：`pip install --break-system-packages uv` 安装 uv，再 `uv sync`（自动下载合适 Python 建 `.venv`，当前为 python3.14）。
  - 跑 pytest 若报 `ImportError: libglib-2.0.so.0 / libGL.so.1 / libEGL.so.1 / libfontconfig.so.1` 缺失，说明 PyQt6 系统库没装，执行：`DEBIAN_FRONTEND=noninteractive apt-get install -y libglib2.0-0 libgl1 libegl1 libopengl0 libfontconfig1 libqt6gui6 libqt6widgets6 libqt6core6 libqt6network6 libqt6xml6`。

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
  - UI 布局定义在 `mdcx/views/MDCx.ui`。**规范流程**：改动一律先改 `MDCx.ui`，再运行 `/workspace/.venv/bin/python3 -m PyQt6.uic.pyuic mdcx/views/MDCx.ui -o mdcx/views/MDCx.py` 重编译，最后 `uv run ruff format mdcx/views/MDCx.py` 对齐格式（可把 diff 从数千行压到几十行）。**不要手工修改 MDCx.py**——有 `tests/test_ui_structure.py::test_mdcx_py_in_sync_with_ui` 在 CI 把关，手工改 `.py` 不同步 `.ui` 会红。
  - 调整布局后必须验证 `import mdcx.views.MDCx` 可正常导入（UI 里有中文/多行 tooltip，编译易出错）。
  - 注意 tab/groupBox 重叠、遮挡问题：所有 groupBox 在 `page_tool` 的滚动区 `scrollAreaWidgetContents_gongju` 内是绝对定位（x/y/width/height），重排顺序要同时更新各 groupBox 的 y 坐标和滚动区 widget 高度（最后一块底部留 20px 边距），否则底部内容被遮挡。
  - **UI 结构有自动化测试**（`tests/test_ui_structure.py`，已挂入 `uv run check` 与 CI）：解析 `MDCx.ui` 检查 groupBox 同父容器不重叠/无负间距/不超滚动区、用户控件 objectName 唯一、`MDCx.py` 与 `MDCx.ui` 重编译同步。改 UI 后跑 `uv run check` 或 `uv run pytest tests/test_ui_structure.py -q` 即可自动验证，无需手写 Qt offscreen 几何检查脚本。
  - 增高某一 groupBox 后，必须连锁把**其下方所有兄弟 groupBox** 的 y 同步 +delta，并同步增高滚动区 widget 高度，最后做 Qt offscreen 几何验证确认两两无重叠。踩坑：曾只检查与紧邻下方 group 的空隙、漏了中间一个 group，导致 110px 重叠；下方 group 不止紧邻的那一个。
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
  - **刮削已是两层并发**：文件间 `_run_tasks_with_limit`（滑动窗口，`asyncio.wait(FIRST_COMPLETED)`，并发数=配置 `thread_number`）；文件内 `_call_crawlers` 多站点 `asyncio.gather`。慢常是单站点超时拖累，而非并发不足。
  - 后续新增异步批量处理工具时，**优先用滑动窗口而非 `Semaphore+gather`**（`mdcx/tools/actor_db_tool.py` 已用）：内存峰值低、取消响应快、大列表不一次性创建海量协程。

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
  - **男优名单来源**：`resources/userdata/male_actors.txt`（625 人），生成脚本 `scripts/build_male_actor_list.py` 可复现，文档 `docs/male_actor_list.md`。
  - **actor 字段噪声大**：含标签词、括号注释、多名字空格连接、合并名、`×`已故标记、`？`噪声。清洗：括号内外拆解、超长(>8)剔除、标签黑名单、去后缀。
  - **女优混入是最大风险**（レズ片会把女优填进 actor 字段）：用 actress 字段交叉验证（某名 actress 次数 ≥ actor×0.5，或 actor≤3 但 actress>0 判定女优）。原则：**宁漏勿误删**。
  - **双通道清洗**：`clean_male_actors` = 名单精确匹配 + TMDB gender=2 校验（gender=0 男优如加藤鷹 TMDB 标不出，靠名单补；名单命中不再重复请求 TMDB）。`sync_from_avdb` filter_male 同理先名单后 TMDB。
  - **低成本两字名**（如テツ）易误杀：用 AVdb actor-mapping.xml 权威收录交叉验证，仅在 AVdb 有映射的低频两字名才保留。

[specs 目录已删除]
- Date: 2026-08-04
- Context: 用户决定清理 .monkeycode/specs/，确认其 4 个 spec（演员库维护/AVdb同步/Emby本地回填/剔除男演员）对应功能均已实现后删除
- Category: 工作流协作
- Instructions:
  - `.monkeycode/specs/` 目录已删除（2026-08-04，提交 f4c52db）。它曾存放已实现功能的 EARS 需求（requirements.md）、技术设计（design.md）、任务清单（tasklist.md）。
  - 这些功能的实现意图可从代码、`tests/` 与 `docs/changelog.md` 回溯，specs 不再保留。
  - 未来若用 `/feature-design` skill 为新功能生成规格，产物会重新出现于 `.monkeycode/specs/`——功能实现并验证后可按用户偏好清理或保留。

[AVdb 源数据 tmdbid 错误映射排查方法论]
- Date: 2026-08-05
- Context: 用户怀疑 AVdb 同步来的有 id 演员含非 AV 演员（动画录音师/声优/好莱坞演员等），用 TMDB API 全量排查 9251 个有 id 演员后确认并清理
- Category: 排错调试
- Instructions:
  - **AVdb actor-mapping 源数据不可信**：名字模糊匹配 TMDB 人物时会把 AV 演员匹配到同名的非 AV person（如 `阿部智佳子`=动画录音师、`安娜伊德慕絲提`=法国影后、`阿部乃みく` 与 `阿部真琴` 同指 id=2132746 但非同一人）。错误映射会形成"无 tmdbid 但 url 有值"的畸形行。
  - **判断标准**：TMDB `person/{id}` 的 `adult` 标记——知名 AV 女优（三上悠亜/波多野結衣等）均为 `adult=True`；`adult=False` + `known_for_department` 非 Acting（Sound/Visual Effects/Art 等）= 明确非 AV；`adult=False` + Acting 需再查 `combined_credits` 按作品名判断成人内容。
  - **沙箱访问 TMDB API**：`api.themoviedb.org` 直连被证书劫持拦截，需用 `api.tmdb.org` 域名 + `Host: api.themoviedb.org` 请求头（项目 `_resolve_tmdb_config` 即此默认域名）。
  - **处理原则宁缺毋滥**：错误 id 比无 id 更糟——刮削兜底会取到错误人物资料、参与性别校验/重复检测全是错上加错。清除错误 id/删除疑似非 AV 行后，刮削遇同名演员按名字重新搜索，能找回正确的就补上、找不回保持无 id。
  - **曾执行**（2026-08-05）：清除 7120 行孤儿 url + 删除疑似非 AV 3447 行（出厂库 24243→20796），详见 changelog「TMDB 演员身份排查与清理」。

[不再使用 AVdb 数据源（GUI 入口已移除）]
- Date: 2026-08-06
- Context: 用户被 AVdb 数据质量坑惨（错误 id、非 AV 人物混入、重复行、生日误填），明确决定不再同步它的数据
- Category: 工作流协作
- Instructions:
  - 用户已决定**不再从 AVdb（Jav-Actors-Mapping）同步演员数据**，工具页「从 AVdb 同步」GUI 入口已在 v2.0.5 移除（连带移除其附属的「校验 tmdbid 与名字匹配」复选框）。
  - `sync_from_avdb` 底层函数与 `tests/test_avdb_actor_sync.py`、`tests/test_actor_db_filter_male.py` 保留，供脚本/测试复用，但**不要主动建议用户重新启用 AVdb 同步**。
  - 「剔除男演员」按钮保留——它是运行时男优防线（刮削 `update_actor_db_row` 会把影片男优写入用户库），与 AVdb 无关。

[ruff RUF100 误删 scripts/*.py 顶部防御性 noqa 的坑]
- Date: 2026-08-10
- Context: 启用 ruff 自动修复时，RUF100 把 scripts/*.py 顶部 `# ruff: noqa: E402` 判为 unused 删除，导致-imports 失败
- Category: 工作流协作
- Instructions:
  - `scripts/*.py` 顶部的 `# ruff: noqa: E402` 多数是必要的——脚本里有 `sys.path.insert(0, '.')` 等 hack 才能让后续 import 工作。E402 在当前 ruff.toml 没启用，所以 RUF100 觉得 noqa 多余，但保留它们能在未来启用 E402 或修改 per-file-ignores 时不致出错。
  - 若启用 RUF100 自动修复，**只应用到 `mdcx/` 与 `main.py`**，scripts/ 目录需手动 `git checkout` 回滚。
  - 探测性 import（try/except ImportError 内 `import xxx` 然后未使用，用于检测包可用性）应显式标注 `# noqa: F401  # 探活`，避免被 F401 误报。已应用：`mdcx/cf_bypass/local_server.py`、`mdcx/config/resources.py`、`mdcx/core/amazon.py`。

[看到"死代码"先怀疑是功能从未运行，而非"清理即可"]
- Date: 2026-08-11
- Context: 审查 emby_actor_manager 工具时我把 PreparePreviewThread 里 `self.minnano_cache = None` 判为"死代码字段"删除——后来用户反问"minnano 缓存是不是可复用"，深查才发现 QThread.run 里 `from .emby_actor_manager import load_cache` 这个导入路径本身就错了（emby_actor_manager 无此函数），整个预览功能对启用 minnano 缓存的用户从来就 ImportError 崩掉，UI 字段从未被读写是因为代码根本跑不到。
- Category: 排错调试
- Instructions:
  - 看到"未被引用的字段/函数/变量"（疑似死代码），先问三个问题再动刀：
    1. 它的赋值点在哪里？赋值语句本身是不是会抛异常？（本次 ImportError）
    2. 它的读取点在哪里？读取点所在函数有没有被调用？
    3. 它的中间产物（如本例的模块级 `_cache_data`）是不是由别处写入？本例 `load_cache()` 写的是 `minnano_crawler._cache_data` 不是 UI 字段，所以 UI 字段确实是死的，但**功能是活的**。
  - 死字段可以删，但字段对应的"功能有没有正常运行"必须先实测验证（最小复现 import / 跑一遍），不能因为字段没人用就直接判定整个功能在跑。
  - 用户反问"是不是可以复用"是高价值信号——小白的常识直觉能刺穿专家的盲点。

[devbox 验证环境默认代理指向无进程的 127.0.0.1:7890]
- Date: 2026-08-14
- Context: 多次踩坑（r18dev/javbus 高清升级、DMM 图下载、check_url 验证时）——mdcx 客户端请求全部失败，现象是 `curl: (7) Failed to connect ... over proxy 127.0.0.1` 或 check_url 全返回 None
- Category: 环境配置
- Instructions:
  - **根因**：mdcx 默认配置 `use_proxy=True` + `proxy=http://127.0.0.1:7890`，而 devbox 验证环境**没有运行该代理进程**，导致所有走 `manager.acquire_computed()` 的 client 请求（check_url、下载、刮削）连不上失败。这不是代码 bug，是验证环境 vs 主流程环境的差异。
  - **踩坑特征**：`manager.config.proxy` 打印为 `http://127.0.0.1:7890`、`use_proxy=True`；同一 URL 用 `curl_cffi`/`curl` 直连却 200 正常。排查时先打印 `manager.config.use_proxy` 与 `manager.config.proxy` 即可定位。
  - **验证环境绕过方法**：脚本开头 `manager._replace_config(manager.config.model_copy(deep=True))` 后设 `cfg.use_proxy=False`、`cfg.proxy=""` 再 `manager._replace_config(cfg)`，即可让 check_url/下载走直连。注意 `manager.config.proxy=""` 或 `use_proxy=False` 直接赋值**不生效**（Computed client 在 import 时已按旧配置构建），必须 `_replace_config` 重建；且这只是内存态，不影响配置文件。
  - 真实用户环境（GUI/平台运行）有可用代理或直连，此问题仅 devbox 验证环境存在，**不要据此改产品代码**。

[GitHub CI 失败 runs 批量清理流程]
- Date: 2026-08-14
- Context: 用户希望批量删除 GitHub Actions 页面上 CI/CD Pipeline #579-#591 共13个失败 run
- Category: 排错调试
- Instructions:
  - GitHub 凭据从 git credential helper 提取：`echo -e "protocol=https\nhost=github.com\n" | git credential fill`，取 password 字段作为 GH_TOKEN。
  - `gh run list --workflow ci.yaml --limit 30 --json databaseId,conclusion,number` 列出所有 CI runs，筛选 conclusion=failure 的 databaseId。
  - 逐条执行 `gh run delete <databaseId>` 即可删除。
  - 批量删除示例：`for id in <ids>; do gh run delete "$id" && echo "deleted $id"; done`。
  - GH_TOKEN 需在 bash 调用前 export（新 shell 不继承），用完即删避免泄露。
