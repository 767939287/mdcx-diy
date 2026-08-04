from __future__ import annotations

import asyncio
import base64
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import aiofiles
import aiofiles.os

from ..base.web import download_file_with_filepath
from ..config.manager import manager
from ..config.resources import resources
from ..models.flags import Flags
from ..signals import signal
from .actress_db import ActressDB
from .minnano_crawler import get_minnano_info
from .wiki import get_detail, search_wiki

GFRIENDS_REPO = "https://raw.githubusercontent.com/gfriends/gfriends/master"
GFRIENDS_FILETREE = f"{GFRIENDS_REPO}/Filetree.json"
GFRIENDS_BASE = f"{GFRIENDS_REPO}/Content"


class ActorTaskStopped(Exception):
    pass


def _is_stop_requested() -> bool:
    return signal.stop or Flags.stop_requested


def _raise_if_stop_requested() -> None:
    if _is_stop_requested():
        raise ActorTaskStopped("手动停止")


@dataclass
class ActorInfo:
    name: str
    actor_id: str
    server_id: str
    has_image: bool = False
    has_overview: bool = False
    existing_overview: str = ""
    existing_taglines: list[str] = field(default_factory=list)
    existing_production_year: int | None = None
    existing_premiere_date: str = ""
    existing_production_locations: list[str] = field(default_factory=list)
    existing_provider_ids: dict[str, str] = field(default_factory=dict)
    existing_genres: list[str] = field(default_factory=list)
    existing_tags: list[str] = field(default_factory=list)
    new_overview: str = ""
    new_taglines: list[str] = field(default_factory=list)
    new_production_year: int | None = None
    new_premiere_date: str = ""
    new_production_locations: list[str] = field(default_factory=list)
    new_provider_ids: dict[str, str] = field(default_factory=dict)
    new_image_path: str | None = None
    new_backdrop_path: str | None = None
    movie_count: int = 0
    movie_titles: list[str] = field(default_factory=list)
    has_backdrop: bool = False
    need_update_info: bool = False
    need_update_image: bool = False
    need_update_backdrop: bool = False

    @property
    def status_text(self) -> str:
        parts = []
        parts.append("有头像" if self.has_image else "缺头像")
        parts.append("有简介" if self.has_overview else "缺简介")
        parts.append(f"{self.movie_count}部关联影片")
        return " | ".join(parts)

    @property
    def status_icon(self) -> str:
        if self.has_image and self.has_overview:
            return "✅"
        if not self.has_image and not self.has_overview:
            return "❌"
        return "⚠️"


def _build_jellyfin_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    request_headers = dict(headers or {})
    request_headers["Authorization"] = f'MediaBrowser Token="{manager.config.api_key}"'
    return request_headers


def _append_query(url: str, params: dict[str, str | None]) -> str:
    from urllib.parse import urlencode

    query = urlencode({k: v for k, v in params.items() if v not in ("", None)})
    return f"{url}?{query}" if query else url


def _is_jellyfin_server() -> bool:
    return manager.config.server_type == "jellyfin"


def _generate_server_url(actor: dict) -> tuple[str, str, str, str, str, str]:
    server_type = manager.config.server_type
    emby_url = str(manager.config.emby_url).rstrip("/")
    from urllib.parse import quote

    actor_name = quote(actor["Name"], safe="")
    actor_id = actor["Id"]
    server_id = actor.get("ServerId", "")
    if "emby" == server_type:
        actor_homepage = f"{emby_url}/web/index.html#!/item?id={actor_id}&serverId={server_id}"
        actor_person = f"{emby_url}/emby/Persons/{actor_name}"
        pic_url = f"{emby_url}/emby/Items/{actor_id}/Images/Primary"
        backdrop_url = f"{emby_url}/emby/Items/{actor_id}/Images/Backdrop"
        backdrop_url_0 = f"{emby_url}/emby/Items/{actor_id}/Images/Backdrop/0"
        update_url = f"{emby_url}/emby/Items/{actor_id}"
    else:
        actor_homepage = f"{emby_url}/web/index.html#!/details?id={actor_id}&serverId={server_id}"
        actor_person = _append_query(f"{emby_url}/Persons/{actor_name}", {"userId": manager.config.user_id})
        pic_url = f"{emby_url}/Items/{actor_id}/Images/Primary"
        backdrop_url = f"{emby_url}/Items/{actor_id}/Images/Backdrop"
        backdrop_url_0 = f"{emby_url}/Items/{actor_id}/Images/Backdrop/0"
        update_url = f"{emby_url}/Items/{actor_id}"
    return actor_homepage, actor_person, pic_url, backdrop_url, backdrop_url_0, update_url


async def get_emby_actor_list() -> list[dict]:
    _raise_if_stop_requested()
    base_url = str(manager.config.emby_url).rstrip("/")
    headers = _build_jellyfin_headers()
    if "emby" == manager.config.server_type:
        server_name = "Emby"
        url = _append_query(base_url + "/emby/Persons", {"userId": manager.config.user_id})
    else:
        server_name = "Jellyfin"
        url = _append_query(
            base_url + "/Persons",
            {
                "personTypes": "Actor",
                "fields": "Overview,ProviderIds,ProductionLocations,Taglines,Genres,Tags",
                "enableImages": "true",
                "userId": manager.config.user_id,
            },
        )
    signal.show_log_text(f"⏳ 连接 {server_name} 服务器...")
    if not manager.config.api_key:
        signal.show_log_text(f"🔴 {server_name} API 密钥未填写！")
        return []
    from ..models.computed import ComputedManager

    async with ComputedManager() as computed:
        response, error = await computed.async_client.get_json(url, headers=headers, use_proxy=False)
    _raise_if_stop_requested()
    if response is None:
        signal.show_log_text(f"🔴 {server_name} 连接失败！{error}")
        return []
    actor_list = response.get("Items", [])
    signal.show_log_text(f"✅ {server_name} 连接成功！共 {len(actor_list)} 个演员")
    return actor_list


async def get_media_folders() -> list[dict]:
    base_url = str(manager.config.emby_url).rstrip("/")
    headers = _build_jellyfin_headers()
    if "emby" == manager.config.server_type:
        url = f"{base_url}/emby/Library/MediaFolders"
    else:
        url = f"{base_url}/Library/MediaFolders"
    from ..models.computed import ComputedManager

    async with ComputedManager() as computed:
        response, error = await computed.async_client.get_json(url, headers=headers, use_proxy=False)
    if response is None:
        return []
    return response.get("Items", [])


async def fetch_actor_detail(actor_name: str) -> dict | None:
    base_url = str(manager.config.emby_url).rstrip("/")
    headers = _build_jellyfin_headers()
    from urllib.parse import quote

    name_encoded = quote(actor_name, safe="")
    if "emby" == manager.config.server_type:
        url = f"{base_url}/emby/Persons/{name_encoded}"
    else:
        url = _append_query(
            f"{base_url}/Persons/{name_encoded}",
            {"userId": manager.config.user_id},
        )
    from ..models.computed import ComputedManager

    async with ComputedManager() as computed:
        response, error = await computed.async_client.get_json(url, headers=headers, use_proxy=False)
    return response


async def fetch_person_item_stats(
    parent_ids: list[str] | None = None,
) -> tuple[dict[str, int], dict[str, list[str]], set]:
    counts: dict = {}
    titles: dict = {}
    person_names: set = set()
    urls = []
    base_url = str(manager.config.emby_url).rstrip("/")
    headers = _build_jellyfin_headers()
    if parent_ids:
        for lib_id in parent_ids:
            if "emby" == manager.config.server_type:
                urls.append(f"{base_url}/emby/Items?Recursive=true&Fields=People&ParentId={lib_id}&Limit=100000")
            else:
                urls.append(f"{base_url}/Items?Recursive=true&Fields=People&ParentId={lib_id}&Limit=100000")
    else:
        if "emby" == manager.config.server_type:
            urls.append(f"{base_url}/emby/Items?Recursive=true&Fields=People&Limit=100000")
        else:
            urls.append(f"{base_url}/Items?Recursive=true&Fields=People&Limit=100000")
    from ..models.computed import ComputedManager

    async with ComputedManager() as computed:
        for url in urls:
            response, error = await computed.async_client.get_json(url, headers=headers, use_proxy=False)
            if response is None:
                continue
            items = response.get("Items", [])
            for item in items:
                people = item.get("People") or []
                item_name = item.get("Name", "")
                item_type = item.get("Type", "")
                seen_in_item = set()
                for person in people:
                    name = person.get("Name", "")
                    if not name:
                        continue
                    seen_in_item.add(name)
                    person_names.add(name)
                for name in seen_in_item:
                    counts[name] = counts.get(name, 0) + 1
                    if name not in titles:
                        titles[name] = []
                    titles[name].append(f"[{item_type}] {item_name}")
    return counts, titles, person_names


async def fetch_all_actors(
    filter_actor_only: bool = True,
    deduplicate: bool = True,
    parent_ids: list[str] | None = None,
    progress_callback: Callable | None = None,
) -> list[ActorInfo]:
    persons = await get_emby_actor_list()
    if not persons:
        return []
    result: list[ActorInfo] = []
    seen_names = set()
    person_counts, person_titles, lib_person_names = await fetch_person_item_stats(parent_ids=parent_ids)
    total = len(persons)
    for i, p in enumerate(persons):
        _raise_if_stop_requested()
        name = p.get("Name", "")
        if not name:
            continue
        if any(ch in name for ch in " .·・-"):
            continue
        if parent_ids and name not in lib_person_names:
            continue
        if deduplicate:
            if name in seen_names:
                continue
            seen_names.add(name)
        actor_id = p.get("Id", "")
        server_id = p.get("ServerId", "")
        image_tags = p.get("ImageTags") or {}
        backdrop_tags = p.get("BackdropImageTags") or []
        info = ActorInfo(
            name=name,
            actor_id=actor_id,
            server_id=server_id,
            has_image="Primary" in image_tags,
            has_backdrop=len(backdrop_tags) > 0,
        )
        detail = await fetch_actor_detail(name)
        if detail:
            overview = detail.get("Overview") or ""
            info.has_overview = bool(overview)
            info.existing_overview = overview
            info.existing_taglines = detail.get("Taglines") or []
            info.existing_production_year = detail.get("ProductionYear")
            info.existing_premiere_date = detail.get("PremiereDate") or ""
            info.existing_production_locations = detail.get("ProductionLocations") or []
            info.existing_provider_ids = detail.get("ProviderIds") or {}
            info.existing_genres = detail.get("Genres") or []
            info.existing_tags = detail.get("Tags") or []
        info.movie_count = person_counts.get(name, 0)
        info.movie_titles = person_titles.get(name, [])
        result.append(info)
        if progress_callback:
            progress_callback(i + 1, total, name)
    return result


async def get_gfriends_index() -> dict[str, str] | None:
    gfriends_github = manager.config.gfriends_github
    gfriends_local_path = manager.config.gfriends_local_path
    raw_url = f"{gfriends_github}".replace("github.com/", "raw.githubusercontent.com/").replace("://www.", "://")
    if gfriends_local_path and os.path.isdir(gfriends_local_path):
        local_filetree = os.path.join(gfriends_local_path, "Filetree.json")
        if os.path.isfile(local_filetree):
            try:
                async with aiofiles.open(local_filetree, encoding="utf-8") as f:
                    content = await f.read()
                    data = json.loads(content)
                content_data = data.get("Content")
                result = {}
                for category, items in content_data.items():
                    for filename, filepath in items.items():
                        if filename not in result:
                            result[filename] = f"{raw_url}/master/Content/{category}/{filepath}"
                return result
            except Exception:
                signal.show_log_text("⚠️ 本地 Gfriends index 读取失败，尝试远程下载")
    gfriends_json_path = resources.u("gfriends.json")
    if not await aiofiles.os.path.exists(gfriends_json_path):
        signal.show_log_text("⏳ 下载 Gfriends 数据表...")
        filetree_url = f"{raw_url}/master/Filetree.json"
        from ..models.computed import ComputedManager

        async with ComputedManager() as computed:
            response, error = await computed.async_client.get_content(filetree_url)
        if response is None:
            signal.show_log_text("🔴 Gfriends 数据表下载失败")
            return None
        async with aiofiles.open(gfriends_json_path, "wb") as f:
            await f.write(response)
    try:
        async with aiofiles.open(gfriends_json_path, encoding="utf-8") as f:
            content = await f.read()
            data = json.loads(content)
        if "Content" in data:
            result = {}
            content_data = data["Content"]
            for category, items in content_data.items():
                for filename, filepath in items.items():
                    if filename not in result:
                        result[filename] = f"{raw_url}/master/Content/{category}/{filepath}"
            return result
        return data
    except Exception:
        signal.show_log_text("⚠️ Gfriends index 文件解析失败")
        return None


async def update_person_info(actor: ActorInfo) -> tuple[bool, str]:
    _, _, _, _, _, update_url = _generate_server_url(
        {"Name": actor.name, "Id": actor.actor_id, "ServerId": actor.server_id}
    )
    overview = (actor.new_overview or actor.existing_overview or "").replace("\n", "<br/>")
    payload: dict[str, object] = {
        "Name": actor.name,
        "Id": actor.actor_id,
        "ServerId": actor.server_id,
        "Overview": overview,
        "Taglines": actor.new_taglines or [],
        "ProductionLocations": actor.new_production_locations or [],
        "ProviderIds": actor.new_provider_ids or {},
    }
    if actor.new_production_year:
        payload["ProductionYear"] = actor.new_production_year
    if actor.new_premiere_date:
        payload["PremiereDate"] = actor.new_premiere_date
    headers = _build_jellyfin_headers()
    from ..models.computed import ComputedManager

    async with ComputedManager() as computed:
        ok, err = await computed.async_client.post_content(
            url=update_url, data=json.dumps(payload), headers=headers, use_proxy=False
        )
    if ok:
        return True, f"✅ {actor.name} 信息更新成功"
    return False, f"❌ {actor.name} 信息更新失败: {err}"


async def upload_actor_image(actor: ActorInfo, image_path: str | Path) -> tuple[bool, str]:
    _, _, pic_url, _, _, _ = _generate_server_url(
        {"Name": actor.name, "Id": actor.actor_id, "ServerId": actor.server_id}
    )
    img_path = Path(image_path)
    if not img_path.exists():
        return False, f"❌ 图片文件不存在: {image_path}"
    try:
        async with aiofiles.open(img_path, "rb") as f:
            img_data = await f.read()
        b64_data = base64.b64encode(img_data).decode("ascii")
        content_type = "image/jpeg" if img_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
        header = {"Content-Type": content_type}
        header = _build_jellyfin_headers(header)
        from ..models.computed import ComputedManager

        async with ComputedManager() as computed:
            ok, err = await computed.async_client.post_content(
                url=pic_url, data=b64_data, headers=header, use_proxy=False
            )
        if ok:
            return True, f"✅ {actor.name} 头像上传成功"
        return False, f"❌ {actor.name} 头像上传失败: {err}"
    except Exception as e:
        return False, f"❌ {actor.name} 上传异常: {e}"


async def delete_actor_image(actor: ActorInfo) -> tuple[bool, str]:
    _, _, _, _, _, _ = _generate_server_url({"Name": actor.name, "Id": actor.actor_id, "ServerId": actor.server_id})
    base_url = str(manager.config.emby_url).rstrip("/")
    if "emby" == manager.config.server_type:
        url = f"{base_url}/emby/Items/{actor.actor_id}/Images/Primary"
    else:
        url = f"{base_url}/Items/{actor.actor_id}/Images/Primary"
    headers = _build_jellyfin_headers()
    from ..models.computed import ComputedManager

    async with ComputedManager() as computed:
        await computed.async_client.request("DELETE", url, headers=headers, use_proxy=False)
    return True, f"✅ {actor.name} 旧头像已删除"


async def delete_actor_backdrop(actor: ActorInfo) -> tuple[bool, str]:
    base_url = str(manager.config.emby_url).rstrip("/")
    if "emby" == manager.config.server_type:
        url = f"{base_url}/emby/Items/{actor.actor_id}/Images/Backdrop/0"
    else:
        url = f"{base_url}/Items/{actor.actor_id}/Images/Backdrop/0"
    headers = _build_jellyfin_headers()
    from ..models.computed import ComputedManager

    async with ComputedManager() as computed:
        await computed.async_client.request("DELETE", url, headers=headers, use_proxy=False)
    return True, f"✅ {actor.name} 旧背景已删除"


async def upload_actor_backdrop(actor: ActorInfo, image_path: str | Path) -> tuple[bool, str]:
    _, _, _, backdrop_url, _, _ = _generate_server_url(
        {"Name": actor.name, "Id": actor.actor_id, "ServerId": actor.server_id}
    )
    img_path = Path(image_path)
    if not img_path.exists():
        return False, f"❌ 背景图片文件不存在: {image_path}"
    try:
        async with aiofiles.open(img_path, "rb") as f:
            img_data = await f.read()
        b64_data = base64.b64encode(img_data).decode("ascii")
        content_type = "image/jpeg" if img_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
        header = {"Content-Type": content_type}
        header = _build_jellyfin_headers(header)
        from ..models.computed import ComputedManager

        async with ComputedManager() as computed:
            ok, err = await computed.async_client.post_content(
                url=backdrop_url, data=b64_data, headers=header, use_proxy=False
            )
        if ok:
            return True, f"✅ {actor.name} 背景上传成功"
        return False, f"❌ {actor.name} 背景上传失败: {err}"
    except Exception as e:
        return False, f"❌ {actor.name} 背景上传异常: {e}"


def gfriends_find_actor(gfriends_index: dict[str, str], name: str) -> str | None:
    for key, url in gfriends_index.items():
        if key.startswith(f"{name}."):
            return url
    return None


async def from_gfriends(actor: ActorInfo, gfriends_index: dict[str, str], cache_dir: Path) -> str | None:
    url = gfriends_find_actor(gfriends_index, actor.name)
    if not url:
        return None
    local_path = cache_dir / f"{actor.name}_gf.jpg"
    if not await download_file_with_filepath(url, local_path, cache_dir):
        return None
    if local_path.exists():
        return str(local_path)
    return None


async def from_graphis(actor: ActorInfo, cache_dir: Path) -> tuple[str, str | None] | None:
    from urllib.parse import quote

    from parsel import Selector

    local_data = resources.get_actor_data(actor.name)
    jp_name = actor.name
    if local_data.get("has_name"):
        jp_name = local_data.get("jp", actor.name)

    urls = [
        f"https://graphis.ne.jp/monthly/?K={quote(jp_name)}",
        f"https://graphis.ne.jp/monthly/?S=1&K={quote(jp_name)}",
    ]
    for url in urls:
        from ..models.computed import ComputedManager

        async with ComputedManager() as computed:
            res, _ = await computed.async_client.get_text(url)
        if res is None:
            continue
        html = Selector(res)
        src = html.xpath("//div[@class='gp-model-box']/ul/li/a/img/@src").getall()
        names = html.xpath("//li[@class='name-jp']/span/text()").getall()
        if jp_name in names:
            idx = names.index(jp_name)
            if idx < len(src):
                small_pic = src[idx]
                big_pic = small_pic.replace("/prof.jpg", "/model.jpg")
                avatar_path = cache_dir / f"{actor.name}_graphis.jpg"
                if await download_file_with_filepath(small_pic, avatar_path, cache_dir):
                    if avatar_path.exists():
                        backdrop_path = cache_dir / f"{actor.name}_graphis_bg.jpg"
                        backdrop_ok = await download_file_with_filepath(big_pic, backdrop_path, cache_dir)
                        backdrop = str(backdrop_path) if backdrop_ok and backdrop_path.exists() else None
                        return str(avatar_path), backdrop
    return None


async def from_minnano_image(actor: ActorInfo, cache_dir: Path) -> str | None:
    from ..models.emby import EMbyActressInfo
    from .minnano_crawler import get_minnano_info

    info = EMbyActressInfo(name=actor.name, server_id="", id="")
    res, _ = await get_minnano_info(info, "")
    if res and hasattr(info, "avatar_url") and info.avatar_url:
        local_path = cache_dir / f"{actor.name}_minnano.jpg"
        if await download_file_with_filepath(info.avatar_url, local_path, cache_dir):
            if local_path.exists():
                return str(local_path)
    return None


def from_local_avatar(actor: ActorInfo, local_avatar_dir: str) -> str | None:
    if not local_avatar_dir:
        return None
    avatar_dir = Path(local_avatar_dir)
    if not avatar_dir.exists():
        return None
    for f in avatar_dir.rglob("*"):
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png") and f.stem == actor.name:
            return str(f)
    return None


async def search_actor_info(actor: ActorInfo, wiki_intro: str = "") -> bool:
    from ..models.emby import EMbyActressInfo

    info = EMbyActressInfo(name=actor.name, server_id=actor.server_id, id=actor.actor_id)

    # 0) 本地演员库命中回填（最优先，离线可用）
    local_found = False
    local_overview = ""
    try:
        local_data = resources.get_actor_data(actor.name)
        if local_data.get("has_name"):
            bd = (local_data.get("birth_date") or "").strip()
            bio = (local_data.get("bio") or "").strip()
            if bd:
                info.birthday = bd
                info.year = bd[:4]
            if bio:
                local_overview = bio.replace("\n", "<br/>")
                info.overview = local_overview
            if not info.locations:
                info.locations = ["日本"]
            local_found = True
    except Exception:
        local_found = False

    # 本地命中且简介非空：完全采用本地数据，跳过外部网络来源
    if not (local_found and local_overview):
        res_wiki, _ = await search_wiki(info)
        wiki_found = False
        wiki_intro = ""
        if res_wiki is not None:
            result_wiki, _ = await get_detail(res_wiki, "", info)
            if result_wiki:
                wiki_intro = info.overview or ""
                wiki_found = True
        res, _ = await get_minnano_info(info, wiki_intro)
        if not res and not wiki_found and manager.config.use_database:
            _, _ = ActressDB.update_actor_info_from_db(info)
    if hasattr(info, "dump"):
        data = info.dump() if callable(info.dump) else info.__dict__
        actor.new_overview = data.get("overview", data.get("new_overview", ""))
        actor.new_taglines = data.get("taglines", data.get("new_taglines", []))
        actor.new_production_year = data.get("production_year", data.get("new_production_year"))
        actor.new_premiere_date = data.get("premiere_date", data.get("new_premiere_date", ""))
        actor.new_production_locations = data.get("production_locations", data.get("new_production_locations", []))
        actor.new_provider_ids = data.get("provider_ids", data.get("new_provider_ids", {}))
        if actor.new_overview or actor.new_taglines:
            actor.need_update_info = True
            return True
    return False


def sync_actor(actor: ActorInfo, sync_type: str = "both") -> tuple[bool, str]:
    logs = []
    if sync_type in ("both", "info"):
        if actor.need_update_info:
            loop = asyncio.new_event_loop()
            try:
                ok, msg = loop.run_until_complete(update_person_info(actor))
                logs.append(msg)
            finally:
                loop.close()
    if sync_type in ("both", "image"):
        if actor.need_update_image:
            if actor.new_image_path:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(delete_actor_image(actor))
                    ok, msg = loop.run_until_complete(upload_actor_image(actor, actor.new_image_path))
                    logs.append(msg)
                finally:
                    loop.close()
            else:
                loop = asyncio.new_event_loop()
                try:
                    ok, msg = loop.run_until_complete(delete_actor_image(actor))
                    logs.append(msg)
                finally:
                    loop.close()
        if actor.need_update_backdrop and actor.new_backdrop_path:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(delete_actor_backdrop(actor))
                ok, msg = loop.run_until_complete(upload_actor_backdrop(actor, actor.new_backdrop_path))
                logs.append(msg)
            finally:
                loop.close()
    success = all("成功" in log for log in logs) if logs else True
    return success, "\n".join(logs)


def sync_batch(
    actors: list[ActorInfo], progress_callback: Callable | None = None, actor_callback: Callable | None = None
) -> tuple[int, int]:
    success_count = 0
    fail_count = 0
    total = len(actors)
    for i, actor in enumerate(actors):
        if progress_callback:
            progress_callback(i + 1, total, f"正在同步: {actor.name} ({i + 1}/{total})")
        ok, msg = sync_actor(actor)
        if ok:
            success_count += 1
        else:
            fail_count += 1
        if actor_callback:
            actor_callback(actor, ok, msg)
    return success_count, fail_count
