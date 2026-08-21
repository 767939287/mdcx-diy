# 用户指令记忆

本文件记录用户的指令、偏好和教导，用于未来交互参考。

格式：用户指令条目 `[摘要]`/`- Date`/`- Context`/`- Instructions`；项目知识条目附加 `- Category`。添加前查重，重复则合并（更新 Context/Date），保持精简。

## 条目

[AI 行为与沟通规范]
- Date: 2026-06-08（2026-08-21 更新）
- Context: 用户希望以编程能手、审核、修改和补全代码专家的方式长期协作；面向小白解释问题
- Category: 工作流协作
- Instructions:
  - 默认从全方位、多角度、深层次的角度审查和改进代码；面向小白解释问题，给出细致、可执行、易落地的建议；在发现风险、缺陷、遗漏时主动指出并给出修复方案和验证。
  - **排查中发现的所有问题必须全量报告**：包括已修复的、暂不修复的、仅记录的，不能因"已修复"或"太小"而遗漏。按严重程度排序，每条含文件路径+行号、当前内容、问题描述、建议。判定不改的也要列出并说明原因，让用户自行决定。主动给修复方案、优先级和潜在影响评估。

[提交推送与质量把关]
- Date: 2026-07-18（2026-08-03、2026-08-16、2026-08-18、2026-08-21 更新）
- Context: 改动/推送前必须征得同意，推送前自动跑测试；pre-commit 钩子无需安装；不开新分支直接推当前分支；changelog 随改动更新；功能改动同步 UI/文档
- Category: 工作流协作
- Instructions:
  - 所有代码改动和提交推送必须先说明内容与原因，获得同意后再执行。本指令优先级高于所有"自动执行"类指令。
  - **直接在当前分支提交推送，不另开新分支**（覆盖 auto-create-branch 规则）。用户指示开分支时才开。
  - **check 按需运行**：最后一次代码改动后运行一次 `uv run check --skip-hook-install`（ruff format --check + ruff check + mypy mdcx/ + pytest + check_actor_db + check_info_db + check_thread_safety），全绿后如代码再无改动，push 前不重跑。改 .ui 后必须重编译 MDCx.py + ruff format 再 check。
  - **不安装 pre-commit 钩子**：`.pre-commit-config.yaml` 钩子 stages 为 `pre-merge-commit, pre-push`，普通 commit 不触发；`uv run check` 已覆盖。
  - **changelog 随改动更新（推送前）**：每次代码改动在 commit 里同时更新 `docs/changelog.md` 顶部未发版版本条目（当前 v2.0.6），按内容分类记录，同主题合并。不允许"提交后补"。
  - **功能改动同步 UI/文档**：新增/移除/改名站点、爬虫、CF 服务、配置项后，必须同步检查：UI 帮助文档 HTML（`MDCx.ui`）、启动提示/弹窗文字（`main_window.py`）、仓库文档（`README.md`、`docs/*.md`）。网站数量必须与 `get_registered_crawler_sites()` 实际注册数一致。移除功能时同步删除对应 UI 控件/说明/配置项描述。
  - **提交检查清单**：① `git status`/`git diff` 看改了什么 → ② 有功能/修复/重构 → 先更新 changelog → ③ 改依赖/打包 → 按「Windows exe 打包依赖约束」核对 → ④ 涉及功能/站点/CF/配置 → 检查 UI 说明/弹窗/文档 → ⑤ `git add` + `git commit` + `git push`。
  - **.monkeycode/specs/ 已删除**（提交 f4c52db），实现意图从代码/`tests/`/`docs/changelog.md` 回溯；未来 feature-design 新生成 spec 实现验证后可清理。

[Windows exe 打包依赖约束]
- Date: 2026-08-03（2026-08-18 更新）
- Context: 用户以单 exe 运行，改动需兼容 Windows 单 exe 打包发布
- Category: 环境配置
- Instructions:
  - 优先标准库，不主动引入三方依赖；持久化路径沿用 `resources`/`userdata` 目录习惯。
  - 延迟导入模块须加入 `scripts/build.py` 的 `--hidden-import`/`--collect-all`，否则 exe 报 ModuleNotFoundError。顶层 import 的三方依赖 PyInstaller 自动收集。`EXCLUDED_MODULES` 排除的包（rich/typer 等）绝不能被 GUI 运行期引用。已知 rich/typer 仅 CLI 脚本 `mdcx/cmd/crawl.py` 使用，不被打包，排除安全。
  - 改 `pyproject.toml` 依赖、`scripts/build.py`、`.github/workflows/build-windows.yml`/`release.yml`、或运行时引入新三方依赖时，必须按上述清单逐项核对，确认无遗漏再提交。

[UI 改动与排查注意事项]
- Date: 2026-08-03（2026-08-16、2026-08-21 更新）
- Context: 多次调整工具页 UI 沉淀约束；排查 UI 功能时漏看弹窗模块误报
- Category: 环境配置
- Instructions:
  - **规范流程**：先改 `.ui` → `uv run python -m PyQt6.uic.pyuic mdcx/views/MDCx.ui -o mdcx/views/MDCx.py` → `uv run ruff format mdcx/views/MDCx.py`。不要手工改 MDCx.py（`test_mdcx_py_in_sync_with_ui` 把关）。新文案必须回写 `.ui` 让其成唯一权威源。改后跑 `uv run pytest tests/test_ui_structure.py -q` 验证。
  - **groupBox 绝对定位**：`page_tool` 滚动区内增高某 groupBox 后须连锁把下方所有兄弟 groupBox y 同步 +delta，并同步增高滚动区高度（底部留 20px）。
  - **gridLayout 陷阱**：同一 `row:col` 只能放一个 widget/layout，多个会覆盖/重影。长 label 用 `addWidget(w, row, 0, 1, 2)` 跨整行 + `setWordWrap(True)`。新增控件前先 `grep -n` 扫描现有 row/col 分布。
  - **中文字体等宽**：统一用 `font:"Courier New"`，不用裸 `"Courier"`（中文显示方框）。
  - **排查 UI 必须覆盖弹窗**：排查功能时搜索所有 QDialog 子类和弹窗模块（`grep -rn "QDialog\|class.*Dialog"`），不能只看主窗口。项目弹窗集中在 `mdcx/controllers/main_window/site_priority_dialog.py` 等独立文件。典型坑：配置项在二次弹窗（如 FieldPriorityDialog），主窗口只放触发按钮，不看弹窗内部就误判"UI 没暴露该配置"。
  - 新增按钮检查三处一致：`MDCx.ui` + `MDCx.py` + `init.py`（clicked 槽 + setText 防重入）。删除按钮后清理失联 delegate 死代码。

[排错调试方法论]
- Date: 2026-08-03（2026-08-04、2026-08-11、2026-08-21 更新）
- Context: Onefile 静默退出、openpyxl 空行残留、死代码误删、UI 弹窗漏查等典型坑
- Category: 排错调试
- Instructions:
  - **疑似死代码先怀疑功能从未运行**：问三点——赋值点在哪（是否抛异常）、读取点在哪（是否被调用）、中间产物是否由别处写入。删前必须先实测验证功能正常（最小复现 import/跑一遍）。用户"是不是可复用"的反问是高价值信号。
  - **Onefile 静默退出**：`-w` 下普通 Python 异常被静默吞掉（`sys.__stderr__` 不存在），表现为程序直接退出。诊断三件套：`faulthandler.enable()` + `sys.excepthook` 写文件 + stdout/stderr 重定向到 `MAIN_PATH/crash/`。工具内部日志走 `signal_qt.show_log_text`，`LogBuffer.log().write()` 只存内存不显示。
  - **openpyxl delete_rows 空行残留**：历史脏库上 `delete_rows` 后 `max_row` 不变、空行残留（样式残留导致行号错乱）。可靠方案：重建工作簿——`iter_rows` 过滤空行，`Workbook()` 新建 append 表头+数据、重设样式。`check_actor_db` 报大量"jp 为空"即空行残留信号。

[executor.submit 与跨线程 Qt 安全]
- Date: 2026-08-03（2026-08-16 更新）
- Context: 修复演员库工具按钮 + Emby 演员管理器 executor.run 阻塞主线程问题
- Category: 工作流协作
- Instructions:
  - `AsyncBackgroundExecutor.submit(coro)` 只收单个协程对象，正确写法 `executor.submit(run())`；`submit(asyncio.run, run())` 报 TypeError。
  - 协程在后台线程事件循环执行，不可直接操作 QWidget。模式：主线程 setEnabled(False)+emit"运行中"，协程 finally 发射 pyqtSignal（线程安全），主线程槽恢复。
  - **Emby 阻塞陷阱**：`_on_connect`/`_on_fetch` 等按钮槽在主线程调 `executor.run()` 同步阻塞。`signal.show_log_text`（主界面）vs `self.log`（管理器日志框）是两条独立通道，管理器日志空不代表网络请求没在跑。
  - **Emby 弹窗保存陷阱**：`EmbyActorSettingsDialog._save` 等必须补 `manager.save()`，否则退出重进配置恢复原样。
  - **跨线程收口工具**：新代码后台任务统一用 `mdcx/utils/qt_thread.py::run_in_background(button=, coro_factory=, busy_signal=, busy_text=, finished_signal=, finished_arg=, log_prefix=)`。需要回传结果时用自定义 Signal + `add_done_callback(lambda fut: self.xxx_signal.emit(_future_result_or(fut, default)))`，协程只返回结果不碰 QWidget。模态弹窗 `exec()` 改非模态 `show()`。
  - **跨线程安全扫描**：`scripts/check_thread_safety.py` AST 扫 async def 体内直接操作 QWidget setter 的违规，新增后台协程前跑一遍防回归。

[并发与性能优化约束]
- Date: 2026-08-03（2026-08-17 更新）
- Context: 刮削并发架构 + 性能优化批次 + 启动数据库延迟加载沉淀的可复用模式
- Category: 构建方法
- Instructions:
  - **刮削两层并发**：文件间 `_run_tasks_with_limit`（滑动窗口 `asyncio.wait(FIRST_COMPLETED)`，并发=配置 thread_number）；文件内 `_call_crawlers` 多站点 `asyncio.gather`。慢常是单站点超时拖累。新增异步批量工具优先用滑动窗口而非 `Semaphore+gather`。
  - **httpx session 绑定全局 loop 是硬约束**：`computed.async_client` 在全局 executor loop 创建，跨 loop 复用会破坏连接池/代理/CF-bypass。网络请求必须留在全局 loop。
  - **启动重型资源后台加载**：`Resources` 构造只做路径/图标/字典，XLSX 迁移合并加载走 `start_data_loading()` 后台线程 + `ensure_data_ready()` 同步屏障，GUI 首屏不被阻塞。
  - **save_remain_list 后台写**：QTimer 触发时快照 `list(Flags.remain_list)` 后丢 daemon 线程，`threading.Lock` 防重复，主线程不写盘。
  - **ScrapeStateCache**：WAL + `synchronous=NORMAL`，写操作 `commit=False` 批量积累（32 条自动 flush），`close()` 兜底 flush。
  - **json_data_dic 有界**：OrderedDict 上限 2000，写时 `move_to_end` + 超限 `popitem(last=False)`。
  - **info_db 索引**：加载时 `_normalize_info_key`（大写+全半角）+ `_build_info_db_index` 建 dict，查询 O(1)。

[演员库结构与清洗方法论（TMDB 校验）]
- Date: 2026-08-04（2026-08-05、2026-08-06 更新）
- Context: 梳理本地 actor 数据读写路径、提取男优名单去噪、TMDB 全量排查非 AV 演员
- Category: 运维部署
- Instructions:
  - **两层 actor 库**：出厂模板 `resources/userdata/actor_database.xlsx`（git 跟踪，新用户首启复制）；运行时实际读写库 `manager.data_folder/userdata/actor_database.xlsx`（默认 git 忽略）。给用户用改运行时库，进 git 作新装默认改出厂模板并提交。
  - `get_actor_data(name)`（`resources.py`）按名反查返回 `birth_date`/`bio`/`has_name`，是 Emby 补全等下游统一查询入口。
  - **AVdb 已弃用**：GUI 入口 v2.0.5 移除，`sync_from_avdb` 与测试保留供脚本复用但不主动建议。
  - **男优名单**：`resources/userdata/male_actors.txt`，脚本 `scripts/build_male_actor_list.py` 可复现。
  - **清洗**：括号拆解、超长(>8)剔除、标签黑名单、去后缀。女优混入是最大风险（レズ片女优填进 actor），用 actress 字段交叉验证。双通道清洗：名单精确匹配 + TMDB gender=2 校验。宁缺毋滥。
  - 沙箱访问 TMDB：用 `api.tmdb.org` 域名 + `Host: api.themoviedb.org` 请求头。

[ruff RUF100 误删 scripts/*.py 防御性 noqa 的坑]
- Date: 2026-08-10
- Context: RUF100 自动修复把 scripts/*.py 顶部 `# ruff: noqa: E402` 判 unused 删除导致 import 失败
- Category: 工作流协作
- Instructions:
  - scripts/*.py 顶部 noqa: E402 是必要的（脚本内 `sys.path.insert` hack 依赖）；E402 未启用时 RUF100 误判多余，保留以防未来启用。
  - 启用 RUF100 自动修复只应用到 `mdcx/` 与 `main.py`，scripts/ 需 git checkout 回滚。
  - 探测性 import（try/except ImportError 内）显式标注 `# noqa: F401  # 探活`。

[devbox 验证环境配置]
- Date: 2026-08-14（2026-08-19 更新）
- Context: devbox 默认代理指向无进程的 127.0.0.1:7890 导致请求失败；首次跑 check 时 PyQt6 依赖系统库缺失
- Category: 环境配置
- Instructions:
  - **默认代理坑**：mdcx 默认 `use_proxy=True` + `proxy=http://127.0.0.1:7890`，devbox 无该代理进程。定位：打印 `manager.config.use_proxy`/`proxy`；同一 URL curl 直连 200 而 client 失败即中招。绕过：`manager._replace_config(cfg)` 后设 `use_proxy=False`、`proxy=""` 再 `_replace_config`。真实用户环境有可用代理，**不要据此改产品代码**。
  - **系统 GUI 库**：devbox 缺 PyQt6 运行所需系统库，pytest import `mdcx.image` 时报 `libglib-2.0.so.0` 等 not found。一次性补装：`DEBIAN_FRONTEND=noninteractive apt-get install -y libglib2.0-0 libgl1 libegl1 libdbus-1-3 libfontconfig1 libxkbcommon0 libxkbcommon-x11-0 libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0`（先 `apt-get update`）。uv 通过 `pip3 install uv` 安装，`uv run` 可能拉 Python 3.14.x。

[GitHub CI 失败 runs 批量清理流程]
- Date: 2026-08-14
- Context: 批量删除 Actions 页 CI/CD 失败 run
- Category: 排错调试
- Instructions:
  - 凭据：`echo -e "protocol=https\nhost=github.com\n" | git credential fill` 取 password 作 GH_TOKEN（需在 bash 调用前 export，用完即删）。
  - 列 runs：`gh run list --workflow ci.yaml --limit 30 --json databaseId,conclusion,number`，筛选 failure；逐条 `gh run delete <databaseId>`。

[时间以北京时间为准]
- Date: 2026-08-19
- Context: 开发环境系统时区为 UTC，git 提交时间戳显示 UTC
- Category: 工作流协作
- Instructions:
  - 所有文档/记忆/changelog 中的日期标注一律使用北京时间（UTC+8），不直接照抄 git log 的 UTC 时间戳或系统 date 输出。

[长时间后台任务的断点续传与自动循环]
- Date: 2026-08-20
- Context: fill_zh_javdb 演员库补全任务需处理 18606 行，单轮 47 分钟只能跑 ~2400 条
- Category: 构建方法
- Instructions:
  - **后台 1 小时硬超时**：background_terminal_create timeout 默认 1 小时会被强杀，长任务必须设 `--max-runtime`（建议 2820s≈47min）。
  - **断点续传**：每批完成后写 state 文件（JSON `{"offset":N,"updated":M}`），重启时读取 offset 续跑。state 文件加入 `.gitignore`。
  - **单轮退出后自动循环重启**：脚本拆成 `run_round()` + 外层 `for round_num in range(max_rounds)`，单轮 max_runtime 到期保存 state 返回，外层 `await asyncio.sleep(5)` 后自动下一轮。设 `--max-rounds` 上限防无限循环。
  - **分批处理**：单批 200 条，`count_pending(offset)` 每轮统计剩余避免空跑。
  - **并发踩坑**：JavDB API 高并发（15/8）反而被限流降吞吐，实测并发 5 是天花板（~1 条/s）。临时脚本放 `scripts/` 并在 `.gitignore` 排除。
  - **内存预算**：background_terminal_create 前先 `background_terminal_list` 检查现有终端，新增 memory_percent + 既有总额不超环境总内存 85%。
