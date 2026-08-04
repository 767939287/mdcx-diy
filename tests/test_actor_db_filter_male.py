import asyncio
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from mdcx.config.resources import COL_JP, DB_HEADERS
from mdcx.core import tmdb_actor
from mdcx.tools import actor_db_tool

_XML = """<?xml version="1.0" encoding="UTF-8"?>
<actor-mapping>
  <actor>
    <a zh_cn="阿部純子" zh_tw="阿部純子" jp="阿部純子" keyword="阿部純子" tmdb_id="1417328" verified="1" />
    <a zh_cn="阿部涼音" zh_tw="阿部涼音" jp="阿部涼音" keyword="阿部涼音" tmdb_id="1417329" verified="1" />
  </actor>
</actor-mapping>
"""


@pytest.fixture
def _tmp_actor_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(tmdb_actor.manager, "data_folder", tmp_path)
    monkeypatch.setattr(tmdb_actor.resources, "actor_db", {})
    userdata = tmp_path / "userdata"
    userdata.mkdir(parents=True, exist_ok=True)
    return userdata / "actor_database.xlsx"


@pytest.fixture(autouse=True)
def _reset_actor_db_row_index():
    with tmdb_actor._ACTOR_DB_ROW_INDEX_LOCK:
        tmdb_actor._ACTOR_DB_ROW_INDEX.clear()


@pytest.fixture
def _avdb_xml(tmp_path: Path):
    path = tmp_path / "mapping.xml"
    path.write_text(_XML, encoding="utf-8")
    return path


def _write_db(path: Path, rows, headers=DB_HEADERS):
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    wb.save(path)
    wb.close()


def _read_rows(path: Path):
    wb = load_workbook(path)
    ws = wb.active
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    wb.close()
    return rows


def _mock_tmdb(monkeypatch, genders: dict[int, int | None]):
    monkeypatch.setattr(actor_db_tool, "_resolve_tmdb_config", lambda: ("http://base", "test-key"))
    calls: list[int] = []

    async def fake_fetch(pid, base_url, api_key, client):
        calls.append(pid)
        return genders.get(pid)

    monkeypatch.setattr(actor_db_tool, "fetch_person_gender", fake_fetch)
    return calls


def test_sync_skips_male_when_filter_male(_tmp_actor_db: Path, _avdb_xml: Path, monkeypatch):
    _mock_tmdb(monkeypatch, {1417328: 2, 1417329: 1})
    result = asyncio.run(actor_db_tool.sync_from_avdb("file", str(_avdb_xml)))
    assert result.skipped_male == 1
    assert result.created == 1
    rows = _read_rows(_tmp_actor_db)
    assert len(rows) == 1
    assert rows[0][COL_JP] == "阿部涼音"


def test_sync_keeps_female_and_unknown(_tmp_actor_db: Path, _avdb_xml: Path, monkeypatch):
    _mock_tmdb(monkeypatch, {1417328: 1, 1417329: 0})
    result = asyncio.run(actor_db_tool.sync_from_avdb("file", str(_avdb_xml)))
    assert result.skipped_male == 0
    assert result.created == 2


def test_sync_keeps_when_gender_unknown(_tmp_actor_db: Path, _avdb_xml: Path, monkeypatch):
    _mock_tmdb(monkeypatch, {1417328: None, 1417329: None})
    result = asyncio.run(actor_db_tool.sync_from_avdb("file", str(_avdb_xml)))
    assert result.skipped_male == 0
    assert result.created == 2


def test_sync_no_filter_when_no_tmdb_key(_tmp_actor_db: Path, _avdb_xml: Path, monkeypatch):
    monkeypatch.setattr(actor_db_tool, "_resolve_tmdb_config", lambda: ("", ""))
    result = asyncio.run(actor_db_tool.sync_from_avdb("file", str(_avdb_xml)))
    assert result.skipped_male == 0
    assert result.created == 2


def test_sync_does_not_requery_existing_tmdbid(_tmp_actor_db: Path, _avdb_xml: Path, monkeypatch):
    _write_db(_tmp_actor_db, [["阿部純子", "阿部純子", "", "", "", 1417328, "", "", ""]])
    calls = _mock_tmdb(monkeypatch, {1417328: 2, 1417329: 1})
    result = asyncio.run(actor_db_tool.sync_from_avdb("file", str(_avdb_xml)))
    assert 1417328 not in calls  # 本地已有该 tmdbid，不重复请求性别
    assert result.skipped_male == 0
    assert result.created == 1


def test_clean_removes_male_and_backs_up(_tmp_actor_db: Path, monkeypatch):
    _write_db(
        _tmp_actor_db,
        [["男优A", "男优A", "", "", "", 1001, "", "", ""], ["女优B", "女优B", "", "", "", 1002, "", "", ""]],
    )
    _mock_tmdb(monkeypatch, {1001: 2, 1002: 1})
    result = asyncio.run(actor_db_tool.clean_male_actors())
    assert result.removed_male == 1
    rows = _read_rows(_tmp_actor_db)
    assert [r[COL_JP] for r in rows] == ["女优B"]
    wb = load_workbook(_tmp_actor_db)
    assert "男优备份" in wb.sheetnames
    backup = list(wb["男优备份"].iter_rows(min_row=1, values_only=True))
    wb.close()
    assert len(backup) == 1
    assert backup[0][0] == "男优A"


def test_clean_keeps_female_unknown_and_missing(_tmp_actor_db: Path, monkeypatch):
    _write_db(
        _tmp_actor_db,
        [
            ["女优A", "女优A", "", "", "", 2001, "", "", ""],
            ["未知B", "未知B", "", "", "", 2002, "", "", ""],
            ["无idC", "无idC", "", "", "", "", "", "", ""],
        ],
    )
    _mock_tmdb(monkeypatch, {2001: 1, 2002: None})
    result = asyncio.run(actor_db_tool.clean_male_actors())
    assert result.removed_male == 0
    rows = _read_rows(_tmp_actor_db)
    assert len(rows) == 3


def test_clean_no_tmdb_key_noop(_tmp_actor_db: Path, monkeypatch):
    _write_db(_tmp_actor_db, [["男优A", "男优A", "", "", "", 3001, "", "", ""]])
    monkeypatch.setattr(actor_db_tool, "_resolve_tmdb_config", lambda: ("", ""))
    result = asyncio.run(actor_db_tool.clean_male_actors())
    assert result.removed_male == 0
    assert len(_read_rows(_tmp_actor_db)) == 1


def test_clean_limit_applies(_tmp_actor_db: Path, monkeypatch):
    _write_db(
        _tmp_actor_db,
        [["男优A", "男优A", "", "", "", 4001, "", "", ""], ["男优B", "男优B", "", "", "", 4002, "", "", ""]],
    )
    _mock_tmdb(monkeypatch, {4001: 2, 4002: 2})
    result = asyncio.run(actor_db_tool.clean_male_actors(limit=1))
    assert result.removed_male == 1
    rows = _read_rows(_tmp_actor_db)
    assert len(rows) == 1


def test_clean_idempotent(_tmp_actor_db: Path, monkeypatch):
    _write_db(_tmp_actor_db, [["女优A", "女优A", "", "", "", 5001, "", "", ""]])
    _mock_tmdb(monkeypatch, {5001: 1})
    asyncio.run(actor_db_tool.clean_male_actors())
    result = asyncio.run(actor_db_tool.clean_male_actors())
    assert result.removed_male == 0
    assert len(_read_rows(_tmp_actor_db)) == 1
