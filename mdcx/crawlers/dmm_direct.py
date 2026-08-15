"""番号 -> DMM 官方 CDN 高清图直链构造。

DMM 官方高清封面托管在 awsimgsrc CDN，URL 规律:
    https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/{cid}/{cid}pl.jpg   (横版高清, 如 2184x1469)
    https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/{cid}/{cid}ps.jpg   (竖版高清, 如 1032x1469)

cid = {mPrefix}{series}{编号5位补零}，mPrefix 由品牌(series)决定，不同品牌有各自的目录前缀。
该 CDN 对不存在的图直接返回 404(区别于 pics.dmm.co.jp 返回占位图)，适合做无爬虫直连兜底。
"""

from __future__ import annotations

import asyncio
import re
import threading
import time
from typing import Any

_DMM_CDN_BASE = "https://awsimgsrc.dmm.co.jp/pics_dig/digital/video"

_PREFIX_GROUPS: dict[str, list[str]] = {
    "": [
        "adn",
        "bf",
        "cawd",
        "cnd",
        "dasd",
        "dvdms",
        "ebod",
        "eyan",
        "gdhh",
        "hibl",
        "hmn",
        "hnd",
        "hntd",
        "ipit",
        "ipvr",
        "ipx",
        "ipzz",
        "jue",
        "jufd",
        "juk",
        "jul",
        "jux",
        "juy",
        "juq",
        "kawd",
        "meyd",
        "miab",
        "miad",
        "mibd",
        "mide",
        "midv",
        "mifd",
        "mtsp",
        "mudr",
        "mukd",
        "mvsd",
        "mymd",
        "nima",
        "ofje",
        "onsd",
        "pred",
        "rki",
        "sone",
        "sora",
        "ssis",
        "ssni",
        "waaa",
    ],
    "1": [
        "dandy",
        "dism",
        "dldss",
        "dvdes",
        "fcdss",
        "fset",
        "fsdss",
        "gs",
        "hunt",
        "kmhrs",
        "mmgh",
        "rct",
        "rctd",
        "sdab",
        "sdam",
        "sdde",
        "sdjs",
        "sdmf",
        "sdmm",
        "sdms",
        "sdmt",
        "sdmu",
        "sdfk",
        "sdnm",
        "star",
        "stars",
        "start",
        "svdvd",
        "sw",
        "vandr",
    ],
    "3": ["wanz"],
    "13": ["ayb", "gg", "gvg", "gvh", "ovg"],
    "17": ["bkd"],
    "18": ["momj", "ntrd"],
    "41": ["dok"],
    "42": ["sma"],
    "49": ["avop", "madm"],
    "55": ["t28"],
    "77": ["cre"],
    "118": ["onez"],
    "143": ["ppd", "umd"],
    "433": ["mbd"],
    "436": ["abf"],
    "5642": ["hodv"],
    "h_068": ["mxgs"],
    "h_113": ["ggg"],
    "h_205": ["ssnd"],
    "h_491": ["fone"],
    "h_1100": ["hzgd"],
    "h_1240": ["milk"],
    "h_1324": ["skmj"],
    "h_1371": ["zmen"],
    "h_1374": ["ksvr"],
    "h_1454": ["bdsr", "husr"],
    "h_189": ["ymd"],
    "h_237": ["nact"],
    "h_910": ["vrtm"],
    "h_995": ["bokd"],
}

# 同名系列跨厂商/跨编号段前缀不同，附加候选前缀兜底
_EXTRA_PREFIXES: dict[str, list[str]] = {
    "sw": ["h_113"],
    "bdsr": ["57"],
    "husr": ["57"],
    "sma": ["83"],
}

_SPECIAL_THRESHOLDS: dict[str, tuple[int, str, str]] = {
    "avop": (168, "", "1"),
    "gigl": (643, "h_860", ""),
    "ekdv": (655, "49", ""),
}

_COMMON_PREFIXES: list[str] = ["", "1", "13", "49", "436", "118", "55", "57", "83", "5642"]


_DIGIT_SERIES: list[str] = sorted(
    {series for members in _PREFIX_GROUPS.values() for series in members if any(ch.isdigit() for ch in series)},
    key=len,
    reverse=True,
)


def _parse_number(number: str) -> list[tuple[str, int, str]]:
    cleaned = number.lower().strip().replace("-", "").replace(" ", "")
    for series in _DIGIT_SERIES:
        if cleaned.startswith(series):
            rest = cleaned[len(series) :]
            if rest.isdigit() and rest:
                return [(series, int(rest), f"{int(rest):05d}")]
    m = re.match(r"^([a-z]+)(\d+)$", cleaned)
    if not m:
        return []
    series, digits = m.group(1), m.group(2)
    return [(series, int(digits), f"{int(digits):05d}")]


def _prefixes_for(series: str, num: int) -> list[str]:
    extra = _EXTRA_PREFIXES.get(series, [])
    if series in _SPECIAL_THRESHOLDS:
        threshold, small_prefix, large_prefix = _SPECIAL_THRESHOLDS[series]
        prefix = small_prefix if num <= threshold else large_prefix
        return list(dict.fromkeys([prefix] + extra))
    for group_prefix, members in _PREFIX_GROUPS.items():
        if series in members:
            return list(dict.fromkeys([group_prefix, ""] + extra))
    return list(dict.fromkeys(_COMMON_PREFIXES + extra))


def generate_cid_candidates(number: str) -> list[str]:
    seen: set[str] = set()
    candidates: list[str] = []
    for series, num, padded in _parse_number(number):
        for prefix in _prefixes_for(series, num):
            cid = f"{prefix}{series}{padded}"
            if cid not in seen:
                seen.add(cid)
                candidates.append(cid)
    return candidates


def generate_image_candidates(number: str) -> list[tuple[str, str]]:
    """返回 (orientation, url) 候选。orientation 为 landscape(横版 pl) 或 portrait(竖版 ps)。"""
    candidates: list[tuple[str, str]] = []
    for cid in generate_cid_candidates(number):
        candidates.append(("portrait", f"{_DMM_CDN_BASE}/{cid}/{cid}ps.jpg"))
        candidates.append(("landscape", f"{_DMM_CDN_BASE}/{cid}/{cid}pl.jpg"))
    return candidates


_UNCENSORED_PREFIXES = ("FC2", "HEYZO", "1PONDO", "CARIB", "10MUCH", "200GANA", "PACO", "MKD", "MIUM")

_DMM_UPGRADE_CACHE_TTL = 10 * 60
_DMM_UPGRADE_CACHE_MAX = 4096
_dmm_upgrade_cache: dict[str, tuple[float, str | None, str | None]] = {}
_dmm_upgrade_pending: dict[tuple[int, str], asyncio.Future[Any]] = {}
_dmm_cache_lock = threading.Lock()


def _normalize_dmm_number(number: str) -> str:
    return re.sub(r"[^a-z0-9]", "", number.lower())


def _clear_dmm_upgrade_cache() -> None:
    """清空升级缓存与 in-flight 表（测试复位用）。"""
    with _dmm_cache_lock:
        _dmm_upgrade_cache.clear()
        _dmm_upgrade_pending.clear()


def _prune_dmm_upgrade_cache(now: float) -> None:
    if len(_dmm_upgrade_cache) < _DMM_UPGRADE_CACHE_MAX:
        return
    expired = [key for key, (ts, _, _) in _dmm_upgrade_cache.items() if now - ts >= _DMM_UPGRADE_CACHE_TTL]
    for key in expired:
        _dmm_upgrade_cache.pop(key, None)


def is_uncensored_number(number: str) -> bool:
    """DMM 是有码源，判断番号是否为明显无码（含 `_` 或命中无码前缀），用于跳过 DMM 候选."""
    if "_" in number:
        return True
    return (number or "").upper().replace(" ", "").startswith(_UNCENSORED_PREFIXES)


def build_aws_cover_candidates(number: str) -> list[str]:
    """从番号构造 DMM 高清封面 (thumb/pl.jpg) 候选 URL 列表.

    复用番号→DMM cid 构造器，取横版 pl 候选。
    """
    return [url for orient, url in generate_image_candidates(number) if orient == "landscape"]


def build_aws_poster_candidates(number: str) -> list[str]:
    """从番号构造 DMM 高清海报 (poster/ps.jpg) 候选 URL 列表.

    复用番号→DMM cid 构造器，取竖版 ps 候选。
    """
    return [url for orient, url in generate_image_candidates(number) if orient == "portrait"]


_DMM_HD_MIN_WIDTH = 700


async def _is_dmm_hd_image(url: str) -> bool:
    """校验 DMM 图是否存在且为高清（宽≥700）.

    awsimgsrc 同一 URL 格式下会返回 147x200 缩略图或 745x1081/1032x1469 高清图，
    仅 check_url 验存在无法区分，需读取分辨率过滤缩略图占位图。
    """
    from mdcx.base.web import get_imgsize

    width, _height = await get_imgsize(url)
    return width >= _DMM_HD_MIN_WIDTH


async def upgrade_dmm_cover(ctx, number: str, cover_url: str, poster_url: str) -> tuple[str, str]:
    """尝试将爬虫低清/水印图升级为 DMM 高清 ps/pl，返回 (cover, poster).

    复用 dmm_direct 生成 awsimgsrc 高清候选，check_url 验证成功后覆盖，
    失败回退原图。无码番号直接跳过。

    探测结果按规范化番号进程内 TTL 缓存（成功缓存高清 URL，失败缓存 None），
    并对同事件循环的并发调用做 in-flight 合并，避免 javbus/javdb/r18dev 等
    站点并行刮削同一番号时重复探测相同候选。
    """
    from mdcx.base.web import check_url

    number = (number or "").strip()
    if not number or is_uncensored_number(number):
        return cover_url, poster_url
    norm = _normalize_dmm_number(number)
    now = time.monotonic()
    with _dmm_cache_lock:
        cached = _dmm_upgrade_cache.get(norm)
    if cached is not None and now - cached[0] < _DMM_UPGRADE_CACHE_TTL:
        cached_cover, cached_poster = cached[1], cached[2]
        if cached_cover and cached_cover != cover_url:
            ctx.debug(f"封面命中 DMM 升级缓存: {cached_cover}")
        return (cached_cover or cover_url), (cached_poster or poster_url)

    loop = asyncio.get_running_loop()
    key = (id(loop), norm)
    with _dmm_cache_lock:
        pending = _dmm_upgrade_pending.get(key)
    if pending is not None and not pending.done():
        return await pending

    future = loop.create_future()
    with _dmm_cache_lock:
        _dmm_upgrade_pending[key] = future
    try:
        cover_found = ""
        for url in build_aws_cover_candidates(number):
            if await check_url(url) and await _is_dmm_hd_image(url):
                cover_found = url
                break
        poster_found = ""
        for url in build_aws_poster_candidates(number):
            if await check_url(url) and await _is_dmm_hd_image(url):
                poster_found = url
                break
        if cover_found and cover_found != cover_url:
            ctx.debug(f"封面升级为高清: {cover_found}")
        if poster_found and poster_found != poster_url:
            ctx.debug(f"海报升级为高清竖版: {poster_found}")
        result = (cover_found or cover_url), (poster_found or poster_url)
        now = time.monotonic()
        with _dmm_cache_lock:
            _dmm_upgrade_cache[norm] = (now, cover_found or None, poster_found or None)
            _prune_dmm_upgrade_cache(now)
        if not future.done():
            future.set_result(result)
        return result
    except BaseException as exc:
        if not future.done():
            future.set_exception(exc)
        raise
    finally:
        with _dmm_cache_lock:
            _dmm_upgrade_pending.pop(key, None)
