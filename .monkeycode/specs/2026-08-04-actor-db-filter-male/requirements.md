# Requirements Document

## Introduction

`actor_database.xlsx` 当前数据来自 AVdb 的 `actor-mapping.xml`，该映射包含男优（抽查确认加藤鷹、しみけん、吉村卓等男优已在库中），而本地库与 AVdb 源均无性别字段。本功能通过 TMDB person API 的 `gender`（1=女 / 2=男 / 0=未标注）判定性别，在**同步源头过滤**与**存量清洗**两个环节剔除男演员，使库内只保留女演员（gender=1）或未标注（gender=0）的数据。

## Glossary

- **男演员**：TMDB person `gender=2` 的演员。
- **TMDB gender**：`/3/person/{id}` 返回的 `gender` 字段（1=女 / 2=男 / 0=未标注）。
- **同步源头过滤**：`sync_from_avdb` 写入新条目前的性别校验，gender=2 的条目不写入。
- **存量清洗**：对已存在的库，按 tmdbid 逐条校验 gender 并删除 gender=2 的行。

## Requirements

### Requirement 1：同步源头过滤男优

**User Story:** 作为用户，我希望 AVdb 同步时不再把男演员写进演员库，以便后续库内不混入男优。

#### Acceptance Criteria

1. WHEN 执行 AVdb 同步且某条带 `tmdb_id` 的待新建条目 gender=2，系统 SHALL 跳过该条目，不写入演员库。
2. WHEN 执行 AVdb 同步且某条待新建条目 gender=1 或 0，系统 SHALL 正常写入。
3. WHEN 同步过滤启用但 TMDB 未配置或请求失败，系统 SHALL 保留该条目不删（跳过校验，不误删）。
4. IF 本地已有该 tmdbid 的条目，系统 SHALL 复用本地已有 gender 判定，不重复请求 TMDB。

### Requirement 2：存量清洗剔除男演员

**User Story:** 作为用户，我希望一键剔除演员库中已存在的男演员，只保留女演员或未标注性别的演员。

#### Acceptance Criteria

1. WHEN 执行存量清洗，系统 SHALL 仅校验含 tmdbid 的行，gender=2 的行被删除。
2. WHEN 某行 gender=1 或 0，系统 SHALL 保留该行。
3. WHEN 某行 TMDB 请求失败或 gender 未知，系统 SHALL 保留该行，不误删。
4. WHEN 无 tmdbid 的行，系统 SHALL 跳过（无法判定，不删除）。
5. WHILE 清洗进行中，系统 SHALL 支持手动停止，已删除行不回滚。
6. WHEN 清洗完成，系统 SHALL 在日志输出剔除数量、保留数量与失败明细。

### Requirement 3：清洗安全与幂等

**User Story:** 作为用户，我希望清洗是安全的、可重复的、且不破坏未判定数据。

#### Acceptance Criteria

1. IF 被校验行 tmdbid 对应的 person 已不存在（404），系统 SHALL 保留该行并记录日志。
2. WHEN 重复执行清洗，系统 SHALL 只处理仍存在的男演员行，不产生重复删除。
3. WHEN 清洗中断后重启，系统 SHALL 从上次进度继续（基于行索引断点）。
4. 系统 SHALL 在删除前将男演员行备份到独立工作表或日志，便于复核。

### Requirement 4：可观测性

**User Story:** 作为用户，我希望清楚看到性别校验与剔除的进度与结果。

#### Acceptance Criteria

1. WHEN 同步过滤跳过某男优，系统 SHALL 在日志输出「跳过男优」与演员名。
2. WHEN 存量清洗处理中，系统 SHALL 输出进度（如每 10% 一次）与并发状态。
3. WHEN 存量清洗完成，系统 SHALL 汇总输出剔除数/保留数/请求失败数。
