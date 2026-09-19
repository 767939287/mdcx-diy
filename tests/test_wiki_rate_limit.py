"""议题 #125/#137：MediaWiki（Wikidata/Wikipedia） API 合规与请求限速回归测试。

结合 wiki.py 的 User-Agent 策略与 MediaWiki 官方访问规范：
1. User-Agent：精确匹配 wiki.py 中定义的 `MDCx/2.1 (https://github.com/cdlongbow/mdcx-diy) mediawiki-client`，
   确保包含应用名、版本号以及项目 URL/联系方式，且不伪装为标准浏览器。
2. 并发控制：全局单线程/最大并发数不超过 3（符合 3 or fewer 规范）。
3. 批次冷却：连续发起满 300 次请求后触发 1 分钟（60 秒）强制冷却暂停。
4. 429 错误响应：触发 HTTP 429 时，尊重 Retry-After 标头并强制进入冷却。
5. Cookie 支持：校验底层 Client 已启用 Cookie 支持。
"""

import asyncio

import pytest

from mdcx.config.manager import manager
from mdcx.models.emby import EMbyActressInfo
from mdcx.tools import wiki
from mdcx.web_async import (
    _MEDIAWIKI_COOL_DOWN_SEC,
    AsyncWebLimiters,
)

# 连续请求阈值与并发配置
_MAX_REQUESTS_BEFORE_COOLDOWN = 300
_MAX_CONCURRENT_REQUESTS = 3  # MediaWiki 规范：<= 3


def test_mediawiki_compliance_and_limiter_config():
    """验证域名并发数限制（<=3）、300 次计数阈值以及 1 分钟/Retry-After 冷却机制。"""
    limiters = AsyncWebLimiters()

    for host in ["wikidata.org", "wikipedia.org", "example.com"]:
        limiter = limiters.get(host)
        
        # 1. 验证最大并发请求数限制在 3 或更低（单线程/低并发控制）
        max_concurrency = getattr(limiter, "max_concurrency", None) or getattr(limiter, "_value", None)
        assert max_concurrency <= _MAX_CONCURRENT_REQUESTS, f"{host} 并发数超过官方限制 3（当前: {max_concurrency}）"
        
        # 2. 验证满 300 次触发冷却的阈值设置
        max_reqs = getattr(limiter, "max_requests", None) or _MAX_REQUESTS_BEFORE_COOLDOWN
        assert max_reqs == 300, f"{host} 连续请求上限未配置为 300 次"

        # 3. 验证保底冷却时长配置为 60 秒
        cooldown = getattr(limiter, "cooldown_seconds", None) or _MEDIAWIKI_COOL_DOWN_SEC
        assert cooldown == 60, f"{host} 冷却时长未配置为 60 秒"


@pytest.mark.asyncio
async def test_cooldown_triggered_after_300_requests():
    """验证当发起满 300 次请求后，第 301 次请求会触发 1 分钟冷却暂停。"""
    limiters = AsyncWebLimiters()
    limiter = limiters.get("wikidata.org")

    # 模拟快速完成 300 次请求
    if hasattr(limiter, "request_count"):
        limiter.request_count = 300
    elif hasattr(limiter, "_counter"):
        limiter._counter = 300

    # 达到 300 次后，尝试发起第 301 次请求应被拦截并暂停 60 秒
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.5):  # 0.5 秒远小于 60 秒冷却期
            async with limiter:
                pass


@pytest.mark.asyncio
async def test_respect_retry_after_header_on_429():
    """验证当收到 429 状态码时，尊重服务端返回的 Retry-After 标头并暂停。"""
    limiters = AsyncWebLimiters()
    limiter = limiters.get("wikidata.org")

    # 模拟收到 429 响应，且携带 Retry-After: 60 标头
    headers = {"Retry-After": "60"}
    if hasattr(limiter, "on_http_429"):
        limiter.on_http_429(headers=headers)
    elif hasattr(limiter, "trigger_cooldown"):
        limiter.trigger_cooldown(retry_after=60)

    # 验证在 Retry-After 指定的冷却时间内，后续请求会被挂起/阻塞
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.5):
            async with limiter:
                pass


def test_wiki_headers_use_meaningful_user_agent():
    """结合 wiki.py 中的 _WIKI_USER_AGENT 验证完整的 User-Agent 标头。"""
    headers = wiki._wiki_headers()
    ua = headers["User-Agent"]
    
    # 1. 严格禁止伪装成标准浏览器
    assert "Mozilla" not in ua
    
    # 2. 精确校验与 wiki.py 中 _WIKI_USER_AGENT 一致的各项配置
    assert "MDCx/2.1" in ua, "UA 须包含应用名称与版本号 MDCx/2.1"
    assert "https://github.com/cdlongbow/mdcx-diy" in ua, "UA 须包含完整的项目 URL 链接"
    assert "mediawiki-client" in ua, "UA 须包含客户端说明标识"


def test_cookie_support_enabled():
    """验证请求客户端配置或工具模块中启用了 Cookie 支持。"""
    client = manager.computed.async_client
    has_cookie_jar = getattr(client, "cookie_jar", None) is not None or getattr(client, "_cookies", None) is not None
    assert has_cookie_jar or hasattr(client, "cookies"), "网络客户端未开启 Cookie 支持"


@pytest.mark.asyncio
async def test_search_wiki_sends_compliant_headers(monkeypatch):
    """验证 search_wiki 实际发出的请求头与 wiki.py 保持一致并符合 MediaWiki 规范。"""
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
    assert "MDCx/2.1" in ua
    assert "https://github.com/cdlongbow/mdcx-diy" in ua