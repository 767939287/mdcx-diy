#!/usr/bin/python
import re
from typing import Any, override

from ..config.manager import manager
from ..config.models import Website
from ..models.model_types import CrawlerInput
from .base import BaseCrawler, Context, CrawlerData, CrawlerException

_JP_ACTOR_CACHE: dict[str, str] = {}


async def _fetch_jp_actor_name(actor_id: str, client: Any) -> str | None:
    """从 xcity.jp 源站抓取演员日文名。"""
    if actor_id in _JP_ACTOR_CACHE:
        return _JP_ACTOR_CACHE[actor_id]
    url = f"https://xcity.jp/idol/detail/{actor_id}/"
    html, error = await client.get_text(url)
    if html is None:
        return None
    m = re.search(r"<title>([^(]+?)(?:\s*\(|無料|\||$)", html)
    if m:
        name = m.group(1).strip()
        _JP_ACTOR_CACHE[actor_id] = name
        return name
    return None


class XcityContext(Context):
    cached_program: dict[str, Any] | None = None


class XcityCrawler(BaseCrawler[XcityContext]):
    description = "Xcity 综合（仅能有码）"
    # xcity.jp 缺 SSNI-647（用户实测），ABF-050 已确认收录
    probe_number = "ABF-050"
    # xcity 镜像域名（主站 + 备用；用户配置 custom_url 时优先使用）
    _domains: list[str] = [
        "https://tc.xcity.jp",
        "https://xcity.jp",
    ]

    @override
    def __init__(self, client, base_url: str = "", browser=None):
        super().__init__(client, base_url=base_url, browser=browser)
        self._init_rotator(self._domains, custom_url=manager.config.get_site_url(Website.XCITY, ""))

    @override
    def new_context(self, input: CrawlerInput) -> XcityContext:
        return XcityContext(input=input)

    @classmethod
    @override
    def site(cls) -> Website:
        return Website.XCITY

    @override
    def _get_headers(self, ctx: Context) -> dict[str, str] | None:
        return {"Accept-Language": "zh-TW,zh;q=0.9,ja;q=0.8,en;q=0.5"}

    @classmethod
    @override
    def base_url_(cls) -> str:
        return manager.config.get_site_url(Website.XCITY, "https://tc.xcity.jp")

    @override
    async def _generate_search_url(self, ctx: Context) -> list[str] | str | None:
        return f"{self.base_url}/api/search?q={ctx.input.number.replace('-', '')}"

    @override
    async def _parse_search_page(self, ctx: XcityContext, html: Any, search_url: str) -> list[str] | str | None:
        data = html.get()
        if not isinstance(data, dict):
            ctx.debug(f"xcity 搜索结果格式异常: {type(data).__name__}")
            return None

        program_list = (data.get("frontprogramlist") or {}).get("program") or []
        if not program_list:
            ctx.debug("xcity 搜索没有匹配结果")
            return None

        ctx.cached_program = program_list[0]

        program_id = program_list[0].get("id")
        if program_id:
            return [f"{self.base_url}/avod/detail?id={program_id}"]

        ctx.debug("xcity 搜索结果缺少 id")
        return None

    @override
    async def _parse_detail_page(self, ctx: XcityContext, html: Any, detail_url: str) -> CrawlerData | None:
        program = ctx.cached_program
        if not program:
            raise CrawlerException("xcity 数据缺失: 未获取到节目数据")

        title = program.get("title") or ""
        originaltitle = program.get("titleKana") or title
        if not title:
            raise CrawlerException("数据获取失败: 未获取到title")

        actors = []
        for person in program.get("person") or []:
            name = person.get("name")
            actor_id = person.get("id")
            if name and actor_id:
                jp_name = await _fetch_jp_actor_name(actor_id, self.async_client)
                actors.append(jp_name or name)
            elif name:
                actors.append(name)

        genre = program.get("genre") or []

        release = (program.get("releaseDate") or "").replace("/", "-")

        runtime = str(program.get("duration") or "")

        series_name = ""
        series_data = program.get("series")
        if isinstance(series_data, dict):
            series_name = series_data.get("name") or ""

        maker_name = ""
        maker_data = program.get("maker")
        if isinstance(maker_data, dict):
            maker_name = maker_data.get("name") or ""

        label_name = ""
        label_data = program.get("label")
        if isinstance(label_data, dict):
            label_name = label_data.get("name") or ""

        front_image = (program.get("frontPackageImage") or "").replace("/medium/", "/large/")
        back_image = (program.get("backPackageImage") or "").replace("/medium/", "/large/")

        return CrawlerData(
            number=ctx.input.number,
            title=title,
            originaltitle=originaltitle,
            actors=actors,
            all_actors=actors,
            outline=program.get("synopsis") or "",
            originalplot=program.get("synopsis") or "",
            tags=genre,
            release=release,
            year=release[:4] if len(release) >= 4 else "",
            runtime=runtime,
            series=series_name,
            studio=maker_name,
            publisher=label_name,
            thumb=back_image,
            poster=front_image,
            image_download=False,
            mosaic="有码",
            external_id=detail_url,
        )
