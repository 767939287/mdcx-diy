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

## 日亚数据库校正与验证链路

- Date: 2026-08-27
- Category: 排错调试
- Instructions:
  - amazon_asin_database.xlsx 是 ASIN-番号映射库，以 ASIN 为唯一可信锚点（ASIN 唯一，番号可由多个搜索误挂到同一 ASIN）；冲突形态：同一 ASIN 挂多个番号且各行标题相同（都是该 ASIN 真实商品的日亚标题）。
  - 权威校验源（devbox 免代理无地区锁）：libredmm `https://www.libredmm.com/movies/{番号小写带横杠}`（如 meyd-011），页面 `<h1><span>番号</span><span>DMM标题</span></h1>` 直接给 DMM 商品标题，与 DB 里该 ASIN 的日亚标题比对（归一化后核心子串互相包含）即可裁决正确番号；libredmm 站点慢（单页 2-10s），批量需限速重试。libredmm 无标题全文搜索，只有 fuzzy（返回内部数字 ID，不便反查），反查靠候选番号逐个直查比对。
  - DMM（dmm.co.jp）/fanza 均地区锁（日本外 302 到 not-available-in-your-region），无法从 devbox 直连；日亚 dp 页 devbox 直连 404（amazon.co.jp 在默认代理表，需代理/日本节点，用户提醒日亚要走日本节点）。封面 OCR（tesseract eng）对日系封面效果差，不可作验证依据。
  - tenhow.net 图床：图片按 Amazon ASIN 命名 `images/{ASIN}.jpg`（大图）与 icon_/s_ 前缀小图；全站仅 ~250 静态页（演员/类别），BFS 一次收敛，约 8000 条目，条目 DOM 内 ASIN 图与 DMM cid 绑定（cid→番号：去掉厂商数字前缀+去零，如 13gvg00564→GVG-564）。索引内无 ASIN↔cid 冲突。对 DB ASIN 覆盖率仅 ~9%，但图床按需服务——索引外的 ASIN 也有 ~45% 直接可下图（无 cid 信息）。经 13 个冲突 ASIN 对 libredmm 实测 13/13 绑定正确，可信。可用于 T0：拿到 ASIN 后先试 tenhow 直连下图（免代理），404 回退 Amazon。

- Date: 2026-08-28
- Category: 排错调试
- Instructions:
  - ASIN 冲突裁决方法梯队（按可靠性排序，已实测验证）：① `_cover_similarity` 图像相似度（阈值 0.82）以 DMM 官方图为裁判最可信——竖版 ps 直接用、横版 pl（800×499 套图）必须 `_cut_thumb_right_image` 裁右半再比；②javdb 的 cover_url 是重压处理图，与 DMM 原图相似度仅 0.5~0.7，**不可作裁判**；③标题文本比对不可用（归一化再好也搞不定 BEST/合集）。脚本沉淀：`scripts/clean_asin_db_conflicts.py`（预览默认、--apply 执行、错配行移「待修正」sheet 不删除）。
  - 「一 ASIN 挂多个不同分集番号」多数是该 ASIN 对应合集商品（BEST 8時間 类），各番号单集封面 ≠ 合集封面，图像法也救不了，属不可自动裁决类，all_match（同分>0.82）才是「同一商品多番号发行」的都正常。
  - DMM 图床占位图坑：pics.dmm.co.jp 对无效 cid 会返回 200 + ~2.7KB 甚至 142B 的垃圾体，单凭 check_url 的 200 会通过；真实封面再小也 ≥10KB。已在 `base/web.py::_validate_dmm_image_url` 加 <4096B 拒收（`_DMM_PLACEHOLDER_MAX_BYTES`）。
  - **裁判图源优先级**（已实测校准，勿改回乱序）：① **thejavdb api** `https://api.thejavdb.net/v1/movies?q={番号}` — 直接返回 DMM 真图 URL（`frontcover_url` 竖版、`frontcover_url` 横版），首选因免猜 cid、免多请求；缺点：少数下架番号（如 URE-018）404。② libredmm `/movies/{番号}` 网页能拿到真实 cid，但没有 API 返回快。③ 直构 cid 枚举（10 个前缀）性能最差但兜底最稳。**注意 javdb573 是另一个爬虫（javdb_api.py），和 thejavdb api（thejavdb_api.py）是两码事**。
  - 爬虫全失败时刮削主流程在 `scraper.py` 直接 return，不会进 `_get_big_poster` → 不会发 Amazon 搜索；`_verify_soft_amazon_poster` 的 DMM 兜底参考（`_load_dmm_official_reference`）只覆盖"爬虫半成功但无图"的边缘路径。
  - DMM 站点页面会下架但 CDN 图床不删对象：URE-018 网页端已下架（r18.dev 连 jacket 都没有），awsimgsrc/pics.dmm 的 ure00018/ure018 图仍 200。下架番号的参考图始终可以按番号直构 cid 去碰。

- Date: 2026-08-28
- Category: 工作流协作
- Instructions:
  - 批量导入外部数据到 xlsx 前，必须走 `save_asin_to_excel` 这类含去重逻辑的入口函数；直接 `ws.append` 会绕过「同番号去重」产生成批重复行（教训：tenhow 8094 行导入产生 699 完全重复行）。
  - 错配行处置规则：不删、不丢番号，移到「待修正」sheet 附原因保留待补；主表只留裁决通过的。
