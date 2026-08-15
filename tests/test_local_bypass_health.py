import time

import pytest

from mdcx.web_async import AsyncWebClient


def _client() -> AsyncWebClient:
    client = AsyncWebClient(timeout=1)
    client._local_bypass_enabled = True
    client._local_bypass_dead_threshold = 3
    return client


def test_initial_health_is_idle():
    client = _client()
    assert client._local_bypass_health == "idle"
    assert client._local_bypass_is_dead() is False


def test_success_keeps_ready():
    client = _client()
    client._local_bypass_health = "ready"
    client._record_local_bypass_success()
    assert client._local_bypass_health == "ready"
    assert client._local_bypass_consecutive_failures == 0


def test_consecutive_failures_marks_dead_and_disables_bypass():
    client = _client()
    client._cf_bypass_enabled = True
    client._record_local_bypass_failure()
    client._record_local_bypass_failure()
    assert client._local_bypass_health != "dead"
    assert client._cf_bypass_enabled is True
    client._record_local_bypass_failure()
    assert client._local_bypass_health == "dead"
    assert client._local_bypass_is_dead() is True
    # 标记 dead 时解除启用，避免继续转发到假死服务
    assert client._cf_bypass_enabled is False


def test_success_after_dead_recovers():
    client = _client()
    for _ in range(3):
        client._record_local_bypass_failure()
    assert client._local_bypass_health == "dead"
    client._record_local_bypass_success()
    assert client._local_bypass_health == "ready"
    assert client._local_bypass_consecutive_failures == 0


def test_dead_cooldown_allows_retry():
    client = _client()
    for _ in range(3):
        client._record_local_bypass_failure()
    assert client._local_bypass_is_dead() is True
    # 冷却期结束后允许重试
    client._local_bypass_dead_at = time.monotonic() - client._local_bypass_retry_dead_after_s - 1
    assert client._local_bypass_is_dead() is False
    assert client._local_bypass_health == "idle"


def test_failure_ignored_when_local_bypass_disabled():
    client = AsyncWebClient(timeout=1)
    client._local_bypass_enabled = False
    client._record_local_bypass_failure()
    client._record_local_bypass_failure()
    client._record_local_bypass_failure()
    assert client._local_bypass_health != "dead"


@pytest.mark.asyncio
async def test_ensure_local_bypass_skips_when_dead():
    client = _client()
    for _ in range(3):
        client._record_local_bypass_failure()
    assert client._local_bypass_health == "dead"
    # dead 状态下不应启动/启用服务
    started = await client._ensure_local_bypass()
    assert started is False
    assert client._cf_bypass_enabled is False


@pytest.mark.asyncio
async def test_ensure_local_bypass_starts_when_enabled():
    client = AsyncWebClient(timeout=1, cf_bypass_auto=True)
    # 直接跳过真实启动：模拟 cf_bypass_enabled 已开启
    client._cf_bypass_enabled = True
    started = await client._ensure_local_bypass()
    assert started is True
