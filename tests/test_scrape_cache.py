import sqlite3
from pathlib import Path

import pytest

from mdcx.core.scrape_cache import ScrapeStateCache


@pytest.fixture
def cache(tmp_path: Path) -> ScrapeStateCache:
    c = ScrapeStateCache(tmp_path / "scrape_state.db")
    assert c.open() is True
    yield c
    c.close()


def test_open_creates_db_and_table(tmp_path: Path):
    db = tmp_path / "scrape_state.db"
    c = ScrapeStateCache(db)
    assert c.open() is True
    assert db.exists()
    assert c.is_usable() is True
    # 建表成功
    conn = sqlite3.connect(str(db))
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert ("scrape_state",) in tables
    conn.close()
    c.close()


def test_wal_mode_enabled(tmp_path: Path):
    db = tmp_path / "scrape_state.db"
    c = ScrapeStateCache(db)
    c.open()
    mode = c._conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"
    c.close()


def test_set_done_and_should_skip(cache: ScrapeStateCache, tmp_path: Path):
    p = tmp_path / "movie.mp4"
    p.write_bytes(b"x")
    cache.set_done(p, mtime=100.0, number="ABC-123")
    # mtime 未变 → 跳过
    assert cache.should_skip(p, mtime=100.0) is True
    # mtime 变化 → 重刮
    assert cache.should_skip(p, mtime=200.0) is False
    # 强制 → 不跳过
    assert cache.should_skip(p, mtime=100.0, force=True) is False


def test_get_state_returns_record(cache: ScrapeStateCache, tmp_path: Path):
    p = tmp_path / "movie.mp4"
    cache.set_done(p, mtime=100.0, number="ABC-123")
    state = cache.get_state(p)
    assert state is not None
    assert state.status == "done"
    assert state.number == "ABC-123"
    assert state.fail_count == 0


def test_set_failed_increments_and_retry(cache: ScrapeStateCache, tmp_path: Path):
    p = tmp_path / "movie.mp4"
    cache.set_failed(p, mtime=100.0, error="network error")
    state = cache.get_state(p)
    assert state.status == "failed"
    assert state.fail_count == 1
    assert "network error" in state.error
    # 未达上限 → 可重试
    assert cache.should_retry(p) is True


def test_fail_limit_stops_retry(cache: ScrapeStateCache, tmp_path: Path):
    p = tmp_path / "movie.mp4"
    for _ in range(3):
        cache.set_failed(p, mtime=100.0, error="err")
    state = cache.get_state(p)
    assert state.fail_count == 3
    # 达到上限 → 不再自动重试
    assert cache.should_retry(p) is False
    # 手动强制重刮仍可（should_skip force 语义）
    assert cache.should_skip(p, mtime=100.0, force=True) is False


def test_success_clears_fail_count(cache: ScrapeStateCache, tmp_path: Path):
    p = tmp_path / "movie.mp4"
    cache.set_failed(p, mtime=100.0, error="err1")
    cache.set_failed(p, mtime=100.0, error="err2")
    assert cache.get_state(p).fail_count == 2
    cache.set_done(p, mtime=100.0, number="ABC-1")
    state = cache.get_state(p)
    assert state.status == "done"
    assert state.fail_count == 0
    # done 后不再重试
    assert cache.should_retry(p) is False


def test_should_retry_only_for_failed(cache: ScrapeStateCache, tmp_path: Path):
    p = tmp_path / "movie.mp4"
    # 无记录 → 不重试
    assert cache.should_retry(p) is False
    cache.set_done(p, mtime=1.0)
    # done → 不重试
    assert cache.should_retry(p) is False


def test_list_pending_filters_existing(cache: ScrapeStateCache, tmp_path: Path):
    p1 = tmp_path / "a.mp4"
    p2 = tmp_path / "b.mp4"
    p1.write_bytes(b"a")
    p2.write_bytes(b"b")
    cache.set_failed(p1, mtime=1.0, error="e")
    cache.set_failed(p2, mtime=1.0, error="e")
    # 只恢复仍存在的文件
    pending = cache.list_pending(existing={p1})
    assert pending == [p1]


def test_cleanup_missing(cache: ScrapeStateCache, tmp_path: Path):
    p1 = tmp_path / "a.mp4"
    p2 = tmp_path / "b.mp4"
    p1.write_bytes(b"a")
    p2.write_bytes(b"b")
    cache.set_done(p1, mtime=1.0)
    cache.set_done(p2, mtime=1.0)
    # p2 不存在于 existing → 被清理
    removed = cache.cleanup_missing(existing={p1})
    assert removed == 1
    assert cache.get_state(p2) is None
    assert cache.get_state(p1) is not None


def test_db_corruption_falls_back(tmp_path: Path):
    db = tmp_path / "scrape_state.db"
    # 写入非法字节模拟损坏
    db.write_bytes(b"this is not a valid sqlite database" * 10)
    c = ScrapeStateCache(db)
    assert c.open() is False
    assert c.is_usable() is False
    # 回退后写操作不崩溃
    p = tmp_path / "movie.mp4"
    c.set_done(p, mtime=1.0)
    assert c.should_skip(p, mtime=1.0) is False
    c.close()


def test_delete_db_and_reopen_rebuilds(tmp_path: Path):
    db = tmp_path / "scrape_state.db"
    c1 = ScrapeStateCache(db)
    c1.open()
    c1.set_done(tmp_path / "movie.mp4", mtime=1.0)
    c1.close()
    # 删除 DB 后重新 open 自动重建
    db.unlink()
    c2 = ScrapeStateCache(db)
    assert c2.open() is True
    assert c2.is_usable() is True
    # 原记录已丢失（视为新库）
    assert c2.get_state(tmp_path / "movie.mp4") is None
    c2.close()


def test_set_done_updates_in_place(cache: ScrapeStateCache, tmp_path: Path):
    p = tmp_path / "movie.mp4"
    cache.set_done(p, mtime=1.0, number="OLD")
    cache.set_done(p, mtime=2.0, number="NEW")
    state = cache.get_state(p)
    assert state.mtime == 2.0
    assert state.number == "NEW"
    assert state.fail_count == 0


def test_list_success_summaries_returns_stored_summaries(cache: ScrapeStateCache, tmp_path: Path):
    p1 = tmp_path / "a.mp4"
    p2 = tmp_path / "b.mp4"
    cache.set_done(p1, mtime=1.0, number="ABC-1", summary={"number": "ABC-1", "title": "T1", "tags": ["x"]})
    cache.set_done(p2, mtime=1.0, number="ABC-2", summary={"number": "ABC-2", "title": "T2", "tags": ["y"]})
    # 失败记录与无 summary 的 done 记录不应进入
    cache.set_failed(tmp_path / "c.mp4", mtime=1.0, error="e")
    summaries = cache.list_success_summaries()
    assert len(summaries) == 2
    numbers = {s["number"] for s in summaries}
    assert numbers == {"ABC-1", "ABC-2"}


def test_list_success_summaries_skips_invalid_json(cache: ScrapeStateCache, tmp_path: Path):
    p = tmp_path / "a.mp4"
    cache.set_done(p, mtime=1.0, number="ABC-1", summary={"number": "ABC-1", "title": "T", "tags": ["x"]})
    # 手工写入损坏的 summary_json 模拟异常数据
    import sqlite3

    conn = sqlite3.connect(str(cache._db_path))
    conn.execute("UPDATE scrape_state SET summary_json = 'not-json' WHERE file_path = ?", (str(p),))
    conn.commit()
    conn.close()
    # 不应抛异常，损坏记录被跳过
    assert cache.list_success_summaries() == []
