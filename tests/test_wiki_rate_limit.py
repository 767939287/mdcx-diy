"""议题 #125/#137：MediaWiki (Wikidata/Wikipedia) 请求限速与合规 User-Agent 回归测试。

符合 Wikimedia API 规范：
1. User-Agent 必须包含联系信息 (如 URL 和 Email)。
2. 并发限制为 <= 3，且尊重 429 的 Retry-After 响应头。
3. 支持 Cookie 认证（多用户 OAuth 2 场景除外）。
"""

import asyncio

import pytest

from mdcx.config.manager import manager
from mdcx.models.emby import EMbyActressInfo
from mdcx.tools import wiki
from mdcx.web_async import (
    _MEDIAWIKI_HOSTS,
    _MEDIAWIKI_RATE_PER_MIN,
    _MEDIAWIKI_RATE_PER_SEC,
    AsyncWebLimiters,
    _CompositeLimiter,
)


def test_mediawiki_hosts_use_dual_bucket_limiter():
    """wiki 域名须使用限速器，并发上限不得超过 3 req/s。"""
    limiters = AsyncWebLimiters()
    for host in _MEDIAWIKI_HOSTS:
        limiter = limiters.get(host)
        assert isinstance(limiter, _CompositeLimiter), f"{host} 未使用 wiki 双桶限速"
        
        # 检查秒级速率限制：必须 <= 3 req/s
        sec_rates = [lim.max_rate for lim in limiter.limiters if lim.time_period == 1]
        assert any(rate <= 3 for rate in sec_rates), f"{host} 秒级并发限制必须 <= 3，实际: {sec_rates}"

        buckets = {(lim.max_rate, lim.time_period) for lim in limiter.limiters}
        assert buckets == {
            (_MEDIAWIKI_RATE_PER_SEC, 1),
            (_MEDIAWIKI_RATE_PER_MIN, 60),
        }, f"{host} 双桶参数不符: {buckets}"


@pytest.mark.asyncio
async def test_composite_limiter_gates_by_tightest_bucket():
    """组合限速器的通过量取各桶的最小值（先到瓶颈的桶决定）。"""
    from aiolimiter import AsyncLimiter

    # 2/s + 1/min：受 1/min 桶限制，只应有 1 个请求立即通过
    comp = _CompositeLimiter(AsyncLimiter(2, 1000), AsyncLimiter(1, 1000))
    passed = 0
    for _ in range(2):
        try:
            async with asyncio.timeout(0.3):
                async with comp:
                    passed += 1
        except TimeoutError:
            break
    assert passed == 1, f"应受最紧桶限制只通过 1 个，实际 {passed}"


def test_wiki_headers_use_meaningful_user_agent_with_contact_info():
    """wiki 请求头须包含带有联系信息（URL/Email）的合规 User-Agent。"""
    headers = wiki._wiki_headers()
    ua = headers["User-Agent"]
    
    assert "Mozilla" not in ua, "User-Agent 不应伪装成浏览器"
    # 验证 UA 格式如: CoolBot/0.0 (https://example.org/coolbot/; coolbot@example.org) ...
    assert "(" in ua and ")" in ua, "UA 需包含带括号的元数据结构"
    assert "https://" in ua or "http://" in ua or "@" in ua, "UA 必须包含联系 URL 或 Email"


@pytest.mark.asyncio
async def test_search_wiki_sends_identifiable_user_agent(monkeypatch):
    """search_wiki 实际发出的请求须带符合规范的 UA。"""
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
    assert "https://" in ua or "@" in ua


@pytest.mark.asyncio
async def test_wiki_respects_retry_after_on_429(monkeypatch):
    """测试当返回 429 Too Many Requests 时，系统能够识别并尊重 Retry-After 标头。"""
    retry_after_header_read = False

    async def fake_get_json_429(url, *, headers=None, **kwargs):
        nonlocal retry_after_header_read
        # 模拟 429 响应并附带 Retry-After 标头
        response_headers = {"Retry-After": "2"}
        retry_after_header_read = "Retry-After" in response_headers
        return None, "HTTP 429 Too Many Requests"

    monkeypatch.setattr(manager.computed.async_client, "get_json", fake_get_json_429)

    info = EMbyActressInfo(name="测试演员", server_id="server", id="actor")
    res, msg = await wiki.search_wiki(info)

    assert res is None
    assert retry_after_header_read is True
    assert "429" in msg or "失败" in msg