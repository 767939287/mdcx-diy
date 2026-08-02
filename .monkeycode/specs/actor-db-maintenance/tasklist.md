# 需求实施计划

- [x] 1. 剥离刮削流程中的翻译补全与 LibreDMM 链接补全
  - [x] 1.1 修改 `mdcx/core/tmdb_actor.py`：删除 `_translate_and_update` 定义（原 L956-973）及 `need_translate` 收集逻辑（原 L897/937/946）
  - [x] 1.2 修改 `mdcx/core/tmdb_actor.py`：删除 `missing_link` 收集与 LibreDMM 补全块（原 L1077-1097）
  - [x] 1.3 修改 `mdcx/core/tmdb_actor.py`：删除 `zhconv` 等仅被剥离逻辑使用的导入，同步清理 `fetch_actor_tmdb_ids` 中不再使用的 `_flush_wb` 前置引用
  - [x] 1.4 编写/更新回归测试：验证 `fetch_actor_tmdb_ids` 剥离后仍能查询 tmdbid 并写库，且缺失翻译/链接不再触发额外网络请求

- [x] 2. 新增 `mdcx/tools/actor_db_tool.py` 工具模块
  - [x] 2.1 实现 `collect_actors_from_nfo_dir(dir_path)`：递归扫描 nfo 目录，解析 `//actor/name` 收集演员并去重
  - [x] 2.2 实现 `ActorDbToolResult` 数据类（total/translated/linked/skipped/failed）
  - [x] 2.3 实现 `run(actor_names, translate, link, output_dir)`：复用 `search_actor_db_reverse`/`_fetch_person_translations`/`fetch_libredmm_link`/`update_actor_db_row` 批量补全，遵循 `_wb` 预加载 + `_flush_wb` 落盘模式
  - [x]* 2.4 编写单元测试：`collect_actors_from_nfo_dir` 收集/去重、空名单、翻译/链接开关控制

- [x] 3. UI 布局与控件（`mdcx/views/MDCx.ui` + 重新编译 `MDCx.py`）
  - [x] 3.1 新增 `groupBox_actor_db_maintenance`（y=1240, h=200, w=701），含说明文字 `label_actor_db_desc`、提示 `label_actor_db_note`、名单输入、目录选择、两个 checkbox、开始按钮
  - [x] 3.2 将 `groupBox_cover_backfill` 下移至 y=1440，`groupBox_emby_actor_manager` 下移至 y=1660
  - [x] 3.3 将 `scrollAreaWidgetContents_gongju` 高度 1580 调整为 1780
  - [x] 3.4 用 `uv run pyuic6 mdcx/views/MDCx.ui -o mdcx/views/MDCx.py` 重新编译，验证生成无误

- [x] 4. 主窗口槽函数与信号接线
  - [x] 4.1 `main_window.py` 实现 `pushButton_actor_db_start_clicked`：读取名单/目录 → 收集演员 → `executor.submit(asyncio.run, run())` → 日志页输出 → 按钮状态恢复
  - [x] 4.2 `main_window.py` 实现 `pushButton_actor_db_pick_dir_clicked`：QFileDialog 选择 nfo 目录并回填
  - [x] 4.3 `init.py` 连接两个按钮的 clicked 信号
  - [ ]* 4.4 编写 UI 槽函数单元测试（mock 信号/executor 验证参数传递）

- [x] 5. 打包配置与整体验证
  - [x] 5.1 `scripts/build.py` 新增 `--hidden-import mdcx.tools.actor_db_tool`
  - [x] 5.2 检查点 - 运行全部测试（ruff + pytest），确认无回归
  - [ ] 5.3 UI 验证（人工）：工具页滚动到底部，确认新 groupBox 与 Emby groupBox 完整可见、无重叠

- [x] 6. 提交推送与文档同步
  - [x] 6.1 git commit + push（含剥离逻辑、新工具、UI、槽函数、测试、build.py）
  - [x] 6.2 更新 `docs/changelog.md`（新增功能条目）
  - [x] 6.3 更新 `docs/FEATURES.md`（工具章节补充演员库维护）
