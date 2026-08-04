"""
演员库维护工具。

从刮削流程剥离出的翻译补全与 LibreDMM 链接补全能力，供「工具」页独立批量触发。
"""

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path

import aiofiles.os
import aiohttp
import zhconv
from lxml import etree

from ..config.resources import (
    COL_BIO,
    COL_BIRTH_DATE,
    COL_JP,
    COL_KEYWORD,
    COL_TMDBID,
    COL_ZH_CN,
    COL_ZH_TW,
    DB_HEADERS,
    resources,
)
from ..core.tmdb_actor import (
    _actor_db_write_lock,
    _fetch_person_translations,
    _format_db_worksheet,
    _get_db_path,
    _merge_keyword_values,
    _normalize_translation,
    _resolve_tmdb_config,
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


AVDB_MAPPING_URL = "https://raw.githubusercontent.com/li-peifeng/Jav-Actors-Mapping/main/actor-mapping.xml"
AVDB_MAPPING_URL_MIRROR = "https://cdn.jsdelivr.net/gh/li-peifeng/Jav-Actors-Mapping@main/actor-mapping.xml"


@dataclass
class ActorDbSyncResult:
    downloaded: bool = False
    parsed: int = 0
    created: int = 0
    filled: int = 0
    merged: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)


def _log_line(message: str) -> None:
    LogBuffer.log().write(message)
    from mdcx.signals import signal_qt

    signal_qt.show_log_text(message)


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


async def run(
    actor_names: list[str],
    translate: bool = True,
    link: bool = True,
) -> ActorDbToolResult:
    """批量维护演员库：补全翻译（中文/繁体）与 LibreDMM 链接。"""
    result = ActorDbToolResult(total=len(actor_names))
    names = [a.strip() for a in actor_names if a and a.strip()]
    names = list(dict.fromkeys(names))  # 去重保序
    if not names:
        return result

    base_url, tmdb_api_key = _resolve_tmdb_config()
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

    async with aiohttp.ClientSession() as client:
        semaphore = asyncio.Semaphore(3)

        async def _process_one(actor_name: str) -> None:
            async with semaphore:
                try:
                    row = search_actor_db_reverse(actor_name)
                    tmdbid = (row or {}).get("tmdbid")
                    jp_name = (row or {}).get("jp") or actor_name

                    need_translate = (
                        translate
                        and tmdbid
                        and base_url
                        and tmdb_api_key
                        and (not (row or {}).get("zh_cn") or not (row or {}).get("zh_tw"))
                    )
                    need_link = link and tmdbid and not (row or {}).get("href")

                    if not need_translate and not need_link:
                        reason = "无 tmdbid" if not tmdbid else "数据已完整"
                        result.skipped += 1
                        _log_line(f"  ℹ️ [演员库维护] {actor_name} 跳过 ({reason})")
                        return

                    # 并行拉取翻译和链接
                    async def _fetch_translations():
                        if need_translate:
                            translations = await _fetch_person_translations(tmdbid, base_url, tmdb_api_key, client)
                            zh_cn = _normalize_translation(translations.get("zh_cn", ""))
                            zh_tw = _normalize_translation(translations.get("zh_tw", ""))
                            if not zh_cn and zh_tw:
                                zh_cn = zhconv.convert(zh_tw, "zh-cn")
                            if not zh_tw and zh_cn:
                                zh_tw = zhconv.convert(zh_cn, "zh-hant")
                            return zh_cn, zh_tw
                        return "", ""

                    async def _fetch_href():
                        if need_link:
                            return await fetch_libredmm_link(jp_name)
                        return ""

                    zh_cn, zh_tw = "", ""
                    href = ""
                    if need_translate and need_link:
                        (zh_cn, zh_tw), href = await asyncio.gather(_fetch_translations(), _fetch_href())
                    elif need_translate:
                        zh_cn, zh_tw = await _fetch_translations()
                    elif need_link:
                        href = await _fetch_href()

                    await update_actor_db_row(
                        jp=jp_name,
                        zh_cn=zh_cn,
                        zh_tw=zh_tw,
                        href=href,
                        tmdbid=tmdbid,
                        overwrite_names=True,
                        _wb=_wb,
                    )

                    if zh_cn or zh_tw:
                        result.translated += 1
                        _log_line(f"  🔄 [演员库维护] {actor_name} 翻译补全: zh_cn={zh_cn or '-'} zh_tw={zh_tw or '-'}")
                    if href:
                        result.linked += 1
                        _log_line(f"  ✅ [演员库维护] {actor_name} -> {href}")
                    elif need_link and not href:
                        _log_line(f"  ⚠️ [演员库维护] {actor_name} 未在 LibreDMM 找到链接")
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
            from mdcx.core.tmdb_actor import _ACTOR_DB_ROW_INDEX, _ACTOR_DB_ROW_INDEX_LOCK

            with _ACTOR_DB_ROW_INDEX_LOCK:
                _ACTOR_DB_ROW_INDEX.clear()
            _log_line(" ✅ [演员库维护] 已保存 actor_database.xlsx 并重载内存缓存")
        except Exception as e:
            _log_line(f" ❌ [演员库维护] 落盘失败，写入可能未保存: {e}")

    _log_line(
        f" 🎬 [演员库维护] 完成: 共 {result.total} 个, 翻译补全 {result.translated}, "
        f"链接补全 {result.linked}, 跳过 {result.skipped}, 失败 {len(result.failed)} ({get_used_time(start_time)}s)"
    )
    return result


async def run_actor_db_xlsx(mode: str) -> None:
    """直接扫描 actor_database.xlsx 执行维护，无需演员名单。

    mode:
      'translate'    — 补全缺中文名的条目
      'link'         — 补全缺 LibreDMM 链接的条目
      'sync_aliases' — 同步 TMDB 最新别名到 keyword 列
    """
    db_path = _get_db_path()
    if not db_path.exists():
        _log_line(" 🔴 actor_database.xlsx 不存在")
        return

    import openpyxl as _xl

    wb = _xl.load_workbook(db_path)
    ws = wb.active
    base_url, tmdb_api_key = _resolve_tmdb_config()
    if not tmdb_api_key:
        _log_line(" ⚠️ 未配置 TMDB API Key，部分功能不可用")

    rows_to_process = []
    for row_idx, row in enumerate(ws.iter_rows(min_row=2, max_col=7, values_only=True), start=2):
        jp = str(row[0] or "").strip()
        tmdbid_val = str(row[5] or "").strip()
        if not jp or not tmdbid_val.isdigit():
            continue
        tmdbid = int(tmdbid_val)
        zh_cn = str(row[1] or "").strip()
        zh_tw = str(row[2] or "").strip()
        href = str(row[4] or "").strip()

        if mode == "translate":
            if not zh_cn or not zh_tw:
                rows_to_process.append((jp, tmdbid, row_idx))
        elif mode == "link":
            if not href:
                rows_to_process.append((jp, tmdbid, row_idx))
        elif mode == "sync_aliases":
            rows_to_process.append((jp, tmdbid, row_idx))

    _log_line(f" 🎬 扫描完成：{len(rows_to_process)} 个演员需要处理 (模式: {mode})")
    if not rows_to_process:
        _log_line(" ✅ 没有需要处理的数据")
        wb.close()
        return

    start_time = time.time()
    translated_count = 0
    linked_count = 0

    async with aiohttp.ClientSession() as client:
        concurrency = 2 if mode == "link" else 5
        task_iter = iter(enumerate(rows_to_process, 1))
        running_tasks: set[asyncio.Task[None]] = set()

        async def _process_one(jp, tmdbid, row_idx):
            nonlocal translated_count, linked_count
            try:
                if mode == "translate" and base_url and tmdb_api_key:
                    translations = await _fetch_person_translations(tmdbid, base_url, tmdb_api_key, client)
                    new_zh_cn = _normalize_translation(translations.get("zh_cn", ""))
                    new_zh_tw = _normalize_translation(translations.get("zh_tw", ""))
                    if not new_zh_cn and new_zh_tw:
                        new_zh_cn = zhconv.convert(new_zh_tw, "zh-cn")
                    if not new_zh_tw and new_zh_cn:
                        new_zh_tw = zhconv.convert(new_zh_cn, "zh-hant")

                    updated = False
                    if new_zh_cn:
                        ws.cell(row=row_idx, column=2, value=new_zh_cn)
                        updated = True
                    if new_zh_tw:
                        ws.cell(row=row_idx, column=3, value=new_zh_tw)
                        updated = True
                    if updated:
                        translated_count += 1
                        _log_line(f"  ✅ {jp}: zh_cn={new_zh_cn}, zh_tw={new_zh_tw}")

                elif mode == "link":
                    href_val = await fetch_libredmm_link(jp)
                    if href_val:
                        ws.cell(row=row_idx, column=5, value=href_val)
                        linked_count += 1
                        _log_line(f"  ✅ {jp} -> {href_val}")
                    else:
                        _log_line(f"  ⚠️ {jp} 未在 LibreDMM 找到链接")

                elif mode == "sync_aliases" and base_url and tmdb_api_key:
                    from mdcx.core.tmdb_actor import query_single_actor_cached

                    query_result = await query_single_actor_cached(jp, base_url, tmdb_api_key, client)
                    if query_result:
                        new_keywords = _merge_keyword_values(
                            query_result.get("name", ""),
                            query_result.get("original_name", ""),
                            query_result.get("also_known_as", []),
                        )

                        existing_kw = str(ws.cell(row=row_idx, column=4).value or "").strip()
                        existing_set = {k.strip() for k in existing_kw.split(",") if k.strip()}
                        merged_set = existing_set | {k for k in new_keywords.split(",") if k.strip()}
                        ws.cell(row=row_idx, column=4, value=",".join(sorted(merged_set)))
                        new_count = len([k for k in new_keywords.split(",") if k.strip()])
                        _log_line(f"  ✅ {jp}: 别名已同步 ({new_count} 个)")
                    else:
                        _log_line(f"  ⚠️ {jp} TMDB 未查询到数据")

            except Exception as e:
                _log_line(f"  ❌ {jp} 处理失败: {e}")

        def _submit_next() -> bool:
            try:
                _, (jp, tmdbid, row_idx) = next(task_iter)
            except StopIteration:
                return False
            task = asyncio.create_task(_process_one(jp, tmdbid, row_idx))
            running_tasks.add(task)
            return True

        for _ in range(min(concurrency, len(rows_to_process))):
            _submit_next()

        total = len(rows_to_process)
        completed = 0
        progress_interval = max(1, total // 10)  # 每 10% 输出一次进度

        while running_tasks:
            done, pending = await asyncio.wait(running_tasks, return_when=asyncio.FIRST_COMPLETED)
            running_tasks = set(pending)
            for _ in range(len(done)):
                _submit_next()
            for done_task in done:
                completed += 1
                try:
                    done_task.result()
                except Exception as e:
                    _log_line(f"  🔴 子任务异常: {e}")
            if completed % progress_interval == 0 or completed == total:
                _log_line(f"  📊 进度: {completed}/{total}")

    _format_db_worksheet(ws)
    wb.save(db_path)
    wb.close()
    resources.reload_actor_db()
    from mdcx.core.tmdb_actor import _ACTOR_DB_ROW_INDEX, _ACTOR_DB_ROW_INDEX_LOCK

    with _ACTOR_DB_ROW_INDEX_LOCK:
        _ACTOR_DB_ROW_INDEX.clear()

    _log_line(f" ✅ 完成: 翻译补全={translated_count}, 链接补全={linked_count} ({get_used_time(start_time)}s)")


def _entry_name_of_row(ws, row_idx: int) -> str:
    for col in (COL_JP, COL_ZH_CN, COL_KEYWORD):
        val = str(ws.cell(row=row_idx, column=col + 1).value or "").strip()
        if val:
            return val.split(",")[0]
    return f"第{row_idx}行"


async def sync_from_avdb(source: str, value: str = "") -> ActorDbSyncResult:
    """从 AVdb (li-peifeng/Jav-Actors-Mapping) 同步演员映射到本地数据库。

    source:
      'jsdelivr'  — 通过 cdn.jsdelivr.net 拉取 (默认)
      'github'    — 通过 GitHub raw 拉取
      'url'       — 从 value 指定的任意下载地址拉取
      'file'      — 从 value 指定的本地 xml 文件导入

    匹配顺序: tmdbid 冲突优先并入 -> jp 精确 -> zh_cn 精确 -> keyword 命中。
    本地已有值优先，仅填充空缺字段；tmdbid 冲突视为同一人并入别名。
    """
    from ..base.web import download_file_with_filepath
    from ..utils.xml_avdb import clean_actor_value, parse_avdb_actor_mapping

    result = ActorDbSyncResult()
    db_path = _get_db_path()

    def _dedup_keywords(*groups: set[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for group in groups:
            for k in sorted(group):
                key = k.casefold()
                if key not in seen:
                    seen.add(key)
                    out.append(k)
        return out

    # ---- 数据源: 读取 XML 文本 ----
    xml_text = ""
    if source == "file":
        file_path = Path(value)
        if not file_path.exists():
            _log_line(f" ❌ [AVdb同步] 本地文件不存在: {file_path}")
            result.failed.append(("<本地文件>", f"文件不存在: {file_path}"))
            return result
        async with aiofiles.open(file_path, encoding="utf-8") as f:
            xml_text = await f.read()
    else:
        url = value or (AVDB_MAPPING_URL_MIRROR if source == "jsdelivr" else AVDB_MAPPING_URL)
        cache_dir = db_path.parent / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = cache_dir / "avdb_actor_mapping.xml"
        if not await download_file_with_filepath(url, tmp_file, cache_dir):
            _log_line(f" ❌ [AVdb同步] 下载失败: {url}")
            result.failed.append((url, "网络下载失败"))
            return result
        result.downloaded = True
        async with aiofiles.open(tmp_file, encoding="utf-8") as f:
            xml_text = await f.read()

    try:
        actors = parse_avdb_actor_mapping(xml_text)
    except ValueError as exc:
        _log_line(f" ❌ [AVdb同步] XML 解析失败: {exc}")
        result.failed.append(("<xml>", str(exc)))
        return result
    result.parsed = len(actors)
    _log_line(f" 🎬 [AVdb同步] 解析 {len(actors)} 条 AVdb 映射, 开始合并")

    # ---- 加载/创建 数据库 ----
    import openpyxl as _xl

    try:
        async with _actor_db_write_lock:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            if db_path.exists():
                wb = _xl.load_workbook(db_path)
            else:
                wb = _xl.Workbook()
                ws = wb.active
                ws.title = "演员数据库"
                for col, header in enumerate(DB_HEADERS, 1):
                    cell = ws.cell(row=1, column=col, value=header)
                    cell.font = _xl.styles.Font(bold=True)
                    cell.fill = _xl.styles.PatternFill("solid", fgColor="C0C0C0")
                    cell.alignment = _xl.styles.Alignment(horizontal="center")
            ws = wb.active
            if ws.title != "演员数据库":
                ws.title = "演员数据库"

            # ---- 构建本地索引 ----
            jp_index: dict[str, int] = {}
            zh_cn_index: dict[str, int] = {}
            keyword_index: dict[str, int] = {}
            tmdb_index: dict[str, int] = {}
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, max_col=len(DB_HEADERS), values_only=True), start=2):
                if row is None:
                    continue

                def _cell(values, col_idx):
                    return str(values[col_idx] or "").strip() if len(values) > col_idx else ""

                jp_val = _cell(row, COL_JP)
                zh_val = _cell(row, COL_ZH_CN)
                kw_val = _cell(row, COL_KEYWORD)
                tmdb_val = _cell(row, COL_TMDBID)
                if jp_val:
                    jp_index.setdefault(jp_val.casefold(), row_idx)
                if zh_val:
                    zh_cn_index.setdefault(zh_val.casefold(), row_idx)
                for k in [k.strip() for k in kw_val.split(",") if k.strip()]:
                    keyword_index.setdefault(k.casefold(), row_idx)
                if tmdb_val:
                    tmdb_index.setdefault(tmdb_val, row_idx)

            total = len(actors)
            progress_interval = max(1, total // 10)  # 每 10% 输出一次进度

            for n, actor in enumerate(actors, 1):
                try:
                    jp = clean_actor_value(actor.jp)
                    zh_cn = clean_actor_value(actor.zh_cn)
                    zh_tw = clean_actor_value(actor.zh_tw)
                    keyword = clean_actor_value(actor.keyword)
                    tmdb_id = clean_actor_value(actor.tmdb_id)
                    birth_date = clean_actor_value(actor.birth_date)
                    bio = clean_actor_value(actor.bio)

                    kw_list = [k.strip() for k in keyword.split(",") if k.strip()]
                    kw_set = set(kw_list)
                    entry_name = jp or zh_cn or (kw_list[0] if kw_list else "<无名字段>")
                    if not jp and not zh_cn and not kw_list:
                        continue

                    def _norm_tmdb(raw: str) -> str:
                        return raw if raw.isdigit() else ""

                    tmdb_key = _norm_tmdb(tmdb_id)

                    # 1) tmdbid 冲突优先并入
                    target_row = None
                    is_tmdb_conflict = False
                    if tmdb_key:
                        conflict_row = tmdb_index.get(tmdb_key)
                        if conflict_row is not None:
                            target_row = conflict_row
                            is_tmdb_conflict = True

                    # 2) jp -> zh_cn -> keyword 文本匹配
                    if target_row is None:
                        candidate = None
                        if jp:
                            candidate = jp_index.get(jp.casefold())
                        if candidate is None and zh_cn:
                            candidate = zh_cn_index.get(zh_cn.casefold())
                        if candidate is None:
                            for k in kw_list:
                                candidate = keyword_index.get(k.casefold())
                                if candidate is not None:
                                    break
                        target_row = candidate

                    # 3) 未匹配 -> 新建
                    if target_row is None:
                        tmdb_val = int(tmdb_key) if tmdb_key else ""
                        ws.append(
                            [jp, zh_cn, zh_tw, ",".join(_dedup_keywords(kw_set)), "", tmdb_val, "", birth_date, bio]
                        )
                        new_idx = ws.max_row
                        if jp:
                            jp_index.setdefault(jp.casefold(), new_idx)
                        if zh_cn:
                            zh_cn_index.setdefault(zh_cn.casefold(), new_idx)
                        for k in kw_set:
                            keyword_index.setdefault(k.casefold(), new_idx)
                        if tmdb_key:
                            tmdb_index.setdefault(tmdb_key, new_idx)
                        result.created += 1
                        continue

                    # 4) 命中 -> 只填空缺值，不覆盖本地
                    def _fill(row_idx: int, col_idx: int, new_val: str) -> None:
                        if not new_val:
                            return
                        existing = str(ws.cell(row=row_idx, column=col_idx + 1).value or "").strip()
                        if not existing:
                            ws.cell(row=row_idx, column=col_idx + 1, value=new_val)

                    _fill(target_row, COL_JP, jp)
                    _fill(target_row, COL_ZH_CN, zh_cn)
                    _fill(target_row, COL_ZH_TW, zh_tw)
                    _fill(target_row, COL_BIRTH_DATE, birth_date)
                    _fill(target_row, COL_BIO, bio)
                    if tmdb_key:
                        existing_tmdb = str(ws.cell(row=target_row, column=COL_TMDBID + 1).value or "").strip()
                        if not existing_tmdb:
                            ws.cell(row=target_row, column=COL_TMDBID + 1, value=int(tmdb_key))

                    existing_kw = str(ws.cell(row=target_row, column=COL_KEYWORD + 1).value or "").strip()
                    existing_elems = [k.strip() for k in existing_kw.split(",") if k.strip()]
                    merged = _dedup_keywords(set(existing_elems), kw_set)
                    merged_str = ",".join(merged)
                    if merged_str != existing_kw:
                        ws.cell(row=target_row, column=COL_KEYWORD + 1, value=merged_str)

                    if is_tmdb_conflict:
                        result.merged += 1
                        _log_line(
                            f"  🔀 [AVdb同步] tmdbid={tmdb_key} 冲突: {entry_name} 并入 {_entry_name_of_row(ws, target_row)}"
                        )
                    else:
                        result.filled += 1

                    if n % progress_interval == 0 or n == total:
                        _log_line(f"  📊 [AVdb同步] 进度 {n}/{total}")
                except Exception as e:
                    result.failed.append((actor.jp or actor.zh_cn or "<未知>", str(e)))
                    _log_line(f"  ❌ [AVdb同步] {actor.jp or actor.zh_cn or '<未知>'} 处理失败: {e}")

            _format_db_worksheet(ws)
            wb.save(db_path)
            wb.close()
    except Exception as e:
        result.failed.append(("<落盘>", str(e)))
        _log_line(f" ❌ [AVdb同步] 写入数据库失败: {e}")
        return result

    try:
        resources.reload_actor_db()
        from mdcx.core.tmdb_actor import _ACTOR_DB_ROW_INDEX, _ACTOR_DB_ROW_INDEX_LOCK

        with _ACTOR_DB_ROW_INDEX_LOCK:
            _ACTOR_DB_ROW_INDEX.clear()
    except Exception as e:
        _log_line(f" ⚠️ [AVdb同步] 重载内存缓存失败: {e}")

    _log_line(
        f" 🎬 [AVdb同步] 完成: 解析 {result.parsed}, 新建 {result.created}, 补齐 {result.filled}, "
        f"冲突合并 {result.merged}, 失败 {len(result.failed)}"
    )
    return result
