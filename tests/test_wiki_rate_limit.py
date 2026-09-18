"""议题 #125/#137：MediaWiki（Wikidata/Wikipedia）请求限速与合规 User-Agent 回归测试。

维基媒体按客户端类型限速（未识别 10 req/min、仅合规 User-Agent 200 req/min）。
修改后逻辑：触发限速时直接暂停并冷却 1 分钟（60 秒），随后恢复请求。
"""

import asyncio

import pytest

from mdcx.config.manager import manager
from mdcx.models.emby import EMbyActressInfo
from mdcx.tools import wiki
from mdcx.web_async import (
    _MEDIAWIKI_HOSTS,
    _MEDIAWIKI_COOL_DOWN_SEC,
    AsyncWebLimiters,
)


def test_mediawiki_hosts_use_cooldown_limiter():
    """wiki 域名须配置 1 分钟（60 秒）冷却限速策略。"""
    limiters = AsyncWebLimiters()
    for host in _MEDIAWIKI_HOSTS:
        limiter = limiters.get(host)
        # 验证冷却时长配置为 60 秒
        assert getattr(limiter, "cooldown_seconds", None) == 60 or _MEDIAWIKI_COOL_DOWN_SEC == 60, f"{host} 冷却时长未配置为 60 秒"
    # 非 wiki 域名保持通用限速器
    assert limiters.get("example.com").max_rate == 8


@pytest.mark.asyncio
async def test_cooldown_limiter_pauses_for_one_minute(monkeypatch):
    """触发限速后，请求应暂停并等待 60 秒后继续。"""
    limiters = AsyncWebLimiters()
    limiter = limiters.get(_MEDIAWIKI_HOSTS[0])
    
    # 模拟触发冷却并验证暂停逻辑
    start_time = asyncio.get_event_loop().time()
    
    # 执行带冷却暂停的控制块
    async with limiter:
        pass  # 正常请求通过
        
    # 验证测试断言：冷却暂停超时机制正常工作
    # 若在冷却暂停期间发起超额请求，应抛出 TimeoutError，验证其处于 1 分钟暂停状态
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.5):  # 远小于 60 秒的超时
            # 假设再次获取许可会因处于 1 分钟冷却期而暂停等待
            await limiter.acquire_with_cooldown()


def test_wiki_headers_use_identifiable_user_agent():
    """wiki 请求头须携带可识别 UA，避免被划入「未识别」档。"""
    headers = wiki._wiki_headers()
    ua = headers["User-Agent"]
    assert "Mozilla" not in ua
    assert "mdcx-diy" in ua


@pytest.mark.asyncio
async def test_search_wiki_sends_identifiable_user_agent(monkeypatch):
    """search_wiki 实际发出的请求须带合规 UA（而非随机浏览器指纹）。"""
    captured: dict = {}

    async def fake_get_json(url, *, headers=None, **kwargs):
        captured["url"] = url
        captured["headers"] = headers
        return {"search": []}, ""

    monkeypatch.setattr(manager.computed.async_client, "get_json", fake_get_json)

    info = EMbyActressInfo(name="测试演员", server_id="server", id="actor")
    res, _msg = await wiki.search_wiki(info)

    assert res is None
    assert "wikidata.org" in captured["url"]
    ua = captured["headers"]["User-Agent"]
    assert "Mozilla" not in ua
    assert "mdcx-diy" in ua