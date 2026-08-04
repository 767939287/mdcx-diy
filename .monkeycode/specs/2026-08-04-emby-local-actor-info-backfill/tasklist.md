# 任务清单：本地演员库回填 Emby 演员信息

## 任务 1: 修改 `emby_actor_info.py` 接入本地库
^[- x] 1.1 在 `_process_actor_async` 中 wiki 步骤前插入 `resources.get_actor_data(name)` 本地查询
^[- x] 1.2 本地命中(`has_name`)时：非空 `birth_date` → `actor_info.birthday/year`；非空 `bio` → `actor_info.overview.replace("\n","<br/>")`（并避免 ActressDB 占位覆盖）
^[- x] 1.3 本地命中且简介/生日已填充 → 跳过 wiki/minnano/ActressDB 网络兜底
^[- x] 1.4 返回标志新增 bit3(值 8) 表示本地命中，沿用既有位掩码
^[- x] 1.5 本地查询异常时 try/except 静默退回外部来源
^[- x] 1.6 汇总统计：`db += (flag>>1)&3`，新增 `Local = sum(flag&8)` 并追加到完成日志

## 任务 2: 单元测试
^[- x] 2.1 本地命中回填生日/简介 + Overview 换行转 `<br/>`
^[- x] 2.2 本地命中跳过外部来源（mock wiki/minnano/ActressDB 断言不被调用）
^[- x] 2.3 本地 bio 为空仍走外部 Overview 兜底、生日仍用本地
^[- x] 2.4 本地未命中走完整既有链路
^[- x] 2.5 返回 bit3 标志不破坏既有 wiki/db/minnano 统计
^[- x] 2.6 本地查询异常不阻断、退回外部
^[- x] 2.7 (可选) actress_db 占位「无维基百科信息」在本地命中时不覆盖真实简介

## 任务 3: 文档与验证
^[- x] 3.1 `uv run check` 全绿（ruff + pytest）
^[- x] 3.2 更新 `docs/changelog.md` v2.0.4 或新版本条目
^[- x] 3.3 更新 `docs/FEATURES.md` Emby 演员信息补全描述
