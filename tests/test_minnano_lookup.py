from pathlib import Path

from mdcx.config.manager import manager
from mdcx.tools import minnano_crawler


def _mock_lookup(monkeypatch, mapping: dict[str, str]):
    """mock resources.get_actor_data 模拟反向索引查找。mapping: 任意名 -> jp。"""

    def fake_get_actor_data(name):
        jp = mapping.get(name)
        if jp is None:
            return {"has_name": False, "jp": name, "zh_cn": name, "zh_tw": name, "keyword": [name]}
        return {
            "has_name": True,
            "jp": jp,
            "zh_cn": name,
            "zh_tw": name,
            "keyword": [name],
        }

    monkeypatch.setattr(minnano_crawler.resources, "get_actor_data", fake_get_actor_data)


def test_cache_file_under_userdata_dir(monkeypatch, tmp_path: Path):
    """缓存文件应落在运行时用户数据目录（data_folder/userdata），而非硬编码相对路径。"""
    monkeypatch.setattr(manager, "data_folder", tmp_path)
    cache_path = minnano_crawler._get_cache_path()
    assert cache_path == tmp_path / "userdata" / "minnano_cache.xlsx"


def test_save_cache_row_creates_parent_dir(monkeypatch, tmp_path: Path):
    """打包后 data_folder 可能无 userdata 子目录，写入前应自动创建。"""
    monkeypatch.setattr(manager, "data_folder", tmp_path)
    row = {
        minnano_crawler.COL_JP: "テスト女優",
        minnano_crawler.COL_ALIAS: "",
        minnano_crawler.COL_BIRTHDAY: "1990-01-01",
        minnano_crawler.COL_HEIGHT: "160cm",
        minnano_crawler.COL_BUST: "",
        minnano_crawler.COL_WAIST: "",
        minnano_crawler.COL_HIP: "",
        minnano_crawler.COL_CUP: "",
        minnano_crawler.COL_PLACE: "",
        minnano_crawler.COL_AGENCY: "",
        minnano_crawler.COL_TWITTER: "",
        minnano_crawler.COL_CAREER: "",
        minnano_crawler.COL_DEBUT: "",
        minnano_crawler.COL_WIKI: "",
        minnano_crawler.COL_MINNANO_URL: "https://www.minnano-av.com/actress/12345.html",
    }
    ok = minnano_crawler.save_cache_row(row)
    assert ok
    cache_path = minnano_crawler._get_cache_path()
    assert cache_path.parent.exists()
    assert cache_path.exists()
    minnano_crawler._cache_data.clear()
    data = minnano_crawler.load_cache()
    assert "テスト女優" in data
    assert data["テスト女優"]["minnano_url"] == "https://www.minnano-av.com/actress/12345.html"


def test_lookup_returns_jp_for_chinese_name(monkeypatch):
    _mock_lookup(monkeypatch, {"桃園怜奈": "桃園怜奈"})
    assert minnano_crawler._lookup_japanese_name("桃園怜奈") == "桃園怜奈"


def test_lookup_returns_jp_for_alias(monkeypatch):
    _mock_lookup(monkeypatch, {"凪沢怜奈": "桃園怜奈"})
    assert minnano_crawler._lookup_japanese_name("凪沢怜奈") == "桃園怜奈"


def test_lookup_returns_none_for_unknown(monkeypatch):
    _mock_lookup(monkeypatch, {})
    assert minnano_crawler._lookup_japanese_name("不存在的演员") is None


def test_lookup_returns_jp_when_same(monkeypatch):
    _mock_lookup(monkeypatch, {"橋本ありな": "橋本ありな"})
    assert minnano_crawler._lookup_japanese_name("橋本ありな") == "橋本ありな"


def test_lookup_handles_empty_name(monkeypatch):
    _mock_lookup(monkeypatch, {})
    assert minnano_crawler._lookup_japanese_name("") is None
