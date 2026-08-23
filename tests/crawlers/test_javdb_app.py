import pytest

from mdcx.config.models import Website
from mdcx.crawlers.javdb_app import JavdbAppCrawler
from mdcx.models.model_types import CrawlerInput


def test_normalize_image_url_rewrites_legacy_host():
    crawler = JavdbAppCrawler(client=None)

    assert (
        crawler._normalize_image_url("https://tp.cmastd.com/rhe951l4q/covers/demo.jpg")
        == "https://c0.jdbstatic.com/covers/demo.jpg"
    )
    assert (
        crawler._normalize_image_url("https://tp.cmastd.com/rhe951l4q/small_covers/demo.jpg")
        == "https://c0.jdbstatic.com/thumbs/demo.jpg"
    )
    assert (
        crawler._normalize_image_url("https://tp.spfcas.com/rhe951l4q/covers/demo.jpg")
        == "https://c0.jdbstatic.com/covers/demo.jpg"
    )
    assert (
        crawler._normalize_image_url("https://tp.spfcas.com/rhe951l4q/thumbs/xz/XzkY4.jpg")
        == "https://c0.jdbstatic.com/thumbs/xz/XzkY4.jpg"
    )


@pytest.mark.asyncio
async def test_run_maps_cover_to_thumb_and_thumb_to_poster():
    class FakeClient:
        async def get_json(self, url: str, **kwargs):
            assert kwargs["headers"]["jdsignature"]
            if "/api/v2/search" in url:
                return (
                    {
                        "data": {
                            "movies": [
                                {
                                    "id": "movie-1",
                                    "number": "URE-018",
                                    "title": "Title",
                                }
                            ]
                        }
                    },
                    "",
                )

            if "/api/v4/movies/movie-1" in url:
                return (
                    {
                        "data": {
                            "movie": {
                                "id": "movie-1",
                                "number": "URE-018",
                                "title": "Title",
                                "origin_title": "Origin Title",
                                "summary": "Outline",
                                "cover_url": "https://tp.cmastd.com/rhe951l4q/covers/cover-wide.jpg",
                                "thumb_url": "https://tp.cmastd.com/rhe951l4q/small_covers/poster-tall.jpg",
                                "duration": 120,
                                "release_date": "2024-01-02",
                                "maker_name": "Maker",
                                "director_name": "Director",
                                "publisher_name": "Publisher",
                                "series_name": "Series",
                                "tags": [{"name": "Tag1"}],
                                "actors": [{"name": "Actor1"}],
                                "preview_images": [{"thumb_url": "https://tp.cmastd.com/rhe951l4q/samples/1.jpg"}],
                                "preview_video_url": "//video.example.com/trailer.mp4",
                            }
                        }
                    },
                    "",
                )

            raise AssertionError(f"unexpected url: {url}")

    crawler = JavdbAppCrawler(client=FakeClient())
    input_data = CrawlerInput.empty()
    input_data.number = "URE-018"

    response = await crawler.run(input_data)

    assert response.data is not None
    assert response.data.source == Website.JAVDB_APP.value
    assert response.data.number == "URE-018"
    assert response.data.title == "Title"
    assert response.data.originaltitle == "Origin Title"
    assert response.data.thumb == "https://c0.jdbstatic.com/covers/cover-wide.jpg"
    assert response.data.poster == "https://c0.jdbstatic.com/thumbs/poster-tall.jpg"
    assert response.data.extrafanart == ["https://c0.jdbstatic.com/samples/1.jpg"]
    assert response.data.trailer == "https://video.example.com/trailer.mp4"
    assert response.data.release == "2024-01-02"
    assert response.data.year == "2024"


@pytest.mark.asyncio
async def test_run_bf_does_not_match_abf():
    class FakeClient:
        async def get_json(self, url: str, **kwargs):
            if "/api/v2/search" in url:
                return (
                    {"data": {"movies": [{"id": "movie-abf", "number": "ABF-002", "title": "Title"}]}},
                    "",
                )
            raise AssertionError(f"unexpected url: {url}")

    crawler = JavdbAppCrawler(client=FakeClient())
    input_data = CrawlerInput.empty()
    input_data.number = "BF-002"

    response = await crawler.run(input_data)

    assert response.data is None


@pytest.mark.asyncio
async def test_run_bf_matches_bf_result_when_present():
    class FakeClient:
        async def get_json(self, url: str, **kwargs):
            if "/api/v2/search" in url:
                return (
                    {
                        "data": {
                            "movies": [
                                {"id": "movie-abf", "number": "ABF-002", "title": "ABF Title"},
                                {"id": "movie-bf", "number": "BF-002", "title": "BF Title"},
                            ]
                        }
                    },
                    "",
                )
            if "/api/v4/movies/movie-bf" in url:
                return (
                    {
                        "data": {
                            "movie": {
                                "id": "movie-bf",
                                "number": "BF-002",
                                "title": "BF Title",
                                "cover_url": "https://c0.jdbstatic.com/covers/bf/bf002.jpg",
                                "thumb_url": "https://c0.jdbstatic.com/thumbs/bf/bf002.jpg",
                            }
                        }
                    },
                    "",
                )
            raise AssertionError(f"unexpected url: {url}")

    crawler = JavdbAppCrawler(client=FakeClient())
    input_data = CrawlerInput.empty()
    input_data.number = "BF-002"

    response = await crawler.run(input_data)

    assert response.data is not None
    assert response.data.number == "BF-002"
    assert response.data.title == "BF Title"


# ============================================================
# fetch_javdb_aliases 测试
# ============================================================


@pytest.mark.asyncio
async def test_fetch_javdb_aliases_returns_other_name(monkeypatch):
    """搜索 → 影片详情 → 演员详情，返回 other_name 中的别名"""
    from mdcx.crawlers import javdb_app

    class _Client:
        async def get_json(self, url, headers=None, retry_count=1, **kwargs):
            if "/api/v2/search" in url:
                return ({"data": {"movies": [{"id": "m1", "number": "ABC-001"}]}}, "")
            if "/api/v4/movies/m1" in url:
                return ({"data": {"movie": {"actors": [{"id": "a1", "name": "波多野結衣", "gender": 0}]}}}, "")
            if "/api/v1/actors/a1" in url:
                return (
                    {
                        "data": {
                            "actor": {
                                "name": "波多野結衣",
                                "name_zht": "波多野結衣",
                                "other_name": "波多野結衣, 酒井愛美",
                            }
                        }
                    },
                    "",
                )
            raise AssertionError(f"unexpected: {url}")

    class _Computed:
        async_client = _Client()

    class _Ctx:
        async def __aenter__(self):
            return _Computed()

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(javdb_app.manager, "acquire_computed", lambda: _Ctx())

    result = await javdb_app.fetch_javdb_aliases("波多野結衣")
    assert result == ["酒井愛美"]


@pytest.mark.asyncio
async def test_fetch_javdb_aliases_includes_name_zht(monkeypatch):
    """name_zht 与 name 不同时作为别名返回"""
    from mdcx.crawlers import javdb_app

    class _Client:
        async def get_json(self, url, headers=None, retry_count=1, **kwargs):
            if "/api/v2/search" in url:
                return ({"data": {"movies": [{"id": "m1"}]}}, "")
            if "/api/v4/movies/m1" in url:
                return ({"data": {"movie": {"actors": [{"id": "a1", "name": "桃乃木かな"}]}}}, "")
            if "/api/v1/actors/a1" in url:
                return (
                    {
                        "data": {
                            "actor": {
                                "name": "桃乃木香奈",
                                "name_zht": "桃乃木香奈",
                                "other_name": "桃乃木かな, 松嶋真麻",
                            }
                        }
                    },
                    "",
                )
            raise AssertionError(f"unexpected: {url}")

    class _Computed:
        async_client = _Client()

    class _Ctx:
        async def __aenter__(self):
            return _Computed()

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(javdb_app.manager, "acquire_computed", lambda: _Ctx())

    result = await javdb_app.fetch_javdb_aliases("桃乃木かな")
    assert "松嶋真麻" in result
    assert "桃乃木かな" not in result  # 原名排除
    assert "桃乃木香奈" not in result  # db_name 排除


@pytest.mark.asyncio
async def test_fetch_javdb_aliases_empty_other_name(monkeypatch):
    """other_name 为 None/空时返回空列表"""
    from mdcx.crawlers import javdb_app

    class _Client:
        async def get_json(self, url, headers=None, retry_count=1, **kwargs):
            if "/api/v2/search" in url:
                return ({"data": {"movies": [{"id": "m1"}]}}, "")
            if "/api/v4/movies/m1" in url:
                return ({"data": {"movie": {"actors": [{"id": "a1", "name": "河北彩花"}]}}}, "")
            if "/api/v1/actors/a1" in url:
                return ({"data": {"actor": {"name": "河北彩花", "name_zht": "", "other_name": None}}}, "")
            raise AssertionError(f"unexpected: {url}")

    class _Computed:
        async_client = _Client()

    class _Ctx:
        async def __aenter__(self):
            return _Computed()

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(javdb_app.manager, "acquire_computed", lambda: _Ctx())

    result = await javdb_app.fetch_javdb_aliases("河北彩花")
    assert result == []


@pytest.mark.asyncio
async def test_fetch_javdb_aliases_no_search_results(monkeypatch):
    """搜索无结果返回空列表"""
    from mdcx.crawlers import javdb_app

    class _Client:
        async def get_json(self, url, headers=None, retry_count=1, **kwargs):
            if "/api/v2/search" in url:
                return ({"data": {"movies": []}}, "")
            raise AssertionError(f"unexpected: {url}")

    class _Computed:
        async_client = _Client()

    class _Ctx:
        async def __aenter__(self):
            return _Computed()

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(javdb_app.manager, "acquire_computed", lambda: _Ctx())

    result = await javdb_app.fetch_javdb_aliases("不存在的演员")
    assert result == []


@pytest.mark.asyncio
async def test_fetch_javdb_aliases_no_actor_match(monkeypatch):
    """影片中无匹配演员时返回空列表"""
    from mdcx.crawlers import javdb_app

    class _Client:
        async def get_json(self, url, headers=None, retry_count=1, **kwargs):
            if "/api/v2/search" in url:
                return ({"data": {"movies": [{"id": "m1"}, {"id": "m2"}]}}, "")
            if "/api/v4/movies/" in url:
                return ({"data": {"movie": {"actors": [{"id": "x", "name": "别人"}]}}}, "")
            raise AssertionError(f"unexpected: {url}")

    class _Computed:
        async_client = _Client()

    class _Ctx:
        async def __aenter__(self):
            return _Computed()

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(javdb_app.manager, "acquire_computed", lambda: _Ctx())

    result = await javdb_app.fetch_javdb_aliases("三上悠亜")
    assert result == []


@pytest.mark.asyncio
async def test_fetch_javdb_aliases_jp_variant_match(monkeypatch):
    """日文异体字差异（亜/亞）也能匹配"""
    from mdcx.crawlers import javdb_app

    class _Client:
        async def get_json(self, url, headers=None, retry_count=1, **kwargs):
            if "/api/v2/search" in url:
                return ({"data": {"movies": [{"id": "m1"}]}}, "")
            if "/api/v4/movies/m1" in url:
                # 搜索"三上悠亜"，影片里演员名是"三上悠亞"
                return ({"data": {"movie": {"actors": [{"id": "a1", "name": "三上悠亞"}]}}}, "")
            if "/api/v1/actors/a1" in url:
                return (
                    {
                        "data": {
                            "actor": {"name": "三上悠亜", "name_zht": "三上悠亜", "other_name": "三上悠亞, 鬼头桃菜"}
                        }
                    },
                    "",
                )
            raise AssertionError(f"unexpected: {url}")

    class _Computed:
        async_client = _Client()

    class _Ctx:
        async def __aenter__(self):
            return _Computed()

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(javdb_app.manager, "acquire_computed", lambda: _Ctx())

    result = await javdb_app.fetch_javdb_aliases("三上悠亜")
    assert "鬼头桃菜" in result


@pytest.mark.asyncio
async def test_fetch_javdb_aliases_empty_input():
    """空输入返回空列表"""
    from mdcx.crawlers.javdb_app import fetch_javdb_aliases

    assert await fetch_javdb_aliases("") == []
    assert await fetch_javdb_aliases("   ") == []


# ============================================================
# fetch_javdb_actor_info 测试
# ============================================================


@pytest.mark.asyncio
async def test_fetch_javdb_actor_info_returns_full_fields(monkeypatch):
    """搜索 → 影片详情 → 演员详情，返回完整 name/name_zht/other_name"""
    from mdcx.crawlers import javdb_app

    class _Client:
        async def get_json(self, url, headers=None, retry_count=1, **kwargs):
            if "/api/v2/search" in url:
                return ({"data": {"movies": [{"id": "m1"}]}}, "")
            if "/api/v4/movies/m1" in url:
                return ({"data": {"movie": {"actors": [{"id": "a1", "name": "桐谷まつり"}]}}}, "")
            if "/api/v1/actors/a1" in url:
                return (
                    {
                        "data": {
                            "actor": {
                                "name": "桐谷茉莉",
                                "name_zht": "桐谷茉莉",
                                "other_name": "桐谷まつり",
                            }
                        }
                    },
                    "",
                )
            raise AssertionError(f"unexpected: {url}")

    class _Computed:
        async_client = _Client()

    class _Ctx:
        async def __aenter__(self):
            return _Computed()

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(javdb_app.manager, "acquire_computed", lambda: _Ctx())

    info = await javdb_app.fetch_javdb_actor_info("桐谷まつり")
    assert info is not None
    assert info.name == "桐谷茉莉"
    assert info.name_zht == "桐谷茉莉"
    assert info.other_name == "桐谷まつり"


@pytest.mark.asyncio
async def test_fetch_javdb_actor_info_null_fields(monkeypatch):
    """JavDB 演员详情中 name_zht/other_name 为 null 时正常返回空串"""
    from mdcx.crawlers import javdb_app

    class _Client:
        async def get_json(self, url, headers=None, retry_count=1, **kwargs):
            if "/api/v2/search" in url:
                return ({"data": {"movies": [{"id": "m1"}]}}, "")
            if "/api/v4/movies/m1" in url:
                return ({"data": {"movie": {"actors": [{"id": "a1", "name": "神木麗"}]}}}, "")
            if "/api/v1/actors/a1" in url:
                return ({"data": {"actor": {"name": "神木麗", "name_zht": None, "other_name": None}}}, "")
            raise AssertionError(f"unexpected: {url}")

    class _Computed:
        async_client = _Client()

    class _Ctx:
        async def __aenter__(self):
            return _Computed()

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(javdb_app.manager, "acquire_computed", lambda: _Ctx())

    info = await javdb_app.fetch_javdb_actor_info("神木麗")
    assert info is not None
    assert info.name == "神木麗"
    assert info.name_zht == ""
    assert info.other_name == ""


@pytest.mark.asyncio
async def test_fetch_javdb_actor_info_no_match(monkeypatch):
    """搜索无结果返回 None"""
    from mdcx.crawlers import javdb_app

    class _Client:
        async def get_json(self, url, headers=None, retry_count=1, **kwargs):
            if "/api/v2/search" in url:
                return ({"data": {"movies": []}}, "")
            raise AssertionError(f"unexpected: {url}")

    class _Computed:
        async_client = _Client()

    class _Ctx:
        async def __aenter__(self):
            return _Computed()

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(javdb_app.manager, "acquire_computed", lambda: _Ctx())

    info = await javdb_app.fetch_javdb_actor_info("不存在的演员")
    assert info is None


@pytest.mark.asyncio
async def test_fetch_javdb_actor_info_empty_input():
    """空输入返回 None"""
    from mdcx.crawlers.javdb_app import fetch_javdb_actor_info

    assert await fetch_javdb_actor_info("") is None
    assert await fetch_javdb_actor_info("   ") is None


def test_javdb_actor_info_dataclass_defaults():
    """JavdbActorInfo 默认值为空串"""
    from mdcx.crawlers.javdb_app import JavdbActorInfo

    info = JavdbActorInfo()
    assert info.name == ""
    assert info.name_zht == ""
    assert info.other_name == ""


def test_normalize_actor_name_strips_punctuation():
    from mdcx.crawlers.javdb_app import _normalize_actor_name

    assert _normalize_actor_name("檸檬.") == _normalize_actor_name("檸檬")
    assert _normalize_actor_name("波多野 結衣") == _normalize_actor_name("波多野結衣")


def test_actor_name_matches_inclusive():
    from mdcx.crawlers.javdb_app import _actor_name_matches

    assert _actor_name_matches("田中檸檬", "檸檬.")
    assert _actor_name_matches("三上悠亜", "三上悠亞")  # 日文异体字
    assert _actor_name_matches("波多野結衣", "波多野結衣")  # 精确
    assert _actor_name_matches("ひかり", "青空ひかり")  # 3字假名包含
    assert not _actor_name_matches("波多野結衣", "桃乃木かな")
    assert not _actor_name_matches("", "有人")


def test_actor_name_matches_short_kana_no_substring():
    """纯假名短名（≤2字）不做子串包含匹配，避免误匹配"""
    from mdcx.crawlers.javdb_app import _actor_name_matches

    assert not _actor_name_matches("りな", "新ありな")  # 2字假名子串→拒绝
    assert not _actor_name_matches("まい", "神菜美まい")  # 2字假名子串→拒绝
    assert _actor_name_matches("さつき", "さつき芽衣")  # 3字假名前缀→允许


def test_actor_name_matches_kanji_substring_allowed():
    """含汉字的短名（≤2字）允许子串包含，如 田中檸檬 → 檸檬"""
    from mdcx.crawlers.javdb_app import _actor_name_matches

    assert _actor_name_matches("田中檸檬", "檸檬")  # 汉字2字子串→允许


def test_is_combo_name_filters_dual_actor_names():
    """组合名（A・B 格式，两边各为日本人姓名）应被过滤"""
    from mdcx.crawlers.javdb_app import _is_combo_name

    assert _is_combo_name("朝比奈菜々子・水原麗子")  # 双人名组合
    assert not _is_combo_name("アンジェラ・ホワイト")  # 外国人名片假名
    assert not _is_combo_name("岸畑孝美(人妻斬り・エッチな0930)")  # 括号内
    assert not _is_combo_name("ボィーン・フジオカ")  # 昵称片假名
    assert not _is_combo_name("ミウ・ザ・ヴァーチャル")  # 3段
    assert not _is_combo_name("岸畑孝美")  # 无・


def test_split_aliases_skips_combo_names():
    """_split_aliases 应过滤组合名"""
    from mdcx.crawlers.javdb_app import _split_aliases

    aliases = _split_aliases(
        other_name="朝比奈菜々子・水原麗子,単体女優,アンジェラ・ホワイト",
        name_zht="",
        search_name="テスト",
        db_name="テスト",
    )
    assert "朝比奈菜々子・水原麗子" not in aliases  # 组合名被过滤
    assert "単体女優" in aliases  # 普通别名保留
    assert "アンジェラ・ホワイト" in aliases  # 外国人名保留
