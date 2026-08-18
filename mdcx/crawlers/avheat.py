#!/usr/bin/env python3
from typing import override

from ..config.models import Website
from .aio_site import AioSiteCrawler


class AvheatCrawler(AioSiteCrawler):
    namespace = "wav"
    domain_site = "avheat"
    fallback_domain = "https://avheat.shop"
    mosaic = "欧美"
    with_outline = True

    @classmethod
    @override
    def site(cls) -> Website:
        return Website.AVHEAT
