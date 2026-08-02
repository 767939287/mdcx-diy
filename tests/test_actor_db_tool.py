from pathlib import Path

import pytest
from openpyxl import load_workbook

from mdcx.core import tmdb_actor
from mdcx.tools import actor_db_tool

pytestmark = pytest.mark.network


@pytest.fixture
def _tmp_actor_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(tmdb_actor.manager, "data_folder", tmp_path)
    monkeypatch.setattr(tmdb_actor.resources, "actor_db", {})
    userdata = tmp_path / "userdata"
    userdata.mkdir(parents=True, exist_ok=True)
    return userdata / "actor_database.xlsx"


def test_collect_actors_from_nfo_dir_gathers_and_dedups(tmp_path: Path):
    sub = tmp_path / "sub"
    sub.mkdir(parents=True, exist_ok=True)
    (tmp_path / "a.nfo").write_text(
        '<?xml version="1.0"?><movie><actor><name>三上悠亚</name></actor><actor><name>明日花绮罗</name></actor></movie>',
        encoding="utf-8",
    )
    (sub / "b.nfo").write_text(
        '<?xml version="1.0"?><movie><actor><name>三上悠亚</name></actor><actor><name>桥本有菜</name></actor></movie>',
        encoding="utf-8",
    )
    (tmp_path / "not.nfo").write_text("hello", encoding="utf-8")

    import asyncio

    actors = asyncio.run(actor_db_tool.collect_actors_from_nfo_dir(tmp_path))

    assert set(actors) == {"三上悠亚", "明日花绮罗", "桥本有菜"}


def test_collect_actors_from_nfo_dir_empty_dir(tmp_path: Path):
    import asyncio

    assert asyncio.run(actor_db_tool.collect_actors_from_nfo_dir(tmp_path)) == []


def test_collect_actors_from_nfo_dir_non_existent(tmp_path: Path):
    import asyncio

    assert asyncio.run(actor_db_tool.collect_actors_from_nfo_dir(tmp_path / "missing")) == []


@pytest.mark.asyncio
async def test_run_with_empty_names(_tmp_actor_db: Path):
    result = await actor_db_tool.run([])
    assert result.total == 0
    assert result.translated == 0
    assert result.linked == 0
    assert result.skipped == 0


@pytest.mark.asyncio
async def test_run_skips_actor_without_tmdbid(monkeypatch: pytest.MonkeyPatch, _tmp_actor_db: Path):
    monkeypatch.setattr(tmdb_actor.manager.config, "tmdb_api_key", "fake-key")
    monkeypatch.setattr(tmdb_actor.manager.config, "tmdb_api_base", "api.tmdb.org")
    monkeypatch.setattr(tmdb_actor.resources, "actor_db", {})
    monkeypatch.setattr(tmdb_actor.resources, "actor_db_reverse_index", None)

    result = await actor_db_tool.run(["未知演员"], translate=True, link=True)

    assert result.total == 1
    assert result.skipped == 1
    assert result.translated == 0
    assert result.linked == 0


@pytest.mark.asyncio
async def test_run_translate_backfills_zh_names(monkeypatch: pytest.MonkeyPatch, _tmp_actor_db: Path):
    await tmdb_actor.update_actor_db_row(jp="三上悠亜", zh_cn="", zh_tw="", tmdbid=12345)
    tmdb_actor.resources.actor_db = {
        "三上悠亜": {"zh_cn": "", "zh_tw": "", "keyword": "", "href": "", "tmdbid": 12345, "tmdb_url": ""}
    }
    tmdb_actor.resources.actor_db_reverse_index = None

    monkeypatch.setattr(tmdb_actor.manager.config, "tmdb_api_key", "fake-key")
    monkeypatch.setattr(tmdb_actor.manager.config, "tmdb_api_base", "api.tmdb.org")

    async def _fake_translations(pid, base_url, api_key, client):
        return {"zh_cn": "三上悠亚", "zh_tw": "三上悠亞"}

    monkeypatch.setattr(actor_db_tool, "_fetch_person_translations", _fake_translations)
    monkeypatch.setattr(actor_db_tool, "fetch_libredmm_link", _no_link)

    result = await actor_db_tool.run(["三上悠亜"], translate=True, link=False)

    assert result.total == 1
    assert result.translated == 1

    wb = load_workbook(_tmp_actor_db)
    ws = wb.active
    for row in ws.iter_rows(min_row=2, values_only=True):
        if str(row[0] or "").strip() == "三上悠亜":
            assert row[1] == "三上悠亚"
            assert row[2] == "三上悠亞"
            break
    wb.close()


@pytest.mark.asyncio
async def test_run_link_backfills_href(monkeypatch: pytest.MonkeyPatch, _tmp_actor_db: Path):
    await tmdb_actor.update_actor_db_row(jp="三上悠亜", zh_cn="三上悠亚", zh_tw="三上悠亞", tmdbid=12345)
    tmdb_actor.resources.actor_db = {
        "三上悠亜": {
            "zh_cn": "三上悠亚",
            "zh_tw": "三上悠亞",
            "keyword": "",
            "href": "",
            "tmdbid": 12345,
            "tmdb_url": "",
        }
    }
    tmdb_actor.resources.actor_db_reverse_index = None

    monkeypatch.setattr(tmdb_actor.manager.config, "tmdb_api_key", "fake-key")
    monkeypatch.setattr(tmdb_actor.manager.config, "tmdb_api_base", "api.tmdb.org")

    async def _fake_link(actor_name: str) -> str:
        return "https://www.libredmm.com/actresses/mikami-yua"

    monkeypatch.setattr(actor_db_tool, "fetch_libredmm_link", _fake_link)

    result = await actor_db_tool.run(["三上悠亜"], translate=False, link=True)

    assert result.total == 1
    assert result.linked == 1

    wb = load_workbook(_tmp_actor_db)
    ws = wb.active
    for row in ws.iter_rows(min_row=2, values_only=True):
        if str(row[0] or "").strip() == "三上悠亜":
            assert row[4] == "https://www.libredmm.com/actresses/mikami-yua"
            break
    wb.close()


@pytest.mark.asyncio
async def test_run_skips_when_translate_disabled(monkeypatch: pytest.MonkeyPatch, _tmp_actor_db: Path):
    await tmdb_actor.update_actor_db_row(jp="三上悠亜", zh_cn="", zh_tw="", tmdbid=12345)
    tmdb_actor.resources.actor_db = {
        "三上悠亜": {"zh_cn": "", "zh_tw": "", "keyword": "", "href": "", "tmdbid": 12345, "tmdb_url": ""}
    }
    tmdb_actor.resources.actor_db_reverse_index = None

    monkeypatch.setattr(tmdb_actor.manager.config, "tmdb_api_key", "fake-key")
    monkeypatch.setattr(tmdb_actor.manager.config, "tmdb_api_base", "api.tmdb.org")

    call_count = {"translations": 0}

    async def _counting_translations(pid, base_url, api_key, client):
        call_count["translations"] += 1
        return {"zh_cn": "三上悠亚", "zh_tw": "三上悠亞"}

    monkeypatch.setattr(actor_db_tool, "_fetch_person_translations", _counting_translations)
    monkeypatch.setattr(actor_db_tool, "fetch_libredmm_link", _no_link)

    result = await actor_db_tool.run(["三上悠亜"], translate=False, link=False)

    assert result.total == 1
    assert result.skipped == 1
    assert call_count["translations"] == 0


async def _no_link(actor_name: str) -> str:
    return ""
