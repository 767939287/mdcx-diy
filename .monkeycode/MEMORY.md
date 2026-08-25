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

## 站点与网络排错

- Date: 2026-08-25
- Category: 排错调试
- Instructions:
  - 各站网络检测探测番号（probe_number）及收录依据见对应爬虫类注释；番号收录情况随站点数据库变化，以实测为准。
  - javdb 检测失败主因是 Cloudflare 拦截；搜普通番号无需 Cookie，仅 FC2 番号搜索需要 Cookie。
  - missav_api 的 Recombee search 端点只接受 POST（GET 返回 405），公开 token 仅授权部分端点；检测须走 POST /search/users/anonymous/items/ 真实路径。
  - DMM Affiliate API v3 ItemList 必需 site/service/floor 参数（缺失返回 400 BAD REQUEST）；keyword 需 content_id 形态（小写前缀+编号补零 5 位，如 ssis00200）才能精确命中，带横杠格式搜索为 0 结果，特殊站内前缀系列回退厂牌词模糊搜索。
  - MGStage 主站详情页非日本 IP 返回 403，但 image.mgstage.com 图片 CDN 直链无地域限制，可用 mgstage_direct.py 的直链规律验证番号收录情况。
  - madouqu 域名由官方发布页 wangzhi.icu/config.js 动态维护（web.py::get_madouqu_domains 解析 domainConfig['md'] 区块，24h 缓存+静态回退）；发布页主体是混淆 JS 渲染，真实数据源是其同域明文 config.js——解析外部站点配置时优先找其 JS 引用的数据源。
  - MDTV 默认域名 mdpjzip.xyz 与 CNMDB 默认域名 cnmdb.net 均已失效（2026-08-25 用户确认）：mdpjzip.xyz 有 JS 挑战防护且迁移至 ww1.mdpjzip.xyz（devbox 无法稳定访问）；cnmdb.net 302 到无关博彩 TG 页（域名被劫持）。两站待用户提供新域名后校准，当前探测番号暂配 MDX-0236。
  - devbox 全量连通性实测（2026-08-25）：devbox 出口对部分日本站/被墙站超时属云端限制（faleno/xcity/mywife/7mmtv/javdb 系等），不代表站点死亡；kin8 检测项 SPECIAL_CHECK_PATHS 样例页 /moviepages/3681 已 404 需换新样例；getchu/getchu_dmm/fantastica/cableav/giga 连通但默认番号探测不命中（单收录范围站，probe_number 待校准）；fc2club/fc2ppvdb 探测异常待查。
  - devbox 高频批量测试会触发站点 CF 的 IP 级临时拉黑（首轮 200 的站次轮批量 403），测试结果需区分"站点问题"与"测试频率风控"；httpx 无浏览器指纹会被 javbus/freejavbt 等站软拦截返回空壳页，验证必须用 curl_cffi impersonate 指纹。parsel Selector.get() 对纯 JSON 文本会直接返回 dict 而非字符串，JSON API 类爬虫解析入参需兼容 str/dict/Selector 三态。
  - javbus 镜像池实测（2026-08-25）：可用=dmmsee.cyou/javsee.cyou/cdnbus.bond/cdnbus.cyou/fanbus.bond/dmmbus.bond；SSL 死亡已删=busjav.bond/seejav.cyou/buscdn.bond/javbus.bond；持续 CF 未纳入=busdmm.bond。devbox 对 javbus 系详情页路径会触发 CF（首页正常），本地验证以实际网络检测为准。
  - madou.club 实测（2026-08-25）：站内番号格式为无横杠+集数后缀（MDX0236-01），搜索必须无横杠关键词（?s=MDX-0236 零结果、?s=MDX0236 命中）；详情页只有标题/分类/标签与 iframe 播放器，封面仅存在于搜索页缩略图（covers 路径去 -240x180 尺寸后缀即原图）；CF 对桌面指纹拦截强，Safari iOS 稳定通过；devbox 出口对该站连接抖动极大（SSL_ERROR_SYSCALL 成批出现、时段性整体断连），验证失败先换时段重试再下结论。
  - devbox 出口 IP 被部分站点屏蔽（如 jav321 HTTP 000），沙箱内无法复现的行为以用户浏览器实测为准；AsyncWebClient 在裸脚本中直接调用会在退出时抛 CancelledError，轻量验证改用 httpx。

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
