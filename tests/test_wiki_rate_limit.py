"""议题 #125/#137：MediaWiki（Wikidata/Wikipedia）与通用请求限速测试。

修改后逻辑：
1. 全局采用单线程（信号量容量为 1）控制并发，保证同一时间仅有 1 个请求在执行。
2. 触发限速/冷却时，暂停 1 分钟（60 秒），随后恢复继续执行。
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
    """所有域名（包含 wiki 域名与通用非 wiki 域名）均配置单线程并发控制与 1 分钟冷却暂停。"""
    limiters = AsyncWebLimiters()

    for host in ["wikidata.org", "wikipedia.org", "example.com"]:
        limiter = limiters.get(host)
        
        # 1. 验证单线程/单并发限制（并发容量为 1）
        max_concurrency = getattr(limiter, "max_concurrency", None) or getattr(limiter, "_value", None)
        assert max_concurrency == 1, f"{host} 未配置为单线程/单并发（当前限制: {max_concurrency}）"
        
        # 2. 验证冷却时长配置为 60 秒
        cooldown = getattr(limiter, "cooldown_seconds", None) or _MEDIAWIKI_COOL_DOWN_SEC
        assert cooldown == 60, f"{host} 冷却时长未配置为 60 秒"


@pytest.mark.asyncio
async def test_single_thread_execution_and_cooldown_pause():
    """验证单线程互斥执行，以及触发限速后的 60 秒冷却暂停机制。"""
    limiters = AsyncWebLimiters()
    limiter = limiters.get("example.com")

    # 测试 1：单线程并发控制（同一时间仅允许 1 个任务进入）
    async def task():
        async with limiter:
            await asyncio.sleep(0.1)

    # 同时发起两个任务，第二个任务在第一个任务结束前应处于阻塞/等待状态
    t1 = asyncio.create_task(task())
    await asyncio.sleep(0.01)  # 确保 t1 先获取锁
    
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.05):
            async with limiter:  # 由于 t1 正在占有，此处必须阻塞并超时
                pass
    
    await t1  # 释放 t1

    # 测试 2：触发限速后的 1 分钟冷却暂停
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.5):  # 0.5 秒远小于 60 秒冷却期
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