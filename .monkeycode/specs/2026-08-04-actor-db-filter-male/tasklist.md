# 任务清单：剔除男演员（TMDB gender 校验）

## 任务 1: TMDB 性别查询
- [x] 1.1 `mdcx/core/tmdb_actor.py` 新增 `fetch_person_gender(pid, base_url, api_key, client)`，请求 `/3/person/{pid}` 返回 gender；失败/404 返回 None
- [x] 1.2 内存缓存 `{pid: gender}` 去重

## 任务 2: sync 源头过滤
- [x] 2.1 `sync_from_avdb` 新增 `filter_male=True` 参数
- [x] 2.2 待新建且带 tmdb_id 的条目校验 gender，gender=2 跳过不写入，`skipped_male += 1` 并日志「跳过男优」
- [x] 2.3 本地已有该 tmdbid 复用已有判定，不重复请求
- [x] 2.4 TMDB 未配置/请求失败时跳过校验直接写入（不误删）
- [x] 2.5 `ActorDbSyncResult` 新增 `skipped_male` 字段

## 任务 3: 存量清洗
- [x] 3.1 `actor_db_tool.py` 新增 `CleanActorResult` dataclass
- [x] 3.2 新增 `clean_male_actors()`：遍历含 tmdbid 的行，滑动窗口并发校验 gender
- [x] 3.3 gender=2 行备份到独立备份 sheet 后删除；gender 1/0/None/404 保留
- [x] 3.4 支持 limit 限量与手动停止
- [x] 3.5 写库持锁 + 落盘 + reload；日志进度/明细/汇总

## 任务 4: UI 接线（存量清洗按钮）
- [x] 4.1 `MDCx.ui` 在 actor_db 维护组新增「剔除男演员」按钮（AVdb 同步按钮下方，group 高度相应增高）
- [x] 4.2 `MDCx.py` 手工补控件（创建段+翻译段），offscreen 几何验证
- [x] 4.3 `main_window.py` 新增 pyqtSignal + `_run_actor_db_clean_male`（executor.submit + 信号恢复）
- [x] 4.4 `tool_handlers.py` clicked 槽；`init.py` 接线

## 任务 5: 测试与验证
- [x] 5.1 编写 `tests/test_actor_db_filter_male.py`（sync 过滤/不误删/本地复用；clean 剔除/保留/幂等/限量）
- [x] 5.2 `uv run check` 全绿
- [x] 5.3 更新 `docs/changelog.md` 与 `docs/FEATURES.md`
- [x] 5.4 对正式运行时库跑一次清洗验证（限量），确认男优剔除
