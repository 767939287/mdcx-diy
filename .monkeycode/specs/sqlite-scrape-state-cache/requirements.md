# Requirements Document

## Introduction

为 MDCx 刮削流程引入基于 SQLite 的刮削状态缓存层。当前刮削状态（待处理队列、已处理标记、失败记录）全部保存在进程内存（`Flags` dataclass）中，程序重启或崩溃后状态丢失，导致大库存刮削需要从头开始。本功能以轻量 SQLite 状态表持久化刮削状态，实现断点续刮与失败重试，不改变现有权威数据层（NFO 元数据、xlsx 演员库）。

## Glossary

- **System**: MDCx 刮削工具
- **刮削状态缓存**: 记录单个源文件刮削处理情况的 SQLite 持久化数据
- **断点续刮**: 程序重启后，从上次未完成的位置继续刮削，不重复处理已完成文件
- **源文件**: 待刮削的视频文件路径
- **WAL**: SQLite Write-Ahead Logging 模式，允许多读单写并发
- **mtime**: 源文件的修改时间戳，用于判断文件是否变化

## Requirements

### Requirement 1: 刮削状态持久化

**User Story:** 作为 MDCx 用户，我希望刮削状态能持久化保存，以便程序重启或崩溃后能继续上次未完成的刮削。

#### Acceptance Criteria

1. WHEN 系统完成一个源文件的刮削，系统 SHALL 将该文件的处理状态写入 SQLite 数据库
2. WHEN 系统收到刮削请求，系统 SHALL 检查数据库中的状态记录以确定是否已处理
3. WHILE 刮削任务进行中，系统 SHALL 为每个已处理文件维护一条状态记录
4. IF 程序在刮削中途退出，系统 SHALL 在下次启动时恢复未完成文件的处理队列

### Requirement 2: 断点续刮

**User Story:** 作为 MDCx 用户，我希望重启后能接着上次的进度继续刮削，而不重复处理已完成文件。

#### Acceptance Criteria

1. WHEN 系统启动刮削任务，系统 SHALL 跳过状态为 `done` 且源文件 mtime 未变化的文件
2. WHEN 源文件 mtime 发生变化，系统 SHALL 将该文件视为未处理并重新刮削
3. IF 文件状态为 `failed` 且未超过最大重试次数，系统 SHALL 将该文件重新加入待处理队列
4. IF 文件状态为 `failed` 且超过最大重试次数，系统 SHALL 跳过该文件并记录错误

### Requirement 3: 失败重试管理

**User Story:** 作为 MDCx 用户，我希望刮削失败的文件能被自动重试，以便网络抖动等临时问题不导致永久失败。

#### Acceptance Criteria

1. WHEN 一个文件刮削失败，系统 SHALL 记录失败原因并增加失败计数
2. WHEN 一个文件刮削成功，系统 SHALL 清除该文件的失败计数并更新状态为 `done`
3. IF 文件连续失败次数达到配置上限，系统 SHALL 将该文件标记为 `failed` 并停止自动重试
4. WHEN 用户发起手动刮削，系统 SHALL 允许对任何文件（含 `done` 与 `failed`）强制重新刮削

### Requirement 4: 数据安全与可恢复性

**User Story:** 作为 MDCx 用户，我希望状态缓存数据库损坏时不影响主程序运行。

#### Acceptance Criteria

1. IF SQLite 数据库文件损坏或无法打开，系统 SHALL 回退到无持久化状态继续刮削
2. IF 数据库操作失败，系统 SHALL 记录日志且不中断刮削主流程
3. WHEN 系统使用 SQLite，系统 SHALL 以 WAL 模式运行以支持并发读写

### Requirement 5: 向后兼容

**User Story:** 作为 MDCx 用户，我希望引入状态缓存后现有刮削功能保持正常。

#### Acceptance Criteria

1. WHILE 未启用持久化状态（如首次运行），系统 SHALL 按现有内存逻辑刮削全部文件
2. WHEN 缓存数据库被删除，系统 SHALL 自动重建空数据库并继续工作
3. IF 数据库中存在过期记录（源文件已不存在），系统 SHALL 在刮削开始时清理该记录

## 设计决策（已确认）

1. 状态缓存**默认启用**，无配置开关；数据库损坏自动回退内存模式
2. 失败自动重试最大次数默认 **3 次**（作为常量，可后续做成配置）
3. SQLite 数据库文件存放于 **userdata 目录**（`manager.data_folder/userdata/scrape_state.db`），沿用现有 `resources`/`userdata` 目录习惯
