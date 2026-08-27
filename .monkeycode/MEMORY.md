# 用户指令记忆

本文件只记录长期有效的行为规范、构建发布流程、排错方法和环境约束。项目实现细节以代码、测试和文档为准。

## 协作与质量

- Date: 2026-08-27
- Category: 工作流协作
- Instructions:
  - 简体中文回复；面向小白说明按"现象和影响 → 原因 → 可执行步骤"组织。
  - 改动前说明内容与原因；用户明确要求提交/推送后才执行，绝不擅自操作。直接在当前分支操作。
  - 每次代码改动后跑 `uv run quick-check`；提交前跑 `uv run check --skip-hook-install` 并确认退出码。仅改 `docs/*.md` 或本文件时只需 `git diff --check`。
  - 提交前必看 `git status` 全部未跟踪文件：程序运行时残留（如配置损坏回退 `_failed.json`）不得 `git add -A` 入库，应 `.gitignore` 排除后单独清理；本次已有教训（2026-08-27 误提交后再补救）。
  - 不装 pre-commit；提交前更新 `docs/changelog.md` 当前版本条目并合并同类；文档日期用北京时间。
  - 站点/爬虫/配置改动须同步检查 UI 文案（启动文字 main_window.py、.ui）、README、`docs/*.md`、爬虫总数（`crawler_names()` 长度）。
  - 文档/UI 中写死数字或清单前必须先 grep 代码核实，禁止凭记忆。高频漂移锚点（2026-08 核查实证）：默认网站源顺序（`config/models.py` ↔ `resources/config/default_config.json`，`test_config_conversion.py::test_config_default_site_priorities_follow_current_frontend_defaults` 锁定，改注释勿动枚举）、代理域名列表（`Config.proxy_sites`）、命名变量表（`core/naming/fields.py::FIELD_DESCRIPTIONS`）、设置 Tab 名（tabWidget.setTabText）、水印行为（`MarkType` 徽标+角落轮转，无文字水印）、字段优先级数（`manual.py::REDUCED_FIELDS`）、演员库列（`resources.py::DB_HEADERS`）、指纹池（`network_fingerprint.py`，默认 7/Amazon 6，无令牌桶限流）、主窗口行数（`wc -l controllers/main_window/*.py`）。

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
