# 需求实施计划

- [x] 1. 实现 ScrapeStateCache 核心类（mdcx/core/scrape_cache.py）
  - 依据 design.md "Components and Interfaces"：实现 `ScrapeStateCache` 与 `ScrapeState` dataclass
  - `open()`：创建 userdata 目录、连接 SQLite、开启 WAL（`PRAGMA journal_mode=WAL`）、建表；失败返回 False
  - `close()` / `is_usable()`：连接生命周期管理
  - `get_state` / `set_done` / `set_failed`：状态读写，成功时清 fail_count
  - `should_skip` / `should_retry`：断点续刮与失败重试判断（done 且 mtime 未变跳过；fail_count<3 重试）
  - `list_pending` / `cleanup_missing`：队列恢复与过期记录清理
  - 所有写操作 try/except 吞错记日志，单条失败不影响主流程

- [x] 2. 实现断点续刮过滤逻辑（mdcx/core/scraper.py）
  - 依据 design.md "已确认决策-跳过语义"：`_run_tasks_with_limit` 提交任务前，对 `done` 且 mtime 未变的文件直接跳过（不调用 `process_one_file`）
  - `start_new_scrape` 中 open 缓存、`cleanup_missing` 清理、`list_pending` 恢复队列（failed 未超限的重新入队）
  - 刮削循环中成功/失败时调用 `set_done` / `set_failed` 记录状态
  - 缓存不可用（`is_usable()` False）时全部走现有内存逻辑，行为与现状一致

- [x] 3. 接入主窗口生命周期（mdcx/controllers/main_window/main_window.py）
  - 依据 design.md "接入点"：刮削完成/停止时调用 `ScrapeStateCache.close()`
  - 刮削启动前确保缓存已打开
  - （已由 Scraper.run 的 finally 统一管理，主窗口无需额外改动）

- [x] 4. 为 ScrapeStateCache 编写单元测试（tests/test_scrape_cache.py）
  - `set_done`/`should_skip`：mtime 未变跳过、mtime 变化重刮
  - `set_failed`/`should_retry`：失败计数递增、达上限不再重试、成功清零
  - DB 损坏回退：写入非法字节后 `open()` 返回 False、`is_usable()` False
  - WAL 生效：`PRAGMA journal_mode` 返回 `wal`
  - 删除重建：删 DB 后再次 open 正常建表
  - 用 tmp_path fixture，不依赖 GUI

- [x] 5. 检查点 - 确保所有测试通过,如有疑问请询问用户
  - 运行 `uv run check --skip-hook-install` 全量检查
  - 确认断点续刮逻辑不破坏现有刮削流程（回归测试通过）
