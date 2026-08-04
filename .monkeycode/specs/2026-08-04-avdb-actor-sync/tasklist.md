# 需求实施计划（avdb-actor-sync）

## 阶段一：核心逻辑（无 UI，先跑通数据链路）

- [x] 1. 新增 `mdcx/utils/xml_avdb.py` 解析模块
  - [x] 1.1 定义 `AvdbActor` 数据类（zh_cn/zh_tw/jp/keyword/tmdb_id/bio_graphy/birth_date/bio）
  - [x] 1.2 实现 `parse_avdb_actor_mapping(xml_text)`：标准库 xml.etree 解析 `<a>` 节点，忽略 `<actor-blacklist>`，缺失字段一律空值化，绝不抛错
  - [x] 1.3 实现 `extract_birth_date(bio_graphy)`：正则覆盖 `YYYY年M月D日`/`YYYY.M.D`/`YYYY/M/D` 变体，归一化为 `YYYY-MM-DD`，无日期返回空串
  - [x] 1.4 实现 `strip_age_and_birth(bio_graphy, birth_date)`：剔除 `\d+岁` 年龄片段与已提取的出生段
  - [x] 1.5 实现 `clean_actor_value(value)`：html.unescape 解码重复实体 → 去换行/`\t`/`\x00-\x1F` 控制字符 → 剥离字面 `\uXXXX`/`\xNN`/`\n` 反斜杠串 → trim
  - [x] 1.6 编写单元测试 `tests/test_avdb_actor_sync.py`：解析（含缺字段/blacklist）、出生日期提取多变体、年龄剔除、转义清洗

- [x] 2. 扩展 `mdcx/config/resources.py` 列常量
  - [x] 2.1 `DB_HEADERS` 末尾追加「出生日期」「简介」，新增 `COL_BIRTH_DATE=7` / `COL_BIO=8`（不改动既有列索引）
  - [x] 2.2 `get_actor_data` 返回值新增 `birth_date`、`bio` 键（默认空串）

- [x] 3. `mdcx/core/tmdb_actor.py` 老文件兼容与写入扩展
  - [x] 3.1 `read_actor_db_xlsx` / `load_actor_db`：列数不足时缺失列按空值处理，不报错
  - [x] 3.2 `update_actor_db_row` 追加 `birth_date`/`bio` 可写参数（默认 None，仅本地为空时填充，保持「已有值不覆盖」语义）
  - [x] 3.3 `_format_db_worksheet` 列宽计算由 `len(DB_HEADERS)` 驱动，自动适配 9 列（caps 补 8/9 列）

- [x] 4. 扩展 `mdcx/tools/actor_db_tool.py` 新增 `sync_from_avdb`
  - [x] 4.1 定义 `ActorDbSyncResult`（downloaded/parsed/created/filled/merged/failed）
  - [x] 4.2 数据源分发：`source="file"` 读本地；`"jsdelivr"/"github"` 用内置 URL（jsDelivr 为默认）；`"url"` 用传入地址；下载复用 `download_file_with_filepath`
  - [x] 4.3 合并逻辑：jp 精确 → zh_cn 精确 → keyword 命中（大小写不敏感）→ 未匹配新建；本地优先只填空缺；keyword 合并去重
  - [x] 4.4 tmdbid 冲突：冲突条目不新建，keyword/bio/出生日期并入已占用该 tmdbid 的本地条目
  - [x] 4.5 bio_graphy 解析 + `clean_actor_value` 清洗接入全部写入路径
  - [x] 4.6 写库串行化复用 `_actor_db_write_lock`，落盘 `_flush_wb` + `resources.reload_actor_db()`
  - [x] 4.7 日志页输出汇总（新建/补齐/冲突合并/失败）
  - [x] 4.8 单元测试：合并匹配（jp/zh_cn/keyword/新建）、本地不覆盖、tmdbid 冲突并入、老 7 列文件兼容

## 阶段二：静态校验

- [x] 5. 新增 `scripts/check_actor_db.py`
  - [x] 5.1 检查项：同 jp 名重复、keyword 首尾/连续逗号与重复词、zh_cn/zh_tw/jp 空字段、tmdbid 重复、出生日期列格式
  - [x] 5.2 挂入 `uv run check`（本地数据把关）

## 阶段三：UI 与信号接线

- [ ] 6. UI 与信号接线
  - [ ] 6.1 `mdcx/views/MDCx.ui` 在 `groupBox_actor_db_maintenance` 内新增：说明 label、数据源 comboBox、URL/本地路径输入框、选择按钮、同步按钮
  - [ ] 6.2 pyuic6 重新编译生成 `MDCx.py`，验证 `import mdcx.views.MDCx` 可导入
  - [ ] 6.3 `init.py` 信号接线（sync/pick_xml/combo 切换）+ `main_window.py` 槽函数（executor.submit + pyqtSignal 恢复，跨线程 Qt 安全）
  - [ ] 6.4 `scripts/build.py` 新增 `--hidden-import mdcx.utils.xml_avdb`

## 阶段四：整体验证与文档

- [ ] 7. 整体验证
  - [ ] 7.1 `uv run check --skip-hook-install` 全绿（ruff + pytest）
  - [ ] 7.2 UI 人工验证：工具页控件无重叠遮挡
  - [ ] 7.3 打包验证（人工）：exe 运行确认 `mdcx.utils.xml_avdb` 可导入
  - [ ] 7.4 更新 `docs/changelog.md` 与 `docs/FEATURES.md`
