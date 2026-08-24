# 用户指令记忆

本文件记录用户的指令、偏好和项目长期经验。添加前查重，重复内容合并；只记录行为规范、构建部署、排错调试和协作流程，不记录可从代码直接获得的实现细节。

## 条目

[协作与质量流程]
- Date: 2026-08-24
- Context: 长期代码开发、审查、修改、测试和发布协作
- Category: 工作流协作
- Instructions:
  - 所有回复使用简体中文；面向小白解释时先说现象和后果，再说明原因，最后给出可直接执行的步骤。
  - 发现的问题必须全部报告，包含已修复、暂不修复和仅记录项；按严重程度排序，提供路径、行号、当前内容、影响和建议。
  - 代码改动和提交推送前先说明内容与原因并获得同意；用户明确要求提交/推送后才执行。直接在当前分支操作，不另开分支。
  - 每次代码改动后运行 `uv run quick-check`；用户要求提交/推送时，最后一次代码改动后运行 `uv run check --skip-hook-install`。必须确认退出码和完整结果，不能只 grep 关键词。
  - 不安装 pre-commit 钩子；`uv run check` 已覆盖所需检查。
  - 代码改动提交前同步更新 `docs/changelog.md` 顶部当前版本条目，按内容分类并合并同主题。
  - 新增、移除或改名站点、爬虫、CF 服务、配置项后，检查 `MDCx.ui` 帮助 HTML、`main_window.py` 启动/弹窗文字、`README.md` 和 `docs/*.md`。网站数量必须与 `get_registered_crawler_sites()` 一致；移除功能时清理 UI、说明和配置描述。
  - 文档日期使用北京时间（UTC+8）。
  - `scripts/*.py` 顶部的 `# ruff: noqa: E402` 属于路径 hack，必须保留；探测性 import 使用 `# noqa: F401`。

[Windows 打包与依赖]
- Date: 2026-08-24
- Context: Windows 单 exe 打包和 GitHub Release
- Category: 环境配置
- Instructions:
  - 优先使用标准库，不主动引入三方依赖；运行时持久化沿用 `resources`/`userdata` 目录。
  - 延迟导入模块必须加入 `scripts/build.py` 的 `--hidden-import` 或 `--collect-all`；修改依赖、`scripts/build.py`、Windows 构建或 Release 工作流时逐项核对。
  - `EXCLUDED_MODULES` 中的 `rich`/`typer` 等不得被 GUI 运行期引用；它们只供构建脚本或 CLI 开发环境使用。
  - Windows `curl_cffi` wheel 的 `curl_cffi.libs` 需要显式 `--add-binary` 收集。
  - Release Tag 使用纯数字 `YYYYMMDD`，以便版本检查执行 `int(tag_name)`；Windows 和 macOS 构建都必须显式传入 Release Tag。

[UI 开发与排查]
- Date: 2026-08-24
- Context: 多次调整工具页、设置页、弹窗和滚动区布局
- Category: 环境配置
- Instructions:
  - UI 修改流程：先改 `.ui`，再运行 `uv run python -m PyQt6.uic.pyuic mdcx/views/MDCx.ui -o mdcx/views/MDCx.py`，随后 `uv run ruff format mdcx/views/MDCx.py`，最后运行 `uv run pytest tests/test_ui_structure.py -q`。不要手工改生成的 `MDCx.py`。
  - 新文案回写 `.ui`，使 `.ui` 成为唯一权威源。ElementTree 只读解析，写入使用文本级精确替换，避免重排整个文件。
  - `QCheckBox`、`QRadioButton`、`QPushButton`、`QGroupBox` 不支持 `wordWrap`；长文本通过容器放宽和 `sizePolicy Fixed→Minimum` 解决。
  - 长说明 QLabel 使用 `wordWrap`；垂直策略不能锁死为 Fixed。测量 `sizeHint` 前必须 `show()` + `processEvents()`，或切换到对应 stackedWidget 页面。
  - `QLabel.wordWrap=true` 仍可能因固定 `minimumHeight` 在 Windows 字体/DPI 下裁切底部文字；说明文字必须按实际宽度检查运行时 `sizeHint()`，最小高度留出足够余量，并验证最后一行像素边界。
  - `gridLayout` 同一 `row:column` 只能放一个 widget/layout；Qt Designer XML 使用 `row` 和 `column` 属性；长 label 使用跨列布局；每个 `.ui` item 必须明确行列。
  - 增高滚动区内 groupBox 时，连锁调整下方兄弟 groupBox 的 y 和滚动区高度，底部保留约 60px 安全余量；绝对定位内容的高度变化同步更新内容 widget 的最小高度。
  - 排查功能必须覆盖所有 QDialog 子类和独立弹窗模块；新增按钮同步检查 `MDCx.ui`、`MDCx.py`、`init.py` 的信号和防重入逻辑。修改主窗口初始化链（信号连接/布局/配置加载）后运行 `tests/test_main_window_startup.py` 冒烟验证，静态检查发现不了 Qt API 签名错误。
  - 滚动区排查必须同时检查 `widgetResizable`、内容 widget 的运行时最小宽高和 `childrenRect`；绝对定位内容使用 `CustomScrollArea` 同步 `childrenRect.right()/bottom()`，单独设置 `widgetResizable=true` 不能保证垂直滚动。内容 geometry 可以保留 `.ui` 的设计基准宽度，运行时通过最小尺寸适配视口。
  - 横向裁切排查需要逐页切换 stackedWidget 并执行 `show()` + `processEvents()`，检查页面边界、滚动内容宽度和覆盖层（如 NFO 编辑器）；使用 `scripts/check_ui_layout.py` 配合运行时审计。
  - 打包前必须逐页检查最后一个可见控件与内容底部的安全余量；滚动条 range 非零只代表能滚动，不能证明最后一行可见。绝对定位滚动内容底部保留约 60px 余量，并在不同窗口/DPI 下复测。
  - UI 审计应覆盖主界面、日志、工具、设置全部子页、检测网络、NFO 编辑器和 NFO 库管理；静态布局检查、offscreen 几何测试和逐页运行时审计三者缺一不可。
  - 中文等宽字体使用 `Courier New`，不要使用裸 `Courier`。

[Qt 跨线程与后台任务]
- Date: 2026-08-24
- Context: 演员库工具、Emby 管理器和后台网络任务
- Category: 工作流协作
- Instructions:
  - `AsyncBackgroundExecutor.submit(coro)` 只接收协程对象，使用 `executor.submit(run())`；后台协程不得直接操作 QWidget。
  - 统一使用 `mdcx/utils/qt_thread.py::run_in_background`；主线程负责按钮状态，后台任务通过 pyqtSignal 把结果和完成状态传回主线程。
  - 模态弹窗的后台任务使用 `show()`，避免 `exec()` 与主线程同步阻塞；`EmbyActorSettingsDialog` 保存设置后必须调用 `manager.save()`。
  - 新增后台协程后运行 `scripts/check_thread_safety.py`，防止 async 函数直接调用 QWidget setter。

[排错调试方法论]
- Date: 2026-08-24
- Context: Onefile 静默退出、数据文件损坏、死代码误删和文本转换问题
- Category: 排错调试
- Instructions:
  - Qt 严格校验重载签名，不能把 `QSplitter.setStretchFactor(int, int)` 的 index 调用套到 `QLayout`；`QLayout.setStretchFactor()` 只接受 QWidget/QLayout，按 index 用 `QBoxLayout.setStretch()`，而 `QSplitter.setStretchFactor()` 恰好接受 int index，同名方法两类签名语义相反，改前先查目标类的重载。
  - 给测试桩追加属性时显式枚举，严禁 `__getattr__` 通配兜底返回值；生产代码可能靠 `AttributeError` 做资源缺失优雅降级（如 `is_male_actor` 检测 `resources.r`），兜底会把降级路径变成运行期崩溃。
  - Onefile 无控制台异常使用 `faulthandler.enable()`、`sys.excepthook` 和 `MAIN_PATH/crash/` 日志定位；GUI 日志必须走 `signal_qt.show_log_text`，`LogBuffer.log().write()` 只写内存。
  - 删除死代码前核实赋值点、读取点和中间产物来源；检查装饰器注册、字符串类型注解、延迟 import、动态字符串工厂。删除后重扫零引用和 F401。
  - openpyxl 历史脏库使用 `delete_rows` 可能保留空行和错误 `max_row`；可靠方案是新建 Workbook，过滤空行后重建表头、数据和样式。
  - `zhconv` 不覆盖日文新字体/异体字；简体列在转换前使用项目映射表，info_database 的 jp/keyword 列保持原始匹配内容。
  - `str.maketrans` 映射字典的 key 是 int，检查覆盖率使用 `ord(ch) in mapping`。
  - `ElementTree p.find()` 返回无子节点 Element 时真值为 False；必须使用 `is not None` 判断。
  - 使用 edit 删除函数时，oldString 必须包含函数全文和下一函数定义行；删除后检查死 import 和死变量。
  - 环境无 gh CLI：GitHub Actions 失败日志通过 `git credential fill`（host=github.com）取 token，再调 `{actions/runs/<run_id>/jobs}` 找 job id、`{actions/jobs/<job_id>/logs}` 下载文本日志。

[并发与性能]
- Date: 2026-08-24
- Context: 刮削并发、网络连接池、缓存和启动性能
- Category: 构建方法
- Instructions:
  - 文件间使用滑动窗口 `asyncio.wait(FIRST_COMPLETED)`，文件内多站点使用 `asyncio.gather`；异步批量任务优先滑动窗口，不盲目使用 `Semaphore+gather`。
  - `computed.async_client` 绑定全局 executor loop，网络请求不能跨 loop 复用。
  - 重型 XLSX 资源使用后台加载线程和 `ensure_data_ready()` 同步屏障；QTimer 写盘先快照，再交给 daemon 线程，并用锁防重复。
  - `ScrapeStateCache` 使用 WAL、`synchronous=NORMAL` 和批量 commit；有界缓存使用 OrderedDict 淘汰最旧项；info_database 加载时建立 O(1) 规范化索引。

[演员库与标签库]
- Date: 2026-08-24
- Context: actor_database、info_database、TMDB 校验和日文异体字清洗
- Category: 运维部署
- Instructions:
  - 出厂模板在 `resources/userdata/*.xlsx`，运行时实际读写库在 `manager.data_folder/userdata/*.xlsx`；用户数据修改进运行时库，默认数据修改进出厂模板。
  - `get_actor_data(name)` 是 Emby 等下游查询演员 `birth_date`/`bio`/`has_name` 的统一入口。
  - AVdb GUI 入口已移除；`sync_from_avdb` 和测试只供脚本复用。
  - info_database 的 jp/keyword 列用于原始匹配，维护重点是 zh_cn 和 zh_tw；演员清洗遵循宁缺毋滥，女优混入是最大风险。

[验证环境与长任务]
- Date: 2026-08-24
- Context: devbox 验证和大批量后台任务
- Category: 环境配置
- Instructions:
  - devbox 默认代理 `127.0.0.1:7890` 可能无进程；排查网络时临时关闭 `manager.config.use_proxy` 并清空 proxy，不据此修改产品默认配置。
  - PyQt6 测试缺系统库时按 devbox 环境文档安装依赖；先确认当前系统状态再处理。
  - 后台长任务必须先 `background_terminal_list` 统计资源，新增内存额度与已有运行任务总额不超过总内存 85%。
  - 长任务设置明确 timeout；每批完成写 JSON state（offset/updated），重启读取 offset 续跑；批次保持有限大小和并发上限，避免无限循环。
