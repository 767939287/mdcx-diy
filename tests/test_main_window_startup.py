"""启动冒烟测试：offscreen 下完整构造主窗口。

回归背景：v2.0.6 NFO 库页布局修复引入了 PyQt5 风格的
`QLayout.setStretchFactor(index, stretch)` 调用，PyQt6 严格重载下
启动即抛 TypeError 崩溃（Windows 打包版首发时暴露）。本测试
在 CI 双平台（Linux offscreen / Windows offscreen）完整执行主窗口
初始化链（setupUi → Init_Singal → Init_Ui → load_config → ...），
任何签名不兼容/属性缺失都会在此暴露，而不是留给用户运行时发现。
"""

import sys

import pytest
from PyQt6.QtWidgets import QApplication

_app: QApplication | None = None


def _ensure_app() -> QApplication:
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


@pytest.fixture(scope="module")
def app():
    return _ensure_app()


def test_main_window_startup_no_crash(app, monkeypatch, tmp_path):
    """MyMAinWindow 完整初始化不抛异常（含 Init_Singal 全部信号/布局调用）。"""
    # 打桩启动链中与 GUI 无关的副作用：网络自检/版本检查/剩余任务保存
    from mdcx.controllers.main_window import main_window as mw_mod

    monkeypatch.setattr(mw_mod, "run_startup_health_checks", lambda: None)
    monkeypatch.setattr(mw_mod, "show_netstatus", lambda: None)
    monkeypatch.setattr(mw_mod, "check_version", lambda: None)
    monkeypatch.setattr(mw_mod, "save_remain_list", lambda: None)

    monkeypatch.chdir(tmp_path)  # load_config/get_success_list 会写当前目录

    win = mw_mod.MyMAinWindow()
    try:
        assert win.Ui is not None
        # NFO 库页三栏 stretch 已应用（回归点：setStretch 而非 setStretchFactor(int)）
        layout = win.Ui.nfo_lib_content_layout
        assert layout.itemAt(0) is not None
        assert layout.itemAt(1) is not None
        assert layout.itemAt(2) is not None
    finally:
        win.timer.stop()
        win.timer_scrape.stop()
        win.timer_update.stop()
        win.timer_remain_task.stop()
        win.close()
        win.deleteLater()
        app.processEvents()


def test_emby_actor_manager_dialog_startup_no_crash(app):
    """Emby 演员管理器对话框完整构造不抛异常。

    覆盖 _init_ui 全部 Qt 控件构造路径（QSplitter/表格/日志区等），
    配合主窗口冒烟测试，防止 PyQt6 签名不兼容类问题推迟到用户
    打开窗口时才暴露。
    """
    from mdcx.tools.emby_actor_manager_ui import EmbyActorManagerDialog

    dlg = EmbyActorManagerDialog()
    try:
        assert dlg.windowTitle() == "Emby 演员管理器"
    finally:
        dlg.close()
        dlg.deleteLater()
        app.processEvents()


def test_emby_actor_settings_dialog_startup_no_crash(app):
    """Emby 演员管理器设置对话框完整构造不抛异常。"""
    from mdcx.tools.emby_actor_manager_ui import EmbyActorSettingsDialog

    dlg = EmbyActorSettingsDialog()
    try:
        assert dlg.windowTitle()
    finally:
        dlg.close()
        dlg.deleteLater()
        app.processEvents()
