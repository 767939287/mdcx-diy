# 用户指令记忆

本文件记录用户的指令、偏好和教导，用于未来交互参考。

格式：用户指令条目 `[摘要]`/`- Date`/`- Context`/`- Instructions`；项目知识条目附加 `- Category`。添加前查重，重复则合并（更新 Context/Date），保持精简。

## 条目

[面向小白的细致指导风格]
- Date: 2026-06-08
- Context: 用户希望我以编程能手、审核、修改和补全代码专家的方式长期协作
- Instructions:
  - 默认从全方位、多角度、深层次的角度审查和改进代码。
  - 面向小白解释问题，给出细致、可执行、易落地的建议。
  - 在发现风险、缺陷、遗漏时主动指出，并尽量给出修复方案和进行验证。

[提交推送与质量把关]
- Date: 2026-07-18（2026-08-03、2026-08-16、2026-08-18 更新）
- Context: 用户要求改动/推送前必须征得同意，推送前自动跑测试；pre-commit 钩子经评估无需安装；不开新分支直接推当前分支；每次改动随代码更新 changelog 未发版条目
- Category: 工作流协作
- Instructions:
  - 所有代码改动（新建/修改/删除文件）和提交推送（`git add`+`git commit`+`git push`）必须先说明内容与原因，获得同意后再执行。本指令优先级高于所有"自动执行"类指令。
  - **直接在当前分支提交推送，不另开新分支**（覆盖 `.ai-ready/rules/auto-create-branch-on-master.md`）。`git add`+`git commit` 后直接 `git push` 到当前分支远程；用户指示开分支时才开。
  - **check 按需运行，不重复空跑**：最后一次代码改动后运行一次 `uv run check --skip-hook-install`（ruff format --check + ruff check + mypy mdcx/ + pytest --tb=short -m "not network" -x + check_actor_db），全绿后如代码再无改动，`git push` 前**不重跑**，直接推；只有"全绿 check 之后又改过代码"才需在 push 前重跑。失败则修复再推，不强行推送。
  - **不安装 pre-commit 钩子/工具**：`.pre-commit-config.yaml` 两个 ruff 钩子 stages 为 `pre-merge-commit, pre-push`，普通 commit 不触发，`pre-commit install` 对其无效；`uv run check` 已覆盖其作用。
  - **changelog 随改动更新（推送前）**：每次代码改动在 commit 里同时更新 `docs/changelog.md` 顶部未发版版本条目（当前 v2.0.6）——新增功能/修复/重构按内容分类记录。未发版不新建版本号；同主题/相似条目合并进同一行，避免重复。发版时才新建下一版本条目。提交信息与该 changelog 更新保持一致。
  - **提交检查清单（每次 commit 固定执行，防遗漏）**：准备提交时按固定顺序核对，每步是硬性环节而非可选：
    1. `git status`/`git diff` 看本次改了什么；
    2. 若有新功能/修复/重构 → **先更新 changelog**（未发版条目按分类补记，同主题合并），再 `git add`；
    3. 若改依赖/打包/运行时引入三方依赖 → 按「Windows exe 打包依赖约束」清单核对 build.py 与 workflow；
    4. 若涉及功能/站点/CF/配置项 → 检查 UI 说明文字/弹窗/文档是否需同步（见「功能改动同步 UI 说明文字、弹窗与文档」）；
    5. 最后 `git add` + `git commit` + `git push`。
    此清单优先级：changelog、打包核对、UI/文档同步都必须在 push 前完成，不允许"提交后补"。

[Windows exe 打包依赖约束]
- Date: 2026-08-03（2026-08-18 更新）
- Context: 用户以单 exe 运行，改动需兼容 Windows 单 exe 打包发布；影响打包的改动需自动核对打包程序与工作流
- Category: 环境配置
- Instructions:
  - 优先标准库，不主动引入三方依赖；持久化路径沿用 `resources`/`userdata` 目录习惯。
  - 改动打包入口/运行时依赖后按清单核对单 exe 安全：
    - 延迟导入模块须加入 `scripts/build.py` 的 `--hidden-import`/`--collect-all`，否则 exe 报 ModuleNotFoundError。
    - 顶层 import 的三方依赖 PyInstaller 静态分析自动收集，必要时补 `--collect-all`。
    - `EXCLUDED_MODULES` 排除的包（rich/typer/playwright 等）绝不能被 GUI 运行期引用。
    - 检查 `.github/workflows/build-windows.yml` 与 `release.yml` 打包流程、hidden-import、chromium 缓存过期键（版本更新 bump 末尾 vN）。
  - 已知：rich/typer 仅独立 CLI 脚本 `mdcx/cmd/crawl.py` 使用，不被打包，排除安全。
  - **打包改动自动检查触发条件**：改 `pyproject.toml` 依赖、`scripts/build.py`、`.github/workflows/build-windows.yml`/`release.yml`、或运行时引入新三方依赖时，必须按上面清单逐项核对打包程序与工作流，确认无遗漏再提交（如移除内置 CF 依赖后同步清理 build.py 的 collect-all 与 workflow 缓存步骤）。

[UI 改动注意事项]
- Date: 2026-08-03（2026-08-16 更新）
- Context: 多次调整工具页 UI（groupBox/按钮）沉淀约束；网络页重写影 bug 与 Courier 字体中文方框问题
- Category: 环境配置
- Instructions:
  - 布局定义在 `mdcx/views/MDCx.ui`。**规范流程**：先改 `.ui` → `/workspace/.venv/bin/python3 -m PyQt6.uic.pyuic mdcx/views/MDCx.ui -o mdcx/views/MDCx.py` → `uv run ruff format mdcx/views/MDCx.py`。**不要手工改 MDCx.py**（`tests/test_ui_structure.py::test_mdcx_py_in_sync_with_ui` 把关）。
  - 改后验证 `import mdcx.views.MDCx` 可导入；改 UI 跑 `uv run check` 或 `uv run pytest tests/test_ui_structure.py -q` 自动验证，无需手写 offscreen 检查。
  - groupBox 在 `page_tool` 滚动区 `scrollAreaWidgetContents_gongju` 内绝对定位：增高某 groupBox 后须连锁把**其下方所有兄弟 groupBox** y 同步 +delta，并同步增高滚动区高度（底部留 20px）。曾只查紧邻下方 group 漏中间一个，导致 110px 重叠。
  - **gridLayout 布局陷阱**：`<item row="X" column="Y">` 只能放一个 widget/layout；若多个 item 被放在同一行列会覆盖/重影。新增控件（如 Bypass 落地白名单）前先用 `grep -n` 扫描目标 layout 现有 row/col 分布，或跑 offscreen 脚本 `wid.mapTo(父).geometry()` 检查实际坐标。
  - **gridLayout 跨列长 label 溢出遮挡**：动态注入控件放 col0（标签列，仅 ~130px）时，长说明 label 不换行会向右溢出进入 col1，被 col1 控件不透明背景遮挡，露出前半截产生重影。修复：长 label 用 `addWidget(w, row, 0, 1, 2)` 跨整行 + `setWordWrap(True)`，并移除/隐藏同行被替代的原 label。案例：`main_window.py::_setup_baidu_translate_ui` 的 `label_baidu_hint` 与 `.ui` 原有 `label_60` 重影（260816 修复）。
  - **重编译会回退 MDCx.py 手工文案**：新文案必须回写 `MDCx.ui` 让 `.ui` 成唯一权威源；同步对比测试须用相对路径编译（pyuic6 会把输入路径写进头注释）。
  - findChildren 几何检查须排除 comboBox popup 内部子部件（QListView/QScrollBar 等 0,0/100x30/640x480 误报）；长文本用 `fontMetrics().boundingRect(...).height()`/`horizontalAdvance` 验证。
  - 新增按钮检查三处一致：`MDCx.ui` + `MDCx.py` + `mdcx/controllers/main_window/init.py`（clicked 槽 + setText 防重入）。删除按钮后清理失联 delegate 死代码。
  - 按钮防重入与协程安全参见 `[executor.submit 与跨线程 Qt 安全]`。
  - **中文字体等宽方案**：所有设置页 groupBox 统一用 `font:"Courier New"`（项目惯例）；不用裸 `"Courier"`（西文专用字体，中文显示为方框）。全仓替换一次性完成：`sed -i 's/font:"Courier"/font:"Courier New"/g' mdcx/views/MDCx.ui && sed -i 's/font: "Courier"/font: "Courier New"/g' mdcx/views/MDCx.ui`。

[Onefile 环境调试要点：静默退出与日志通道]
- Date: 2026-08-03
- Context: 按钮点击后程序静默退出/误判卡死
- Category: 排错调试
- Instructions:
  - onefile + `-w` 下普通 Python 异常被静默吞掉（`sys.__stderr__` 不存在），表现为"程序直接退出"，非 C segfault。事件查看器无 WER 记录即是 Python 异常导致 sys.exit 的线索。
  - 诊断三件套在 main.py 启动注册：`faulthandler.enable()` + `sys.excepthook` 写文件 + stdout/stderr 重定向到文件，日志写 `MAIN_PATH/crash/`。
  - 工具内部日志走 `LogBuffer.log().write()`（只存内存）不显示，误以为卡死；所有工具内部日志输出必须走 `signal_qt.show_log_text`。

[executor.submit 与跨线程 Qt 安全]
- Date: 2026-08-03（2026-08-16 更新）
- Context: 修复演员库工具按钮 + Emby 演员管理器 executor.run 阻塞主线程问题
- Category: 工作流协作
- Instructions:
  - `AsyncBackgroundExecutor.submit(coro)` 只收单个协程对象，正确写法 `executor.submit(run())`；`submit(asyncio.run, run())` 报 TypeError。
  - 协程在后台线程事件循环执行，不可直接 `btn.setEnabled()`/`setText()` 跨线程操作 QWidget。模式：主线程点击时 setEnabled(False)+emit"运行中"，协程 finally 发射 pyqtSignal（线程安全），主线程槽恢复。参见 `main_window.py:_run_actor_db_tool`/`_on_actor_db_finished`。
  - `tool_handlers.py` 为模块级函数，`self.xxx` 不自动可用——确保方法在 `MyMAinWindow` 上或不用 self。
- **Emby 演员管理器阻塞陷阱**：`_on_connect`/`_on_fetch` 等按钮槽在 GUI 主线程调用 `executor.run()` 同步阻塞。Emby 服务器响应慢时会卡死 GUI（无日志输出、无反应）。调试时先确认 `signal.show_log_text`（主界面）vs `self.log`（管理器日志框）是两条独立通道，管理器日志为空不代表网络请求没在跑。
- **Emby 弹窗保存陷阱**：`EmbyActorSettingsDialog._save`、`ActorSourceTestDialog._save_quick_settings`、`ActorDetailDialog._save_quick_settings` 三处原来只调 `manager._replace_config()` 不写盘，退出重进配置恢复原样。必须补 `manager.save()`。
- **跨线程收口工具**：新代码后台任务统一用 `mdcx/utils/qt_thread.py::run_in_background(button=, coro_factory=, busy_signal=, busy_text=, finished_signal=, finished_arg=, log_prefix=)`（防重入 + setEnabled(False) + busy_signal + submit + finally 发 finished_signal + 异常 show_log）；禁止直接 `executor.submit` 后在协程内碰 QWidget。`_run_actor_db_async` 已改为调用它作样板。
- **需要回传结果时用自定义 Signal**：`run_in_background` 只恢复按钮不带结果。主线程阻塞调用（Emby 管理器 `_on_connect`/`_on_fetch`/`_on_fetch_finished`、ActorDetailDialog 的头像/简介/同步）改为 `executor.submit(coro)` + `add_done_callback(lambda fut: self.xxx_signal.emit(_future_result_or(fut, default)))`，协程**只返回结果不碰 QWidget**，主线程槽按结果更新 UI。`_future_result_or(future, default)` 兜底 Future 异常，避免回调里 `fut.result()` 抛到全局 loop 线程。模态弹窗 `exec()` 改非模态 `show()` + `WindowMinimizeButtonHint` 可最小化不遮挡主窗口（issue #38）。
- **跨线程安全扫描**：`scripts/check_thread_safety.py` AST 扫 `async def` 体内直接操作 QWidget setter（setEnabled/setText/setGeometry 等）的违规，当前 0 违规。新增后台协程前跑一遍防回归。

[并发与性能优化约束]
- Date: 2026-08-03（2026-08-17 更新）
- Context: 刮削并发架构 + 性能优化批次（8bda0e7）+ 启动数据库延迟加载（5733018）沉淀的可复用模式
- Category: 构建方法
- Instructions:
  - **刮削两层并发**：文件间 `_run_tasks_with_limit`（滑动窗口 `asyncio.wait(FIRST_COMPLETED)`，并发=配置 thread_number）；文件内 `_call_crawlers` 多站点 `asyncio.gather`。慢常是单站点超时拖累。新增异步批量工具优先用滑动窗口而非 `Semaphore+gather`（参考 `mdcx/tools/actor_db_tool.py`）：内存峰值低、取消响应快。
  - **httpx session 绑定全局 loop 是硬约束**：`computed.async_client` 的 httpx session 在全局 executor loop 创建，跨 loop 复用会破坏连接池/代理/CF-bypass 架构。网络请求必须留在全局 loop，不能为并发改多 loop（issue #38 评估过）。
  - **启动重型资源后台加载**：`Resources` 构造只做路径/图标/字典，XLSX 迁移合并加载走 `start_data_loading()` 后台线程（daemon）+ `ensure_data_ready()` 同步屏障（`threading.Event` + 加载错误捕获），业务入口首次访问前等待。GUI 首屏不被数据库加载阻塞。
  - **save_remain_list 后台写**：QTimer 触发时快照 `list(Flags.remain_list)` 后丢 daemon 线程，`threading.Lock` 防重复线程，失败保留 `can_save_remain` 下次重试；主线程不写盘。
  - **水印源图缓存**：只缓存 `Image.open+convert("RGBA")`，resize 因目标图高度不同每文件重算。
  - **同番号等待**：`asyncio.Event` 即时唤醒，保留 1 秒超时循环检查停止/超时兜底；event 与 status 同 key 注册/释放。
  - **ScrapeStateCache**：WAL + `synchronous=NORMAL`，写操作 `commit=False` 批量积累（32 条自动 flush），`close()` 兜底 flush；普通调用保持即时提交兼容。
  - **json_data_dic 有界**：OrderedDict 上限 2000，写时 `move_to_end` + 超限 `popitem(last=False)`，只淘汰结果缓存不影响 json_get_status。
  - **info_db 索引**：加载时 `_normalize_info_key`（大写+全半角）+ `_build_info_db_index`（setdefault 保跨行首个匹配）建 dict，查询 O(1)；`get_info_data` 在索引空时惰性重建兼容外部直接替换 info_db 的测试替身。

[演员库结构与清洗方法论（TMDB 校验）]
- Date: 2026-08-04（2026-08-05、2026-08-06 更新）
- Context: 梳理本地 actor 数据分发读写路径、提取男优名单去噪、TMDB 全量排查非 AV 演员；曾评估 AVdb 同步后弃用
- Category: 运维部署
- Instructions:
  - **两层 actor 库**：出厂模板 `resources/userdata/actor_database.xlsx`（git 跟踪，新用户首启复制到运行时目录）；运行时实际读写库 `manager.data_folder/userdata/actor_database.xlsx`（`mdcx/core/tmdb_actor.py:_get_db_path`，默认 git 忽略）。dev 环境 `data_folder` 指向 /workspace，运行时库是 `/workspace/userdata/`。
  - **改库分清目标**：给用户实际用改运行时库；进 git 作新装默认改出厂模板并提交。
  - `get_actor_data(name)`（`resources.py`）按名反查返回 `birth_date`/`bio`/`has_name`，是 Emby 补全等下游统一查询入口；`emby_actor_info._process_actor_async` 先本地后 wiki/minnano/ActressDB 兜底，返回 bit3(8) 表示本地命中。
  - **AVdb 已弃用**：GUI 入口 v2.0.5 移除，不再从 AVdb 同步；`sync_from_avdb` 与相关测试保留供脚本复用但不主动建议。与该条目相关的 AVdb 匹配/清洗细节均已过时，实施时以 TMDB 校验为准。
  - **男优名单**：`resources/userdata/male_actors.txt`（625 人），脚本 `scripts/build_male_actor_list.py` 可复现，文档 `docs/male_actor_list.md`。
  - actor 字段噪声：标签词/括号/多名字/`×`/`？`。清洗：括号拆解、超长(>8)剔除、标签黑名单、去后缀。
  - 女优混入是最大风险（レズ片把女优填进 actor）：用 actress 字段交叉验证（actress 次数 ≥ actor×0.5，或 actor≤3 且 actress>0 判女优）。原则宁漏勿误删。
  - 双通道清洗：`clean_male_actors`/`filter_male` = 名单精确匹配 + TMDB gender=2 校验（名单命中不重复请求 TMDB）。
  - **宁缺毋滥**：错误 id 比无 id 更糟。曾清除 7120 行孤儿 url + 删疑似非 AV 3447 行（出厂库 24243→20796），详见 changelog「TMDB 演员身份排查与清理」。
  - 沙箱访问 TMDB：`api.themoviedb.org` 直连被证书劫持，用 `api.tmdb.org` 域名 + `Host: api.themoviedb.org` 请求头（`_resolve_tmdb_config` 即此）。

[openpyxl 删除行后 max_row 虚高与空行残留]
- Date: 2026-08-04
- Context: 重建出厂 actor_database.xlsx 时 delete_rows 删不干净空行
- Category: 排错调试
- Instructions:
  - 历史脏库上 `ws.delete_rows` 删空后 `max_row` 不变、空行残留（样式残留导致行号状态错乱）。
  - 可靠方案：重建工作簿——`iter_rows` 过滤 `row[0] is None` 读非空行，`Workbook()` 新建 append 表头+数据、重设样式/auto_filter/freeze_panes。重建后 max_row 精确。
  - 删除数据行（clean_male_actors 删男优）在干净重建库上正常。`check_actor_db` 遍历到 max_row 报大量"jp 为空"即空行残留信号。

[specs 目录已删除]
- Date: 2026-08-04
- Context: 用户决定清理 .monkeycode/specs/（已实现功能的 EARS 需求/设计/任务清单）
- Category: 工作流协作
- Instructions:
  - `.monkeycode/specs/` 已删（提交 f4c52db），实现意图可从代码、`tests/`、`docs/changelog.md` 回溯。
  - 未来 `/feature-design` 新生成 spec 会重新出现，实现验证后可按偏好清理或保留。

[ruff RUF100 误删 scripts/*.py 防御性 noqa 的坑]
- Date: 2026-08-10
- Context: RUF100 自动修复把 scripts/*.py 顶部 `# ruff: noqa: E402` 判 unused 删除导致 import 失败
- Category: 工作流协作
- Instructions:
  - scripts/*.py 顶部 noqa: E402 是必要的（脚本内 `sys.path.insert` hack 依赖）；E402 未启用时 RUF100 误判多余，保留以防未来启用。
  - 启用 RUF100 自动修复只应用到 `mdcx/` 与 `main.py`，scripts/ 需 git checkout 回滚。
  - 探测性 import（try/except ImportError 内）显式标注 `# noqa: F401  # 探活`。已应用：`mdcx/cf_bypass/local_server.py`、`mdcx/config/resources.py`、`mdcx/core/amazon.py`。

[看到"死代码"先怀疑是功能从未运行]
- Date: 2026-08-11
- Context: 把 PreparePreviewThread 的 `self.minnano_cache = None` 判为死代码删除，实为 QThread.run 里 `from .emby_actor_manager import load_cache` 导入路径错误，预览功能对启用 minnano 缓存的用户从未跑过
- Category: 排错调试
- Instructions:
  - 疑似死代码先问三点：赋值点在哪（赋值本身是否抛异常）、读取点在哪（所在函数是否被调用）、中间产物是否由别处写入（死字段≠死功能）。
  - 删死字段前必须先实测验证功能是否正常（最小复现 import/跑一遍），不能因字段没人用判定整个功能在跑。
  - 用户"是不是可复用"的反问是高价值信号，小白的常识直觉能刺穿专家盲点。

[devbox 验证环境默认代理指向无进程的 127.0.0.1:7890]
- Date: 2026-08-14
- Context: 多次踩坑（r18dev/javbus 高清、DMM 图下载、check_url）——所有走 manager.acquire_computed() 的请求失败，curl 报 proxy 127.0.0.1 连接失败
- Category: 环境配置
- Instructions:
  - 根因：mdcx 默认 `use_proxy=True` + `proxy=http://127.0.0.1:7890`，devbox 无该代理进程。非代码 bug，是验证环境差异。
  - 定位：打印 `manager.config.use_proxy`/`manager.config.proxy`（值 7890/True）；同一 URL curl 直连 200 而 client 失败即中招。
  - 绕过：`manager._replace_config(manager.config.model_copy(deep=True))` 后设 `cfg.use_proxy=False`、`cfg.proxy=""` 再 `_replace_config(cfg)`。直接赋值不生效（Computed client import 时已构建），仅内存态不影响配置文件。
  - 真实用户环境有可用代理，**不要据此改产品代码**。

[devbox 跑 uv run check 需装系统 GUI 库]
- Date: 2026-08-19
- Context: devbox 首次跑 `uv run check --skip-hook-install` 时 pytest 收集阶段 ImportError（PyQt6 依赖的系统库缺失）
- Category: 环境配置
- Instructions:
  - uv 通过 pip3 安装：`pip3 install uv`（装到 `/usr/local/bin/uv`），首次 `uv run` 自动拉 Python 3.13/3.14 + 装依赖到 `.venv/`。
  - devbox 缺 PyQt6 运行所需的系统库，pytest import `mdcx.image`（依赖 PyQt6.QtGui/QtCore）时报 `libglib-2.0.so.0`/`libfontconfig.so.1`/`libGL.so.1` 等 not found。
  - 一次性补装：`DEBIAN_FRONTEND=noninteractive apt-get install -y libglib2.0-0 libgl1 libegl1 libdbus-1-3 libfontconfig1 libxkbcommon0 libxkbcommon-x11-0 libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0`（先 `apt-get update`）。
  - 装齐后全量 check 可跑通：ruff format --check + ruff check + mypy mdcx/ + pytest（1095 passed）+ check_actor_db + check_info_db + check_thread_safety。
  - `uv run` 执行的 Python 实际版本可能是 3.14.x（uv 取满足 `requires-python` 的最新版），项目要求 `>=3.13.4`。

[GitHub CI 失败 runs 批量清理流程]
- Date: 2026-08-14
- Context: 批量删除 Actions 页 CI/CD Pipeline #579-#591 共 13 个失败 run
- Category: 排错调试
- Instructions:
  - 凭据：`echo -e "protocol=https\nhost=github.com\n" | git credential fill` 取 password 作 GH_TOKEN。
  - 列 runs：`gh run list --workflow ci.yaml --limit 30 --json databaseId,conclusion,number`，筛选 failure；逐条 `gh run delete <databaseId>`。
  - GH_TOKEN 需在 bash 调用前 export（新 shell 不继承），用完即删避免泄露。

[时间以北京时间为准]
- Date: 2026-08-19
- Context: 用户是中国开发者，开发环境（devbox）系统时区为 UTC（+0000），git 提交时间戳显示 UTC
- Category: 工作流协作
- Instructions:
  - **所有文档/记忆/changelog 中的日期标注一律使用北京时间（UTC+8）**，不直接照抄 git log 的 UTC 时间戳或系统 date 输出。
  - 北京时间换算：UTC + 8 小时。例如 UTC 08-18 16:00 = 北京 08-19 00:00；本次改动按北京时间发生在 08-18 ~ 08-19。
  - 写 changelog 版本日期、记忆条目 Date、发布 Tag 日期时，先换算成北京时间再写。

[功能改动同步 UI 说明文字、弹窗与文档]
- Date: 2026-08-18
- Context: 新增 avmoo/avheat 爬虫、移除内置 CF Bypass 等大量功能改动后，用户发现 UI 使用说明页、启动提示弹窗、仓库文档存在过时内容（如还写着"启用内置 Bypass"、网站数量仍 45 个）
- Category: 工作流协作
- Instructions:
  - 功能改动（新增/移除/改名站点、爬虫、CF 服务、配置项）完成后，必须检查并同步以下用户可见文字：
    - **UI 使用说明页**：`mdcx/views/MDCx.ui` 内的帮助文档 HTML（章节"四、网站选择"的网站数量与站点列表、"五、Cloudflare 绕过"等），改 `.ui` 后重编译 `MDCx.py`。
    - **启动提示/弹窗**：`mdcx/controllers/main_window/main_window.py` 的启动提示（show_net_info）与 `_show_tips` 帮助弹窗、二次弹窗（QMessageBox）文字。
    - **仓库文档**：`README.md`、`docs/*.md`（FEATURES 网站列表与数量、CONFIGURATION 配置项表、USER_GUIDE 常见问题、DEVELOPMENT 架构说明）。
  - 网站数量必须与 `get_registered_crawler_sites()` 实际注册数一致（如新增爬虫后 45→47），不要只改一处。
  - 移除功能时同步删除对应 UI 控件/说明文字/配置项描述（如移除内置 CF 后清理"启用内置 Bypass"开关、placeholder 示例、文档中的内置服务描述）。
  - changelog 随改动更新见「提交推送与质量把关」条目。
