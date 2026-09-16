"""审查修复项回归测试。

覆盖本轮代码审查中修复但尚未有针对性测试的项：
- get_new_release 非标准日期格式容错
- parse_runtime 各格式分支（含 "95分"/"min" 与容错）
- read_link_sync 符号链接环防护
- is_proxy_host 各匹配分支
- _replace_dir_atomic 目录原子替换与失败回滚
"""

import aiofiles
import pytest

from mdcx.base.file import movie_lists
from mdcx.config.enums import NoEscape
from mdcx.config.manager import manager
from mdcx.core.web import _replace_dir_atomic
from mdcx.crawlers.base.parser import parse_runtime
from mdcx.utils import get_new_release
from mdcx.utils.file import read_link_sync
from mdcx.web_async import is_proxy_host

# ---- get_new_release：非标准日期格式容错（修复 findall[0] 越界崩溃）----


def test_get_new_release_standard_format():
    assert get_new_release("2026-08-23", "YYYY.MM.DD") == "2026.08.23"
    assert get_new_release("2026-08-23", "YY.MM.DD") == "26.08.23"


def test_get_new_release_non_standard_format_returns_original():
    # 非 YYYY-MM-DD 格式不再崩溃，原样返回
    assert get_new_release("2026/08/23", "YYYY.MM.DD") == "2026/08/23"
    assert get_new_release("未知", "YYYY.MM.DD") == "未知"


def test_get_new_release_empty_release():
    assert get_new_release("", "YYYY.MM.DD") == "0000.00.00"
    assert get_new_release("", "YYYY-MM-DD") == "0000-00-00"


# ---- parse_runtime：时长解析统一与容错 ----


def test_parse_runtime_hh_mm_ss_ignores_seconds():
    assert parse_runtime("1:20:30") == "80"


def test_parse_runtime_hh_mm():
    assert parse_runtime("1:20") == "80"


def test_parse_runtime_minutes_variants():
    assert parse_runtime("95") == "95"
    assert parse_runtime("95分") == "95"
    assert parse_runtime("95min") == "95"


def test_parse_runtime_non_numeric_safe():
    assert parse_runtime("未知:xx") == ""
    assert parse_runtime("") == ""


# ---- read_link_sync：符号链接环防护 ----


def test_read_link_sync_resolves_normal_link(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("x")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    assert read_link_sync(str(link)) == str(target)


def test_read_link_sync_resolves_relative_link_from_link_directory(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("x")
    link_dir = tmp_path / "nested"
    link_dir.mkdir()
    link = link_dir / "link.txt"
    link.symlink_to("../target.txt")

    assert read_link_sync(link) == str(target)


def test_read_link_sync_breaks_cycle(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.symlink_to(b)
    b.symlink_to(a)
    # 成环（a→b→a）不无限循环；seen 命中后返回当前路径
    assert read_link_sync(str(a)) in {str(a), str(b)}


@pytest.mark.asyncio
async def test_movie_lists_skips_duplicate_symlink_targets_without_deleting_links(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = source_dir / "movie.mp4"
    source.write_bytes(b"video")
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first_link = first_dir / "movie.mp4"
    second_link = second_dir / "movie.mp4"
    first_link.symlink_to("../source/movie.mp4")
    second_link.symlink_to("../source/movie.mp4")
    monkeypatch.setattr(manager.config, "clean_enable", [])
    monkeypatch.setattr(manager.config, "no_escape", [NoEscape.CHECK_SYMLINK])

    movies = await movie_lists([], [".mp4"], tmp_path)

    assert sum(path.is_symlink() for path in movies) == 1
    assert first_link.is_symlink()
    assert second_link.is_symlink()


# ---- is_proxy_host：匹配分支回归（白名单直连模式，语义取反）----


def test_is_proxy_host_direct_and_subdomain():
    # 命中直连白名单 → False（不走代理）
    assert not is_proxy_host("javdb.com", ["javdb.com"])
    assert not is_proxy_host("api.javdb.com", ["javdb.com"])
    # 未命中 → True（走代理）
    assert is_proxy_host("example.com", ["javdb.com"])


def test_is_proxy_host_web_dic_mapping():
    assert not is_proxy_host("javdb.com", ["javdb"])
    assert not is_proxy_host("www.javdb.net", ["javdb"])
    assert is_proxy_host("example.com", ["javdb"])


def test_is_proxy_host_tld_fallback():
    assert not is_proxy_host("libredmm.com", ["libredmm"])
    assert not is_proxy_host("api.libredmm.com", ["libredmm"])
    assert is_proxy_host("example.com", ["libredmm"])


def test_is_proxy_host_empty_list_all_proxy():
    # 空白名单 = 所有站点走代理
    assert is_proxy_host("javdb.com", [])
    assert is_proxy_host("example.com", [])
    assert is_proxy_host("", [])
    assert is_proxy_host("javdb.com", None)


def test_is_proxy_host_wildcard_match_all():
    # "全部流量走代理"开关注入 "*" 时——注意：* 现在表示直连通配（所有 host 直连）
    # 一般场景下不会用 *，但保留兼容性
    assert not is_proxy_host("javdb.com", ["*"])
    assert not is_proxy_host("anything.example", ["*"])
    assert not is_proxy_host("dmm.co.jp", ["javdb", "*"])


# ---- 议题 #83：UI 按 crawler 站点值选代理，实际请求域名必须命中 ----


@pytest.mark.parametrize(
    ("site_value", "host"),
    [
        # 议题附检测日志中的失配证据逐条锁定
        ("missav", "missav.ai"),
        ("missav", "missav.ws"),
        ("javday", "javday.app"),
        ("mywife", "mywife.cc"),
        ("7mmtv", "www.7mmtv.sx"),
        ("7mmtv", "7mmtv.sx"),
        ("7mmtv", "7tv022.com"),
        ("madou_club", "madou.club"),
        ("javlibrary", "www.f101w.com"),
        ("javlibrary", "f101w.com"),
        # 原有命中路径不回退（WEB_DIC 映射与 TLD 兜底）
        ("lulubar", "lulubar.co"),
        ("javdb", "javdb.com"),
    ],
)
def test_proxy_host_matches_crawler_declared_domains(site_value, host):
    """站点值（UI 下拉框所选 crawler 名）必须命中爬虫声明的真实域名/镜像。

    白名单直连模式：站点域名命中 direct_sites 则返 False（直连），否则返 True（走代理）。
    """
    assert not is_proxy_host(host, [site_value]), f"站点 {site_value} 的域名 {host} 应直连（不走代理）"


def test_proxy_host_no_false_positive():
    # 近似名不应误命中无关域名
    assert is_proxy_host("missav.example.com", ["missav"])
    assert is_proxy_host("google.com", ["missav", "javdb", "7mmtv"])


# ---- _replace_dir_atomic：目录原子替换与失败回滚 ----


@pytest.mark.asyncio
async def test_replace_dir_atomic_success(tmp_path):
    target = tmp_path / "extrafanart"
    temp = tmp_path / "extrafanart[DOWNLOAD]"
    target.mkdir()
    (target / "old.jpg").write_bytes(b"old")
    temp.mkdir()
    (temp / "new.jpg").write_bytes(b"new")

    await _replace_dir_atomic(temp, target)

    assert (target / "new.jpg").exists()
    assert not (target / "old.jpg").exists()
    assert not temp.exists()
    assert not (tmp_path / "extrafanart.old").exists()


@pytest.mark.asyncio
async def test_replace_dir_atomic_rollback_on_failure(tmp_path, monkeypatch):
    target = tmp_path / "extrafanart"
    temp = tmp_path / "extrafanart[DOWNLOAD]"
    target.mkdir()
    (target / "old.jpg").write_bytes(b"old")
    temp.mkdir()
    (temp / "new.jpg").write_bytes(b"new")

    real_rename = aiofiles.os.rename

    async def failing_rename(src, dst, *args, **kwargs):
        if src == temp:
            raise OSError("simulated failure")
        return await real_rename(src, dst, *args, **kwargs)

    monkeypatch.setattr(aiofiles.os, "rename", failing_rename)

    with pytest.raises(OSError):
        await _replace_dir_atomic(temp, target)

    # 旧目录已回滚，新目录保留供下次重试
    assert (target / "old.jpg").exists()
    assert temp.exists()
