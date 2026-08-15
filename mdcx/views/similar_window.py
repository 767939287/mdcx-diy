"""相似片推荐对话框：展示与当前选中影片最相似的刮削结果，双击可跳转。"""


from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QLabel, QListWidget, QListWidgetItem, QVBoxLayout

from ..core.similar import SimilarIndex


class SimilarDialog(QDialog):
    """相似片推荐列表对话框。

    构造时传入语料（全部刮削结果）与当前选中影片，
    内部用 SimilarIndex 计算相似度并在列表中展示。
    """

    item_selected = pyqtSignal(str)  # 番号，双击推荐项时发出

    def __init__(
        self,
        corpus: list,
        target,
        parent=None,
        top_n: int = 12,
    ):
        super().__init__(parent)
        self._corpus = corpus
        self._target = target
        self.setWindowTitle(f"相似片推荐 · {getattr(target, 'number', '')}")
        self.resize(480, 480)
        self._build_ui()
        self._populate(top_n)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        hint = QLabel("以下为与当前影片最相似的刮削结果（基于标签/系列/片商/演员等），双击可跳转：")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._list)

        count_label = QLabel()
        layout.addWidget(count_label)
        self._count_label = count_label

    def _populate(self, top_n: int):
        try:
            index = SimilarIndex(self._corpus)
            ranked = index.rank(self._target, top_n=top_n)
        except Exception:
            ranked = []
        if not ranked:
            self._list.addItem("暂无可推荐的相似片（语料太少或与其它影片无共同标签）")
            self._count_label.setText("共 0 条推荐")
            return

        for cand, score in ranked:
            number = getattr(cand, "number", "") or ""
            title = getattr(cand, "title", "") or ""
            series = getattr(cand, "series", "") or ""
            text = f"{number} · 相似度 {score:.2f}"
            if title:
                text += f"\n{title}"
            if series:
                text += f"\n系列: {series}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, number)
            self._list.addItem(item)
        self._count_label.setText(f"共 {len(ranked)} 条推荐")

    def _on_item_double_clicked(self, item: QListWidgetItem):
        number = item.data(Qt.ItemDataRole.UserRole)
        if number:
            self.item_selected.emit(str(number))

    @staticmethod
    def collect_corpus(json_data_dic: dict) -> list:
        """从 Flags.json_data_dic 收集可作为相似语料的刮削结果。

        过滤掉缺番号或完全无标签/无演员的结果，避免噪声。
        """
        corpus = []
        for scrape_result in json_data_dic.values():
            data = getattr(scrape_result, "data", None)
            if data is None:
                continue
            if not getattr(data, "number", "") or not getattr(data, "title", ""):
                continue
            tags = getattr(data, "tags", []) or []
            actors = getattr(data, "actors", []) or []
            if not tags and not actors:
                continue
            corpus.append(data)
        return corpus
