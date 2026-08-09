"""AVWikiDB 别名查询功能单元测试。

通过 mock AsyncSession.get 返回模拟搜索页/详情页 HTML，验证：
- 正常查询能提取别名
- 搜索无结果返回空
- 主名不匹配（防错）返回空
- 详情页无别名返回空
- 请求异常静默返回空
"""

from types import SimpleNamespace

import pytest

from mdcx.core import tmdb_actor

# 模拟详情页 HTML（结构与真实 AVWikiDB Next.js SSR 一致）
DETAIL_HTML_NOZOMI = """
<html><body>
<div class="mt-2 mb-3">
  <div>
    <h1 class="!mt-0 !mb-0 text-xl">有村のぞみ</h1>
    <p class="mt-1 text-muted-foreground text-sm">ありむら のぞみ / Nozomi Arimura</p>
    <p class="mt-1 text-muted-foreground text-sm">別名<!-- -->:<!-- -->
      <a class="underline" href="https://al.dmm.co.jp/?lurl=x" rel="noopener sponsored" target="_blank">早川ひとみ</a>,
      <a class="underline" href="https://al.dmm.co.jp/?lurl=y" rel="noopener sponsored" target="_blank">澤村香（SOD女子社員）</a>
    </p>
  </div>
</div>
</body></html>
"""

DETAIL_HTML_YUMI = """
<html><body>
<div class="mt-2 mb-3">
  <div>
    <h1 class="!mt-0 !mb-0 text-xl">虹村ゆみ</h1>
    <p class="mt-1 text-muted-foreground text-sm">にじむら ゆみ / Yumi Nijimura</p>
    <p class="mt-1 text-muted-foreground text-sm">別名<!-- -->:<!-- -->
      <a class="underline" href="https://al.dmm.co.jp/?lurl=z" rel="noopener sponsored" target="_blank">安藤季世</a>
    </p>
  </div>
</div>
</body></html>
"""

# 无别名详情页
DETAIL_HTML_NO_ALIAS = """
<html><body>
<div class="mt-2 mb-3">
  <div>
    <h1 class="!mt-0 !mb-0 text-xl">某演员</h1>
    <p class="mt-1 text-muted-foreground text-sm">ぼう えんいん / Bo Enin</p>
  </div>
</div>
</body></html>
"""

SEARCH_HTML_NOZOMI = """
<html><body>
<main>
  <ul>
    <li><a href="/actor/1043123/">有村のぞみ</a></li>
    <li><a href="/actor/999/">别的演员</a></li>
  </ul>
</main>
</body></html>
"""

SEARCH_HTML_EMPTY = """
<html><body>
<main><ul><li><a href="/actor/">没有结果</a></li></ul></main>
</body></html>
"""


class _FakeResp:
    def __init__(self, html: str, status: int = 200):
        self.text = html
        self.status_code = status


def _install_fake_session(monkeypatch, search_html: str, detail_html: str):
    """mock _avwiki_session.get，按 URL 区分返回搜索页或详情页。"""

    async def fake_get(url, params=None, headers=None, **kwargs):
        if "search" in url:
            return _FakeResp(search_html)
        return _FakeResp(detail_html)

    fake_session = SimpleNamespace(get=fake_get)
    monkeypatch.setattr(tmdb_actor, "_avwiki_session", fake_session)


def _install_fake_status(monkeypatch, status: int):
    async def fake_get(url, params=None, headers=None, **kwargs):
        return _FakeResp("<html></html>", status)

    fake_session = SimpleNamespace(get=fake_get)
    monkeypatch.setattr(tmdb_actor, "_avwiki_session", fake_session)


@pytest.mark.asyncio
async def test_avwiki_fetch_aliases_normal(monkeypatch):
    _install_fake_session(monkeypatch, SEARCH_HTML_NOZOMI, DETAIL_HTML_NOZOMI)
    aliases = await tmdb_actor.fetch_avwiki_aliases("有村のぞみ")
    assert aliases == ["早川ひとみ", "澤村香（SOD女子社員）"]


@pytest.mark.asyncio
async def test_avwiki_fetch_aliases_single_alias(monkeypatch):
    _install_fake_session(monkeypatch, SEARCH_HTML_NOZOMI, DETAIL_HTML_YUMI)
    aliases = await tmdb_actor.fetch_avwiki_aliases("虹村ゆみ")
    assert aliases == ["安藤季世"]


@pytest.mark.asyncio
async def test_avwiki_search_empty_returns_empty(monkeypatch):
    _install_fake_session(monkeypatch, SEARCH_HTML_EMPTY, DETAIL_HTML_NOZOMI)
    aliases = await tmdb_actor.fetch_avwiki_aliases("不存在的人")
    assert aliases == []


@pytest.mark.asyncio
async def test_avwiki_detail_no_alias_returns_empty(monkeypatch):
    _install_fake_session(monkeypatch, SEARCH_HTML_NOZOMI, DETAIL_HTML_NO_ALIAS)
    aliases = await tmdb_actor.fetch_avwiki_aliases("某演员")
    assert aliases == []


@pytest.mark.asyncio
async def test_avwiki_main_name_mismatch_returns_empty(monkeypatch):
    """搜索页返回 A 演员链接，但详情页主名与查询名差异大 → 防错拒绝。"""
    _install_fake_session(monkeypatch, SEARCH_HTML_NOZOMI, DETAIL_HTML_YUMI)
    aliases = await tmdb_actor.fetch_avwiki_aliases("完全无关的名字")
    assert aliases == []


@pytest.mark.asyncio
async def test_avwiki_http_403_returns_empty(monkeypatch):
    _install_fake_status(monkeypatch, 403)
    aliases = await tmdb_actor.fetch_avwiki_aliases("有村のぞみ")
    assert aliases == []


@pytest.mark.asyncio
async def test_avwiki_exception_returns_empty(monkeypatch):
    async def boom(url, params=None, headers=None, **kwargs):
        raise RuntimeError("network down")

    fake_session = SimpleNamespace(get=boom)
    monkeypatch.setattr(tmdb_actor, "_avwiki_session", fake_session)
    aliases = await tmdb_actor.fetch_avwiki_aliases("有村のぞみ")
    assert aliases == []


@pytest.mark.asyncio
async def test_avwiki_empty_name_returns_empty():
    assert await tmdb_actor.fetch_avwiki_aliases("") == []
    assert await tmdb_actor.fetch_avwiki_aliases("   ") == []


@pytest.mark.asyncio
async def test_avwiki_trailing_slash_detail_url(monkeypatch):
    """详情 href 为绝对 URL 时也能正确处理。"""
    search_html = """
    <html><body><main><ul><li><a href="https://avwikidb.com/actor/1043123/">有村のぞみ</a></li></ul></main></body></html>
    """
    _install_fake_session(monkeypatch, search_html, DETAIL_HTML_NOZOMI)
    aliases = await tmdb_actor.fetch_avwiki_aliases("有村のぞみ")
    assert aliases == ["早川ひとみ", "澤村香（SOD女子社員）"]
