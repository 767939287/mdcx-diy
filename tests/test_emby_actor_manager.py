from pathlib import Path

import pytest

from mdcx.tools.emby_actor_manager import (
    ActorInfo,
    _build_jellyfin_headers,
    _generate_server_url,
    from_local_avatar,
    gfriends_find_actor,
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
