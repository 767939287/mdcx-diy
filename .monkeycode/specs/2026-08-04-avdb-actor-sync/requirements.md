# Requirements Document

## Introduction

当前演员库 `actor_database.xlsx` 的数据（日文名、中文名、别名、tmdbid）依赖刮削流程与人工维护逐步积累，数据不全、别名覆盖不足、缺少演员简介与出生日期。AVdb 项目（li-peifeng/Jav-Actors-Mapping）维护了一份经社区整理与 CI 校验的演员映射表 `actor-mapping.xml`，包含 zh_cn、zh_tw、jp、keyword、tmdb_id、verified、bio_graphy 字段。本特性在「演员库维护」工具中新增「从 AVdb 同步」能力：下载或载入 AVdb 映射表，与现有 `actor_database.xlsx` 合并，补齐中文名/别名/tmdbid，并新增「出生日期」「简介」两列承载 bio_graphy 解析结果。

## Glossary

- **演员数据库（actor_database.xlsx）**：位于 `配置文件目录/userdata/actor_database.xlsx`，存储演员的 jp（日文名）、zh_cn（简体）、zh_tw（繁体）、keyword（反查关键字）、href（LibreDMM 链接）、tmdbid、tmdb_url 的 xlsx 映射表。
- **AVdb 演员映射表（actor-mapping.xml）**：`https://github.com/li-peifeng/Jav-Actors-Mapping` 仓库维护的 XML 文件，根节点 `<actor-mapping>` 含单个 `<actor>` 子节点，演员条目为 `<a zh_cn="..." zh_tw="..." jp="..." keyword="..." tmdb_id="..." verified="..." bio_graphy="..." />`，可选 `<actor-blacklist>` 黑名单节点。
- **bio_graphy**：AVdb 映射表中人工整理、`verified="1"` 已核对的演员百科资料文本，含出生日期、身高、三围、罩杯、血型、籍贯、兴趣、鞋码、所属事务所、出道作品、社交链接等信息；其中年龄为写入时的动态值（如「33岁」）。
- **出生日期（birth_date）**：从 bio_graphy 提取的结构化字段，格式 `YYYY-MM-DD` 或 `YYYY-MM`，喂给 Emby/Jellyfin 演员 `PremiereDate`。
- **简介（bio）**：bio_graphy 剔除动态年龄与出生段后的静态文本，喂给 Emby/Jellyfin 演员 `Overview`。
- **转义清洗**：对写入 xlsx 前的字符串统一执行：解码重复实体转义（如 `&amp;amp;` → `&`）、去除 `\x00-\x1F` 控制字符与换行、剥离字面 `\uXXXX`/`\xNN`/`\n` 反斜杠串、trim 前后空白。
- **演员库维护工具**：`mdcx/tools/actor_db_tool.py` 提供的批量维护能力，已有翻译补全、LibreDMM 链接补全，本特性在其上扩展。

## Requirements

### Requirement 1: 工具内「从 AVdb 同步」入口

**User Story:** AS 用户, I want 在「演员库维护」工具内一键同步 AVdb 映射表, so that 无需等待刮削积累即可获得完整的演员数据

#### Acceptance Criteria

1. WHEN 用户在「工具」页「演员库维护」工具中点击「从 AVdb 同步」按钮, 系统 SHALL 启动同步任务并输出日志。
2. WHEN 同步任务运行中, 系统 SHALL 将按钮置为禁用并在完成或失败后恢复。
3. IF 同步任务与刮削任务同时运行, 系统 SHALL 通过 `_actor_db_write_lock` 串行化对 actor_database.xlsx 的写入。

### Requirement 2: 支持网络下载与本地文件两种数据源

**User Story:** AS 用户, I want 既能从网络自动下载 AVdb 映射表, 也能载入本地已下载的 xml 文件, so that 网络受限环境也能完成同步

#### Acceptance Criteria

1. WHEN 用户点击「从 AVdb 同步」, 系统 SHALL 按用户选择的唯一数据源取数：jsDelivr 加速、GitHub 直连、自定义下载地址、本地 xml 文件 四选一，默认 jsDelivr 加速。
2. WHEN 用户选择「自定义下载地址」, 系统 SHALL 显示地址输入框并使用该地址下载。
3. WHEN 用户选择「本地 xml 文件」, 系统 SHALL 跳过网络下载, 解析所选文件。
4. IF 网络下载失败或超时, 系统 SHALL 提示用户切换加速地址或改用本地文件并中止同步。
5. WHEN 系统解析 XML 失败, 系统 SHALL 输出解析错误原因并中止, 不写库。

### Requirement 3: 合并策略以 jp 名为主键、AVdb 补齐不覆盖本地

**User Story:** AS 开发者, I want 合并时保留本地已有数据, 用 AVdb 补齐缺失字段, so that 本地手工维护的自定义别名与链接不丢失

#### Acceptance Criteria

1. WHEN 系统为待导入条目查找本地匹配, 系统 SHALL 按 jp 精确、zh_cn 精确、keyword 命中的顺序匹配。
2. WHEN 系统为已匹配条目写入字段, 系统 SHALL 仅填充本地为空的值, 不覆盖本地已有值。
3. WHEN 系统处理 AVdb 的 keyword, 系统 SHALL 与本地已有别名合并去重后写回。
4. WHEN 待导入条目未匹配到本地条目, 系统 SHALL 新建一行并写入全部字段。
5. WHEN 系统处理 AVdb 的 verified 字段, 系统 SHALL 忽略该属性, 不写入 xlsx。

### Requirement 4: tmdbid 冲突识别为同一人并合并别名

**User Story:** AS 开发者, I want 导入时识别 tmdbid 冲突并合并, so that 同一演员因改名等导致的重复条目被合并而非报错

#### Acceptance Criteria

1. WHEN 待导入条目的 tmdbid 与本地另一条目相同, 系统 SHALL 将该待导入条目标记为冲突合并, 不新建行。
2. WHEN 系统执行冲突合并, 系统 SHALL 将该条目的 keyword 别名并入已占用该 tmdbid 的本地条目。
3. WHEN 系统执行冲突合并, 系统 SHALL 将该条目的 bio/出生日期补入本地条目（本地为空时）。
4. WHEN 系统完成冲突合并, 系统 SHALL 在日志页输出合并提示（演员名与原因）。

### Requirement 5: bio_graphy 解析为出生日期与简介

**User Story:** AS 用户, I want 演员简介包含出生日期且年龄不写死, so that 展示信息静态不随时间过期

#### Acceptance Criteria

1. WHEN 系统解析 bio_graphy, 系统 SHALL 用正则提取出生日期（覆盖 `YYYY年M月D日`、`YYYY.M.D`、`YYYY/M/D` 等变体）写入「出生日期」列。
2. WHEN 系统解析 bio_graphy, 系统 SHALL 剔除其中的年龄片段（如「33岁」）与已提取的出生段。
3. WHEN 系统解析 bio_graphy 但未提取到出生日期, 系统 SHALL 将「出生日期」置空, 简介保留其余静态内容。
4. WHEN bio_graphy 为空或缺失, 系统 SHALL 将「出生日期」与「简介」均置空。

### Requirement 6: 写入前统一转义清洗

**User Story:** AS 开发者, I want 所有写库字符串先过转义清洗, so that 脏数据最多存活到单元格赋值前

#### Acceptance Criteria

1. WHEN 系统将 AVdb 的任一文本字段写入 xlsx, 系统 SHALL 先执行转义清洗。
2. WHEN 清洗函数处理重复实体转义, 系统 SHALL 解码至单一层（如 `&amp;amp;` → `&`）。
3. WHEN 清洗函数处理控制字符与反斜杠转义串, 系统 SHALL 移除后写库。
4. WHEN 现有 `update_actor_db_row` 与翻译补全路径写库, 系统 SHALL 复用同一清洗函数。

### Requirement 7: 新增「出生日期」「简介」列并兼容老文件

**User Story:** AS 开发者, I want 新增两列且老版本 xlsx 文件不受影响, so that 用户升级后旧数据文件仍可正常读取

#### Acceptance Criteria

1. WHEN 系统创建新 actor_database.xlsx, 系统 SHALL 在 `DB_HEADERS` 末尾追加「出生日期」「简介」两列。
2. WHEN 系统读取列数不足的老版 xlsx, 系统 SHALL 将缺失列的字段视为空值, 不报错。
3. WHEN 用户首次执行同步且本地文件缺少新列, 系统 SHALL 自动补列头并保留原数据。
4. WHEN 系统新增列后, 系统 SHALL 同步更新现有写库函数的行写入与列宽计算逻辑。

### Requirement 8: 同步结果可见与写库后重载

**User Story:** AS 用户, I want 同步结果清晰可查且刮削能读到最新数据, so that 数据一致

#### Acceptance Criteria

1. WHEN 同步任务完成, 系统 SHALL 在日志页输出汇总（新建/补齐/冲突合并/失败条目数）。
2. WHEN 同步任务完成写入, 系统 SHALL 调用 `resources.reload_actor_db()` 重载内存缓存。
3. WHEN 单个条目解析或写入失败, 系统 SHALL 记录失败原因并继续处理后续条目。
4. WHEN 同步失败（下载/解析/写盘）, 系统 SHALL 在日志页输出明确错误原因, 不静默吞掉。
