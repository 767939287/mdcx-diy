"""议题 #154 回归：编辑 NFO 覆盖层随窗口缩放。

背景：覆盖层内容区此前固定 860x1300、19 个字段绝对定位，窗口最大化后字段
仍定宽（右侧大片留白）；保存/关闭按钮固定在 y=630 中部，窗口放大后悬在中间。
现内容区改行式布局随宽度拉伸、按钮钉底。断言：
1) 内容区建立布局，字段宽度随窗口增大；
2) 双字段行左右不重叠；
3) 保存/关闭钉底右下且不被滚动区覆盖；
4) 首次打开路径（不经 resizeEvent）也会同步几何。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

_app: QApplication | None = None


def _ensure_app() -> QApplication:
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


@pytest.fixture(scope="module")
def app():
    return _ensure_app()


@pytest.fixture()
def win(app, monkeypatch, tmp_path):
    from mdcx.controllers.main_window import main_window as mw_mod

    monkeypatch.setattr(mw_mod, "run_startup_health_checks", lambda: None)
    monkeypatch.setattr(mw_mod, "show_netstatus", lambda: None)
    monkeypatch.setattr(mw_mod, "check_version", lambda: None)
    monkeypatch.setattr(mw_mod, "save_remain_list", lambda: None)
    monkeypatch.setattr(mw_mod, "apply_site_priority_theme", lambda _window: None)
    monkeypatch.setattr(mw_mod.MyMAinWindow, "set_style", lambda self: None)
    monkeypatch.chdir(tmp_path)

    window = mw_mod.MyMAinWindow()
    from PyQt6.QtCore import QTimer

    for timer in window.findChildren(QTimer):
        timer.stop()
    window.show()
    yield window
    window.close()


def _open_overlay(win):
    win.Ui.widget_nfo.show()
    win._sync_nfo_overlay_geometry()


def test_overlay_fields_widen_with_window(win):
    ui = win.Ui
    _open_overlay(win)
    content = ui.scrollAreaWidgetContents_nfo_editor
    assert content.layout() is not None, "覆盖层内容区未建立自适应布局"

    win.resize(1032, 737)
    win._sync_nfo_overlay_geometry()
    small_actor_w = ui.lineEdit_nfo_actor.width()
    small_content_w = content.width()

    win.resize(1920, 1080)
    win._sync_nfo_overlay_geometry()
    assert ui.lineEdit_nfo_actor.width() > small_actor_w, "最大化后字段未随宽度拉伸"
    assert content.width() > small_content_w, "内容区宽度未随视口增大"
    assert ui.lineEdit_nfo_actor.width() == pytest.approx(content.width() - 9 - 9 - 82 - 10, abs=4), (
        "单行字段应铺满内容区可用宽度"
    )


def test_overlay_pair_rows_do_not_overlap(win):
    ui = win.Ui
    _open_overlay(win)
    win.resize(1920, 1080)
    win._sync_nfo_overlay_geometry()
    pairs = (
        (ui.lineEdit_nfo_release, ui.lineEdit_nfo_runtime),
        (ui.lineEdit_nfo_score, ui.lineEdit_nfo_wanted),
        (ui.lineEdit_nfo_director, ui.lineEdit_nfo_series),
        (ui.lineEdit_nfo_studio, ui.lineEdit_nfo_publisher),
    )
    for left, right in pairs:
        assert left.x() + left.width() <= right.x(), f"{left.objectName()} 与 {right.objectName()} 重叠"
        assert right.x() + right.width() <= ui.scrollAreaWidgetContents_nfo_editor.width(), "右字段越界"


def test_overlay_buttons_pinned_to_bottom(win):
    ui = win.Ui
    _open_overlay(win)
    nfo = ui.widget_nfo
    scroll = ui.scrollArea_nfo
    for width, height in ((1032, 737), (1920, 1080)):
        win.resize(width, height)
        win._sync_nfo_overlay_geometry()
        save, close = ui.pushButton_nfo_save, ui.pushButton_nfo_close
        assert save.y() == nfo.height() - 12 - 40, f"{width}x{height}: 保存按钮未钉底 (y={save.y()})"
        assert close.x() == nfo.width() - 12 - 91, f"{width}x{height}: 关闭按钮未贴右缘"
        assert scroll.y() + scroll.height() <= save.y(), "滚动区覆盖了底部操作条"
        assert save.x() + save.width() <= close.x(), "保存/关闭按钮重叠"


def test_overlay_syncs_on_first_open_without_resize(win, monkeypatch):
    ui = win.Ui
    monkeypatch.setattr(win, "_check_main_file_path", lambda: True)
    monkeypatch.setattr(win, "_show_nfo_info", lambda: None)
    assert ui.widget_nfo.isHidden()
    win.main_open_nfo_click()
    nfo = ui.widget_nfo
    assert not nfo.isHidden()
    assert ui.pushButton_nfo_save.y() == nfo.height() - 12 - 40, "首次打开未同步钉底几何"
    assert ui.scrollAreaWidgetContents_nfo_editor.layout() is not None, "首次打开未建立内容布局"
