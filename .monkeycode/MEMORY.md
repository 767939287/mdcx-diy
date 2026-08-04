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
  - 用户同意推送后，`git push` 前必须自动运行 `uv run check --skip-hook-install`（ruff format --check + ruff check + pytest --tb=short -m "not network" -x）。失败则修复后再推，不要强行推送。

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
  - 增高某一 groupBox 后，必须连锁把**其下方所有兄弟 groupBox** 的 y 同步 +delta，并同步增高滚动区 widget 高度，最后做 Qt offscreen 几何验证确认两两无重叠。踩坑：曾只检查与紧邻下方 group 的空隙、漏了中间一个 group，导致 110px 重叠；下方 group 不止紧邻的那一个。
  - `MDCx.py` 虽由 pyuic 生成，但仓库版曾被另行整理格式，整体重编译会产生数千行格式噪声 diff。手工增改 MDCx.py 时，务必把 UI 里新增的每个控件在 MDCx.py 的「创建段」和「retranslateUi 翻译段」各加一遍，并逐个 `grep` 核对存在——漏加控件**不会报错只会不显示**；工具页是 QScrollArea 滚动区，增高内容靠滚动条访问即可，无需改 tab/scrollArea 视口高度。
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
  - `AsyncBackgroundExecutor.submit(coro)` 只接受单个协程对象，`executor.submit(asyncio.run, run())` 会报 `TypeError: takes 2 positional arguments but 3 were given`。正确写法：`executor.submit(run())`。`mdcx/controllers/main_window/main_window.py:2617` 和 `tool_handlers.py:45` 两处同源 bug 已修复。
  - 协程在 executor 后台线程事件循环执行，`btn.setEnabled()` / `setText()` 直接操作 QWidget 跨线程不安全。必须用 pyqtSignal 发到主线程执行。正确模式：按钮点击时主线程 setEnabled(False) + emit "运行中"，协程 finally 里发射 `pyqtSignal.emit()`（线程安全），主线程槽负责恢复 setEnabled(True) + setText。参见 `main_window.py:_run_actor_db_tool`/`_on_actor_db_finished`。
  - `tool_handlers.py` 里的函数是模块级函数（通过 `main_window.py:2580` `from .tool_handlers import ...; pushButton_actor_db_open_clicked(self)` 调用），`self._open_actor_db_file` 不会自动可用——必须确保方法存在在 `MyMAinWindow` 上，或完全不用 `self.xxx`。

[刮削并发架构参考]
- Date: 2026-08-03
- Context: 探索 actor_db_tool 并发提速时发现刮削已有成熟的滑动窗口并发
- Category: 构建方法
- Instructions:
  - 正常刮削（`scraper.py`）已经是两层并发：文件间用 `_run_tasks_with_limit`（滑动窗口，`asyncio.wait(..., FIRST_COMPLETED)` 渐进式调度，并发数 = 配置项 `thread_number`）；文件内用 `_call_crawlers` 的 `asyncio.gather` 多站点并发抓取。
  - 不要误以为刮削是串行的。慢可能是单站点超时拖慢整个文件，而非并发不足。
  - actor_db_tool 的可复用并发模式已从 `Semaphore+gather` 升级为滑动窗口（`mdcx/tools/actor_db_tool.py`），与刮削同构。后续新增异步批量处理工具时，优先采用滑动窗口模式而非 `Semaphore+gather`。
  - 滑动窗口优势：内存峰值低（不会同时存在全部协程对象）、取消响应快（最多等当前批次完成）、渐进式调度（大列表不会一次性创建海量协程）。
