"""
演员库维护工具。

从刮削流程剥离出的翻译补全与 LibreDMM 链接补全能力，供「工具」页独立批量触发。
"""

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path

import aiofiles.os
import zhconv
from lxml import etree

from ..config.manager import manager
from ..config.resources import DB_HEADERS, resources
from ..core.tmdb_actor import (
    _fetch_person_translations,
    _format_db_worksheet,
    _get_db_path,
    _normalize_translation,
    fetch_libredmm_link,
    search_actor_db_reverse,
    update_actor_db_row,
)
from ..models.log_buffer import LogBuffer
from ..utils import get_used_time


@dataclass
class ActorDbToolResult:
    total: int = 0
    translated: int = 0
    linked: int = 0
    skipped: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)


def _log_line(message: str) -> None:
    LogBuffer.log().write(message)


async def collect_actors_from_nfo_dir(dir_path: Path) -> list[str]:
    """递归扫描 nfo 目录，解析 //actor/name 收集演员名并去重。"""
    if not await aiofiles.os.path.isdir(dir_path):
        return []

    actors: list[str] = []
    seen: set[str] = set()

    async def _walk(current: Path) -> None:
        try:
            entries = await aiofiles.os.scandir(current)
        except OSError:
            return
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=True):
                    await _walk(Path(entry.path))
                elif entry.name.lower().endswith(".nfo"):
                    await _collect_from_nfo(Path(entry.path), actors, seen)
            except OSError:
                continue

    await _walk(dir_path)
    return actors


async def _collect_from_nfo(nfo_path: Path, actors: list[str], seen: set[str]) -> None:
    try:
        async with aiofiles.open(nfo_path, encoding="utf-8") as f:
            content = await f.read()
    except (OSError, UnicodeDecodeError):
        return
    parser = etree.XMLParser(encoding="utf-8", recover=True)
    try:
        xml_nfo = etree.fromstring(content.encode("utf-8"), parser)
    except etree.XMLSyntaxError:
        return
    if xml_nfo is None:
        return
    for ae in xml_nfo.xpath("//actor"):
        name = "".join(ae.xpath("name/text()")).strip()
        if name and name not in seen:
            seen.add(name)
            actors.append(name)


def _tmdb_config() -> tuple[str, str]:
    """返回 (base_url, api_key)。未配置 API Key 时返回空 api_key。"""
    tmdb_api_key = manager.config.tmdb_api_key.strip()
    tmdb_api_base = manager.config.tmdb_api_base.strip()
    if not tmdb_api_key:
        return "", ""
    if not tmdb_api_base:
        tmdb_api_base = "api.tmdb.org"
    protocol = "https://"
    if tmdb_api_base.startswith("http://"):
        protocol = "http://"
        tmdb_api_base = tmdb_api_base[7:]
    elif tmdb_api_base.startswith("https://"):
        protocol = "https://"
        tmdb_api_base = tmdb_api_base[8:]
    base_url = f"{protocol}{tmdb_api_base}" if tmdb_api_base else "https://api.tmdb.org"
    return base_url, tmdb_api_key


async def run(
    actor_names: list[str],
    translate: bool = True,
    link: bool = True,
    output_dir: Path | None = None,
) -> ActorDbToolResult:
    """批量维护演员库：补全翻译（中文/繁体）与 LibreDMM 链接。"""
    result = ActorDbToolResult(total=len(actor_names))
    names = [a.strip() for a in actor_names if a and a.strip()]
    names = list(dict.fromkeys(names))  # 去重保序
    if not names:
        return result

    base_url, tmdb_api_key = _tmdb_config()
    if not tmdb_api_key:
        _log_line(" ⚠️ [演员库维护] 未配置 TMDB API Key，仅能执行链接补全（如需翻译补全请先配置 TMDB API）")

    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    _wb = None
    try:
        import openpyxl as _openpyxl

        if db_path.exists():
            _wb = _openpyxl.load_workbook(db_path)
        else:
            _wb = _openpyxl.Workbook()
            _ws = _wb.active
            _ws.title = "演员数据库"
            for _col, _header in enumerate(DB_HEADERS, 1):
                _cell = _ws.cell(row=1, column=_col, value=_header)
                _cell.font = _openpyxl.styles.Font(bold=True)
                _cell.fill = _openpyxl.styles.PatternFill("solid", fgColor="C0C0C0")
                _cell.alignment = _openpyxl.styles.Alignment(horizontal="center")
    except ImportError:
        _wb = None

    start_time = time.time()
    _log_line(f" 🎬 [演员库维护] 开始处理 {len(names)} 个演员 (翻译={translate}, 链接={link})")

    import aiohttp

    async with aiohttp.ClientSession() as client:
        semaphore = asyncio.Semaphore(3)

        async def _process_one(actor_name: str) -> None:
            async with semaphore:
                try:
                    row = search_actor_db_reverse(actor_name)
                    tmdbid = (row or {}).get("tmdbid")
                    jp_name = (row or {}).get("jp") or actor_name

                    did_translate = False
                    did_link = False

                    # 翻译补全：已有 tmdbid 但缺 zh_cn/zh_tw
                    if translate and tmdbid and base_url and tmdb_api_key:
                        if not (row or {}).get("zh_cn") or not (row or {}).get("zh_tw"):
                            translations = await _fetch_person_translations(tmdbid, base_url, tmdb_api_key, client)
                            zh_cn = _normalize_translation(translations.get("zh_cn", ""))
                            zh_tw = _normalize_translation(translations.get("zh_tw", ""))
                            if not zh_cn and zh_tw:
                                zh_cn = zhconv.convert(zh_tw, "zh-cn")
                            if not zh_tw and zh_cn:
                                zh_tw = zhconv.convert(zh_cn, "zh-hant")
                            if zh_cn or zh_tw:
                                status = await update_actor_db_row(
                                    jp=jp_name,
                                    zh_cn=zh_cn,
                                    zh_tw=zh_tw,
                                    tmdbid=tmdbid,
                                    overwrite_names=True,
                                    _wb=_wb,
                                )
                                did_translate = True
                                result.translated += 1
                                _log_line(
                                    f"  🔄 [演员库维护] {actor_name} 翻译补全: zh_cn={zh_cn or '-'} zh_tw={zh_tw or '-'} ({status})"
                                )

                    # 链接补全：已有 tmdbid 但缺 href
                    if link and tmdbid and not (row or {}).get("href"):
                        href = await fetch_libredmm_link(jp_name)
                        if href:
                            await update_actor_db_row(jp=jp_name, href=href, _wb=_wb)
                            did_link = True
                            result.linked += 1
                            _log_line(f"  ✅ [演员库维护] {actor_name} -> {href}")
                        else:
                            _log_line(f"  ⚠️ [演员库维护] {actor_name} 未在 LibreDMM 找到链接")

                    if not did_translate and not did_link:
                        reason = "无 tmdbid" if not tmdbid else "数据已完整"
                        result.skipped += 1
                        _log_line(f"  ℹ️ [演员库维护] {actor_name} 跳过 ({reason})")
                except Exception as e:
                    result.failed.append((actor_name, str(e)))
                    _log_line(f"  ❌ [演员库维护] {actor_name} 处理失败: {e}")

        tasks = [asyncio.create_task(_process_one(name)) for name in names]
        await asyncio.gather(*tasks)

    # 落盘 + 重载内存缓存
    if _wb is not None:
        try:
            _ws = _wb.active
            _format_db_worksheet(_ws)
            _wb.save(db_path)
            _wb.close()
            resources.reload_actor_db()
            _log_line(" ✅ [演员库维护] 已保存 actor_database.xlsx 并重载内存缓存")
        except Exception as e:
            _log_line(f" ❌ [演员库维护] 落盘失败，写入可能未保存: {e}")

    _log_line(
        f" 🎬 [演员库维护] 完成: 共 {result.total} 个, 翻译补全 {result.translated}, "
        f"链接补全 {result.linked}, 跳过 {result.skipped}, 失败 {len(result.failed)} ({get_used_time(start_time)}s)"
    )
    return result
