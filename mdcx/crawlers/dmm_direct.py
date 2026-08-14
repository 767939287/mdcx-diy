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
    "": [
        "adn",
        "cawd",
        "ebod",
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
        "meyd",
        "miab",
        "miad",
        "mibd",
        "mide",
        "midv",
        "mifd",
        "mtsp",
        "mvsd",
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
        "dvdes",
        "fcdss",
        "fset",
        "fsdss",
        "gs",
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
    "49": ["avop", "madm"],
    "55": ["t28"],
    "57": ["bdsr"],
    "83": ["sma"],
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
    "h_189": ["ymd"],
    "h_237": ["nact"],
    "h_910": ["vrtm"],
    "h_995": ["bokd"],
}

# 同名系列跨厂商前缀不同（如 sw: SWITCH=1、プラム=h_113），附加候选前缀兜底
_EXTRA_PREFIXES: dict[str, list[str]] = {
    "sw": ["h_113"],
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


def is_uncensored_number(number: str) -> bool:
    """DMM 是有码源，判断番号是否为明显无码（含 `_` 或命中无码前缀），用于跳过 DMM 候选."""
    if "_" in number:
        return True
    return (number or "").upper().replace(" ", "").startswith(_UNCENSORED_PREFIXES)
