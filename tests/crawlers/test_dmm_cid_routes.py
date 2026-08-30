"""静态路由种子（dmm_cid_routes.json）集成回归测试。

背景：libredmm 全站 23472 页 58.9 万番号↔cid 对归纳为规则 + 白名单，经
安全过滤（仅 digital 路径 + 5 位补零 + 无变体，弃用与生产静态表冲突的
系列——libredmm 同名番号被 mono 老厂牌占据，直接注入会污染高频系列
候选顺序：SSIS-001 首候选会被错排成老厂牌 ssis001）。
路由把静态表盲枚举（_COMMON_PREFIXES 10 连试）变成一步直达，且不再
需要运行时请求 libredmm。

测试在 conftest 的 dummy resources 下运行，种子经 monkeypatch 指向真实文件。
"""

import json
from pathlib import Path

import pytest

from mdcx.crawlers import dmm_direct

SEED_PATH = Path(__file__).resolve().parents[2] / "resources" / "userdata" / "dmm_cid_routes.json"


@pytest.fixture(autouse=True)
def _real_routes(monkeypatch):
    """注入真实种子文件路径并复位路由表，测试后再次复位。"""
    if not SEED_PATH.is_file():
        pytest.skip("种子文件不存在")
    monkeypatch.setattr(dmm_direct, "_routes_seed_path", lambda: SEED_PATH)
    dmm_direct.reset_routes_for_testing()
    yield
    dmm_direct.reset_routes_for_testing()


def test_seed_file_shape():
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert isinstance(data["rules"], dict) and len(data["rules"]) > 6000
    assert isinstance(data["whitelist"], dict) and len(data["whitelist"]) > 10000  # 规则条目结构
    letters, combos = next(iter(data["rules"].items()))
    assert isinstance(letters, str) and letters.isupper()
    combo = combos[0]
    assert {"p", "s", "pads", "paths"} <= set(combo.keys())
    assert all(isinstance(p, int) and p > 0 for p in combo["pads"])
    assert all(str(p).startswith(("digital", "mono")) for p in combo["paths"])


def test_seed_high_frequency_series_excluded():
    """高频主流系列必须不在规则/白名单中（同名 mono 老厂牌数据会污染候选顺序）。"""
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    for series in ("SSIS", "IPX", "SONE", "MIDV", "CAWD", "ABF", "SW", "WANZ"):
        assert series not in data["rules"], f"{series} 不应留在规则中"
    for number in ("IPX-399", "SONE-006", "ABF-171"):
        assert number not in data["whitelist"], f"{number} 不应留在白名单中"


def test_route_hit_step_reach():
    """路由系列一步直达：AAJB 真实 cid 是基线盲枚举第 4 位，路由后首候选命中。"""
    cids = dmm_direct.generate_cid_candidates("AAJB-100")
    assert cids[0] == "h_308aajb00100"


def test_whitelist_hit_returns_exact_cid():
    """白名单特例番号：直接返回唯一真实 cid，不落规则枚举。"""
    cids = dmm_direct.generate_cid_candidates("13ID-003")
    assert cids == ["h_113id00003"]


def test_whitelist_image_candidates_use_recorded_path():
    """白名单 digital 路径的图应走 awsimgsrc 高清 CDN。"""
    candidates = dmm_direct.generate_image_candidates("13ID-003")
    urls = [url for _, url in candidates]
    assert urls[0] == "https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/h_113id00003/h_113id00003ps.jpg"
    assert any("pl.jpg" in u for u in urls)


def test_high_frequency_series_first_candidate_unchanged():
    """高频系列首候选不被路由污染（安全过滤回归保护）。"""
    expected = {
        "SSIS-001": "ssis00001",
        "IPX-535": "ipx00535",
        "SONE-833": "sone00833",
        "MIDV-100": "midv00100",
        "CAWD-500": "cawd00500",
        "ABF-042": "436abf00042",
        "SW-123": "1sw00123",
        "WANZ-100": "3wanz00100",
    }
    for number, first in expected.items():
        cids = dmm_direct.generate_cid_candidates(number)
        assert cids[0] == first, f"{number}: 首候选 {cids[0]} != {first}"


def test_static_candidates_still_work_for_unrouted_series():
    """未收录系列的既有静态表行为不变（回归保护）。"""
    cids = dmm_direct.generate_cid_candidates("SSIS-001")
    assert cids[0] == "ssis00001"


def test_invalid_number_returns_empty():
    assert dmm_direct.generate_cid_candidates("") == []
    assert dmm_direct.generate_cid_candidates("12345") == []


def test_routes_load_failure_degrades_silently(monkeypatch):
    """种子损坏时静默降级为空表，不影响既有候选链。"""
    bad = Path("/tmp/opencode/bad_routes.json")
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(dmm_direct, "_routes_seed_path", lambda: bad)
    dmm_direct.reset_routes_for_testing()
    try:
        cids = dmm_direct.generate_cid_candidates("SSIS-001")
        assert cids[0] == "ssis00001"
    finally:
        dmm_direct.reset_routes_for_testing()
