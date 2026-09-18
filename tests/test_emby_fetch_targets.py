"""议题 #127 回归: 演员管理器「获取数据」按模式筛子集, 不再逐人遍历全库。

验证两层:
1. PreparePreviewThread.select_targets 纯函数——各模式下子集成员正确
   (「缺失」类只挑缺失字段者, 占位简介按缺简介处理, force 类取全量)。
2. _try_fetch_info 不再对已有简介的演员发 fetch_actor_detail 网络核对,
   判定全部基于列表阶段带回的 have/existing 数据。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.asyncio


def _make_actor(name: str, *, image: bool, overview: str = ""):
    from mdcx.tools.emby_actor_manager import ActorInfo

    return ActorInfo(
        name=name,
        actor_id=f"id-{name}",
        server_id="srv",
        has_image=image,
        has_overview=bool(overview),
        existing_overview=overview,
    )


@pytest.fixture
def actors():
    return [
        _make_actor("完整", image=True, overview="正常简介"),
        _make_actor("缺头像", image=False, overview="正常简介"),
        _make_actor("缺简介", image=True, overview=""),
        _make_actor("都缺", image=False, overview=""),
        _make_actor("占位简介", image=True, overview="无维基百科信息"),
        _make_actor("占位简介缺图", image=False, overview="无维基百科信息"),
    ]


def _names(result):
    return sorted(a.name for a in result)


def test_missing_image_only_actors_without_image(actors):
    from mdcx.tools.emby_actor_manager_ui import PreparePreviewThread

    got = PreparePreviewThread.select_targets(actors, "missing_image")
    assert _names(got) == ["占位简介缺图", "缺头像", "都缺"]


def test_missing_info_includes_placeholder_overview(actors):
    """占位简介（无维基百科信息）按缺简介处理; 正常简介永不重查。"""
    from mdcx.tools.emby_actor_manager_ui import PreparePreviewThread

    got = PreparePreviewThread.select_targets(actors, "missing_info")
    assert _names(got) == ["占位简介", "占位简介缺图", "缺简介", "都缺"]


def test_missing_all_is_union_not_intersection(actors):
    """「仅全部缺失头像+简介」的语义 = 缺任一字段者都处理 (并集), 完整者除外。"""
    from mdcx.tools.emby_actor_manager_ui import PreparePreviewThread

    got = PreparePreviewThread.select_targets(actors, "missing_all")
    assert _names(got) == ["占位简介", "占位简介缺图", "缺头像", "缺简介", "都缺"]


def test_force_modes_take_everyone(actors):
    from mdcx.tools.emby_actor_manager_ui import PreparePreviewThread

    for mode in ("force_all", "force_image", "force_info"):
        got = PreparePreviewThread.select_targets(actors, mode)
        assert _names(got) == _names(actors), mode


def test_select_targets_returns_new_list_for_force(actors):
    """force 模式返回副本, 调用方增删不影响原表。"""
    from mdcx.tools.emby_actor_manager_ui import PreparePreviewThread

    got = PreparePreviewThread.select_targets(actors, "force_all")
    assert got is not actors


async def _call_try_fetch_info(actor, *, force, search_mock):
    from mdcx.tools.emby_actor_manager_ui import PreparePreviewThread

    fake_self = SimpleNamespace(_INFO_PLACEHOLDER=PreparePreviewThread._INFO_PLACEHOLDER)
    with patch("mdcx.tools.emby_actor_manager_ui.search_actor_info", search_mock):
        await PreparePreviewThread._try_fetch_info(fake_self, actor, force)


async def test_try_fetch_info_skips_actor_with_normal_overview():
    """已有正常简介: 直接跳过, 不搜源、不核对服务器。"""
    search_mock = AsyncMock(return_value=False)
    actor = _make_actor("完整", image=True, overview="正常简介")
    await _call_try_fetch_info(actor, force=False, search_mock=search_mock)
    assert search_mock.await_count == 0


def test_try_fetch_info_no_longer_requeries_server():
    """回归 #127: _try_fetch_info 源码中不得再出现 fetch_actor_detail 逐人网络核对,
    且 ui 模块整体不再导入该符号 (判定已前移到 select_targets)。"""
    import ast
    import inspect

    from mdcx.tools.emby_actor_manager_ui import PreparePreviewThread

    src = inspect.getsource(PreparePreviewThread._try_fetch_info)
    body = ast.parse(src.replace("    async def", "async def", 1))
    called = {n.func.id for n in ast.walk(body) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "fetch_actor_detail" not in called, "_try_fetch_info 不得再核对服务器"

    import mdcx.tools.emby_actor_manager_ui as ui_mod

    assert not hasattr(ui_mod, "fetch_actor_detail"), "ui 模块整体不应再导入 fetch_actor_detail"


async def test_try_fetch_info_requeries_placeholder_overview():
    """占位简介: 视为缺失继续搜源 (重补全是既有有意设计)。"""
    search_mock = AsyncMock(return_value=True)
    actor = _make_actor("占位简介", image=True, overview="无维基百科信息")
    await _call_try_fetch_info(actor, force=False, search_mock=search_mock)
    assert search_mock.await_count == 1
    assert actor.need_update_info


async def test_try_fetch_info_force_ignores_existing(actors):
    """force 模式无视已有简介照常重查 (用户显式重新获取)。"""
    search_mock = AsyncMock(return_value=False)
    complete = actors[0]
    await _call_try_fetch_info(complete, force=True, search_mock=search_mock)
    assert search_mock.await_count == 1
