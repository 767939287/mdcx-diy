# 用户指令记忆

本文件只记录长期有效的行为规范、构建发布流程、排错方法和环境约束。项目实现细节以代码、测试和文档为准。

## 协作与质量

- Date: 2026-08-24
- Category: 工作流协作
- Instructions:
  - 所有回复使用简体中文；面向小白说明时按“现象和影响 → 原因 → 可执行步骤”组织。
  - 代码修改或提交推送前说明内容与原因；用户明确要求提交/推送后才执行。直接在当前分支操作，不另开分支。
  - 每次代码改动后运行 `uv run quick-check`；提交前最后一次改动后运行 `uv run check --skip-hook-install`，确认完整退出结果。
  - 按变更风险分级验证：仅改 `.monkeycode/MEMORY.md`、`docs/*.md` 或 changelog 时运行 `git diff --check` 并审阅内容；修改 `.ui`、生成 UI 或源码时运行相关测试和 `quick-check`；混合提交按代码变更处理；用户明确要求完整验证或发布前再运行 `uv run check --skip-hook-install`。
  - 不安装 pre-commit；`uv run check` 已覆盖项目检查。
  - 提交前更新 `docs/changelog.md` 当前版本条目，合并同类内容。
  - 文档日期使用北京时间（UTC+8）。
  - 修改站点、爬虫、CF 服务或配置项时，同步检查 UI、启动文字、README 和 `docs/*.md`；站点数量以 `get_registered_crawler_sites()` 为准。

## UI 开发与审计

- Date: 2026-08-24
- Category: UI 开发与排查
- Instructions:
  - UI 修改先改 `.ui`，再运行 `uv run python -m PyQt6.uic.pyuic mdcx/views/MDCx.ui -o mdcx/views/MDCx.py`、`uv run ruff format mdcx/views/MDCx.py` 和 `uv run pytest tests/test_ui_structure.py -q`；不要手工改生成的 `MDCx.py`。
  - `.ui` 是文案和布局唯一权威源；Qt Designer XML 的网格属性使用 `row`、`column`。
  - QLabel 长文本使用 `wordWrap`，并按实际宽度检查运行时 `sizeHint()`；固定 `minimumHeight` 可能在 Windows 字体/DPI 下裁切底部文字，底部需保留约 60px 安全余量。
  - QCheckBox、QRadioButton、QPushButton、QGroupBox 不支持 `wordWrap`；长文本通过足够宽度和合适的 `sizePolicy` 处理。
  - 绝对定位滚动内容必须同时检查 `widgetResizable`、内容最小宽高和 `childrenRect`；项目统一使用 `CustomScrollArea` 同步 `childrenRect.right()/bottom()`。
  - `widgetResizable=true` 本身不能保证垂直滚动；滚动条 range 非零也不能证明最后一行可见。
  - 打包前逐页切换 stackedWidget，执行 `show()` + `processEvents()`，审计主界面、日志、工具、设置全部子页、检测网络、NFO 编辑器和 NFO 库管理的边界、滚动范围、横向溢出、底部余量和控件重叠。
  - 运行 `scripts/check_ui_layout.py`，并运行 `tests/test_ui_geometry.py`、`tests/test_main_window_startup.py`；静态检查无法覆盖所有 Qt 运行时问题。
  - 新增按钮或弹窗时同步核对 `.ui`、生成 UI、信号绑定和防重入逻辑；中文等宽字体使用 `Courier New`。

## Qt 与测试排错

- Date: 2026-08-24
- Category: 排错调试
- Instructions:
  - Qt 同名 API 的重载可能不同：`QLayout.setStretchFactor()` 接受 QWidget/QLayout，按 index 使用 `QBoxLayout.setStretch()`；`QSplitter.setStretchFactor()` 接受 int index。修改前先确认目标类签名。
  - 测试桩显式枚举需要的属性和方法，不使用 `__getattr__` 通配返回值；生产代码可能依赖 `AttributeError` 做优雅降级。
  - Onefile 无控制台异常使用 `faulthandler`、`sys.excepthook` 和 `MAIN_PATH/crash/` 日志定位；GUI 日志走 `signal_qt.show_log_text`。
  - 删除代码前检查赋值点、读取点、装饰器注册、延迟 import 和动态工厂；删除后重扫死 import、F401 和零引用。
  - GitHub Actions 日志在无 gh CLI 环境中通过 `git credential fill` 获取 GitHub token，再调用 Actions API 下载 job 日志。
  - 使用编辑工具删除函数时，匹配范围包含完整函数和下一函数定义，修改后检查死变量和格式。

## Windows 打包与发布

- Date: 2026-08-24
- Category: 环境配置
- Instructions:
  - 优先使用标准库，不主动引入依赖；运行时持久化沿用 `resources`/`userdata`。
  - 延迟导入必须同步加入 `scripts/build.py` 的 `--hidden-import` 或 `--collect-all`；修改依赖、构建脚本或 Release 工作流时逐项核对。
  - `EXCLUDED_MODULES` 中的 `rich`、`typer` 等只供构建或 CLI 开发环境使用，GUI 运行期不得引用。
  - Windows `curl_cffi` wheel 的 `curl_cffi.libs` 需要显式 `--add-binary` 收集。
  - Release Tag 使用纯数字 `YYYYMMDD`，Windows 和 macOS 构建都显式传入 Tag。
  - `scripts/*.py` 顶部路径 hack 的 `# ruff: noqa: E402` 和探测性 import 的 `# noqa: F401` 必须保留。

## 并发、数据与验证环境

- Date: 2026-08-24
- Category: 构建方法与排错
- Instructions:
  - 文件间批量任务优先使用 `asyncio.wait(FIRST_COMPLETED)` 滑动窗口，文件内多站点使用 `asyncio.gather`；网络请求不得跨 executor loop 复用。
  - 后台协程统一使用 `mdcx/utils/qt_thread.py::run_in_background`，后台任务不得直接操作 QWidget，结果通过 Qt signal 回主线程。
  - 新增后台协程后运行 `scripts/check_thread_safety.py`；模态后台任务使用 `show()` 避免主线程同步阻塞。
  - 重型 XLSX 使用后台加载和 `ensure_data_ready()` 屏障；QTimer 写盘先快照，再交给带锁的后台线程。
  - 出厂模板位于 `resources/userdata/`，运行时数据位于 `manager.data_folder/userdata/`；不要混淆两者。
  - devbox 代理 `127.0.0.1:7890` 可能没有进程；排查网络时临时关闭代理，不修改产品默认配置。
  - 长任务使用受管理的后台终端，先检查资源预算，设置 timeout，并保存可续跑 state。
