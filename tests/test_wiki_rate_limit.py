"""议题 #125：MediaWiki（Wikidata/Wikipedia）请求限速与合规 User-Agent 回归测试。

维基媒体按客户端类型限速（未识别 10 req/min、仅合规 User-Agent 200 req/min）。
此前 MDCx 对 wiki 域名沿用通用 8 req/s 限速并携带随机浏览器 UA，批量补全演员
信息时会触发 429。现对 wiki 域名单独降速，并改用可识别的 User-Agent。
"""

import pytest

from mdcx.config.manager import manager
from mdcx.models.emby import EMbyActressInfo
from mdcx.tools import wiki
from mdcx.web_async import _MEDIAWIKI_HOSTS, _MEDIAWIKI_RATE, AsyncWebLimiters


def test_mediawiki_hosts_use_slow_limiter():
    """wiki 域名须使用独立的慢速限速器，其它域名保持通用 8 req/s。"""
    limiters = AsyncWebLimiters()
    for host in _MEDIAWIKI_HOSTS:
        limiter = limiters.get(host)
        assert limiter.max_rate == _MEDIAWIKI_RATE, f"{host} 未使用 wiki 慢速限速"
        assert limiter.time_period == 1
    assert limiters.get("example.com").max_rate == 8


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
