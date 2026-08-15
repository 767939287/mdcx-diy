"""SQLite 刮削状态缓存层。

持久化每个源文件的刮削处理状态，实现断点续刮与失败跨会话重试。
这是轻量状态层：权威元数据仍是 NFO，权威演员库仍是 xlsx，本模块只记录
"谁刮过、结果如何"。数据库损坏或不可用时回退到内存模式，不影响主流程。
"""

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

from ..signals import signal

# 失败自动重试的最大次数（设计决策：默认 3 次，达到后不再自动重试，仅手动强制）
MAX_RETRY_COUNT = 3


@dataclass
class ScrapeState:
    """单文件的刮削状态记录。"""

    file_path: str  # 源文件绝对路径
    mtime: float  # 处理时的源文件 mtime
    status: str  # "done" / "failed"
    number: str = ""  # 刮到的番号（成功时）
    fail_count: int = 0  # 连续失败次数
    scraped_at: float = 0.0  # 最后处理时间戳
    error: str = ""  # 最后错误信息（失败时）


class ScrapeStateCache:
    """基于 SQLite（标准库 sqlite3，WAL 模式）的刮削状态缓存访问层。"""

    def __init__(self, db_path: Path, log_fn=None):
        self._db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()  # 刮削为多协程并发写，SQLite 单写者需串行化
        self._log = log_fn or (lambda msg: signal.add_log(f" [刮削缓存] {msg}"))

    # ------------------------------------------------------------------
    # 连接生命周期
    # ------------------------------------------------------------------

    def open(self) -> bool:
        """打开数据库（WAL 模式 + 建表）。失败返回 False（回退内存模式）。"""
        if self._conn is not None:
            return True
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._db_path), timeout=10.0)
            conn.row_factory = sqlite3.Row  # 按列名访问行
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scrape_state (
                    file_path  TEXT PRIMARY KEY,
                    mtime      REAL NOT NULL,
                    status     TEXT NOT NULL,
                    number     TEXT NOT NULL DEFAULT '',
                    fail_count INTEGER NOT NULL DEFAULT 0,
                    scraped_at REAL NOT NULL,
                    error      TEXT NOT NULL DEFAULT ''
                )
                """
            )
            # 迁移：旧表无 summary_json 列时补齐（存相似推荐所需的结果摘要）
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(scrape_state)").fetchall()}
            if "summary_json" not in columns:
                conn.execute("ALTER TABLE scrape_state ADD COLUMN summary_json TEXT NOT NULL DEFAULT ''")
            conn.commit()
            self._conn = conn
            return True
        except Exception as e:
            self._log(f"数据库打开失败，回退内存模式: {e}")
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
            return False

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception as e:
                self._log(f"数据库关闭失败: {e}")
            self._conn = None

    def is_usable(self) -> bool:
        return self._conn is not None

    # ------------------------------------------------------------------
    # 状态读写
    # ------------------------------------------------------------------

    def _execute(self, sql: str, params: tuple = ()) -> bool:
        """执行写 SQL，失败记日志返回 False（尽力而为，不中断主流程）。"""
        if self._conn is None:
            return False
        try:
            with self._lock:
                self._conn.execute(sql, params)
                self._conn.commit()
            return True
        except Exception as e:
            self._log(f"数据库写入失败: {e}")
            return False

    def _fetch(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        if self._conn is None:
            return []
        try:
            with self._lock:
                rows = self._conn.execute(sql, params).fetchall()
            return rows
        except Exception as e:
            self._log(f"数据库查询失败: {e}")
            return []

    def get_state(self, file_path: Path) -> ScrapeState | None:
        rows = self._fetch(
            "SELECT file_path, mtime, status, number, fail_count, scraped_at, error "
            "FROM scrape_state WHERE file_path = ?",
            (str(file_path),),
        )
        if not rows:
            return None
        row = rows[0]
        return ScrapeState(
            file_path=row["file_path"],
            mtime=row["mtime"],
            status=row["status"],
            number=row["number"],
            fail_count=row["fail_count"],
            scraped_at=row["scraped_at"],
            error=row["error"],
        )

    def set_done(self, file_path: Path, mtime: float, number: str = "", summary: dict | None = None) -> None:
        import time

        summary_json = json.dumps(summary, ensure_ascii=False) if summary else ""
        self._execute(
            """
            INSERT INTO scrape_state (file_path, mtime, status, number, fail_count, scraped_at, error, summary_json)
            VALUES (?, ?, 'done', ?, 0, ?, '', ?)
            ON CONFLICT(file_path) DO UPDATE SET
                mtime=excluded.mtime,
                status='done',
                number=excluded.number,
                fail_count=0,
                scraped_at=excluded.scraped_at,
                error='',
                summary_json=excluded.summary_json
            """,
            (str(file_path), mtime, number, time.time(), summary_json),
        )

    def set_failed(self, file_path: Path, mtime: float, error: str = "") -> None:
        import time

        self._execute(
            """
            INSERT INTO scrape_state (file_path, mtime, status, number, fail_count, scraped_at, error)
            VALUES (?, ?, 'failed', '', 1, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                mtime=excluded.mtime,
                status='failed',
                fail_count=fail_count + 1,
                scraped_at=excluded.scraped_at,
                error=excluded.error
            """,
            (str(file_path), mtime, time.time(), error),
        )

    # ------------------------------------------------------------------
    # 判断逻辑
    # ------------------------------------------------------------------

    def should_skip(self, file_path: Path, mtime: float, force: bool = False) -> bool:
        """断点续刮判断：done 且 mtime 未变且未强制 → True（跳过）。

        - force=True：无条件不跳过（手动强制重新刮削）
        - 状态缺失 / failed / mtime 变化 → 不跳过
        """
        if force:
            return False
        state = self.get_state(file_path)
        if state is None or state.status != "done":
            return False
        return abs(state.mtime - mtime) < 1e-6

    def should_retry(self, file_path: Path, max_retries: int = MAX_RETRY_COUNT) -> bool:
        """失败重试判断：fail_count < max_retries → True（重新入队）。

        仅对 failed 状态生效；done 或无记录返回 False。
        """
        state = self.get_state(file_path)
        if state is None or state.status != "failed":
            return False
        return state.fail_count < max_retries

    # ------------------------------------------------------------------
    # 队列恢复与清理
    # ------------------------------------------------------------------

    def list_pending(self, existing: set[Path], max_retries: int = MAX_RETRY_COUNT) -> list[Path]:
        """返回待处理文件列表（failed 且未超限）。

        existing：本次扫描到的源文件集合，仅返回其中仍存在的文件。
        """
        rows = self._fetch(
            "SELECT file_path, fail_count FROM scrape_state WHERE status = 'failed'",
        )
        pending = []
        for row in rows:
            p = Path(row["file_path"])
            if row["fail_count"] < max_retries and p in existing:
                pending.append(p)
        return pending

    def list_success_summaries(self) -> list[dict]:
        """返回全部成功刮削的结果摘要（供跨会话相似推荐等使用）。

        每条摘要包含 number/title/tags/series/studio/actors/release/runtime。
        无 summary_json 的旧记录会被跳过。
        """
        rows = self._fetch(
            "SELECT summary_json FROM scrape_state WHERE status = 'done' AND summary_json != ''",
        )
        summaries = []
        for row in rows:
            try:
                data = json.loads(row["summary_json"])
            except (ValueError, TypeError):
                continue
            if isinstance(data, dict) and data:
                summaries.append(data)
        return summaries

    def cleanup_missing(self, existing: set[Path]) -> int:
        """清理源文件已不存在的过期记录，返回清理条数。"""
        rows = self._fetch("SELECT file_path FROM scrape_state")
        removed = 0
        for row in rows:
            p = Path(row["file_path"])
            if p not in existing:
                if self._execute("DELETE FROM scrape_state WHERE file_path = ?", (row["file_path"],)):
                    removed += 1
        return removed

    def clear(self) -> None:
        """清空全部状态（供手动重置用）。"""
        self._execute("DELETE FROM scrape_state")
