"""番号 -> DMM 官方 CDN 高清图直链构造。

DMM 官方高清封面托管在 awsimgsrc CDN，URL 规律:
    https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/{cid}/{cid}pl.jpg   (横版高清, 如 2184x1469)
    https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/{cid}/{cid}ps.jpg   (竖版高清, 如 1032x1469)

cid = {mPrefix}{series}{编号5位补零}，mPrefix 由品牌(series)决定，不同品牌有各自的目录前缀。
该 CDN 对不存在的图直接返回 404(区别于 pics.dmm.co.jp 返回占位图)，适合做无爬虫直连兜底。
"""

from __future__ import annotations

import re

_DMM_CDN_BASE = "https://awsimgsrc.dmm.co.jp/pics_dig/digital/video"

_PREFIX_GROUPS: dict[str, list[str]] = {
    "1": ["dism", "dvdes", "gs", "rct", "rctd", "vandr", "sdfk", "sdjs", "svdvd", "sw"],
    "13": ["ayb", "gg", "gvg", "ovg"],
    "49": ["avop"],
    "55": ["t28"],
    "57": ["bdsr"],
    "83": ["sma"],
    "5642": ["hodv"],
    "h_1324": ["skmj"],
    "h_1371": ["zmen"],
    "h_1374": ["ksvr"],
    "h_237": ["nact"],
    "h_910": ["vrtm"],
    "h_995": ["bokd"],
}

_SPECIAL_THRESHOLDS: dict[str, tuple[int, str, str]] = {
    "avop": (168, "59", "1"),
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
    if series in _SPECIAL_THRESHOLDS:
        threshold, small_prefix, large_prefix = _SPECIAL_THRESHOLDS[series]
        prefix = small_prefix if num <= threshold else large_prefix
        return [prefix]
    for group_prefix, members in _PREFIX_GROUPS.items():
        if series in members:
            return [group_prefix, ""]
    return _COMMON_PREFIXES


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
