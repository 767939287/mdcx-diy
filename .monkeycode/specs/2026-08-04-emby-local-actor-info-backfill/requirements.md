# Requirements Document

## Introduction

Emby/Jellyfin 演员信息补全当前依赖 wiki → minnano-av → 独立 ActressDB(SQLite) 三级拉取简介与生日，网络依赖重、常失败。本功能将本地 `actor_database.xlsx`（已含 AVdb 入库的结构化「出生日期」「简介」）接入 Emby 演员信息补全，作为命中即用的本地数据源，降低对外部来源的依赖，实现离线可用。

## Glossary

- **本地演员库**：`mdcx/config/resources.py` 维护的 `actor_database.xlsx`，字段含日文名/中文名/繁体名/别名/出生日期/简介等。
- **Emby 演员信息补全**：`mdcx/tools/emby_actor_info.py` 中 `_process_actor_async` 对单个演员获取/回填 Overview（简介）与 PremiereDate（生日）的流程。
- **EMbyActressInfo**：`mdcx/models/emby.py` 中的补全数据载体，`dump()` 输出 Overview、PremiereDate、ProductionYear 等到 Emby/ Jellyfin。
- **本地命中**：通过 `resources.get_actor_data(name)` 在本地演员库找到匹配行且 `has_name=True`。

## Requirements

### Requirement 1：本地库作为 Emby 补全数据源接入

**User Story:** 作为用户，我希望 Emby 补全演员信息时优先使用本地演员库已有的简介与生日，以便在不依赖 wiki/minnano 网络来源时也能补全。

#### Acceptance Criteria

1. WHEN 对演员执行 Emby 信息补全且本地演员库命中，系统 SHALL 用本地「出生日期」填充演员生日。
2. WHEN 对演员执行 Emby 信息补全且本地演员库命中，系统 SHALL 用本地「简介」填充 Emby Overview。
3. WHEN 本地演员库命中，系统 SHALL 将生日年份用于 ProductionYear。
4. WHILE 本地演员库未命中，系统 SHALL 保持原有 wiki → minnano-av → ActressDB 兜底流程不变。

### Requirement 2：本地优先，外部落后

**User Story:** 作为用户，我希望本地已确认的数据不被外部来源覆盖，且能优先使用。

#### Acceptance Criteria

1. IF 本地演员库命中且本地简介非空，系统 SHALL 以本地简介为准，不再调用 wiki/minnano-av 获取简介。
2. IF 本地演员库命中且本地生日非空，系统 SHALL 以本地生日为准。
3. IF 本地命中但简介为空，系统 SHALL 退回外部来源补齐简介；回复生日数据不受影响。

### Requirement 3：数据清洗与格式

**User Story:** 作为用户，我希望写入 Emby 的本地数据格式正确、可被 Emby 正常渲染。

#### Acceptance Criteria

1. WHEN 将本地简介写入 Overview，系统 SHALL 将换行转换为 `<br/>`（与现有 Emby Overview 写法一致）。
2. WHEN 将本地生日写入 PremiereDate，系统 SHALL 保持 `YYYY-MM-DD` 格式，且非空时覆盖 `0000-00-00` 默认值。
3. IF 简介缺失或为空，系统 SHALL 为 Overview 保留现有「无维基百科信息」占位或外部来源结果，不写入空串覆盖。

### Requirement 4：可观测性

**User Story:** 作为用户，我希望知道本地数据是否被采用。

#### Acceptance Criteria

1. WHEN 本地演员库命中并回填，系统 SHALL 在日志输出「本地库命中」指示与回填内容概要。
2. WHEN 本地演员库未命中，系统 SHALL 在日志提示未在本地库找到，并继续既有流程。
