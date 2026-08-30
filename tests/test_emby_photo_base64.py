"""议题 #56 图片上传回归：请求体必须是 base64 字符串而非原始二进制字节。

Emby/Jellyfin 端点 `POST /Items/{id}/Images/{Primary,Backdrop}` 的 body 预期
为 Base64 编码字符串（服务端从 CryptoStream.ReadAsync 解析 Base64），
直接传二进制报错：`System.FormatException: One of the identified items
was in an invalid format`。

本测试直接验证 `_upload_actor_photo` 发送的 body 是已编码的 base64 文本，
而非原始 JPEG 字节流。
"""

import base64
from pathlib import Path

import pytest

import mdcx.tools.emby_shared as em


class _FakeConfig:
    server_type = "emby"
    emby_url = "http://emby:8096"
    api_key = "test-key-63characters-placeholder-fill-padding1234567890abcdef"


class _FakeAsyncClient:
    def __init__(self):
        self.calls: list[dict] = []

    async def post_content(self, url: str, data: str | bytes, headers: dict | None = None, **kwargs):
        self.calls.append({"url": url, "data": data, "headers": headers})
        return b"", ""  # (bytes, error)：模拟成功


class _FakeComputed:
    def __init__(self, client: _FakeAsyncClient):
        self.async_client = client

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


class _Mgr:
    config = _FakeConfig()

    def __init__(self, client: _FakeAsyncClient):
        self._client = client

    def acquire_computed(self):
        return _FakeComputed(self._client)


@pytest.mark.asyncio
async def test_upload_sends_base64_encoded_body(tmp_path: Path):
    """上传请求 body 应为 base64 字符串（ASCII），非原始二进制。"""
    photo = tmp_path / "cover.jpg"
    raw_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # JPEG 魔头
    photo.write_bytes(raw_bytes)

    client = _FakeAsyncClient()
    orig_manager = em.manager
    em.manager = _Mgr(client)
    try:
        ok, err = await em._upload_actor_photo("http://emby:8096/Items/abc/Images/Primary", photo)
        assert ok, f"upload failed: {err}"
        assert len(client.calls) == 1
        sent_body = client.calls[0]["data"]

        # 核心断言：body 必须是字符串（不是字节），且内容是有效的 base64
        assert isinstance(sent_body, str), f"body 应该是 str 不是 {type(sent_body)}"
        # b64decode 不带 validate → 任何字节序列都能解，必须用 validate 确认无非法字节
        raw_back = base64.b64decode(sent_body.encode("ascii"), validate=True)
        assert raw_back == raw_bytes, "base64 解码后应和原始二进制完全一致"
    finally:
        em.manager = orig_manager


@pytest.mark.asyncio
async def test_upload_content_type_image(tmp_path: Path):
    """上传请求应保留正确的图片 Content-Type header。"""
    photo = tmp_path / "cover.png"
    photo.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

    client = _FakeAsyncClient()
    orig_manager = em.manager
    em.manager = _Mgr(client)
    try:
        ok, err = await em._upload_actor_photo("http://emby:8096/Items/abc/Images/Backdrop/0", photo)
        assert ok, f"upload failed: {err}"
        content_type = client.calls[0]["headers"].get("Content-Type", "")
        assert content_type == "image/png", f"Content-Type 错误: {content_type}"
    finally:
        em.manager = orig_manager


@pytest.mark.asyncio
async def test_upload_extension_detection(tmp_path: Path):
    """多种图片格式应都被正确推断 Content-Type。"""
    formats = [
        (".jpg", "image/jpeg"),
        (".jpeg", "image/jpeg"),
        (".png", "image/png"),
        (".webp", "image/webp"),
    ]
    for suffix, expected_mime in formats:
        photo = tmp_path / f"test{suffix}"
        photo.write_bytes(b"\xff\xd8" + b"\x00" * 100)

        client = _FakeAsyncClient()
        orig_manager = em.manager
        em.manager = _Mgr(client)
        try:
            ok, err = await em._upload_actor_photo("http://emby/Items/x/Images/Primary", photo)
            assert ok, f"{suffix} upload failed: {err}"
            actual_mime = client.calls[0]["headers"].get("Content-Type", "")
            assert actual_mime == expected_mime, f"扩展名 {suffix} 推断错误，得到 {actual_mime}"
        finally:
            em.manager = orig_manager


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
