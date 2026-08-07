"""校验 scripts/check_actor_db.py 的静态检查逻辑，尤其新增的 url 错配检查。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from openpyxl import Workbook  # noqa: E402

from mdcx.config.resources import DB_HEADERS  # noqa: E402
from scripts import check_actor_db as mod  # noqa: E402


def _make_db(path: Path, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "演员数据库"
    ws.append(DB_HEADERS)
    for row in rows:
        ws.append(row)
    wb.save(path)
    wb.close()


def _run_checks(rows):
    return [
        mod._check_tmdb_url_no_id(rows),
        mod._check_tmdb_url_mismatch(rows),
        mod._check_tmdb_url_duplicate(rows),
    ]


def test_url_no_id_detected():
    """tmdbid 空但有 url 应报错。"""
    rows = [
        ["演员甲", "演员甲", "", "", "", "", "https://www.themoviedb.org/person/1001", "", ""],
    ]
    no_id, mismatch, dup = _run_checks(rows)
    assert len(no_id) == 1
    assert "tmdbid 为空" in no_id[0]


def test_url_mismatch_detected():
    """tmdbid 与 url 不匹配应报错。"""
    rows = [
        ["演员甲", "演员甲", "", "", "", "1001", "https://www.themoviedb.org/person/9999", "", ""],
    ]
    no_id, mismatch, dup = _run_checks(rows)
    assert len(mismatch) == 1
    assert "不匹配" in mismatch[0]


def test_url_duplicate_detected():
    """同一 url 多行应报错。"""
    rows = [
        ["演员甲", "演员甲", "", "", "", "1001", "https://www.themoviedb.org/person/1001", "", ""],
        ["演员乙", "演员乙", "", "", "", "1002", "https://www.themoviedb.org/person/1001", "", ""],
    ]
    no_id, mismatch, dup = _run_checks(rows)
    assert len(dup) == 1
    assert "重复" in dup[0]


def test_clean_rows_pass():
    """正常行不应报错。"""
    rows = [
        ["演员甲", "演员甲", "", "", "", "1001", "https://www.themoviedb.org/person/1001", "1990-01-01", ""],
        ["演员乙", "演员乙", "", "", "", "1002", "https://www.themoviedb.org/person/1002", "", ""],
    ]
    no_id, mismatch, dup = _run_checks(rows)
    assert no_id == []
    assert mismatch == []
    assert dup == []
