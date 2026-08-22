"""回归测试: emby_actor_manager 与服务器的 POST/DELETE 交互。

背景
----
当 Emby/Jellyfin 服务器对 POST/DELETE 返回 200/204 但 body 为空（b""）时,
旧的 ``post_content`` 调用方会把**成功的空响应误判为失败**。本测试验证:
- 空 body 判成功 (HTTP 200/204)
- 5xx 判失败
- 本地文件不存在时直接失败不发请求
- 并发 fetch_all_actors 每演员仅调一次详情

实现说明
--------
emby_actor_manager 通过 ``async with manager.acquire_computed() as computed``
拿 ``Computed`` 租约到 ``computed.async_client``。测试通过 patch
``manager.acquire_computed`` 注入 fake client (避开真实 Computed 生命周期)。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


def _make_lease(client):
    """构造一个可直接 async with 的 fake lease, .async_client 指向 client."""
    lease = MagicMock()
    lease.__aenter__ = AsyncMock(return_value=MagicMock(async_client=client))
    lease.__aexit__ = AsyncMock(return_value=False)
    return lease


@pytest.fixture
def emby_configured(monkeypatch):
    """填必需的 api_key/emby_url/server_type, 否则 get_emby_actor_list 会提前 return []."""
    from mdcx.config.manager import manager

    monkeypatch.setattr(manager.config, "api_key", "test-token")
    monkeypatch.setattr(manager.config, "emby_url", "http://test:8096")
    monkeypatch.setattr(manager.config, "server_type", "emby")
    monkeypatch.setattr(manager.config, "user_id", "user-1")


@pytest.fixture
def actor_stub():
    from mdcx.tools.emby_actor_manager import ActorInfo

    return ActorInfo(
        name="测试演员",
        actor_id="actor-001",
        server_id="srv",
        has_image=False,
    )


async def test_update_person_info_returns_success_on_200_empty_body(actor_stub):
    """Emby POST /Items/{id} 返回 200 + 空 body 必须判成功.

    回归: post_content 成功时返回 (b"", "")，调用方 ``if ok:`` 不能
    把空 bytes 当 False。
    """
    from mdcx.tools.emby_actor_manager import update_person_info

    fake_client = MagicMock()
    # 注意: post_content 返回 (bytes|None, str)。
    # 服务器 200 + 空 body 时 post_content 返回 (b"", "")——必须算成功
    fake_client.post_content = AsyncMock(return_value=(b"", ""))

    with patch(
        "mdcx.tools.emby_actor_manager.manager.acquire_computed",
        return_value=_make_lease(fake_client),
    ):
        ok, msg = await update_person_info(actor_stub)

    assert ok, f"200 空 body 应成功, 实际: {msg!r}"
    assert "成功" in msg


async def test_update_person_info_failure_on_error(actor_stub):
    """post_content 返回 (None, err) 时判失败."""
    from mdcx.tools.emby_actor_manager import update_person_info

    fake_client = MagicMock()
    fake_client.post_content = AsyncMock(return_value=(None, "HTTP 500"))

    with patch(
        "mdcx.tools.emby_actor_manager.manager.acquire_computed",
        return_value=_make_lease(fake_client),
    ):
        ok, msg = await update_person_info(actor_stub)

    assert not ok
    assert "失败" in msg


async def test_upload_actor_image_success_on_204_empty(actor_stub, tmp_path: Path):
    """Emby 上传图片 204/空 body 判成功."""
    from mdcx.tools.emby_actor_manager import upload_actor_image

    img = tmp_path / "test.jpg"
    img.write_bytes(b"\xff\xd8\xff")

    fake_client = MagicMock()
    fake_client.post_content = AsyncMock(return_value=(b"", ""))

    with patch(
        "mdcx.tools.emby_actor_manager.manager.acquire_computed",
        return_value=_make_lease(fake_client),
    ):
        ok, msg = await upload_actor_image(actor_stub, img)

    assert ok, f"204 空 body 应成功, 实际: {msg!r}"


async def test_upload_actor_image_fails_when_file_missing(actor_stub, tmp_path: Path):
    """本地文件不存在直接失败, 不发请求."""
    from mdcx.tools.emby_actor_manager import upload_actor_image

    ok, msg = await upload_actor_image(actor_stub, tmp_path / "nonexistent.jpg")

    assert not ok
    assert "不存在" in msg


async def test_upload_actor_backdrop_targets_index_zero(actor_stub, tmp_path: Path, emby_configured):
    """P0-2 回归：背景上传应覆盖 /Backdrop/0，而不是追加到未指定 index 的列表。"""
    from mdcx.tools.emby_actor_manager import upload_actor_backdrop

    img = tmp_path / "bg.jpg"
    img.write_bytes(b"\xff\xd8\xff")

    captured: dict[str, str] = {}

    async def _post(url, data, *, headers=None, use_proxy=None, **kwargs):
        captured["url"] = url
        return b"", ""

    fake_client = MagicMock()
    fake_client.post_content = AsyncMock(side_effect=_post)

    with patch(
        "mdcx.tools.emby_actor_manager.manager.acquire_computed",
        return_value=_make_lease(fake_client),
    ):
        ok, msg = await upload_actor_backdrop(actor_stub, img)

    assert ok, f"上传应成功, 实际: {msg!r}"
    assert captured["url"].endswith("/Items/actor-001/Images/Backdrop/0")


async def test_delete_actor_image_200_is_success(actor_stub):
    """HTTP 200/204 删除成功."""
    from mdcx.tools.emby_actor_manager import delete_actor_image

    for status in (200, 204):
        fake_resp = MagicMock()
        fake_resp.status_code = status
        fake_client = MagicMock()
        fake_client.request = AsyncMock(return_value=(fake_resp, ""))

        with patch(
            "mdcx.tools.emby_actor_manager.manager.acquire_computed",
            return_value=_make_lease(fake_client),
        ):
            ok, msg = await delete_actor_image(actor_stub)

        assert ok, f"HTTP {status} 应成功, 实际: {msg!r}"


async def test_delete_actor_image_404_is_already_gone(actor_stub):
    """404 表示本来就没头像, 视为删除干净以便后续上传."""
    from mdcx.tools.emby_actor_manager import delete_actor_image

    fake_resp = MagicMock()
    fake_resp.status_code = 404
    fake_client = MagicMock()
    fake_client.request = AsyncMock(return_value=(fake_resp, ""))

    with patch(
        "mdcx.tools.emby_actor_manager.manager.acquire_computed",
        return_value=_make_lease(fake_client),
    ):
        ok, _ = await delete_actor_image(actor_stub)

    assert ok


async def test_delete_actor_image_500_is_failure(actor_stub):
    """5xx 服务端错误必须判失败, 上层会跳过后续上传."""
    from mdcx.tools.emby_actor_manager import delete_actor_image

    fake_resp = MagicMock()
    fake_resp.status_code = 500
    fake_client = MagicMock()
    fake_client.request = AsyncMock(return_value=(fake_resp, ""))

    with patch(
        "mdcx.tools.emby_actor_manager.manager.acquire_computed",
        return_value=_make_lease(fake_client),
    ):
        ok, msg = await delete_actor_image(actor_stub)

    assert not ok
    assert "500" in msg


async def test_delete_actor_image_network_failure(actor_stub):
    """request 返回 (None, err) 时判失败."""
    from mdcx.tools.emby_actor_manager import delete_actor_image

    fake_client = MagicMock()
    fake_client.request = AsyncMock(return_value=(None, "ConnRefused"))

    with patch(
        "mdcx.tools.emby_actor_manager.manager.acquire_computed",
        return_value=_make_lease(fake_client),
    ):
        ok, msg = await delete_actor_image(actor_stub)

    assert not ok


async def test_concurrent_fetch_all_actors_does_not_duplicate_network_calls(actor_stub, emby_configured):
    """asyncio.gather 并发抓详情时, fetch_actor_detail 不应对同一 name 调用多次.

    回归目标: 重构并发后保证 per-actor 只调用一次, 不重复请求。
    """

    from mdcx.tools.emby_actor_manager import fetch_all_actors

    actor_names = [f"演员{i}" for i in range(5)]
    call_log: list[str] = []

    async def fake_detail(name: str):
        call_log.append(name)
        return {"Overview": "test"}

    persons_resp = {
        "Items": [
            {"Name": n, "Id": f"id-{i}", "ServerId": "srv", "ImageTags": {}, "BackdropImageTags": []}
            for i, n in enumerate(actor_names)
        ]
    }

    fake_client = MagicMock()

    async def fake_get_json(url, **kwargs):
        if "Persons" in url:
            return persons_resp, ""
        return {"Items": []}, ""

    fake_client.get_json = fake_get_json

    with (
        patch(
            "mdcx.tools.emby_actor_manager.manager.acquire_computed",
            return_value=_make_lease(fake_client),
        ),
        patch("mdcx.tools.emby_actor_manager.fetch_actor_detail", side_effect=fake_detail),
    ):
        result = await fetch_all_actors(filter_actor_only=False, deduplicate=True, parent_ids=None)

    assert len(result) == 5
    # 每个 name 只被调一次 (N+1 重构后必须)
    assert sorted(call_log) == sorted(actor_names), f"实际调用 {len(call_log)} 次: {call_log}"


async def test_fetch_all_actors_reuses_list_fields_when_present(emby_configured):
    """P1-5 回归：/Persons 列表项已含 detail 字段时，不再逐人 fetch_actor_detail。"""
    from mdcx.tools.emby_actor_manager import fetch_all_actors

    call_log: list[str] = []

    persons_resp = {
        "Items": [
            {
                "Name": "演员1",
                "Id": "id-1",
                "ServerId": "srv",
                "ImageTags": {},
                "BackdropImageTags": [],
                "Overview": "已有简介",
                "Taglines": ["t"],
                "ProductionYear": 2020,
            }
        ]
    }

    fake_client = MagicMock()

    async def fake_get_json(url, **kwargs):
        if "Persons" in url:
            return persons_resp, ""
        return {"Items": []}, ""

    fake_client.get_json = fake_get_json

    async def fake_detail(name: str):
        call_log.append(name)
        return {"Overview": "detail"}

    with (
        patch("mdcx.tools.emby_actor_manager.manager.acquire_computed", return_value=_make_lease(fake_client)),
        patch("mdcx.tools.emby_actor_manager.fetch_actor_detail", side_effect=fake_detail),
    ):
        result = await fetch_all_actors(filter_actor_only=False, deduplicate=True, parent_ids=None)

    assert len(result) == 1
    assert result[0].existing_overview == "已有简介"
    assert call_log == []
