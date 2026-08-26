# 用户指令记忆

本文件只记录长期有效的行为规范、构建发布流程、排错方法和环境约束。项目实现细节以代码、测试和文档为准。

## 协作与质量

- Date: 2026-08-24
- Category: 工作流协作
- Instructions:
  - 所有回复使用简体中文；面向小白说明时按“现象和影响 → 原因 → 可执行步骤”组织。
  - 代码修改或提交推送前说明内容与原因；用户明确要求提交/推送后才执行。直接在当前分支操作。
  - 每次代码改动后运行 `uv run quick-check`；提交前最后一次改动后运行 `uv run check --skip-hook-install` 并确认退出码。仅改 `docs/*.md` 或 MEMORY.md 时只需 `git diff --check` 并审阅内容。
  - 不安装 pre-commit；提交前更新 `docs/changelog.md` 当前版本条目并合并同类内容；文档日期用北京时间（UTC+8）。
  - 修改站点、爬虫、CF 服务或配置项时，同步检查 UI 文案（含启动文字 main_window.py 与 .ui）、README 和 `docs/*.md`；爬虫数量以 `get_registered_crawler_sites()` 为准。

## UI 开发与排错

- Date: 2026-08-24
- Category: UI 开发与排查
- Instructions:
  - UI 修改先改 `.ui`（文案和布局唯一权威源），再运行 pyuic 重生成 MDCx.py、`ruff format`、`tests/test_ui_structure.py`；不要手工改生成的 `MDCx.py`。
  - QLabel 长文本用 `wordWrap` 并检查运行时 sizeHint；固定 minimumHeight 在 Windows 字体/DPI 下可能裁切底部，底部留约 60px 余量。QCheckBox/RadioButton/PushButton/GroupBox 不支持 wordWrap。
  - 主窗口全局为绝对定位布局（centralwidget 无布局管理器），窗口缩放靠 MyMAinWindow.resizeEvent 手动同步导航栏/stackedWidget/进度条几何；新增顶层悬浮控件时记得纳入该同步。
  - 绝对定位滚动内容统一走 CustomScrollArea.sync_content_min_height（childrenRect 补最小宽高）；widgetResizable=true 不保证垂直滚动可用。
  - 打包前逐页切换 stackedWidget 执行 show()+processEvents() 审计全部页面边界与溢出；配合 scripts/check_ui_layout.py、tests/test_ui_geometry.py、test_main_window_startup.py。
  - Qt 同名 API 重载签名不同（如 QLayout/QSplitter 的 setStretchFactor），修改前先确认目标类签名。
  - 测试桩显式枚举需要的属性方法，不用 __getattr__ 通配；生产代码可能依赖 AttributeError 降级。
  - Onefile 无控制台异常用 faulthandler + sys.excepthook + MAIN_PATH/crash/ 日志定位；GUI 日志走 signal_qt.show_log_text。
  - 删除代码前检查赋值点、读取点、装饰器注册、延迟 import 和动态工厂，删后重扫死 import 与零引用。

## 站点与网络

- Date: 2026-08-25
- Category: 排错调试
- Instructions:
  - 各站探测番号（probe_number）及收录依据见对应爬虫类注释；收录情况随站点变化以实测为准。javdb 搜普通番号无需 Cookie，仅 FC2 需 Cookie。
  - missav_api Recombee search 仅接受 POST；DMM Affiliate v3 ItemList 必需 site/service/floor，keyword 用 content_id 形态（ssis00200）才能精确命中；MGStage 主站非日本 IP 403 但 image.mgstage.com 图源无地域限制。
  - madouqu 域名由发布页 wangzhi.icu/config.js 动态维护（web.py::get_madouqu_domains，24h 缓存）；解析外部站点配置时优先找其 JS 引用的明文数据源。
  - madou.club：番号无横杠+集数后缀（MDX0236-01），搜索必须无横杠关键词；封面只在搜索页缩略图（covers 去 -240x180 后缀即原图）；Safari iOS 指纹稳定过 CF。
  - 7mmtv.sx 新上 CF「Just a moment」JS 挑战，纯指纹全拦，依赖 TRAWL/FlareSolverr 外部 CF Bypass 服务自动通过；javbus 镜像池实测结论见 mdcx/crawlers/javbus.py 注释。
  - 已删 11 站（2026-08 用户决定）：失效=cnmdb/hdouban/mdtv/love6/kin8/giga/cableav；数据重复下线=jav321/fantastica + dahlia/faleno（模块保留为 official 厂牌子爬虫，_skip_auto_register=True 且 site() 返回 OFFICIAL）。若恢复从 git 历史找回并重建枚举/注册/默认源。
  - heyzo.com/caribbeancom.com/1pondo.tv 五个无码官网由 official 爬虫统一路由（mdcx/crawlers/official_uncensored.py），勿重复开发独立爬虫；三站均被墙，已加入默认走代理列表；1pondo 首页有反 bot 壳（curl_cffi 指纹也拿不到数据），但其 dyn/phpauto JSON API 不设防可直接访问。
  - 日本 IP 地理限制站点（2026-08-26 实测）：faleno.jp（非日本 IP 403 且对 TLS 指纹苛刻，免费日本节点全被拒）、giga-web.jp（年龄确认 cookie 机制）、mywife.cc（被墙+日本节点才通）。测这类站用 `scripts/dev_proxy.py start --port 7891 --regions "jp|日本"` 起纯日本节点实例；mgstage 主站同样非日本 IP 403。免费节点里 maflya 订阅日本节点最多（23 个）。
  - 被墙站点测试代理：`uv run python -m scripts.dev_proxy start|status|test <url>|stop`（mihomo 内核自动下载到系统临时目录，proxy-providers 直接引用订阅 URL 免 yaml 解析，url-test 自动选节点）；启动后等 10-20 秒节点测速完成再用；支持 --port 多实例并存、--regions 按地区过滤节点、--source 自定义订阅。
  - parsel Selector.get() 对纯 JSON 文本直接返回 dict 而非字符串，JSON API 类爬虫解析入参兼容 str/dict/Selector 三态。
  - devbox 环境限制：部分日本站/被墙站超时属云端限制不代表站点死亡；高频批量测试会触发站点 CF IP 级临时拉黑，失败先换时段重试再下结论；出口 IP 被个别站点屏蔽（如 jav321 HTTP 000）时以用户浏览器实测为准。
  - 站点连通性验证必须用 curl_cffi impersonate 指纹（httpx 无指纹会被 javbus/freejavbt 等软拦截返回空壳页）；AsyncWebClient 裸脚本调用退出时会抛 CancelledError。

## Windows 打包与发布

- Date: 2026-08-24
- Category: 环境配置
- Instructions:
  - 函数内延迟导入的模块必须同步加入 scripts/build.py 的 --hidden-import 或 --collect-all；修改依赖、构建脚本或 Release 工作流时逐项核对。
  - EXCLUDED_MODULES 中的 rich/typer 等只供构建或 CLI 环境，GUI 运行期不得引用；Windows curl_cffi.libs 需显式 --add-binary 收集。
  - Release Tag 用纯数字 YYYYMMDD（check_version 对 tag 做 int()），双平台构建都显式传 Tag；scripts/*.py 顶部的 `# ruff: noqa: E402` 与探测 import 的 `# noqa: F401` 必须保留。

## 并发与数据

- Date: 2026-08-24
- Category: 构建方法
- Instructions:
  - 文件间批量任务用 asyncio.wait(FIRST_COMPLETED) 滑动窗口，文件内多站点用 gather；网络请求不跨 executor loop 复用。
  - 后台协程统一用 utils/qt_thread.py::run_in_background，不得直接操作 QWidget，结果经 Qt signal 回主线程；新增后跑 scripts/check_thread_safety.py。
  - 重型 XLSX 后台加载 + ensure_data_ready() 屏障；QTimer 写盘先快照再交带锁后台线程。
  - 出厂模板在 resources/userdata/，运行时数据在 manager.data_folder/userdata/，勿混淆；devbox 代理 127.0.0.1:7890 可能无进程，排查网络时临时关闭代理而不改产品默认配置。
