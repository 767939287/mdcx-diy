"""UI 几何回归测试：防止同一 gridLayout 内可见控件包围盒相交（重影/重叠）。

历史坑：
- 翻译页 label_baidu_hint 放 col0 长文本不换行向右溢出，被 col1 的 label_60
  不透明背景遮挡，露出前半截产生重影
- 网络页 trusted_hosts 输入框与超时行同 cell 冲突（同一 gridLayout cell 放两 widget）
- 多处 gridLayout 同行同列多 item 覆盖

这些都是运行时几何冲突，纯 XML 静态结构测试 (test_ui_structure) 抓不到。
本测试 offscreen 实例化 Ui_MDCx，强制激活每个 gridLayout，断言同 layout 内
任意两个可见直接子控件包围盒无交集。覆盖 .ui 静态控件层（运行时动态注入的
控件需收口到 .ui 后才能覆盖）。
"""

import os
from itertools import combinations

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import (
    QApplication,
    QGridLayout,
    QLayout,
    QMainWindow,
    QStackedWidget,
    QTabWidget,
    QWidget,
)

import mdcx.views.MDCx as M

# comboBox popup 等内部子部件在 offscreen 下有 (0,0)/(100,30)/(640,480) 占位
# geometry，与几何校验无关，全部跳过（参见 MEMORY 的 findChildren 几何检查排除项）。
_POPUP_CLASSES = {"QListView", "QScrollBar", "QMenu", "QComboBoxListView", "QToolButton"}

# 已知的合法重叠（非 bug）。新增条目前请先确认是否真为 bug。
# 每项: (parent_objectname, widget1_objectname, widget2_objectname)
_KNOWN_OK_OVERLAPS: set[tuple[str, str, str]] = {
    # widget_setting 侧边栏：left_backgroud_widget 是全幅背景层，上层按钮/关闭区合法叠加
    ("widget_setting", "close_widget", "left_backgroud_widget"),
    ("widget_setting", "left_backgroud_widget", "widget_buttons"),
    # groupBox_10 内「演示动画：」label_7 与其后的链接 label_get_cookie_url 紧邻设计
    ("groupBox_10", "label_7", "label_get_cookie_url"),
}


def _skip_widget(w: QWidget) -> bool:
    if not w.isVisible():
        return True
    if w.__class__.__name__ in _POPUP_CLASSES:
        return True
    g = w.geometry()
    if g.isNull() or g.width() <= 0 or g.height() <= 0:
        return True
    return False


def _bbox_in(w: QWidget, ref: QWidget) -> tuple[int, int, int, int] | None:
    g = w.geometry()
    if g.isNull() or g.width() <= 0 or g.height() <= 0:
        return None
    tl = w.mapTo(ref, g.topLeft())
    br = w.mapTo(ref, g.bottomRight())
    return (tl.x(), tl.y(), br.x(), br.y())


def _overlap_area(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy


def _activate_ancestors(w: QWidget) -> None:
    """offscreen 下 widget 必须自身及所有祖先可见才会被布局引擎计算几何。"""
    cur: QWidget | None = w
    while cur is not None:
        try:
            cur.setVisible(True)
        except Exception:
            break
        cur = cur.parentWidget()


def _activate_all_tabs(mw: QMainWindow) -> None:
    """切换每个 QTabWidget / QStackedWidget 的所有页，触发隐藏页子控件布局。"""
    app = QApplication.instance()
    for tw in mw.findChildren(QTabWidget):
        for i in range(tw.count()):
            tw.setCurrentIndex(i)
            if app is not None:
                app.processEvents()
    for sw in mw.findChildren(QStackedWidget):
        for i in range(sw.count()):
            w = sw.widget(i)
            if w is not None:
                sw.setCurrentWidget(w)
                if app is not None:
                    app.processEvents()


def _activate(layout: QLayout) -> None:
    """offscreen 下 tab 未激活时子控件 geometry 全 0，强制激活布局让 geometry 生效。"""
    pw = layout.parentWidget()
    if pw is None:
        return
    try:
        _activate_ancestors(pw)
        pw.show()
        pw.ensurePolished()
        sz = pw.sizeHint()
        if sz.isValid() and not sz.isEmpty():
            pw.resize(sz.expandedTo(pw.minimumSizeHint()))
        layout.activate()
        layout.invalidate()
        layout.activate()
        app = QApplication.instance()
        if app is not None:
            app.processEvents()
    except Exception:
        pass


_APP: QApplication | None = None
_MW: QMainWindow | None = None


@pytest.fixture(scope="module")
def main_window() -> QMainWindow:
    # QApplication / QMainWindow 必须由 module 级全局持有，否则 fixture 返回后
    # 局部 app 被 GC 析构会连带删除所有 Qt 窗体（offscreen 下复现）。
    global _APP, _MW
    if _APP is None:
        _APP = QApplication.instance() or QApplication([])
    if _MW is None:
        _MW = QMainWindow()
        M.Ui_MDCx().setupUi(_MW)
        _MW.show()
        _APP.processEvents()
    return _MW


def test_gridlayouts_no_visible_overlap(main_window: QMainWindow) -> None:
    _activate_all_tabs(main_window)
    failures: list[str] = []
    for lay in main_window.findChildren(QLayout):
        if not isinstance(lay, QGridLayout):
            continue
        _activate(lay)
        ref = lay.parentWidget()
        if ref is None:
            continue
        ref_name = ref.objectName() or ""
        boxes: list[tuple[str, tuple[int, int, int, int]]] = []
        for i in range(lay.count()):
            it = lay.itemAt(i)
            w = it.widget() if it is not None else None
            if w is None:
                continue
            if _skip_widget(w):
                continue
            bb = _bbox_in(w, ref)
            if bb is None:
                continue
            boxes.append((w.objectName() or w.__class__.__name__, bb))
        for (n1, a), (n2, b) in combinations(boxes, 2):
            if _overlap_area(a, b) <= 0:
                continue
            key = tuple(sorted((n1, n2)))
            if (ref_name, key[0], key[1]) in _KNOWN_OK_OVERLAPS:
                continue
            failures.append(f"layout={ref_name!r} 重叠: {n1}{a} <-> {n2}{b} (面积 {_overlap_area(a, b)})")
    assert not failures, "检测到 gridLayout 内可见控件重叠（重影风险）:\n" + "\n".join(failures)


def test_absolutely_positioned_children_no_overlap(main_window: QMainWindow) -> None:
    """绝对定位子控件重叠检查。

    覆盖父 widget 无 layout（layout() is None）的情形：子控件靠 setGeometry
    绝对摆放（如 groupBox_10 内的 label_75/label_get_cookie_url/label_7 +
    gridLayoutWidget_10）。三处动态注入收口后这些绝对坐标已固化进 .ui，
    本测试防止「增高/下移固化时绝对定位控件互相压叠或溢出」类回归。
    QStackedWidget/QTabWidget 自带 layout 不会进入本分支，其堆叠页天然
    同位不误报。
    """
    _activate_all_tabs(main_window)
    app = QApplication.instance()
    failures: list[str] = []
    for parent in main_window.findChildren(QWidget):
        if parent.layout() is not None:
            continue
        # QMainWindow 的 centralWidget 在 offscreen 下未 resize，其直接子
        # （tabWidget/各分区容器）几何退化，无法做有效重叠校验。
        if parent.objectName() == "centralwidget":
            continue
        # tab 页容器（page_*）含运行时切换显示的日志/列表控件，offscreen 下
        # 默认全 visible 会误报；非本次收口范围，排除。
        if parent.objectName().startswith("page_"):
            continue
        _activate_ancestors(parent)
        try:
            parent.show()
            parent.ensurePolished()
            if app is not None:
                app.processEvents()
        except Exception:
            pass
        pg = parent.geometry()
        if pg.isNull() or pg.width() <= 0 or pg.height() <= 0:
            continue
        ref_name = parent.objectName() or parent.__class__.__name__
        boxes: list[tuple[str, tuple[int, int, int, int]]] = []
        for child in parent.children():
            if not isinstance(child, QWidget):
                continue
            if _skip_widget(child):
                continue
            bb = _bbox_in(child, parent)
            if bb is None:
                continue
            # offscreen 下未激活布局的子控件几何退化为 1x1 占位，跳过
            if bb[2] - bb[0] <= 1 and bb[3] - bb[1] <= 1:
                continue
            boxes.append((child.objectName() or child.__class__.__name__, bb))
        for (n1, a), (n2, b) in combinations(boxes, 2):
            if _overlap_area(a, b) <= 0:
                continue
            key = tuple(sorted((n1, n2)))
            if (ref_name, key[0], key[1]) in _KNOWN_OK_OVERLAPS:
                continue
            failures.append(f"parent={ref_name!r} 绝对定位子重叠: {n1}{a} <-> {n2}{b} (面积 {_overlap_area(a, b)})")
    assert not failures, "检测到绝对定位子控件重叠（重影风险）:\n" + "\n".join(failures)
