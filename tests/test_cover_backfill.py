import asyncio
from pathlib import Path

import pytest

from mdcx.config.enums import FixedScrapingType, Website
from mdcx.core import file_crawler
from mdcx.models.types import FileInfo
from scripts import cover_backfill as cb


def test_dedupe_candidates_filters_empty_urls_and_keeps_order():
    candidates = [
        ("poster", "https://a.com/1.jpg"),
        ("poster", ""),
        ("thumb", "https://a.com/1.jpg"),
        ("thumb", "https://b.com/2.jpg"),
        ("fanart", None),
    ]
    assert cb._dedupe_candidates(candidates) == [
        ("poster", "https://a.com/1.jpg"),
        ("thumb", "https://b.com/2.jpg"),
    ]


def test_dedupe_candidates_returns_empty_for_no_valid_candidates():
    assert cb._dedupe_candidates([("poster", ""), ("thumb", None)]) == []


def _build_file_info(tmp_path: Path, number: str = "ABC-123") -> FileInfo:
    file_info = FileInfo.empty()
    file_info.number = number
    file_info.file_path = tmp_path / f"{number}.mp4"
    file_info.folder_path = tmp_path
    file_info.file_name = number
    return file_info


def test_cover_candidate_sites_forced_site_wins():
    file_info = _build_file_info(Path("/tmp"))
    assert cb._cover_candidate_sites(file_info, forced_site="r18dev") == ["r18dev"]


def test_cover_candidate_sites_uses_single_website(monkeypatch: pytest.MonkeyPatch):
    file_info = _build_file_info(Path("/tmp"))

    classification = file_crawler.ScrapeClassification(FixedScrapingType.AUTO, "auto", website=Website.KIN8)
    monkeypatch.setattr(cb, "classify_scrape_task", lambda task, config: classification)

    assert cb._cover_candidate_sites(file_info, forced_site=None) == ["kin8"]


def test_cover_candidate_sites_orders_priority_first(monkeypatch: pytest.MonkeyPatch):
    file_info = _build_file_info(Path("/tmp"))

    classification = file_crawler.ScrapeClassification(
        FixedScrapingType.AUTO,
        "auto",
        sites=[Website.MISSAV, Website.R18DEV, Website.OFFICIAL, Website.MGSTAGE],
    )
    monkeypatch.setattr(cb, "classify_scrape_task", lambda task, config: classification)

    assert cb._cover_candidate_sites(file_info, forced_site=None) == [
        "official",
        "mgstage",
        "missav",
        "r18dev",
    ]


def test_resolve_backfill_input_empty_raises():
    with pytest.raises(ValueError, match="input is empty"):
        asyncio.run(cb.resolve_backfill_input("   "))


def test_resolve_backfill_input_parses_number_from_raw(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    async def _fake_get_file_info_v2(info_path, copy_sub=False):
        file_info = _build_file_info(tmp_path, number="ABC-123")
        return file_info

    monkeypatch.setattr(cb, "get_file_info_v2", _fake_get_file_info_v2)

    result = asyncio.run(cb.resolve_backfill_input("ABC-123"))

    assert result.number == "ABC-123"
    assert result.source_file is None


def test_resolve_backfill_input_falls_back_to_file_info_number(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    async def _fake_get_file_info_v2(info_path, copy_sub=False):
        file_info = _build_file_info(tmp_path, number="XYZ-999")
        return file_info

    monkeypatch.setattr(cb, "get_file_info_v2", _fake_get_file_info_v2)
    monkeypatch.setattr(cb, "get_file_number", lambda filepath, escape_list: "")

    result = asyncio.run(cb.resolve_backfill_input("some-random-string"))

    assert result.number == "XYZ-999"
