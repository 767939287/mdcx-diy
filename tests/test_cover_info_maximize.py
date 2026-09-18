"""议题 #144/#152 回归: 最大化时封面/缩略图随框同步放大; 简介/标签行高随窗口增高。

三态纪律(MEMORY #110/#117): fresh 小窗 → 拉大 → 还原小窗, 断言
1) 封面 pixmap 显示尺寸跟随 label 框几何(等比、随窗口变大变小), 且切换封面
   后不得再把已放大的框砸回设计尺寸(旧 resize(156,220) 硬编码回归);
2) 简介/标签行高: 小窗 == 设计 40, 大窗 > 40(按整行 40px 翻倍、最多 4 行),
   下划线随行底, 后续行 = +2*grow(#152 撤销 #144 的 60px 拉伸行高);
3) 还原后与小窗 fresh 状态完全一致(双向幂等)。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtGui import QColor, QImage, QPixmap
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
    # 本文件断言全部为几何公式驱动(pixmap scaled 尺寸/行高公式), 不涉字体度量
    # 临界点; 保留 set_style stub 与 window_state_matrix 家族一致, 若未来涉及
    # 换行/裁剪断言必须改挂真实样式(#117 教训)。
    monkeypatch.setattr(mw_mod.MyMAinWindow, "set_style", lambda self: None)

    monkeypatch.chdir(tmp_path)

    window = mw_mod.MyMAinWindow()
    # 停掉 QTimer 防 qFatal(MEMORY: 含 Qt 测试纪律)
    from PyQt6.QtCore import QTimer

    for timer in window.findChildren(QTimer):
        timer.stop()
    window.show()
    yield window
    window.close()


def _make_pixmap(w: int, h: int) -> QPixmap:
    image = QImage(w, h, QImage.Format.Format_RGB32)
    image.fill(QColor(200, 30, 30))
    return QPixmap.fromImage(image)


def _posters(win) -> tuple[QPixmap, QPixmap]:
    poster = _make_pixmap(331, 475)
    thumb = _make_pixmap(800, 539)
    win.resize_label_and_setpixmap(
        [True, poster, "Local: 331*475", 156, 220], [True, thumb, "Local: 800*539", 328, 220]
    )
    return poster, thumb


def test_pixmap_tracks_box_geometry_on_grow_and_restore(win):
    ui = win.Ui
    ui.checkBox_cover.setChecked(True)
    _posters(win)

    win.resize(1032, 737)
    win._sync_page_layouts()
    small_box_h = ui.label_poster.height()
    small_pic_h = ui.label_poster.pixmap().size().height()
    assert small_pic_h == small_box_h, "竖版封面在小窗应按框高贴合"

    win.resize(1600, 1000)
    win._sync_page_layouts()
    big_box_h = ui.label_poster.height()
    big_pic_h = ui.label_poster.pixmap().size().height()
    assert big_box_h > small_box_h, "最大化封面框应按 cover_scale 增大"
    assert big_pic_h == big_box_h, f"封面图必须随框同步放大: box={big_box_h} pic={big_pic_h}"

    win.resize(1032, 737)
    win._sync_page_layouts()
    assert ui.label_poster.pixmap().size().height() == small_pic_h
    assert (
        ui.label_thumb.pixmap().size().height() < ui.label_thumb.height()
        or ui.label_thumb.pixmap().size().width() <= ui.label_thumb.width()
    )


def test_switching_cover_keeps_enlarged_box(win):
    """切换新封面不得把已放大的框砸回 156x220(旧硬编码 resize 回归)。"""
    ui = win.Ui
    win.resize(1600, 1000)
    win._sync_page_layouts()
    box_before = ui.label_poster.size()

    _posters(win)  # resize_label_and_setpixmap 模拟切番号出图
    assert ui.label_poster.size() == box_before, "出图流程不得改写已放大的几何"
    assert ui.label_poster.size().height() > 220


def test_info_rows_grow_for_taller_window(win):
    ui = win.Ui
    win.resize(1030, 700)
    win._sync_page_layouts()
    assert ui.label_outline.height() == 40, "默认窗口(设计基准)简介行高必须保持 40"
    small_outline_h = ui.label_outline.height()

    win.resize(1700, 1100)
    win._sync_page_layouts()
    big_outline_h = ui.label_outline.height()
    grow = big_outline_h - 40
    assert grow > 0, "窗口拉高后简介行高必须增高(可显示更多行)"
    assert grow % 40 == 0, f"简介行高按整行(40px)翻倍: grow={grow}"
    assert big_outline_h <= 40 + 4 * 40, "行高增幅必须有上限(最多 4 行翻倍)"
    # 下划线贴行底(设计偏移 30 保持), 标签行在 underline 间距 20 之后
    assert ui.line_6.y() - ui.label_outline.y() == 30 + grow
    assert ui.label_tag.y() - ui.line_6.y() == 20
    assert ui.line_7.y() - ui.label_tag.y() == 30 + grow
    # 简介/标签以下(日期行)再让出两行增高
    assert ui.label_release.y() - ui.line_7.y() >= 20
    assert ui.label_outline.y() <= ui.line_6.y() < ui.label_tag.y() < ui.line_7.y() <= ui.label_release.y()

    win.resize(1030, 700)
    win._sync_page_layouts()
    assert ui.label_outline.height() == small_outline_h == 40, "还原必须回到设计行高(双向幂等)"


def test_cover_off_placeholder_survives_resizes(win):
    """关闭封面显示后 resize 不得把图盖回占位文本。"""
    ui = win.Ui
    ui.checkBox_cover.setChecked(True)
    _posters(win)
    ui.checkBox_cover.setChecked(False)
    win.checkBox_cover_clicked()

    win.resize(1600, 1000)
    win._sync_page_layouts()
    assert ui.label_poster.text() == "封面图"
    assert ui.label_poster.pixmap().isNull()
