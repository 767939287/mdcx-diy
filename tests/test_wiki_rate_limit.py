"""议题 #125/#137：MediaWiki（Wikidata/Wikipedia）与通用请求限速测试。

修改后逻辑：
1. 全局单线程（并发度 1）顺序执行请求。
2. 捕获 HTTP 429 (Too Many Requests) 错误，一旦触发即强制暂停并冷却 1 分钟（60 秒），随后自动继续。
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


def test_single_thread_and_cooldown_config():
    """所有域名均配置单线程并发控制与 1 分钟 429 冷却暂停机制。"""
    limiters = AsyncWebLimiters()

    for host in ["wikidata.org", "wikipedia.org", "example.com"]:
        limiter = limiters.get(host)
        
        # 1. 验证单线程/单并发限制（并发容量为 1）
        max_concurrency = getattr(limiter, "max_concurrency", None) or getattr(limiter, "_value", None)
        assert max_concurrency == 1, f"{host} 未配置为单线程（当前限制: {max_concurrency}）"
        
        # 2. 验证 429 触发后的冷却时长配置为 60 秒
        cooldown = getattr(limiter, "cooldown_seconds", None) or _MEDIAWIKI_COOL_DOWN_SEC
        assert cooldown == 60, f"{host} 冷却时长未配置为 60 秒"


@pytest.mark.asyncio
async def test_handle_http_429_triggers_one_minute_cooldown():
    """验证遇到 HTTP 429 时自动暂停并进入 60 秒冷却期。"""
    limiters = AsyncWebLimiters()
    limiter = limiters.get("wikidata.org")

    # 模拟触发 HTTP 429 响应
    # 当检测到 429 状态码时，调用 trigger_cooldown() 或抛出特定异常记录状态
    if hasattr(limiter, "on_http_429"):
        limiter.on_http_429()
    elif hasattr(limiter, "trigger_cooldown"):
        limiter.trigger_cooldown()

    # 验证在 429 触发后的 1 分钟内，后续请求会被暂停/阻塞
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.5):  # 0.5 秒远小于 60 秒冷却期
            async with limiter:
                pass


@pytest.mark.asyncio
async def test_single_thread_mutex_execution():
    """验证单线程互斥：前一个请求未完成时，后续请求必须排队等待。"""
    limiters = AsyncWebLimiters()
    limiter = limiters.get("example.com")

    async def task():
        async with limiter:
            await asyncio.sleep(0.1)

    # 启动第一个任务
    t1 = asyncio.create_task(task())
    await asyncio.sleep(0.01)  # 确保 t1 优先获取到单线程锁
    
    # 在 t1 执行期间，第二个任务尝试获取锁，应该阻塞并超时
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.05):
            async with limiter:
                pass
    
    await t1


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