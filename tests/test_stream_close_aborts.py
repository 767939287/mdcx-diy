"""流式响应关闭回归测试（C3）：提前放弃的流必须立即中止。

实测背景（2026-08-29，本地慢速服务器 4MB/4s）：
- aclose(): 阻塞 3.5s，服务端发满 4MB —— 提前放弃的探测会退化成整图下载
- close():   0.00s 返回，服务端只发出已消费部分，且同 session 后续请求正常

这两个性质是 _close_response 改用 close() 的依据，行为测试锁定防回退。
"""

import asyncio
import socket
import threading
import time

import pytest

pytestmark = pytest.mark.asyncio

_TOTAL = 4 * 1024 * 1024
_CHUNK = 256 * 1024


class _SlowServer:
    """慢速 HTTP 服务器：4MB 响应体，每块间隔 0.25s（发完约 4 秒）。"""

    def __init__(self):
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(8)
        self.port = self._srv.getsockname()[1]
        self.sent_bytes = 0
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def _accept_loop(self):
        while True:
            try:
                conn, _ = self._srv.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn: socket.socket):
        with conn:
            try:
                conn.recv(65536)
            except OSError:
                return
            try:
                conn.sendall(
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: application/octet-stream\r\n"
                    + f"Content-Length: {_TOTAL}\r\n".encode()
                    + b"Connection: close\r\n\r\n"
                )
            except OSError:
                return
            sent = 0
            while sent < _TOTAL:
                try:
                    conn.sendall(b"x" * _CHUNK)
                except OSError:
                    break  # 客户端断开，立即停止发送
                sent += _CHUNK
                with self._lock:
                    self.sent_bytes = max(self.sent_bytes, sent)
                time.sleep(0.25)

    def reset(self):
        with self._lock:
            self.sent_bytes = 0


@pytest.fixture()
def slow_server():
    return _SlowServer()


async def test_abandoned_stream_is_not_fully_downloaded(slow_server):
    """提前放弃的流不得把响应体拉满（图片探测只读头部场景）。"""
    import contextlib

    from curl_cffi import AsyncSession

    url = f"http://127.0.0.1:{slow_server.port}/big.bin"
    s = AsyncSession()
    try:
        r = await s.get(url, stream=True)
        got = 0
        async for chunk in r.aiter_content():
            got += len(chunk)
            if got >= 512 * 1024:
                break
        close_started = time.monotonic()
        # 被测行为：同步 close 立即中止传输
        r.close()
        close_elapsed = time.monotonic() - close_started
    finally:
        # curl_cffi 0.16：中止流后 session.close 会抛库内 TypeError（curl 句柄已置 None），
        # 与真实链路一致地容忍（web_async._close_sessions 有 suppress 包裹）
        with contextlib.suppress(TypeError):
            await s.close()

    await asyncio.sleep(0.5)  # 留出服务端停止发送的时间窗口
    ratio = slow_server.sent_bytes / _TOTAL

    assert close_elapsed < 1.0, f"close() 阻塞 {close_elapsed:.2f}s，未立即中止传输"
    assert ratio < 0.9, f"提前放弃的流被拉满（服务端已发 {ratio:.0%}）——aclose 式等待传输完成的行为回归了"


async def test_session_reusable_after_aborted_stream(slow_server):
    """close() 中止流后，同一 session 的后续请求必须正常（连接池复用场景）。"""
    import contextlib

    from curl_cffi import AsyncSession

    url = f"http://127.0.0.1:{slow_server.port}/big.bin"
    s = AsyncSession()
    try:
        r1 = await s.get(url, stream=True)
        got = 0
        async for chunk in r1.aiter_content():
            got += len(chunk)
            if got >= 256 * 1024:
                break
        r1.close()

        # 同 session 复用：非流式请求应正常完成
        r2 = await s.get(url, stream=False)
        assert len(r2.content) == _TOTAL, "中止流后 session 复用失败"
    finally:
        with contextlib.suppress(TypeError):
            await s.close()


async def test_close_response_via_client(slow_server):
    """_close_response 走 close() 路径且不抛异常。"""
    from mdcx.web_async import AsyncWebClient

    client = AsyncWebClient(timeout=10)
    try:
        url = f"http://127.0.0.1:{slow_server.port}/big.bin"
        resp, err = await client.request("GET", url, stream=True, retry_count=1)
        assert resp is not None, f"请求失败: {err}"
        got = 0
        async for chunk in resp.aiter_content():
            got += len(chunk)
            if got >= 256 * 1024:
                break
        # 被测行为：客户端统一关闭入口
        started = time.monotonic()
        await client._close_response(resp)
        elapsed = time.monotonic() - started
        assert elapsed < 1.0, f"_close_response 阻塞 {elapsed:.2f}s，未立即中止"
    finally:
        await client.close()
