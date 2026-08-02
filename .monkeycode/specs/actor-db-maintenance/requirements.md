# Requirements Document

## Introduction

当前「演员数据库维护」的翻译补全（`tmdb_actor.py:966`）与 LibreDMM 链接补全（`tmdb_actor.py:1091`）内嵌在刮削流程 `fetch_actor_tmdb_ids` 中。它们与刮削结果无关，却在每次刮削时被触发，可能造成额外 TMDB / LibreDMM 网络请求，拖慢刮削。本特性将这两项能力从刮削流程中抽离，做成独立的「演员库维护」UI 工具，使用户可以在刮削之外手动批量触发；同时让刮削流程只保留「查询 tmdbid 并写库」的核心职责。

## Glossary

- **演员数据库（actor_database.xlsx）**：位于 `配置文件目录/userdata/actor_database.xlsx`，存储演员的 jp（日文名）、zh_cn（简体）、zh_tw（繁体）、keyword（反查关键字）、href（LibreDMM 链接）、tmdbid、tmdb_url 的 xlsx 映射表。
- **翻译补全**：对已有 tmdbid 但缺少 zh_cn 或 zh_tw 的演员，通过 TMDB `translations` API 获取多语言翻译并写回。
- **LibreDMM 链接补全**：对已有 tmdbid 但 href 为空的演员，通过 LibreDMM 查询演员主页链接并写回。
- **刮削流程**：`mdcx/core/scraper.py` 中处理单个影片文件的完整流程，其中 `fetch_actor_tmdb_ids` 负责演员 TMDB ID 查询与写库。
- **工具页（gongju tab）**：主界面「工具」标签页，容器为 `scrollAreaWidgetContents_gongju`，内含多个 groupBox 工具。

## Requirements

### Requirement 1: 独立工具入口

**User Story:** AS 用户, I want 在「工具」页独立触发演员库维护, so that 不必通过刮削即可批量补全演员库数据

#### Acceptance Criteria

1. WHEN 用户在「工具」页点击「演员库维护」工具的按钮, 系统 SHALL 打开演员库维护工具界面。
2. WHEN 用户关闭演员库维护工具界面, 系统 SHALL 释放相关资源且不影响主窗口其他功能。
3. IF 演员库维护工具与刮削任务同时运行, 系统 SHALL 通过写锁串行化对 actor_database.xlsx 的写入。

### Requirement 2: 从刮削流程剥离翻译补全

**User Story:** AS 开发者, I want 移除刮削流程中的翻译补全逻辑, so that 刮削不再因补翻译而额外请求 TMDB

#### Acceptance Criteria

1. WHEN 刮削流程执行 `fetch_actor_tmdb_ids`, 系统 SHALL 不再调用 `_translate_and_update`（原 tmdb_actor.py:956-973）。
2. WHEN 刮削流程执行 `fetch_actor_tmdb_ids`, 系统 SHALL 仍保留「查询 tmdbid 并写入 actor_database.xlsx」的核心行为。
3. IF 演员已在 actor_database.xlsx 中匹配到 tmdbid 但缺少 zh_cn/zh_tw, 刮削流程 SHALL 跳过该演员的翻译补全。

### Requirement 3: 从刮削流程剥离 LibreDMM 链接补全

**User Story:** AS 开发者, I want 移除刮削流程中的 LibreDMM 链接补全逻辑, so that 刮削不再因补链接而额外请求 LibreDMM

#### Acceptance Criteria

1. WHEN 刮削流程执行 `fetch_actor_tmdb_ids`, 系统 SHALL 不再执行 LibreDMM 链接补全（原 tmdb_actor.py:1077-1097）。
2. WHEN 刮削流程执行 `fetch_actor_tmdb_ids`, 系统 SHALL 不再检查缺失 href 的演员。
3. IF actor_database.xlsx 中演员已有 tmdbid 但 href 为空, 刮削流程 SHALL 不触发 LibreDMM 请求。

### Requirement 4: 工具支持按演员名单批量补全

**User Story:** AS 用户, I want 输入演员名单批量补全其翻译与链接, so that 可以针对已知演员主动维护数据

#### Acceptance Criteria

1. WHEN 用户在工具中输入演员名单（逗号/空格分隔）并点击开始, 系统 SHALL 对每个演员执行翻译补全。
2. WHEN 系统处理某个演员, 系统 SHALL 先反查 actor_database.xlsx 获取 jp 名与 tmdbid。
3. WHEN 系统处理某个演员且该演员无 tmdbid, 系统 SHALL 跳过翻译补全并记录原因。
4. WHEN 系统完成处理, 系统 SHALL 在日志页输出每个演员的补全结果（成功/跳过/失败）。

### Requirement 5: 工具支持扫描 nfo 目录收集演员

**User Story:** AS 用户, I want 扫描本地 nfo 目录自动收集演员名批量补全, so that 不需要手动枚举演员

#### Acceptance Criteria

1. WHEN 用户在工具中选择一个 nfo 目录并点击开始, 系统 SHALL 递归扫描该目录下所有 `.nfo` 文件。
2. WHEN 系统扫描 nfo 文件, 系统 SHALL 从 `//actor/name` 节点收集演员名并去重。
3. WHEN 系统完成 nfo 扫描, 系统 SHALL 对去重后的演员名单执行翻译补全与链接补全。

### Requirement 6: 工具提供可选项控制

**User Story:** AS 用户, I want 控制工具执行哪些补全动作, so that 避免执行不需要的网络请求

#### Acceptance Criteria

1. WHEN 工具界面展示, 系统 SHALL 提供「补全翻译」勾选项。
2. WHEN 工具界面展示, 系统 SHALL 提供「补全 LibreDMM 链接」勾选项。
3. WHEN 用户取消勾选「补全翻译」, 系统 SHALL 跳过翻译补全步骤。
4. WHEN 用户取消勾选「补全 LibreDMM 链接」, 系统 SHALL 跳过链接补全步骤。

### Requirement 7: 工具 UI 完整显示于工具页

**User Story:** AS 用户, I want 工具的所有控件在「工具」页完整可见, so that 不会出现上次 Emby 按钮那样的显示不全问题

#### Acceptance Criteria

1. WHEN 演员库维护工具在「工具」页展示, 系统 SHALL 将控件置于独立的 `groupBox` 中, 不与既有 groupBox 重叠。
2. WHEN 工具 groupBox 放置在 `scrollAreaWidgetContents_gongju` 中, 系统 SHALL 同步增大该容器的 height 以容纳新 groupBox。
3. WHEN 新增 groupBox 高度不超过现有页面底部, 系统 SHALL 保证页面滚动后所有控件完整可见。
4. IF 新增 groupBox 的 y 坐标与高度之和超出 `scrollAreaWidgetContents_gongju` 的 height, 系统 SHALL 在提交前调整容器高度。

### Requirement 8: 刮削后自动重载

**User Story:** AS 开发者, I want 工具写库后让刮削流程读取到最新数据, so that 数据一致

#### Acceptance Criteria

1. WHEN 工具完成 actor_database.xlsx 写入, 系统 SHALL 调用 `resources.reload_actor_db()` 重载内存缓存。
2. WHEN 工具执行期间有刮削任务在读取 actor_database.xlsx, 系统 SHALL 保证写入完成后才重载。
3. WHEN 工具写入 actor_database.xlsx 失败（文件锁定/缺少 openpyxl）, 系统 SHALL 在日志页输出明确错误原因。
