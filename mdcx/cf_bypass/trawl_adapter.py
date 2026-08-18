import asyncio
import atexit
import json
import logging
import os
import socket
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import httpx

from mdcx.consts import IS_PYINSTALLER

if TYPE_CHECKING:
    import uvicorn

try:
    import uvicorn  # type: ignore[import-untyped]
except ImportError:  # 仅在冻结模式(in-process)下需要
    uvicorn = None  # type: ignore[assignment, no-redef]

logger = logging.getLogger(__name__)
ADAPTER_HOST = "127.0.0.1"
SERVER_START_TIMEOUT = 60
HEALTH_CHECK_INTERVAL = 0.5
TRAWL_REQUEST_TIMEOUT = 65.0
DEFAULT_MAX_TIMEOUT_MS = 60_000


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((ADAPTER_HOST, 0))
        return s.getsockname()[1]


async def _send_text(send, status: int, body: bytes, headers: list[tuple[bytes, bytes]] | None = None) -> None:
    response_headers = list(headers or [])
    response_headers.extend(
        [
            (b"content-type", b"text/html; charset=utf-8"),
            (b"content-length", str(len(body)).encode()),
        ]
    )
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": response_headers,
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _send_json(send, status: int, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _call_trawl(
    client: httpx.AsyncClient, trawl_url: str, payload: dict, timeout: float = TRAWL_REQUEST_TIMEOUT
) -> dict:
    """调用 TRAWL 的 /scrape 原生 API（比 /v1 多返回 statusCode/responseHeaders/body）。"""
    try:
        resp = await client.post(f"{trawl_url}/scrape", json=payload, timeout=timeout)
    except httpx.HTTPError as exc:
        return {"error": f"TRAWL 连接失败: {exc}"}
    if resp.status_code == 503:
        return {"error": "TRAWL 浏览器池初始化中，请稍后重试"}
    if resp.status_code == 429:
        return {"error": "TRAWL 浏览器池已饱和，请稍后重试"}
    if resp.status_code != 200:
        return {"error": f"TRAWL 返回 HTTP {resp.status_code}"}
    try:
        data = resp.json()
    except Exception as exc:
        return {"error": f"TRAWL 响应解析失败: {exc}"}
    if isinstance(data, dict) and data.get("error"):
        return {"error": f"TRAWL 错误: {data['error']}"}
    return data


def _build_target_url(hostname: str, path: str, query_string: str) -> str:
    """按 cf_bypasser mirror 协议重建目标 URL：https://{x-hostname}{path}?{query}。"""
    if not hostname.startswith(("http://", "https://")):
        hostname = f"https://{hostname}"
    parsed = urlparse(hostname)
    base = f"{parsed.scheme}://{parsed.netloc}"
    safe_path = path or "/"
    url = base + safe_path
    if query_string:
        url += f"?{query_string}"
    return url


def _cookie_to_set_cookie(cookie: dict) -> str:
    name = cookie.get("name", "")
    value = cookie.get("value", "")
    parts = [f"{name}={value}"]
    if cookie.get("path"):
        parts.append(f"Path={cookie['path']}")
    if cookie.get("domain"):
        parts.append(f"Domain={cookie['domain']}")
    if cookie.get("secure"):
        parts.append("Secure")
    if cookie.get("httpOnly"):
        parts.append("HttpOnly")
    if cookie.get("sameSite"):
        parts.append(f"SameSite={cookie['sameSite']}")
    return "; ".join(parts)


def create_trawl_adapter_app(trawl_url: str):
    """创建把 cf_bypasser 协议翻译成 TRAWL /scrape 的 ASGI 适配层。"""

    async def app(scope, receive, send):
        if scope["type"] != "http":
            await send({"type": "http.response.start", "status": 404, "headers": []})
            await send({"type": "http.response.body", "body": b""})
            return

        path = scope.get("path", "") or "/"
        query_string = scope.get("query_string", b"").decode("latin-1")
        qs = parse_qs(query_string)
        headers = {k.lower(): v for k, v in scope.get("headers", [])}

        # 只接受本地 127.0.0.1 的连接（mdcx 客户端总是本地转发）
        client_host = ""
        if "client" in scope:
            client_host = (scope["client"] or ("", 0))[0] or ""
        if client_host and client_host not in ("127.0.0.1", "::1"):
            await _send_json(send, 403, {"error": "forbidden"})
            return

        try:
            client = httpx.AsyncClient(timeout=TRAWL_REQUEST_TIMEOUT)
        except Exception as exc:
            await _send_json(send, 500, {"error": f"创建 HTTP 客户端失败: {exc}"})
            return

        try:
            if path == "/cookies":
                await _handle_cookies(client, trawl_url, qs, send)
            elif path == "/html":
                await _handle_html(client, trawl_url, qs, headers, send)
            else:
                await _handle_mirror(client, trawl_url, scope, path, query_string, headers, receive, send)
        finally:
            await client.aclose()

    return app


async def _handle_cookies(client, trawl_url, qs, send) -> None:
    target = qs.get("url", [""])[0]
    if not target:
        await _send_json(send, 400, {"error": "缺少 url 参数"})
        return
    data = await _call_trawl(client, trawl_url, {"url": target, "maxTimeout": DEFAULT_MAX_TIMEOUT_MS})
    if "error" in data:
        await _send_json(send, 502, {"error": data["error"]})
        return
    cookies: dict[str, str] = {}
    for cookie in data.get("cookies") or []:
        if cookie.get("name") and cookie.get("value"):
            cookies[cookie["name"]] = cookie["value"]
    user_agent = data.get("userAgent") or ""
    await _send_json(send, 200, {"cookies": cookies, "user_agent": user_agent})


async def _handle_html(client, trawl_url, qs, headers, send) -> None:
    target = qs.get("url", [""])[0]
    if not target:
        await _send_json(send, 400, {"error": "缺少 url 参数"})
        return
    payload: dict = {"url": target, "maxTimeout": DEFAULT_MAX_TIMEOUT_MS}
    if qs.get("proxy"):
        payload["proxy"] = qs["proxy"][0]
    if qs.get("bypassCookieCache"):
        payload["skipHttp"] = True
    data = await _call_trawl(client, trawl_url, payload)
    if "error" in data:
        await _send_json(send, 502, {"error": data["error"]})
        return
    status_code = int(data.get("statusCode") or 200)
    html = data.get("html") or ""
    final_url = data.get("url") or target
    extra_headers: list[tuple[bytes, bytes]] = [
        (b"x-cf-bypasser-final-url", final_url.encode("utf-8")),
        (b"x-cf-bypasser-cookies", str(len(data.get("cookies") or [])).encode()),
        (b"x-cf-bypasser-user-agent", (data.get("userAgent") or "").encode("utf-8")),
    ]
    await _send_text(send, status_code, html.encode("utf-8"), extra_headers)


async def _handle_mirror(client, trawl_url, scope, path, query_string, headers, receive, send) -> None:
    hostname = (headers.get(b"x-hostname") or b"").decode("latin-1").strip()
    if not hostname:
        await _send_json(send, 400, {"error": "缺少 x-hostname 头"})
        return

    target_url = _build_target_url(hostname, path, query_string)
    payload: dict = {"url": target_url, "maxTimeout": DEFAULT_MAX_TIMEOUT_MS}
    payload["method"] = (scope.get("method") or "GET").upper()

    upstream_headers: dict[str, str] = {}
    for raw_name, raw_value in scope.get("headers", []):
        name = raw_name.decode("latin-1").lower()
        if name in ("x-hostname", "x-proxy", "x-bypass-cache", "host", "content-length", "connection"):
            continue
        value = raw_value.decode("latin-1")
        upstream_headers[name] = upstream_headers.get(name, "") + (", " if name in upstream_headers else "") + value
    if upstream_headers:
        payload["headers"] = upstream_headers

    if (headers.get(b"x-proxy") or b"").decode("latin-1").strip():
        payload["proxy"] = headers[b"x-proxy"].decode("latin-1").strip()
    if (headers.get(b"x-bypass-cache") or b"").decode("latin-1").strip().lower() == "true":
        payload["skipHttp"] = True

    if scope.get("method", "GET").upper() in ("POST", "PUT", "PATCH", "DELETE"):
        try:
            body_received = await _read_body(scope, receive)
        except Exception:
            body_received = b""
        if body_received:
            payload["body"] = body_received.decode("utf-8", errors="replace")

    data = await _call_trawl(client, trawl_url, payload)
    if "error" in data:
        await _send_json(send, 502, {"error": data["error"]})
        return

    status_code = int(data.get("statusCode") or 200)
    response_headers: list[tuple[bytes, bytes]] = []
    upstream_response_headers = data.get("responseHeaders") or {}
    for name, value in upstream_response_headers.items():
        if name.lower() in ("content-length", "connection", "transfer-encoding"):
            continue
        response_headers.append((name.encode("latin-1"), str(value).encode("latin-1")))

    for cookie in data.get("cookies") or []:
        response_headers.append((b"set-cookie", _cookie_to_set_cookie(cookie).encode("latin-1")))

    final_url = data.get("url") or target_url
    response_headers.append((b"x-cf-bypasser-final-url", final_url.encode("utf-8")))

    body = data.get("body")
    if isinstance(body, list) and body and isinstance(body[0], int):
        body_bytes = bytes(body)
    elif isinstance(body, str) and body:
        body_bytes = body.encode("utf-8")
    else:
        body_bytes = (data.get("html") or "").encode("utf-8")

    await _send_text(send, status_code, body_bytes, response_headers)


async def _read_body(scope, receive) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        if message["type"] != "http.request":
            continue
        chunks.append(message.get("body") or b"")
        if not message.get("more_body"):
            break
    return b"".join(chunks)


class TrawlAdapterServer:
    """本地 TRAWL 适配层服务：把 cf_bypasser 协议翻译成 TRAWL /scrape。

    与 LocalBypassServer 同模式：随机空闲端口 + uvicorn 子进程/进程内线程。
    """

    def __init__(self, trawl_url: str, log_fn: Callable[[str], None] | None = None):
        self._trawl_url = (trawl_url or "").strip().rstrip("/")
        self._process: asyncio.subprocess.Process | None = None
        self._thread: threading.Thread | None = None
        self._server: uvicorn.Server | None = None
        self._in_process: bool = False
        self._port: int = 0
        self._url: str = ""
        self._started = False
        self._closing = False
        self._log_fn = log_fn or (lambda msg: logger.info(msg))
        self._atexit_registered = False

    def _log(self, msg: str) -> None:
        self._log_fn(f"[TRAWL适配] {msg}")

    @property
    def url(self) -> str:
        return self._url

    @property
    def is_running(self) -> bool:
        if self._in_process:
            return self._started and self._server is not None and not getattr(self._server, "should_exit", True)
        return self._started and self._process is not None and self._process.returncode is None

    def _check_dependencies(self) -> tuple[bool, str]:
        missing = []
        try:
            import uvicorn  # noqa: F401  # 探活
        except ImportError:
            missing.append("uvicorn")
        try:
            import httpx  # noqa: F401  # 探活
        except ImportError:
            missing.append("httpx")
        if missing:
            return False, f"缺少依赖: {', '.join(missing)}\n请运行: pip install {' '.join(missing)}"
        return True, ""

    async def start(self) -> tuple[bool, str]:
        if self.is_running:
            return True, self._url
        if not self._trawl_url:
            return False, "未配置 TRAWL 地址"

        deps_ok, deps_error = self._check_dependencies()
        if not deps_ok:
            return False, deps_error

        self._port = _find_free_port()
        self._url = f"http://{ADAPTER_HOST}:{self._port}"
        self._log(f"启动 TRAWL 适配层 {self._url} -> {self._trawl_url} ...")

        if IS_PYINSTALLER:
            ok, err = await self._start_in_process()
        else:
            ok, err = await self._start_subprocess()
        if not ok:
            return False, err

        self._started = True
        self._log(f"TRAWL 适配层已就绪: {self._url}")
        return True, self._url

    async def _start_subprocess(self) -> tuple[bool, str]:
        import asyncio as _asyncio

        self._process = await _asyncio.create_subprocess_exec(
            __import__("sys").executable,
            "-m",
            "uvicorn",
            "mdcx.cf_bypass.trawl_adapter:create_trawl_adapter_factory",
            "--factory",
            "--host",
            ADAPTER_HOST,
            "--port",
            str(self._port),
            "--log-level",
            "warning",
            stdout=_asyncio.subprocess.DEVNULL,
            stderr=_asyncio.subprocess.DEVNULL,
            start_new_session=True,
            env={**os.environ, "MDCX_TRAWL_URL": self._trawl_url},
        )
        self._register_atexit()
        ready, error = await self._wait_ready()
        if not ready:
            await self.stop()
            return False, error
        return True, ""

    def _register_atexit(self) -> None:
        if self._atexit_registered:
            return
        self._atexit_registered = True
        atexit.register(self._atexit_cleanup)

    def _atexit_cleanup(self) -> None:
        proc = self._process
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
            except Exception:
                pass

    async def _start_in_process(self) -> tuple[bool, str]:
        import uvicorn

        try:
            config = uvicorn.Config(
                create_trawl_adapter_app(self._trawl_url),
                host=ADAPTER_HOST,
                port=self._port,
                log_level="warning",
            )
            self._server = uvicorn.Server(config)  # type: ignore[assignment]
            assert self._server is not None
            self._thread = threading.Thread(target=self._server.run, daemon=True)
            self._thread.start()
        except Exception as e:
            return False, f"启动 TRAWL 适配层线程失败: {e}"

        ready, error = await self._wait_ready()
        if not ready:
            await self.stop()
            return False, error
        self._in_process = True
        return True, ""

    async def _wait_ready(self, timeout: int = SERVER_START_TIMEOUT) -> tuple[bool, str]:
        deadline = time.monotonic() + timeout
        last_error = ""
        while time.monotonic() < deadline:
            if self._in_process and self._thread is not None and not self._thread.is_alive():
                return False, "TRAWL 适配层线程已退出 (uvicorn 启动失败)"
            if not self._in_process and self._process and self._process.returncode is not None:
                return False, f"适配层进程异常退出 (code={self._process.returncode})"
            try:
                async with httpx.AsyncClient() as probe:
                    resp = await probe.get(f"{self._url}/cookies?url=http://example.com", timeout=5)
                    if resp.status_code == 200:
                        return True, ""
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
                last_error = str(e)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
        return False, f"TRAWL 适配层启动超时 ({SERVER_START_TIMEOUT}s): {last_error}"

    async def stop(self) -> None:
        if self._closing:
            return
        self._closing = True
        if self._in_process and self._server is not None:
            self._log("正在停止 TRAWL 适配层(线程)...")
            try:
                self._server.should_exit = True
                if self._thread is not None:
                    self._thread.join(timeout=5)
            except Exception as e:
                self._log(f"停止服务异常: {e}")
            self._server = None
            self._thread = None
            self._in_process = False
        elif self._process is not None:
            self._log("正在停止 TRAWL 适配层...")
            try:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5)
                except TimeoutError:
                    self._process.kill()
                    await asyncio.wait_for(self._process.wait(), timeout=3)
            except ProcessLookupError:
                pass
            except Exception as e:
                self._log(f"停止服务异常: {e}")
        self._process = None
        self._started = False
        self._url = ""
        self._port = 0
        self._log("TRAWL 适配层已停止")


def create_trawl_adapter_factory():
    """uvicorn --factory 入口：从环境变量读取 TRAWL 地址并创建适配层。"""
    trawl_url = os.environ.get("MDCX_TRAWL_URL", "")
    return create_trawl_adapter_app(trawl_url)
