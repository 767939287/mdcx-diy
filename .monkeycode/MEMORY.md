# 用户指令记忆

本文件只记录长期有效的行为规范、构建发布流程、排错方法和环境约束。项目实现细节以代码、测试和文档为准。

## 协作与质量

- Date: 2026-08-26
- Category: 工作流协作
- Instructions:
  - 所有回复使用简体中文；面向小白说明时按"现象和影响 → 原因 → 可执行步骤"组织。
  - 改动前说明内容与原因；用户明确要求提交/推送后才执行，绝不擅自提交推送。直接在当前分支操作。
  - 每次代码改动后运行 `uv run quick-check`；提交前最后一次改动后运行 `uv run check --skip-hook-install` 并确认退出码。仅改 `docs/*.md` 或 MEMORY.md 时只需 `git diff --check` 并审阅内容。
  - 不安装 pre-commit；提交前更新 `docs/changelog.md` 当前版本条目并合并同类内容；文档日期用北京时间（UTC+8）。
  - 修改站点、爬虫或配置项时，同步检查 UI 文案（含启动文字 main_window.py 与 .ui）、README、`docs/*.md` 及 `get_registered_crawler_sites()` 的爬虫数量。

## UI 开发与排错

- Date: 2026-08-26
- Category: UI 开发与排查
- Instructions:
  - UI 修改先改 `.ui`（唯一权威源），再 pyuic 重生成 MDCx.py、`ruff format`、`tests/test_ui_structure.py`；禁手工改生成的 MDCx.py。
  - 主窗口全局绝对定位、无布局管理器：长文本 QLabel 用 wordWrap 并查 sizeHint，固定高度底部留约 60px 余量；scroll 内容走 CustomScrollArea.sync_content_min_height；新增顶层悬浮控件要纳入 resizeEvent 的手动几何同步。
  - 打包前逐页切换 stackedWidget 审计边界溢出（scripts/check_ui_layout.py、tests/test_ui_geometry.py、test_main_window_startup.py）。
  - Qt 同名 API 重载签名不同（如 QLayout/QSplitter 的 setStretchFactor），改前先确认目标类签名；测试桩显式枚举属性方法，不用 __getattr__ 通配（生产代码可能依赖 AttributeError 降级）。
  - Onefile 无控制台异常用 faulthandler + crash/ 日志定位；GUI 日志走 signal_qt.show_log_text。
  - 删除代码前检查赋值点、读取点、装饰器注册、延迟 import 和动态工厂，删后重扫死 import 与零引用。

## 站点与网络

- Date: 2026-08-26
- Category: 排错调试
- Instructions:
  - 各站探测番号与收录依据见爬虫类注释；javdb 搜普通番号无需 Cookie，仅 FC2 需要。
  - 站点 API 特性：missav_api Recombee search 仅 POST；DMM Affiliate v3 ItemList 必需 site/service/floor，keyword 用 content_id 形态（ssis00200）；madouqu 域名由发布页 wangzhi.icu/config.js 动态维护（web.py::get_madouqu_domains，24h 缓存）；madou_club 番号无横杠；parsel Selector.get() 对纯 JSON 返回 dict，JSON 类爬虫解析兼容 str/dict/Selector 三态。
  - 已删 15 站（2026-08 用户决定）：cnmdb/hdouban/mdtv/love6/kin8/giga/cableav/7mmtv/hscangku/fc2club/fc2hub（失效或 CF 维护成本高）+ jav321/fantastica（重复）+ dahlia/faleno（降级为 official 厂牌子爬虫，_skip_auto_register=True）。若恢复从 git 历史找回并重建枚举/注册/默认源。
  - 无码官网（caribbeancom/heyzo/1pondo/pacopacomama/10musume）由 official_uncensored.py 统一路由，勿重复开发；均被墙需代理；1pondo 首页有反 bot 壳但 dyn/phpauto JSON API 可直接访问。
  - 日本 IP 地理限制站点：faleno.jp/giga-web.jp/mywife.cc/mgstage.com，测试用 `scripts/dev_proxy.py start --port 7891 --regions "jp|日本"` 起纯日本节点实例。
  - 站点访问分层结论（2026-08-26 实测）：多数站 devbox 可直通；getchu/iqqtv/madou_club/missav/xcity 需代理；avbase/javdb/javlibrary/theporndb 等在免费代理下不稳主要是 devbox 云端限制，用户本地多可直连。批量探测判定必须校验 data.title 为真实字符串防假阳性。
  - 被墙站测试：`uv run python -m scripts.dev_proxy start|status|test <url>|stop`，启动后等 10-20 秒节点测速再用；支持 --port 多实例、--regions 地区过滤。
  - devbox 环境限制：超时属云端限制不代表站点死亡；高频批量测试会触发 CF IP 级拉黑，失败先换时段重试；连通性验证必须用 curl_cffi impersonate 指纹（httpx 无指纹会被软拦截）；出口 IP 被屏蔽时以用户浏览器实测为准。

## Windows 打包与发布

- Date: 2026-08-24
- Category: 环境配置
- Instructions:
  - 函数内延迟导入的模块必须同步加入 scripts/build.py 的 --hidden-import 或 --collect-all；改依赖/构建脚本/Release 工作流时逐项核对。
  - EXCLUDED_MODULES 中的 rich/typer 等只供构建或 CLI，GUI 运行期不得引用；Windows curl_cffi.libs 需显式 --add-binary 收集。
  - Release Tag 纯数字 YYYYMMDD（check_version 对 tag 做 int()），双平台构建都显式传 Tag；scripts/*.py 顶部的 `# ruff: noqa: E402` 与探测 import 的 `# noqa: F401` 必须保留。

## 并发与数据

- Date: 2026-08-24
- Category: 构建方法
- Instructions:
  - 文件间批量任务用 asyncio.wait(FIRST_COMPLETED) 滑动窗口，文件内多站点用 gather；网络请求不跨 executor loop 复用。
  - 后台协程统一用 utils/qt_thread.py::run_in_background，不得直接操作 QWidget，结果经 Qt signal 回主线程；新增后跑 scripts/check_thread_safety.py。
  - 出厂模板在 resources/userdata/，运行时数据在 manager.data_folder/userdata/，勿混淆；devbox 代理 127.0.0.1:7890 可能无进程，排查网络时临时关闭代理而不改产品默认配置。
