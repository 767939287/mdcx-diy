"""crawl CLI 客户端构造测试：确保代理白名单(proxy_sites)正确传递。

回归保护：crawl.py 曾漏传 proxy_sites，导致 AsyncWebClient 的 _is_proxy_host
对任何 host 都返回 False，--proxy 参数实际不生效（代理形同虚设）。
"""

from concurrent.futures import Future
from unittest.mock import MagicMock, patch

from mdcx.cmd import crawl as crawl_module
from mdcx.config.models import Website
from mdcx.models.types import CrawlerInput


class _FakeExecutor:
    """模拟全局 executor：不真正执行任务，直接返回带结果的 future."""

    def __init__(self):
        self.futures = []

    def submit(self, fn):
        future = Future()
        # fn 是 task(c) 协程（未 await 也可，我们不真正执行）
        res = MagicMock()
        res.debug_info.logs = []
        res.debug_info.error = None
        res.debug_info.execution_time = 0.0
        res.data = None
        future.set_result(res)
        self.futures.append(future)
        return future

    def wait_all(self):
        return None

    def run(self, coro):
        return None


@patch.object(crawl_module, "executor", new=_FakeExecutor())
@patch.object(crawl_module, "AsyncWebClient")
def test_crawl_passes_proxy_sites(mock_client):
    """crawl CLI 构造 AsyncWebClient 时必须传递 proxy_sites 白名单."""
    input_data = CrawlerInput.empty()
    crawl_module._crawl(
        sites=[Website.JAVBUS],
        input=input_data,
        output=None,
        proxy="http://127.0.0.1:7890",
        timeout=5,
        retry=1,
    )

    call_kwargs = mock_client.call_args.kwargs
    assert "proxy_sites" in call_kwargs, "AsyncWebClient 未收到 proxy_sites 参数"
    assert isinstance(call_kwargs["proxy_sites"], list)
    assert call_kwargs["proxy"] == "http://127.0.0.1:7890"
