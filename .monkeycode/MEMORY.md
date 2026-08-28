# 用户指令记忆

本文件只记录长期有效的行为规范、构建发布流程、排错方法和环境约束。项目实现细节以代码、测试和文档为准。

## 协作与质量

- Date: 2026-08-29
- Category: 工作流协作
- Instructions:
  - 简体中文回复；面向小白说明按"现象和影响 → 原因 → 可执行步骤"组织；日期时间一律用北京时间 (UTC+8) 表述并显式注明，避免歧义。
  - 改动前说明内容与原因；用户明确要求提交/推送后才执行，绝不擅自操作。直接在当前分支操作。
  - 每次代码改动后跑 `uv run quick-check`；提交前跑 `uv run check --skip-hook-install` 并确认退出码。仅改 `docs/*.md` 或本文件时只需 `git diff --check`。
  - 提交前必看 `git status` 全部未跟踪文件：程序运行时残留与脚本中间产物（如 `_failed.json`、`amazon_asin_manual_review_*.xlsx`）不得 `git add -A` 入库，应先 `.gitignore` 排除再单独清理（2026-08-27 误提交后补救的教训）。
  - 不装 pre-commit；提交前更新 `docs/changelog.md` 当前版本条目并合并同类。**版本号归属用户**：不得擅自新开版本号段落（如 v2.0.8），条目一律追加进当前进行中的版本小节（2026-08-28 用户指正）。
  - 站点/爬虫/配置改动须同步检查：UI 文案（启动文字 main_window.py、.ui）、README、`docs/*.md`、爬虫总数（`crawler_names()` 长度）、**`config/migrations.py` 旧值清洗**。删站点漏写迁移的后果是旧配置 pydantic 校验整体失败 → 配置被写入 `_failed.json` 且界面回写被跳过，用户表现为"保存不生效"（2026-08 删 15 站漏迁移，一个月后才由议题 #55 带出）。
  - 文档/UI 中写死数字或清单前必须先 grep 代码核实，禁止凭记忆。高频漂移锚点（2026-08 核查实证）：默认网站源顺序（`config/models.py` ↔ `resources/config/default_config.json`，`test_config_conversion.py::test_config_default_site_priorities_follow_current_frontend_defaults` 锁定，改注释勿动枚举）、代理域名列表（`Config.proxy_sites`）、命名变量表（`core/naming/fields.py::FIELD_DESCRIPTIONS`）、设置 Tab 名（tabWidget.setTabText）、水印行为（`MarkType` 徽标+角落轮转，无文字水印）、字段优先级数（`manual.py::REDUCED_FIELDS`）、演员库列（`resources.py::DB_HEADERS`）、指纹池（`network_fingerprint.py`，默认 7/Amazon 6，无令牌桶限流）、主窗口行数（`wc -l controllers/main_window/*.py`）。
  - **长时间运行任务的标准做法**（2026-08-28 用户强调）：① 一律用 `background_terminal_create` 建后台终端执行，不许用普通 bash；② 必须实现断点续传（checkpoint state 持久化到磁盘，重启后从断点续跑）；③ 分批处理，批间落盘；④ 用外层 wrapper 每 50 分钟自动重启进程（规避云环境超时杀进程）；⑤ 执行期间监测进度，定期主动汇报，用户询问时能立即给出。

## GitHub 议题处理

- Date: 2026-08-29
- Category: 环境配置
- Instructions:
  - `gh` 自带 token 已失效（`monkeycode-ai[bot]` invalid）。正确姿势：从 git credential helper 取 token 传 `GH_TOKEN` 走 `gh api` —— `TOKEN=$(printf "protocol=https\nhost=github.com\n\n" | git credential fill | sed -n 's/^password=//p')`，再 `GH_TOKEN="$TOKEN" gh api repos/<owner>/<repo>/issues/<n>`。`gh api user` 会 403（integration 无该权限）但仓库议题读写正常，不要据此判定 token 不可用。凭据值禁止回显到聊天或落盘。
  - 读议题正文/评论优先 `gh api`。退化到抓 GitHub 网页 HTML 时，评论正文要从内联 JSON 的 `"body"` 字段提取（`comment-body markdown-body` 类名已不存在）；未认证直连 `api.github.com` 会撞 IP 级 rate limit。
  - 回帖用 `gh api ... -F body=@文件` 传 Markdown 文件，避免命令行转义问题。
  - 关闭议题的判断标准：修复完整且用户明确要求才 `-f state=closed -f state_reason=completed`。根因未完全查清时保留 open，回帖如实写明"已修的部分解释了什么、解释不了什么"，并给出需报告人补充的具体信息（日志文件、进程内存数值、复现操作序列、特征文件是否存在）与已排除的假设清单，避免对方往错方向猜。不硬套一个原因去凑完整叙事。

## 排查与本地验证

- Date: 2026-08-29
- Category: 排错调试
- Instructions:
  - **仓库根 `config.json` 是脏配置**（含已删站点值），`manager.load()` 遇校验失败会走 except 分支保留旧配置、不调 `_replace_config`。拿它写验证脚本会看到"一切正常"的假象。验证配置加载/网络栈相关行为须用 `Config()` 默认配置写临时文件再指 `manager.path`。
  - 泄漏/累积类问题先写最小复现脚本量化再下结论：统计 `gc.get_objects()` 中目标类存活数、事件循环 `asyncio.all_tasks()` 未完成数，跑 N 轮看是否线性增长。必须做对照实验区分"每次操作都泄漏"与"泄漏一次后被钉住"（议题 #55 靠对照确认单纯点保存无害，必须先有一次停止刮削造成的租约泄漏）。
  - 结构约束类修复（要求某调用必须在/不在某条件分支内）用 AST 哨兵测试锁定位置，行为测试覆盖不到。写完必须拿**修复前的代码片段**反向喂哨兵确认能判定失败，否则哨兵可能恒真（先例：`tests/test_actor_mapping_decoupled.py`、`tests/test_issue55_memory_leak.py`）。
  - conftest 用 dummy 模块替换了 `mdcx.config.manager`、`mdcx.config.resources`、`mdcx.signals`，测试内无法 import 这些模块的真实类；需要检查其源码结构时直接读文件做 AST 解析。
  - 用 subagent 做大范围根因排查时，要求它输出"已排除的假设清单 + 每条排除理由"，比只给可疑点更有价值——可直接写进议题回帖，也能防止自己重复走同一条死路。

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

## 日亚 ASIN 数据库校正

- Date: 2026-08-28
- Category: 排错调试
- Instructions:
  - amazon_asin_database.xlsx 是 ASIN-番号映射库，**以 ASIN 为唯一可信锚点**（ASIN 唯一，番号可由多个搜索误挂到同一 ASIN）。冲突形态：同一 ASIN 挂多个番号且各行标题相同。
  - **冲突裁决梯队**（已实测校准）：① `_cover_similarity` 图像相似度（阈值 0.82）以 DMM 官方图为裁判最可信——竖版 ps 直接用、横版 pl（800×499 套图）必须 `_cut_thumb_right_image` 裁右半再比；② javdb 的 cover_url 是重压处理图，与 DMM 原图相似度仅 0.5~0.7，**不可作裁判**；③ 标题文本比对不可用（归一化再好也搞不定 BEST/合集）。脚本沉淀 `scripts/clean_asin_db_conflicts.py`（默认预览、--apply 执行、--limit 采样）。
  - **裁判图源优先级**（勿改回乱序）：① thejavdb api `https://api.thejavdb.net/v1/movies?q={番号}` 直接返回 DMM 真图 URL，首选（少数下架番号如 URE-018 会 404）；② libredmm `/movies/{番号小写带横杠}` 网页可拿真实 cid，页面 `<h1><span>番号</span><span>DMM标题</span></h1>` 也给 DMM 标题可作标题裁决，但单页 2-10s 慢且无标题全文搜索；③ 直构 cid 前缀枚举（10 个前缀）最慢但最稳。**注意 javdb_api.py 与 thejavdb_api.py 是两个不同爬虫**。
  - 「一 ASIN 挂多个不同分集番号」多数是合集商品（BEST 8時間 类），各番号单集封面 ≠ 合集封面，图像法也救不了，属不可自动裁决类；all_match（同分 >0.82）才是"同一商品多番号发行"的正常情况。
  - 环境限制：DMM/fanza 地区锁（日本外 302 到 not-available-in-your-region），devbox 无法直连；日亚 dp 页 devbox 直连 404（amazon.co.jp 需代理/日本节点）；封面 OCR（tesseract eng）对日系封面效果差不可作依据。DMM 站点页面会下架但 CDN 图床不删对象（URE-018 网页端已下架，awsimgsrc/pics.dmm 的 ure00018 图仍 200），下架番号的参考图始终可按番号直构 cid 去碰。
  - DMM 图床占位图坑：pics.dmm.co.jp 对无效 cid 返回 200 + ~2.7KB 甚至 142B 垃圾体，单凭 check_url 的 200 会通过；真实封面再小也 ≥10KB。已在 `base/web.py::_validate_dmm_image_url` 加 <4096B 拒收。
  - tenhow.net 图床：图片按 ASIN 命名 `images/{ASIN}.jpg`（大图）+ icon_/s_ 前缀小图；条目 DOM 内 ASIN 图与 DMM cid 绑定，经 13 个冲突 ASIN 对 libredmm 实测 13/13 正确。**双向价值**：正向按 ASIN 免代理直接取图（T0 优先，404 再回退 Amazon）；反向凡页面条目里的图文件名都是可入库 ASIN，全站爬一遍即一次 ASIN 增量发现。2026-08-28 重爬全站收敛 **1903 页 / 36441 ASIN**（无冲突），结果在 `/tmp/opencode/tenhow_index_full.json`、页面缓存 `/tmp/opencode/tenhow_pages/`；旧索引 8126 条严重不全（旧脚本每批 50 页无新链接即整体退出，只抓 250/1903 页）已作废。另有 ~5388 条目只有 ASIN 无 cid，未来可用封面图像比对反查番号补库。
  - cid→番号清洗规则（与仓库 `_parse_number`/DMM 官方约定对齐）：cid 形态 `^(\d*)([a-z]+)(\d+)([a-z])?$` = 可选厂商数字前缀 + 系列字母 + 数字（content_id 5 位补零）+ 可选变体字母。番号 = `系列字母大写 + f"{int(数字):03d}"`（去前导零但至少 3 位：24ped00030→PED-030、13gvg00564→GVG-564、onsg00064→ONSG-064，**绝不**缩成 PED-30，旧库 tenhow 行此类错误写法待修）；末尾变体字母（b/c/f/r 等）视为同番号变体归并；去重比对一律用 (系列字母, int(数字)) 做 key 以兼容去零/补零两种存量写法；不匹配该形态的 cid 进「待人工」sheet 不猜番号。
  - 批量导入外部数据到 xlsx 前必须走 `save_asin_to_excel` 这类含去重逻辑的入口函数；直接 `ws.append` 会绕过同番号去重产生成批重复行（教训：tenhow 8094 行导入产生 699 完全重复行）。错配行处置规则：不删、不丢番号，移到「待修正」sheet 附原因保留待补，主表只留裁决通过的。
