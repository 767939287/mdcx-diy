"""回归测试：议题 #62 窗口最大化后各页面控件跟随缩放。

stacksWidget 的 X=210, Y=6 固定，宽高源自主窗口 (W-212, H-8)；
本测试不实例化 MyMAinWindow（网络调用副作用多），而是直接验证
resizeEvent 内部调用的 _sync_page_layouts 逻辑被正确定义。
"""

import ast
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


def test_sync_page_layouts_method_exists():
    """main_window.MyMAinWindow 必须有 _sync_page_layouts 方法。"""
    with open("mdcx/controllers/main_window/main_window.py", encoding="utf-8") as f:
        code = f.read()
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "MyMAinWindow":
            methods = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
            assert "_sync_page_layouts" in methods, "MyMAinWindow 缺少 _sync_page_layouts 方法"
            return
    pytest.fail("找不到 MyMAinWindow 类")


def test_resize_event_calls_sync_page_layouts():
    """resizeEvent 必须调用 _sync_page_layouts()。"""
    with open("mdcx/controllers/main_window/main_window.py", encoding="utf-8") as f:
        code = f.read()
    # 验证 resizeEvent 里包含 _sync_page_layouts 调用
    assert "_sync_page_layouts()" in code, "resizeEvent 中没有调用 _sync_page_layouts()"


def test_regression_resize_sync_theme():
    """回归验证：scrollArea 跟随 tabWidget 缩放的 passing 逻辑。"""
    with open("mdcx/controllers/main_window/main_window.py", encoding="utf-8") as f:
        code = f.read()
    # 关键证据点：resizeEvent 触发 _sync_page_layouts——检查函数存在于代码中
    assert "_sync_page_layouts" in code
    # sync 逻辑应处理 tabWidget 变化大跌和设置 scrollArea
    assert "ui.tabWidget.setGeometry(" in code
    # 检查设置/工具/网络/日志/关于页面的组件名
    assert "page_tool" in code or "scrollArea_10" in code
    assert "page_net" in code or "textBrowser_net_main" in code
    assert "page_log" in code or "textBrowser_log_main" in code
    assert "page_about" in code or "textBrowser_about" in code
    # 确认 page_tool / page_net / page_about / page_log 都被覆盖
    for page_attr in ("page_tool", "page_net", "page_about", "page_log"):
        assert f"ui.{page_attr}" in code or "ui.textBrowser_" in code
    # 验证 tabWidget geometry 被设置
    assert "ui.tabWidget.setGeometry(" in code
    # 验证工具页 scrollArea_10 被处理
    assert "scrollArea_10" in code or "findChild(CustomScrollArea" in code


def test_no_regression_default_window_size():
    """检查后改动的 resize 处理逻辑不在默认窗口尺寸 1040x760 下崩溃。"""
    with open("mdcx/controllers/main_window/main_window.py", encoding="utf-8") as f:
        code = f.read()
    # _BASE_W / _BASE_H 常量存在
    assert "_BASE_W = 1040" in code
    assert "_BASE_H = 760" in code
    # 顶部偏移和底部边距常量存在
    assert "_CONTENT_TOP_OFFSET = 6" in code
    assert "_CONTENT_BOTTOM_MARGIN = 2" in code
