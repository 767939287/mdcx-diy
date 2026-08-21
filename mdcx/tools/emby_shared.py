"""Emby/Jellyfin API 共用工具函数。

供内置补全 (emby_actor_info/emby_actor_image) 和管理器工具 (emby_actor_manager) 共用。
"""

from __future__ import annotations

import traceback
from pathlib import Path
from urllib.parse import quote, urlencode

import aiofiles

from ..config.manager import manager
from ..signals import signal

JELLYFIN_PERSON_FIELDS = (
    "Overview",
    "ProviderIds",
    "ProductionLocations",
    "Taglines",
    "Genres",
    "Tags",
)


def _is_jellyfin_server() -> bool:
    # server_type 配置为 Literal["emby", "ln"]，UI 用 "ln" 表示 Jellyfin
    return manager.config.server_type != "emby"


def _build_jellyfin_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    request_headers = dict(headers or {})
    request_headers["Authorization"] = f'MediaBrowser Token="{manager.config.api_key}"'
    return request_headers


def _append_query(url: str, params: dict[str, str | None]) -> str:
    query = urlencode({k: v for k, v in params.items() if v not in ("", None)})
    return f"{url}?{query}" if query else url


def _generate_server_url(actor: dict) -> tuple[str, str, str, str, str, str]:
    server_type = manager.config.server_type
    emby_url = str(manager.config.emby_url).rstrip("/")
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


async def _upload_actor_photo(url: str, pic_path: Path) -> tuple[bool, str]:
    try:
        async with aiofiles.open(pic_path, "rb") as f:
            content = await f.read()
        header = {"Content-Type": "image/jpeg" if pic_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"}
        header = _build_jellyfin_headers(header)
        async with manager.acquire_computed() as computed:
            r, err = await computed.async_client.post_content(url=url, data=content, headers=header, use_proxy=False)
        return r is not None, err
    except Exception as e:
        signal.show_log_text(traceback.format_exc())
        return False, f"上传头像失败: {url} {pic_path} {e!s}"
