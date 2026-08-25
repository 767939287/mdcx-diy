from ..config.models import Website
from . import (
    avbase,
    avsox,
    cableav,
    dahlia,
    dmm_api,
    faleno,
    fantastica,
    giga,
    hscangku,
    jav321,
    javday,
    lulubar,
    madouqu,
    mgstage,
    missav,
    mmtv,
    thejavdb_api,
    xcity,
)
from .airav_cc import AiravCcCrawler
from .avbase import AvbaseCrawler
from .avheat import AvheatCrawler
from .avmoo import AvmooCrawler
from .avsex import AvsexCrawler
from .avsox import AvsoxCrawler
from .base import get_crawler, get_registered_crawler_sites, register_crawler
from .cableav import CableavCrawler
from .dahlia import DahliaCrawler
from .dmm import DmmCrawler
from .faleno import FalenoCrawler
from .fantastica import FantasticaCrawler
from .fc2 import Fc2Crawler
from .fc2club import Fc2clubCrawler
from .fc2hub import Fc2hubCrawler
from .fc2ppvdb import Fc2ppvdbCrawler
from .freejavbt import FreejavbtCrawler
from .getchu import GetchuCrawler
from .giga import GigaCrawler
from .hscangku import HscangkuCrawler
from .iqqtv import IqqtvCrawler
from .jav321 import Jav321Crawler
from .javbus import JavbusCrawler
from .javday import JavdayCrawler
from .javdb import JavdbCrawler
from .javdb_api import JavdbApiCrawler
from .javdb_app import JavdbAppCrawler
from .javlibrary import JavlibraryCrawler
from .libredmm import LibredmmCrawler
from .lulubar import LulubarCrawler
from .madou_club import MadouClubCrawler
from .madouqu import MadouquCrawler
from .mgstage import MgstageCrawler
from .missav import MissavCrawler
from .missav_api import MissavApiCrawler
from .mmtv import MmtvCrawler
from .mywife import MywifeCrawler
from .official import OfficialCrawler
from .prestige import PrestigeCrawler
from .r18dev import R18devCrawler
from .thejavdb_api import TheJavdbApiCrawler
from .theporndb import TheporndbCrawler
from .xcity import XcityCrawler

register_crawler(DmmCrawler)
register_crawler(JavdbCrawler)
register_crawler(JavdbApiCrawler)
register_crawler(JavdbAppCrawler)
register_crawler(dmm_api.DmmApiCrawler)
register_crawler(TheJavdbApiCrawler)
register_crawler(AvbaseCrawler)
register_crawler(missav.MissavCrawler)
register_crawler(MissavApiCrawler)
register_crawler(FalenoCrawler)
register_crawler(Jav321Crawler)
register_crawler(CableavCrawler)
register_crawler(MadouquCrawler)
register_crawler(MadouClubCrawler)
register_crawler(MmtvCrawler)
register_crawler(DahliaCrawler)
register_crawler(FantasticaCrawler)
register_crawler(AvsoxCrawler)
register_crawler(AvmooCrawler)
register_crawler(AvheatCrawler)
register_crawler(HscangkuCrawler)
register_crawler(LibredmmCrawler)
register_crawler(LulubarCrawler)
register_crawler(XcityCrawler)
register_crawler(GigaCrawler)
register_crawler(MgstageCrawler)
register_crawler(JavdayCrawler)
register_crawler(Fc2ppvdbCrawler)
register_crawler(PrestigeCrawler)
register_crawler(R18devCrawler)
register_crawler(Fc2clubCrawler)
register_crawler(Fc2Crawler)
register_crawler(Fc2hubCrawler)
register_crawler(JavbusCrawler)
register_crawler(FreejavbtCrawler)
register_crawler(IqqtvCrawler)
register_crawler(AiravCcCrawler)
register_crawler(AvsexCrawler)
register_crawler(GetchuCrawler)
register_crawler(MywifeCrawler)
register_crawler(JavlibraryCrawler)
register_crawler(OfficialCrawler)
register_crawler(TheporndbCrawler)


def get_registered_crawler_site_values(*, include_hidden: bool = False) -> list[str]:
    """返回已注册刮削器的网站值, 用于 UI 动态填充."""
    return [site.value for site in get_registered_crawler_sites(include_hidden=include_hidden)]
