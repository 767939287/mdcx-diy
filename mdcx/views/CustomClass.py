from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QComboBox, QScrollArea, QSlider, QSpinBox


class CustomQComboBox(QComboBox):
    def wheelEvent(self, e):
        if e.type() == QEvent.Type.Wheel:
            e.ignore()


class CustomQSpinBox(QSpinBox):
    def wheelEvent(self, e):
        if e.type() == QEvent.Type.Wheel:
            e.ignore()


class CustomQSlider(QSlider):
    def wheelEvent(self, e):
        if e.type() == QEvent.Type.Wheel:
            e.ignore()


class CustomScrollArea(QScrollArea):
    """widgetResizable=true 时按子控件包围盒维护内容最小高度的滚动区。

    背景：设计器生成的滚动区内容 widget 无布局，子控件绝对定位；
    widgetResizable=false 时内容保持固定几何尺寸、垂直滚动正常，但内容
    宽度不跟随视口（高 DPI 下右侧被裁剪）；widgetResizable=true 后宽度自
    适应，但 Qt 对无布局 widget 的最小尺寸提示不来自 childrenRect，内容
    被拉伸到视口高度，垂直滚动条失效。这里在滚动区尺寸变化 / 页面显示时
    按 childrenRect 显式补最小高度，同时保留宽度自适应。
    """

    # Leave enough room for the last row, frame, font metrics, and DPI scaling.
    _CONTENT_BOTTOM_MARGIN = 60

    def sync_content_min_height(self) -> None:
        content = self.widget()
        if content is None:
            return
        children_rect = content.childrenRect()
        if children_rect.height() <= 0:
            return
        min_width = children_rect.right() + 1
        min_height = children_rect.bottom() + self._CONTENT_BOTTOM_MARGIN
        if content.minimumWidth() != min_width or content.minimumHeight() != min_height:
            content.setMinimumWidth(min_width)
            content.setMinimumHeight(min_height)
            content.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.sync_content_min_height()

    def showEvent(self, event):
        super().showEvent(event)
        self.sync_content_min_height()
