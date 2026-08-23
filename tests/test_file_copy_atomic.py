"""文件复制原子替换回归测试。"""

from pathlib import Path

import pytest

from mdcx.utils import file as file_utils


def test_copy_file_sync_keeps_existing_target_when_copy_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = tmp_path / "source.jpg"
    target = tmp_path / "target.jpg"
    source.write_bytes(b"new")
    target.write_bytes(b"old")

    def fail_copy(*args, **kwargs):
        raise OSError("simulated copy failure")

    monkeypatch.setattr(file_utils.shutil, "copy", fail_copy)

    success, _ = file_utils.copy_file_sync(source, target)

    assert success is False
    assert target.read_bytes() == b"old"
    assert list(tmp_path.glob(".target.jpg.*.tmp")) == []


def test_copy_file_sync_replaces_target_after_success(tmp_path: Path):
    source = tmp_path / "source.jpg"
    target = tmp_path / "target.jpg"
    source.write_bytes(b"new")
    target.write_bytes(b"old")

    success, error = file_utils.copy_file_sync(source, target)

    assert success is True
    assert error == ""
    assert target.read_bytes() == b"new"


@pytest.mark.asyncio
async def test_copy_file_async_keeps_existing_target_when_copy_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = tmp_path / "source.jpg"
    target = tmp_path / "target.jpg"
    source.write_bytes(b"new")
    target.write_bytes(b"old")

    def fail_copy(*args, **kwargs):
        raise OSError("simulated copy failure")

    monkeypatch.setattr(file_utils.shutil, "copy", fail_copy)

    success, _ = await file_utils.copy_file_async(source, target)

    assert success is False
    assert target.read_bytes() == b"old"
    assert list(tmp_path.glob(".target.jpg.*.tmp")) == []
