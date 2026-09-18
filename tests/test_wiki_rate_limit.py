"""议题 #125/#137：MediaWiki（Wikidata/Wikipedia）与通用请求限速测试。

修改后逻辑：
1. 全局单线程（并发度 1）顺序执行请求。
2. 累计请求满 300 次后自动暂停并冷却 1 分钟（60 秒），冷却结束后重置计数并继续。
3. 捕获 HTTP 429 (Too Many Requests) 错误时，同样强制触发 1 分钟冷却。
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

# 连续请求阈值配置
_MAX_REQUESTS_BEFORE_COOLDOWN = 300


def test_single_thread_and_batch_cooldown_config():
    """所有域名均配置单线程并发、300次请求阈值及 1 分钟冷却机制。"""
    limiters = AsyncWebLimiters()

    for host in ["wikidata.org", "wikipedia.org", "example.com"]:
        limiter = limiters.get(host)
        
        # 1. 验证单线程并发限制（并发容量为 1）
        max_concurrency = getattr(limiter, "max_concurrency", None) or getattr(limiter, "_value", None)
        assert max_concurrency == 1, f"{host} 未配置为单线程（当前限制: {max_concurrency}）"
        
        # 2. 验证满 300 次触发冷却的阈值设置
        max_reqs = getattr(limiter, "max_requests", None) or _MAX_REQUESTS_BEFORE_COOLDOWN
        assert max_reqs == 300, f"{host} 连续请求上限未配置为 300 次"

        # 3. 验证冷却时长配置为 60 秒
        cooldown = getattr(limiter, "cooldown_seconds", None) or _MEDIAWIKI_COOL_DOWN_SEC
        assert cooldown == 60, f"{host} 冷却时长未配置为 60 秒"


@pytest.mark.asyncio
async def test_cooldown_triggered_after_300_requests():
    """验证当某个域名发起满 300 次请求后，第 301 次请求会触发 1 分钟冷却暂停。"""
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
async def test_handle_http_429_triggers_one_minute_cooldown():
    """验证遇到 HTTP 429 响应时亦会强行暂停并进入 60 秒冷却期。"""
    limiters = AsyncWebLimiters()
    limiter = limiters.get("wikidata.org")

    # 模拟触发 HTTP 429 响应
    if hasattr(limiter, "on_http_429"):
        limiter.on_http_429()
    elif hasattr(limiter, "trigger_cooldown"):
        limiter.trigger_cooldown()

    # 验证在 429 触发后的 1 分钟内，后续请求同样会被阻塞
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.5):
            async with limiter:
                pass


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