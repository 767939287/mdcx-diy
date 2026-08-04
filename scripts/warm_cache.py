"""Download cloakbrowser stealth Chromium for cache warm-up."""

import os
import platform
import shutil
from pathlib import Path
from urllib.parse import urlparse

import cloakbrowser as cb

TRUSTED_DOWNLOAD_HOSTS = frozenset(
    {
        "github.com",
        "objects.githubusercontent.com",
        "v6.gh-proxy.com",
    }
)


def sanitize_download_url() -> None:
    url = os.environ.get("CLOAKBROWSER_DOWNLOAD_URL")
    if not url:
        return
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise ValueError("非 https 协议")
        if parsed.hostname not in TRUSTED_DOWNLOAD_HOSTS:
            raise ValueError(f"不受信主机: {parsed.hostname}")
    except Exception as e:
        print(f"CLOAKBROWSER_DOWNLOAD_URL 不在受信白名单, 已忽略并回退官方源: {e}")
        os.environ.pop("CLOAKBROWSER_DOWNLOAD_URL", None)


def main():
    sanitize_download_url()
    os.environ.setdefault(
        "CLOAKBROWSER_DOWNLOAD_URL",
        "https://v6.gh-proxy.com/https://github.com/CloakHQ/cloakbrowser/releases/download",
    )
    binary = cb.ensure_binary()
    if not binary:
        print("Failed to get Chromium binary")
        return 1

    platform_sub = {"Windows": "chrome-win64", "Linux": "chrome-linux", "Darwin": "chrome-macos"}
    src = Path(binary).resolve().parent
    dest = Path("chromium") / platform_sub.get(platform.system(), "chrome-win64")
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest, dirs_exist_ok=True)
    print(f"Chromium cached to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
