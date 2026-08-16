from pathlib import Path

import pytest

from mdcx.tools.emby_actor_manager import (
    ActorInfo,
    _build_jellyfin_headers,
    _generate_server_url,
    build_local_avatar_index,
    delete_actor_image,
    from_local_avatar,
    gfriends_find_actor,
    search_actor_info,
)


def test_build_jellyfin_headers_includes_auth_token(monkeypatch: pytest.MonkeyPatch):
    from mdcx.config.manager import manager

    monkeypatch.setattr(manager.config, "api_key", "test-token-123")
    headers = _build_jellyfin_headers()
    assert headers["Authorization"] == 'MediaBrowser Token="test-token-123"'


def test_build_jellyfin_headers_merges_provided_headers(monkeypatch: pytest.MonkeyPatch):
    from mdcx.config.manager import manager

    monkeypatch.setattr(manager.config, "api_key", "key")
    headers = _build_jellyfin_headers({"Content-Type": "application/json"})
    assert headers["Content-Type"] == "application/json"
    assert "Authorization" in headers


def test_generate_server_url_emby_format(monkeypatch: pytest.MonkeyPatch):
    from mdcx.config.manager import manager

    monkeypatch.setattr(manager.config, "server_type", "emby")
    monkeypatch.setattr(manager.config, "emby_url", "http://localhost:8096")

    actor = {"Name": "三上悠亞", "Id": "actor-123", "ServerId": "srv-1"}
    homepage, person, pic, backdrop, backdrop0, update = _generate_server_url(actor)

    assert homepage == "http://localhost:8096/web/index.html#!/item?id=actor-123&serverId=srv-1"
    assert person == "http://localhost:8096/emby/Persons/%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9E"
    assert pic == "http://localhost:8096/emby/Items/actor-123/Images/Primary"
    assert backdrop == "http://localhost:8096/emby/Items/actor-123/Images/Backdrop"
    assert backdrop0 == "http://localhost:8096/emby/Items/actor-123/Images/Backdrop/0"
    assert update == "http://localhost:8096/emby/Items/actor-123"


def test_generate_server_url_jellyfin_format(monkeypatch: pytest.MonkeyPatch):
    from mdcx.config.manager import manager

    monkeypatch.setattr(manager.config, "server_type", "jellyfin")
    monkeypatch.setattr(manager.config, "emby_url", "http://jellyfin:8096")
    monkeypatch.setattr(manager.config, "user_id", "user-456")

    actor = {"Name": "Mikami Yua", "Id": "actor-456", "ServerId": "srv-2"}
    homepage, person, pic, backdrop, backdrop0, update = _generate_server_url(actor)

    assert homepage == "http://jellyfin:8096/web/index.html#!/details?id=actor-456&serverId=srv-2"
    assert person == "http://jellyfin:8096/Persons/Mikami%20Yua?userId=user-456"
    assert pic == "http://jellyfin:8096/Items/actor-456/Images/Primary"
    assert backdrop == "http://jellyfin:8096/Items/actor-456/Images/Backdrop"
    assert backdrop0 == "http://jellyfin:8096/Items/actor-456/Images/Backdrop/0"
    assert update == "http://jellyfin:8096/Items/actor-456"


def test_gfriends_find_actor_matches_stem():
    index = {"三上悠亞.jpg": "https://gf.com/1.jpg", "橋本有菜.png": "https://gf.com/2.png"}
    assert gfriends_find_actor(index, "三上悠亞") == "https://gf.com/1.jpg"


def test_gfriends_find_actor_returns_none_when_not_found():
    assert gfriends_find_actor({"A.jpg": "https://x.com/a.jpg"}, "B") is None


def test_gfriends_find_actor_returns_none_for_empty_index():
    assert gfriends_find_actor({}, "三上悠亞") is None


def test_from_local_avatar_returns_path_when_file_matches(tmp_path: Path):
    avatar_dir = tmp_path / "avatars"
    avatar_dir.mkdir(parents=True)
    (avatar_dir / "三上悠亚.jpg").write_text("fake", encoding="utf-8")
    (avatar_dir / "other.png").write_text("fake", encoding="utf-8")

    actor = ActorInfo(name="三上悠亚", actor_id="id1", server_id="srv1")
    result = from_local_avatar(actor, str(avatar_dir))
    assert result == str(avatar_dir / "三上悠亚.jpg")


def test_from_local_avatar_returns_none_when_dir_empty(tmp_path: Path):
    avatar_dir = tmp_path / "empty_avatars"
    avatar_dir.mkdir(parents=True)

    actor = ActorInfo(name="三上悠亚", actor_id="id1", server_id="srv1")
    assert from_local_avatar(actor, str(avatar_dir)) is None


def test_from_local_avatar_returns_none_when_dir_not_exists(tmp_path: Path):
    actor = ActorInfo(name="三上悠亚", actor_id="id1", server_id="srv1")
    assert from_local_avatar(actor, str(tmp_path / "nonexistent")) is None


def test_from_local_avatar_returns_none_when_dir_empty_string():
    actor = ActorInfo(name="三上悠亚", actor_id="id1", server_id="srv1")
    assert from_local_avatar(actor, "") is None


def test_from_local_avatar_with_pre_scanned_index_hit(tmp_path: Path):
    avatar_dir = tmp_path / "avatars"
    avatar_dir.mkdir(parents=True)
    pic = avatar_dir / "三上悠亚.jpg"
    pic.write_text("fake", encoding="utf-8")

    index = build_local_avatar_index(str(avatar_dir))
    assert "三上悠亚" in index

    actor = ActorInfo(name="三上悠亚", actor_id="id1", server_id="srv1")
    result = from_local_avatar(actor, str(avatar_dir), pre_scanned_index=index)
    assert result == str(pic)


def test_from_local_avatar_with_pre_scanned_index_miss():
    index = {"别的演员": "/some/path.jpg"}
    actor = ActorInfo(name="三上悠亚", actor_id="id1", server_id="srv1")
    assert from_local_avatar(actor, "/nonexistent", pre_scanned_index=index) is None


def test_from_local_avatar_with_empty_index_returns_none():
    actor = ActorInfo(name="三上悠亚", actor_id="id1", server_id="srv1")
    assert from_local_avatar(actor, "/nonexistent", pre_scanned_index={}) is None


def test_build_local_avatar_index_skips_non_image_files(tmp_path: Path):
    avatar_dir = tmp_path / "avatars"
    avatar_dir.mkdir(parents=True)
    (avatar_dir / "actor1.jpg").write_text("fake", encoding="utf-8")
    (avatar_dir / "actor2.png").write_text("fake", encoding="utf-8")
    (avatar_dir / "readme.txt").write_text("fake", encoding="utf-8")
    (avatar_dir / "actor1.json").write_text("{}", encoding="utf-8")

    index = build_local_avatar_index(str(avatar_dir))
    assert set(index.keys()) == {"actor1", "actor2"}


def test_build_local_avatar_index_returns_empty_for_nonexistent_dir():
    assert build_local_avatar_index("/nonexistent/path") == {}


def test_build_local_avatar_index_returns_empty_for_empty_string():
    assert build_local_avatar_index("") == {}


def test_actor_info_status_text():
    actor = ActorInfo(name="Test", actor_id="id1", server_id="srv1")
    assert "缺头像" in actor.status_text
    assert "缺简介" in actor.status_text


def test_actor_info_status_text_shows_missing_image():
    actor = ActorInfo(name="Test", actor_id="id1", server_id="srv1", has_image=False, has_overview=True)
    assert "缺头像" in actor.status_text


def test_actor_info_status_text_shows_missing_info():
    actor = ActorInfo(name="Test", actor_id="id1", server_id="srv1", has_image=True, has_overview=False)
    assert "缺简介" in actor.status_text


def test_actor_info_status_text_shows_both_missing():
    actor = ActorInfo(name="Test", actor_id="id1", server_id="srv1")
    assert "缺头像" in actor.status_text
    assert "缺简介" in actor.status_text


def test_actor_info_status_icon_returns_emoji():
    complete = ActorInfo(name="T", actor_id="id", server_id="s", has_image=True, has_overview=True)
    assert complete.status_icon == "✅"

    missing = ActorInfo(name="T", actor_id="id", server_id="s")
    assert missing.status_icon in ("❌", "⬜")


@pytest.mark.asyncio
async def test_search_actor_info_reads_dump_pascalcase_keys(monkeypatch: pytest.MonkeyPatch):
    import mdcx.tools.emby_actor_manager as em

    async def _no_wiki(info):
        return None, ""

    async def _fill_minnano(info, wiki_intro: str = ""):
        info.overview = "测试简介"
        info.taglines = ["测试标签"]
        info.year = 2024
        info.locations = ["日本"]
        return True, ""

    monkeypatch.setattr(em, "search_wiki", _no_wiki)
    monkeypatch.setattr(em, "get_minnano_info", _fill_minnano)
    actor = ActorInfo(name="Test", actor_id="id1", server_id="srv1")

    found = await search_actor_info(actor)

    assert found is True
    assert actor.need_update_info is True
    assert actor.new_overview == "测试简介"
    assert actor.new_taglines == ["测试标签"]
    assert actor.new_production_year == 2024
    assert actor.new_production_locations == ["日本"]


@pytest.mark.asyncio
async def test_delete_actor_image_404_treated_as_success(monkeypatch: pytest.MonkeyPatch):
    from mdcx.config.manager import manager

    async def _fake_request(method, url, *, headers=None, use_proxy=None, **kwargs):
        assert method == "DELETE"
        return None, "DELETE 失败: HTTP 404"

    monkeypatch.setattr(manager.config, "server_type", "emby")
    monkeypatch.setattr(manager.config, "emby_url", "http://127.0.0.1:8096")
    monkeypatch.setattr(manager.computed.async_client, "request", _fake_request)

    actor = ActorInfo(name="Test", actor_id="id1", server_id="srv1")
    ok, msg = await delete_actor_image(actor)

    assert ok is True
    assert "404" in msg
