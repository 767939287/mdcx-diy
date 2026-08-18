import asyncio
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from urllib.parse import quote_plus, urljoin

from mdcx.config.enums import Website

if TYPE_CHECKING:
    from mdcx.web_async import AsyncWebClient


class NetworkCheckStatus(StrEnum):
    OK = "ok"
    WARNING = "warning"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class NetworkCheckSpec:
    name: str
    group: str
    url: str
    site: Website | None = None
    method: str = "GET"
    use_proxy: bool = True
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    encoding: str = "utf-8"
    note: str = ""
    warning_if_missing: str = ""
    enable_cf_bypass: bool = False
    validator: str = ""


@dataclass(frozen=True)
class NetworkCheckResult:
    spec: NetworkCheckSpec
    status: NetworkCheckStatus
    message: str
    status_code: int | None = None
    elapsed_ms: int | None = None
    final_url: str = ""
    error: str = ""
    used_proxy: bool | None = None


# 连通性检测通过后，用该番号实际探测爬虫搜索能力，避免"能连≠能刮"误导用户
SCRAPE_PROBE_NUMBER = "SSNI-647"
SCRAPE_PROBE_TIMEOUT = 8.0


ProgressCallback = Callable[[str], None]


def _manager():
    from mdcx.config.manager import manager

    return manager


SPECIAL_CHECK_PATHS: dict[Website, str] = {
    Website.AIRAV_CC: "/playon.aspx?hid=44733",
    Website.JAVDB: "/v/D16Q5?locale=zh",
    Website.JAVBUS: "/FSDSS-660",
    Website.JAVLIBRARY: "/cn/?v=javme2j2tu",
    Website.KIN8: "/moviepages/3681/index.html",
    Website.JAVDB_APP: "/api/v2/search?q=SSNI-647&page=1",
    Website.MISSAV_API: "/search/SSNI-647?uitype=frontpage",
}

DEFAULT_SITE_URLS: dict[Website, str] = {
    Website.DMM: "https://www.dmm.co.jp",
    Website.AVSOX: "https://avsox.click",
    Website.AVMOO: "https://avmoo.shop",
    Website.AVHEAT: "https://avheat.shop",
    Website.OFFICIAL: "",
}

GROUP_ORDER = ("基础环境", "基础连通性", "刮削站点", "账号/API", "辅助服务")
STATUS_ORDER = {
    NetworkCheckStatus.FAILED: 0,
    NetworkCheckStatus.WARNING: 1,
    NetworkCheckStatus.OK: 2,
    NetworkCheckStatus.SKIPPED: 3,
    NetworkCheckStatus.CANCELLED: 4,
}


def _status_icon(status: NetworkCheckStatus) -> str:
    return {
        NetworkCheckStatus.OK: "✅",
        NetworkCheckStatus.WARNING: "⚠️",
        NetworkCheckStatus.FAILED: "❌",
        NetworkCheckStatus.SKIPPED: "ℹ️",
        NetworkCheckStatus.CANCELLED: "⛔️",
    }[status]


def _elapsed_text(elapsed_ms: int | None) -> str:
    return "-" if elapsed_ms is None else f"{elapsed_ms} ms"


def _status_code_text(status_code: int | None) -> str:
    return "-" if status_code is None else str(status_code)


def _join_url(base_url: str, path: str) -> str:
    if not path:
        return base_url
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _configured_or_default_url(site: Website, default_url: str) -> tuple[str, bool]:
    manager = _manager()
    custom_url = manager.config.get_site_url(site)
    if custom_url:
        return custom_url, True
    return default_url.rstrip("/"), False


def _diagnostic_timeout() -> float:
    manager = _manager()
    return max(float(manager.config.timeout or 5), 2.0)


def _is_cloudflare_challenge(text: str) -> bool:
    lowered = text.lower()
    strong_markers = (
        "cdn-cgi/challenge-platform/h/b/",
        "cf-chl",
        "challenges.cloudflare.com",
    )
    if any(marker in lowered for marker in strong_markers):
        return True
    weak_markers = (
        "cf-browser-verification",
        "just a moment",
        "attention required",
        "enable javascript and cookies",
        "checking your browser before accessing",
    )
    return "cloudflare" in lowered and any(marker in lowered for marker in weak_markers)


def _is_proxy_error(error: str) -> bool:
    lowered = error.lower()
    return "proxy" in lowered or "socks" in lowered or "tunnel" in lowered


def _message_for_error(error: str) -> str:
    if not error:
        return "请求失败"
    if _is_proxy_error(error):
        return "代理连接失败，请检查代理地址或代理软件"
    if "超时" in error or "timeout" in error.lower():
        return "连接超时，请检查网络或代理节点"
    if "dns" in error.lower() or "resolve" in error.lower():
        return "DNS 解析失败"
    return error


def _clean_error(error: str) -> str:
    error = str(error or "").strip()
    if ": " not in error:
        return error
    left, right = error.split(": ", 1)
    if left.startswith(("GET ", "POST ", "HEAD ")) and right.startswith(left):
        return right
    return error


def _classify_http_result(spec: NetworkCheckSpec, status_code: int, text: str) -> tuple[NetworkCheckStatus, str]:
    if _is_cloudflare_challenge(text):
        return NetworkCheckStatus.WARNING, "被 Cloudflare 挑战页拦截"

    if spec.site == Website.JAVDB:
        manager = _manager()
        if "The owner of this website has banned your access based on your browser's behaving" in text:
            ip_address = re.findall(r"(\d+\.\d+\.\d+\.\d+)", text)
            ip_text = f"{ip_address[0]} " if ip_address else ""
            return NetworkCheckStatus.FAILED, f"当前 IP {ip_text}被 JavDB 封禁"
        if "Due to copyright restrictions" in text or "Access denied" in text:
            return NetworkCheckStatus.FAILED, "当前 IP 被 JavDB 限制，请使用非日本节点"
        if "/logout" in text:
            return NetworkCheckStatus.OK, "连接正常，Cookie 有效"
        if manager.config.javdb:
            return NetworkCheckStatus.WARNING, "站点可访问，但 JavDB Cookie 可能无效"
        return NetworkCheckStatus.OK, "连接正常"

    if spec.site == Website.JAVBUS:
        manager = _manager()
        if "lostpasswd" in text and manager.config.javbus:
            return NetworkCheckStatus.WARNING, "站点可访问，但 JavBus Cookie 可能无效"
        if "lostpasswd" in text:
            return NetworkCheckStatus.WARNING, "当前节点可能需要 JavBus Cookie"
        return NetworkCheckStatus.OK, "连接正常"

    if spec.site == Website.DMM:
        if "このページはお住まいの地域からご利用になれません" in text:
            return NetworkCheckStatus.FAILED, "DMM 地域限制，请使用日本节点"

    if spec.site == Website.MGSTAGE and not text.strip():
        return NetworkCheckStatus.FAILED, "MGStage 返回空页面，通常是地域限制，请使用日本节点"

    if status_code in {401, 403}:
        return NetworkCheckStatus.WARNING, f"HTTP {status_code}，可能需要 Cookie、API Token 或更换节点"
    if status_code == 429:
        return NetworkCheckStatus.WARNING, "HTTP 429，请求被限流"
    if 200 <= status_code < 400:
        return NetworkCheckStatus.OK, "连接正常"
    if 500 <= status_code:
        return NetworkCheckStatus.FAILED, f"站点服务异常 HTTP {status_code}"
    return NetworkCheckStatus.FAILED, f"HTTP {status_code}"


def _compute_used_proxy(spec: NetworkCheckSpec) -> bool:
    """计算该检测项实际是否走代理.

    与 AsyncWebClient.request 的真实路由判定保持一致：
    走代理需同时满足 全局代理启用、spec 允许代理、host 命中 proxy_sites。
    """
    if not spec.use_proxy or not spec.url:
        return False
    manager = _manager()
    if not (manager.config.use_proxy and manager.config.proxy):
        return False
    try:
        from httpx import URL

        host = URL(spec.url).host or ""
    except Exception:
        host = ""
    if not host:
        return False
    try:
        from mdcx.web_async import is_proxy_host

        return is_proxy_host(host, manager.config.proxy_sites.split(",") if manager.config.proxy_sites else None)
    except Exception:
        return False


async def _probe_crawler_capability(
    client: Any,
    spec: NetworkCheckSpec,
) -> tuple[NetworkCheckStatus | None, str]:
    """连通性检测通过后，用真实爬虫搜索路径探测刮削能力.

    返回 (None, "") 表示该站点无需/无法探测；否则返回探测状态与说明。
    """
    site = spec.site
    if site is None:
        return None, ""
    try:
        from parsel import Selector

        from mdcx.config.enums import Language
        from mdcx.crawlers import get_crawler
        from mdcx.crawlers.base.types import CrawlerException
        from mdcx.models.types import CrawlerInput
    except Exception:
        return None, ""

    try:
        crawler_cls = get_crawler(site)
        if crawler_cls is None:
            return None, ""
        crawler = crawler_cls(client=client, base_url=spec.url.rstrip("/"), browser=None)
        input_data = CrawlerInput(
            appoint_number="",
            appoint_url="",
            file_path=None,
            mosaic="",
            number=SCRAPE_PROBE_NUMBER,
            short_number="",
            language=Language.UNDEFINED,
            org_language=Language.UNDEFINED,
        )
        ctx: Any = crawler.new_context(input_data)
        search_urls = await crawler._generate_search_url(ctx)
        if not search_urls:
            return NetworkCheckStatus.WARNING, "站点可达但无法自动探测刮削，可用设置页指定网址实测"
        if isinstance(search_urls, str):
            search_urls = [search_urls]

        headers = crawler._get_headers(ctx) or None
        cookies = crawler._get_cookies(ctx) or None

        for search_url in search_urls:
            response, error = await client.request(
                "GET",
                search_url,
                headers=headers,
                cookies=cookies,
                use_proxy=spec.use_proxy,
                timeout=SCRAPE_PROBE_TIMEOUT,
                retry_count=1,
            )
            if response is None:
                return NetworkCheckStatus.WARNING, f"站点可达但搜索页请求失败: {error}"
            search_text = ""
            try:
                response.encoding = spec.encoding
                search_text = response.text or ""
            except Exception:
                search_text = ""
            if _is_cloudflare_challenge(search_text):
                return NetworkCheckStatus.WARNING, "站点可达但搜索页被 Cloudflare 拦截"
            selector = Selector(text=search_text)
            detail_urls = await crawler._parse_search_page(ctx, selector, search_url)
            if detail_urls:
                return NetworkCheckStatus.OK, "连接正常，刮削正常"
            return NetworkCheckStatus.WARNING, "站点可达但搜索无结果，可能该测试番号未收录"
        return NetworkCheckStatus.WARNING, "站点可达但搜索无结果"
    except NotImplementedError:
        return NetworkCheckStatus.WARNING, "站点可达但无法自动探测刮削，可用设置页指定网址实测"
    except CrawlerException as exc:
        return NetworkCheckStatus.WARNING, f"站点可达但刮削探测失败: {exc}"
    except Exception as exc:
        return NetworkCheckStatus.WARNING, f"站点可达但刮削探测异常: {exc}"


def _is_bypass_capable_client(client: Any) -> bool:
    return callable(getattr(client, "_try_bypass_cloudflare", None))


async def _try_bypass_for_check(
    client: Any,
    spec: NetworkCheckSpec,
) -> tuple[Any | None, str]:
    if not spec.enable_cf_bypass:
        return None, "此检测项未启用 CF Bypass"
    manager = _manager()
    if not manager.config.cf_bypass_url.strip():
        return None, "未配置 CF Bypass"
    if not _is_bypass_capable_client(client):
        return None, "当前客户端不支持 CF Bypass"

    try:
        from httpx import URL
    except Exception as exc:
        return None, f"URL 解析依赖不可用: {exc}"

    try:
        host = URL(spec.url).host or ""
    except Exception as exc:
        return None, f"URL 解析失败: {exc}"
    if not host:
        return None, "URL 缺少 host"

    return await client._try_bypass_cloudflare(
        host=host,
        method=spec.method,
        target_url=spec.url,
        headers=spec.headers or None,
        cookies=spec.cookies or None,
        data=None,
        json_data=None,
        # CF Bypass 往往需要启动浏览器、刷新 Cookie 或等待挑战页完成, 使用 AsyncWebClient 内置的
        # _cf_bypass_timeout, 不用普通诊断请求的短超时覆盖。
        timeout=None,
        allow_redirects=True,
        use_proxy=spec.use_proxy,
    )


def _format_header() -> list[str]:
    manager = _manager()
    use_proxy = bool(manager.config.use_proxy and manager.config.proxy)
    cf_bypass_url = manager.config.cf_bypass_url.strip()
    cf_bypass_proxy = manager.config.cf_bypass_proxy.strip()
    trawl_url = manager.config.cf_bypass_trawl_url.strip()
    lines = [time.strftime("%Y-%m-%d %H:%M:%S").center(88, "=")]
    lines.append("基础环境")
    lines.append(f"  {'代理状态':<16}{'已启用' if use_proxy else '未启用'}")
    if use_proxy:
        lines.append(f"  {'代理地址':<16}{manager.config.proxy}")
    lines.append(f"  {'CF Bypass':<16}{'已配置' if cf_bypass_url else '未配置'}")
    lines.append(f"  {'CF Bypass代理':<16}{'已配置' if cf_bypass_proxy else '未配置'}")
    lines.append(f"  {'外部CF服务':<16}{'已配置' if trawl_url else '未配置'}")
    lines.append(f"  {'诊断超时':<16}{_diagnostic_timeout():.1f}s")
    lines.append("  " + "-" * 84)
    lines.append(f"  {'状态':<4} {'站点':<18} {'状态码':>4}  {'耗时':>8}  {'路由':<4} 信息")
    lines.append("=" * 88)
    return lines


def format_result_line(result: NetworkCheckResult) -> str:
    icon = _status_icon(result.status)
    name = result.spec.name[:18]
    status_code = _status_code_text(result.status_code)
    elapsed = _elapsed_text(result.elapsed_ms)
    used_proxy = result.used_proxy if result.used_proxy is not None else result.spec.use_proxy
    proxy = "代理" if used_proxy else "直连"
    proxy = f"{proxy:<4}"
    message = result.message
    if result.error and result.status == NetworkCheckStatus.FAILED:
        if result.error not in message:
            message = f"{message}: {result.error}"
    return f"  {icon} {name:<18} {status_code:>4}  {elapsed:>8}  {proxy} {message}"


def format_summary(results: list[NetworkCheckResult], elapsed: float, cancelled: bool) -> list[str]:
    failed = sum(1 for result in results if result.status == NetworkCheckStatus.FAILED)
    warning = sum(1 for result in results if result.status == NetworkCheckStatus.WARNING)
    ok = sum(1 for result in results if result.status == NetworkCheckStatus.OK)
    skipped = sum(1 for result in results if result.status == NetworkCheckStatus.SKIPPED)
    status = "已取消" if cancelled else "已完成"
    lines = [
        "-" * 88,
        f"网络检测{status}：正常 {ok}，警告 {warning}，失败 {failed}，跳过 {skipped}，用时 {elapsed:.2f} 秒",
    ]
    if failed or warning:
        lines.append("建议优先查看失败/警告项；若基础连通性失败，先检查代理或系统网络。")
    lines.append("=" * 88)
    return lines


async def _build_site_specs() -> list[NetworkCheckSpec]:
    from mdcx.crawlers import get_crawler, get_registered_crawler_sites

    manager = _manager()
    specs: list[NetworkCheckSpec] = []
    for site in get_registered_crawler_sites(include_hidden=False):
        if site == Website.THEPORNDB:
            continue
        crawler_cls = get_crawler(site)
        if crawler_cls is None:
            continue

        default_url = DEFAULT_SITE_URLS.get(site)
        if default_url is None:
            try:
                default_url = crawler_cls.base_url_()
            except Exception:
                default_url = ""

        base_url, customized = _configured_or_default_url(site, default_url or "")
        if not base_url:
            specs.append(
                NetworkCheckSpec(
                    name=site.value,
                    group="刮削站点",
                    url="",
                    site=site,
                    note="没有固定入口，按实际番号动态检测",
                )
            )
            continue

        path = SPECIAL_CHECK_PATHS.get(site, "")
        url = _join_url(base_url, path)
        headers: dict[str, str] = {}
        cookies: dict[str, str] = {}
        use_proxy = True
        if site == Website.JAVDB and manager.config.javdb:
            headers["cookie"] = manager.config.javdb
        elif site == Website.JAVBUS:
            headers["Accept-Language"] = "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,ja;q=0.6"
            if manager.config.javbus:
                headers["cookie"] = manager.config.javbus
        elif site == Website.JAVLIBRARY and customized:
            use_proxy = False
        elif site == Website.MGSTAGE:
            cookies["adc"] = "1"
        elif site == Website.DMM_API:
            url = f"{url.rstrip('/')}/movies?q=ssni-200"
            specs.append(
                NetworkCheckSpec(
                    name=site.value,
                    group="账号/API",
                    url=url,
                    site=site,
                    headers={"Accept": "application/json"},
                    validator="dmm_api",
                )
            )
            continue
        elif site == Website.GETCHU or site == Website.GETCHU_DMM:
            specs.append(
                NetworkCheckSpec(
                    name=site.value,
                    group="刮削站点",
                    url=url,
                    site=site,
                    use_proxy=use_proxy,
                    encoding="euc-jp",
                )
            )
            continue
        elif site == Website.JAVDB_APP:
            # javdb_app API 需要 jdsignature header
            from ..crawlers.javdb_app import make_signature

            headers["jdsignature"] = make_signature()
            headers["accept-language"] = "zh"
            headers["User-Agent"] = "Dart/3.5 (dart:io)"
        elif site == Website.MISSAV_API:
            # missav_api 用 Recombee API，需 HMAC 签名且不走 missav.ws
            from ..crawlers.missav_api import MissavApiCrawler

            base_url = f"https://{MissavApiCrawler.RECOMBEE_HOST}"
            url = _join_url(base_url, path)
            signed_path = MissavApiCrawler._sign_path(path.split("?")[0])
            url = f"{base_url}{signed_path}"

        specs.append(
            NetworkCheckSpec(
                name=site.value,
                group="刮削站点",
                url=url,
                site=site,
                use_proxy=use_proxy,
                headers=headers,
                cookies=cookies,
                enable_cf_bypass=True,
            )
        )
    return specs


def _build_static_specs() -> list[NetworkCheckSpec]:
    manager = _manager()
    specs = [
        NetworkCheckSpec(
            name="GitHub Raw",
            group="基础连通性",
            url="https://raw.githubusercontent.com",
            use_proxy=bool(manager.config.use_proxy and manager.config.proxy),
        ),
        NetworkCheckSpec(
            name="通用 HTTPS",
            group="基础连通性",
            url="https://www.google.com/generate_204",
            use_proxy=bool(manager.config.use_proxy and manager.config.proxy),
        ),
    ]

    cf_bypass_url = manager.config.cf_bypass_url.strip()
    if cf_bypass_url:
        health_url = cf_bypass_url.rstrip("/") + "/cookies?url=http://example.com"
        bypass_proxy = manager.config.cf_bypass_proxy.strip()
        if bypass_proxy:
            health_url += "&proxy=" + quote_plus(bypass_proxy)
        specs.append(NetworkCheckSpec(name="CF Bypass", group="辅助服务", url=health_url, use_proxy=False))
    else:
        specs.append(
            NetworkCheckSpec(
                name="CF Bypass",
                group="辅助服务",
                url="",
                note="未配置，仅遇到 Cloudflare 挑战页时需要",
            )
        )

    trawl_url = manager.config.cf_bypass_trawl_url.strip()
    if trawl_url:
        backend = (manager.config.cf_bypass_trawl_backend or "trawl").strip().lower()
        health_path = "/health" if backend == "trawl" else "/"
        specs.append(
            NetworkCheckSpec(
                name="外部 CF 服务",
                group="辅助服务",
                url=trawl_url.rstrip("/") + health_path,
                use_proxy=False,
            )
        )

    api_token = manager.config.theporndb_api_token.strip()
    if api_token:
        specs.append(
            NetworkCheckSpec(
                name="ThePornDB Token",
                group="账号/API",
                url="https://api.theporndb.net/scenes/hash/8679fcbdd29fa735",
                headers={
                    "Authorization": f"Bearer {api_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                validator="theporndb_token",
            )
        )
    else:
        specs.append(
            NetworkCheckSpec(
                name="ThePornDB Token",
                group="账号/API",
                url="",
                warning_if_missing="未填写 API Token，影响欧美刮削",
            )
        )
    return specs


async def build_network_check_specs() -> list[NetworkCheckSpec]:
    return [*_build_static_specs(), *(await _build_site_specs())]


async def run_network_check_item(
    spec: NetworkCheckSpec,
    *,
    cancel_event: threading.Event | None = None,
    client: "AsyncWebClient | Any | None" = None,
) -> NetworkCheckResult:
    if cancel_event and cancel_event.is_set():
        return NetworkCheckResult(spec=spec, status=NetworkCheckStatus.CANCELLED, message="已取消")
    if spec.warning_if_missing:
        return NetworkCheckResult(spec=spec, status=NetworkCheckStatus.WARNING, message=spec.warning_if_missing)
    if not spec.url:
        return NetworkCheckResult(spec=spec, status=NetworkCheckStatus.SKIPPED, message=spec.note or "无固定检测入口")

    used_proxy = _compute_used_proxy(spec)
    start_time = time.perf_counter()
    try:
        request_client = client or _manager().computed.async_client
        response, error = await request_client.request(
            spec.method,  # type: ignore[arg-type]
            spec.url,
            headers=spec.headers or None,
            cookies=spec.cookies or None,
            use_proxy=spec.use_proxy,
            timeout=_diagnostic_timeout(),
            enable_cf_bypass=spec.enable_cf_bypass and bool(_manager().config.cf_bypass_url.strip()),
        )
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        if cancel_event and cancel_event.is_set():
            return NetworkCheckResult(spec=spec, status=NetworkCheckStatus.CANCELLED, message="已取消")
        if response is None:
            clean_error = _clean_error(error)
            message = _message_for_error(clean_error)
            return NetworkCheckResult(
                spec=spec,
                status=NetworkCheckStatus.FAILED,
                message=message,
                elapsed_ms=elapsed_ms,
                error=clean_error,
                used_proxy=used_proxy,
            )

        text = ""
        try:
            response.encoding = spec.encoding
            text = response.text or ""
        except Exception as exc:
            return NetworkCheckResult(
                spec=spec,
                status=NetworkCheckStatus.WARNING,
                message=f"响应可达，但文本解析失败: {exc}",
                status_code=response.status_code,
                elapsed_ms=elapsed_ms,
                final_url=str(getattr(response, "url", "") or ""),
                used_proxy=used_proxy,
            )

        if _is_cloudflare_challenge(text) and spec.enable_cf_bypass and _manager().config.cf_bypass_url.strip():
            bypass_response, bypass_error = await _try_bypass_for_check(request_client, spec)
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            if bypass_response is None:
                clean_error = _clean_error(bypass_error)
                return NetworkCheckResult(
                    spec=spec,
                    status=NetworkCheckStatus.FAILED,
                    message="Cloudflare Bypass 失败",
                    status_code=int(response.status_code),
                    elapsed_ms=elapsed_ms,
                    final_url=str(getattr(response, "url", "") or ""),
                    error=clean_error,
                    used_proxy=used_proxy,
                )
            response = bypass_response
            try:
                response.encoding = spec.encoding
                text = response.text or ""
            except Exception as exc:
                return NetworkCheckResult(
                    spec=spec,
                    status=NetworkCheckStatus.WARNING,
                    message=f"Bypass 响应可达，但文本解析失败: {exc}",
                    status_code=response.status_code,
                    elapsed_ms=elapsed_ms,
                    final_url=str(getattr(response, "url", "") or ""),
                    used_proxy=used_proxy,
                )
            if not _is_cloudflare_challenge(text):
                bypass_mode = ""
                try:
                    bypass_mode = response.headers.get("x-mdcx-bypass-mode", "")
                except Exception:
                    bypass_mode = ""
                status, message = _classify_http_result(spec, int(response.status_code), text)
                if status == NetworkCheckStatus.OK:
                    mode_text = f"（{bypass_mode}）" if bypass_mode else ""
                    message = f"连接正常，已通过 CF Bypass{mode_text}"
                return NetworkCheckResult(
                    spec=spec,
                    status=status,
                    message=message,
                    status_code=int(response.status_code),
                    elapsed_ms=elapsed_ms,
                    final_url=str(getattr(response, "url", "") or ""),
                    used_proxy=used_proxy,
                )

        status, message = _classify_http_result(spec, int(response.status_code), text)
        if spec.validator == "theporndb_token":
            status, message = _classify_theporndb_token(int(response.status_code), text)
        elif spec.validator == "dmm_api":
            status, message = _classify_dmm_api(int(response.status_code), text)
        elif spec.name == "CF Bypass" and status == NetworkCheckStatus.OK:
            message = "服务可用"

        if (
            status == NetworkCheckStatus.OK
            and spec.site is not None
            and not spec.validator
            and spec.name != "CF Bypass"
        ):
            probe_status, probe_message = await _probe_crawler_capability(request_client, spec)
            if probe_status is not None:
                status, message = probe_status, probe_message

        return NetworkCheckResult(
            spec=spec,
            status=status,
            message=message,
            status_code=int(response.status_code),
            elapsed_ms=elapsed_ms,
            final_url=str(getattr(response, "url", "") or ""),
            used_proxy=used_proxy,
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        return NetworkCheckResult(
            spec=spec,
            status=NetworkCheckStatus.FAILED,
            message="检测异常",
            elapsed_ms=elapsed_ms,
            error=str(exc),
        )


def _classify_theporndb_token(status_code: int, text: str) -> tuple[NetworkCheckStatus, str]:
    if status_code == 401 and "Unauthenticated" in text:
        return NetworkCheckStatus.FAILED, "API Token 错误"
    if status_code == 200 and '"data"' in text:
        return NetworkCheckStatus.OK, "API Token 有效"
    if status_code == 200:
        return NetworkCheckStatus.WARNING, "API 返回数据异常"
    return _classify_http_result(
        NetworkCheckSpec(name="ThePornDB Token", group="账号/API", url="", site=Website.THEPORNDB), status_code, text
    )


def _classify_dmm_api(status_code: int, text: str) -> tuple[NetworkCheckStatus, str]:
    if status_code == 200 and ("universal_id" in text or "SSNI" in text.upper()):
        return NetworkCheckStatus.OK, "API 查询正常"
    if status_code == 200:
        return NetworkCheckStatus.WARNING, "API 可访问，但 ssni-200 查询返回数据异常"
    return _classify_http_result(
        NetworkCheckSpec(name="dmm_api", group="账号/API", url="", site=Website.DMM_API), status_code, text
    )


async def run_network_check(
    *,
    progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
    concurrency: int = 10,
    client: "AsyncWebClient | Any | None" = None,
    emit_header: bool = True,
) -> list[NetworkCheckResult]:
    progress = progress or (lambda line: None)
    if emit_header:
        for line in _format_header():
            progress(line)

    specs = await build_network_check_specs()
    results: list[NetworkCheckResult] = []
    grouped_specs = {group: [spec for spec in specs if spec.group == group] for group in GROUP_ORDER}
    semaphore = asyncio.Semaphore(max(int(concurrency), 1))

    async def run_one(spec: NetworkCheckSpec) -> NetworkCheckResult:
        async with semaphore:
            return await run_network_check_item(spec, cancel_event=cancel_event, client=client)

    start_time = time.perf_counter()
    for group in GROUP_ORDER:
        group_specs = grouped_specs.get(group, [])
        if not group_specs or group == "基础环境":
            continue
        progress(group)
        tasks = [asyncio.create_task(run_one(spec)) for spec in group_specs]
        for task in asyncio.as_completed(tasks):
            if cancel_event and cancel_event.is_set():
                task.close()
                for pending in tasks:
                    pending.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                elapsed = time.perf_counter() - start_time
                for line in format_summary(results, elapsed, cancelled=True):
                    progress(line)
                return results
            result = await task
            results.append(result)
            progress(format_result_line(result))

    elapsed = time.perf_counter() - start_time
    for line in format_summary(results, elapsed, cancelled=bool(cancel_event and cancel_event.is_set())):
        progress(line)
    return sorted(
        results,
        key=lambda result: (
            GROUP_ORDER.index(result.spec.group) if result.spec.group in GROUP_ORDER else len(GROUP_ORDER),
            STATUS_ORDER[result.status],
            result.spec.name,
        ),
    )
