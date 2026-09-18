import re
from dataclasses import dataclass, field
from datetime import date

# 议题 #145: 宽松匹配各种合法生日写法（1990-1-2 / 1990/1/2 / 1990.1.2 / 1990年1月2日 / 19900102）。
# 允许非零填充，月/日交给 date() 做真实日历校验；不锚定结尾，忽略尾部时间等多余内容。
_DATE_TEXT_RE = re.compile(r"^(\d{4})\s*[-/.\s年]\s*(\d{1,2})\s*[-/.\s月]\s*(\d{1,2})\s*日?")
_DATE_COMPACT_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})")


def normalize_premiere_date(value: object) -> str | None:
    """生日归一化为服务器可解析的 ISO 时间串，无法构成合法日期时返回 None。

    接受 1990-1-2 / 1990/1/2 / 1990.1.2 / 1990年1月2日 / 19900102 等写法（议题 #145），
    补零并用真实日历校验后输出 Emby/Jellyfin DTO 规范格式。哨兵 "0000-xx-xx"、
    空值、截断串、越界日期（13 月 / 2 月 30 等）返回 None，调用方据此省略 PremiereDate
    （议题 #126）。返回 None 而非空串，避免模型绑定 DateTime 时再报 400。
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text.startswith("0000"):
        return None
    match = _DATE_TEXT_RE.match(text) or _DATE_COMPACT_RE.match(text)
    if match is None:
        return None
    try:
        year, month, day = (int(part) for part in match.groups())
        date(year, month, day)
    except ValueError:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}T00:00:00.0000000Z"


def normalize_production_year(value: object) -> int | None:
    """年份字段归一化为正整数；哨兵 "0000"、非数字、非正数一律视为空（议题 #126）。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        year = int(value.strip())
        return year if year > 0 else None
    return None


@dataclass
class EMbyActressInfo:
    name: str
    server_id: str
    id: str
    birthday: str = "0000-00-00"
    year: str = "0000"
    overview: str = ""
    taglines: list = field(default_factory=list)
    genres: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    provider_ids: dict = field(default_factory=dict)
    taglines_translate: bool = False
    locations: list = field(default_factory=list)

    def dump(self) -> dict:
        # 此处生成的 json 符合 emby/jellyfin 规范；
        # 日期/年份在模型层统一归一化，内置补全与管理器同步共用同一出口（议题 #126/#145）。
        return {
            "Name": self.name,
            "ServerId": self.server_id,
            "Id": self.id,
            "Genres": self.genres,
            "Tags": self.tags,
            "ProviderIds": self.provider_ids,
            "ProductionLocations": self.locations,
            "PremiereDate": normalize_premiere_date(self.birthday),
            "ProductionYear": normalize_production_year(self.year),
            "Overview": self.overview,
            "Taglines": self.taglines,
        }
