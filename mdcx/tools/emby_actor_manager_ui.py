from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config.manager import manager
from .emby_actor_manager import (
    ActorInfo,
    fetch_all_actors,
    from_gfriends,
    from_local_avatar,
    from_minnano_image,
    get_gfriends_index,
    get_media_folders,
    search_actor_info,
    sync_batch,
)


class LibrarySelectDialog(QDialog):
    def __init__(self, libraries: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择媒体库")
        self.setMinimumWidth(420)
        self.setMinimumHeight(320)
        self._libraries = libraries
        self._checkboxes = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        count = len(self._libraries)
        label = QLabel(f"选择要获取演员的媒体库（共 {count} 个，默认全选）：")
        layout.addWidget(label)
        self.list_widget = QListWidget()
        for lib in self._libraries:
            name = lib.get("Name", "未知")
            ctype = lib.get("CollectionType", "")
            display = f"{name}  [{ctype}]" if ctype else name
            cb = QCheckBox(display)
            cb.setChecked(True)
            self._checkboxes.append(cb)
            item = QListWidgetItem()
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, cb)
        layout.addWidget(self.list_widget)
        btn_layout = QHBoxLayout()
        btn_all = QPushButton("全选")
        btn_all.clicked.connect(lambda: self._set_all(True))
        btn_none = QPushButton("取消全选")
        btn_none.clicked.connect(lambda: self._set_all(False))
        btn_layout.addWidget(btn_all)
        btn_layout.addWidget(btn_none)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_all(self, checked: bool):
        for cb in self._checkboxes:
            cb.setChecked(checked)

    def get_selected_ids(self) -> list[str]:
        selected = []
        for i, cb in enumerate(self._checkboxes):
            if cb.isChecked() and i < len(self._libraries):
                selected.append(self._libraries[i].get("Id", ""))
        return selected


class FetchActorsThread(QThread):
    progress = Signal(int, int, str)
    fetch_done = Signal(list)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.library_ids = None

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            actors = loop.run_until_complete(
                fetch_all_actors(
                    filter_actor_only=True,
                    deduplicate=True,
                    parent_ids=self.library_ids,
                    progress_callback=lambda c, t, m: self.progress.emit(c, t, m),
                )
            )
            self.fetch_done.emit(actors)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            loop.close()


class PreparePreviewThread(QThread):
    progress = Signal(int, int, str)
    preview_done = Signal(list)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.actors = []
        self.mode = "missing_all"
        self.gfriends_index = None
        self.cache_dir = Path("/tmp")
        self.minnano_cache = None
        self.image_sources = ["gfriends", "minnano", "local"]
        self.info_sources = ["minnano", "local_db"]
        self.local_avatar_dir = ""
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        from .emby_actor_manager import load_cache as minnano_load_cache

        minnano_load_cache()
        total = len(self.actors)
        if total == 0:
            self.preview_done.emit(self.actors)
            return
        need_image = self.mode in ("missing_all", "missing_image", "force_all", "force_image")
        need_info = self.mode in ("missing_all", "missing_info", "force_all", "force_info")
        force = "force" in self.mode
        completed = 0
        cancelled = False

        def process_one(actor: ActorInfo):
            if self._cancel:
                return
            if need_image:
                self._try_fetch_image(actor, force)
            if need_info:
                self._try_fetch_info(actor, force)

        max_workers = 10
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_one, actor): actor for actor in self.actors}
            for future in as_completed(futures):
                if self._cancel:
                    cancelled = True
                    break
                completed += 1
                try:
                    future.result()
                except Exception:
                    pass
                actor = futures[future]
                self.progress.emit(completed, total, f"处理中: {actor.name} ({completed}/{total})")
            if cancelled:
                for f in futures:
                    f.cancel()
        if not cancelled:
            self.progress.emit(total, total, "预览数据准备完成")
        self.preview_done.emit(self.actors)

    def _try_fetch_image(self, actor: ActorInfo, force: bool):
        if not force and actor.has_image:
            return
        for src in self.image_sources:
            if src == "gfriends" and self.gfriends_index:
                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(from_gfriends(actor, self.gfriends_index, self.cache_dir))
                finally:
                    loop.close()
                if result:
                    actor.new_image_path = result
                    actor.need_update_image = True
                    return
            elif src == "minnano":
                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(from_minnano_image(actor, self.cache_dir))
                finally:
                    loop.close()
                if result:
                    actor.new_image_path = result
                    actor.need_update_image = True
                    return
            elif src == "local":
                result = from_local_avatar(actor, self.local_avatar_dir)
                if result:
                    actor.new_image_path = result
                    actor.need_update_image = True
                    return

    def _try_fetch_info(self, actor: ActorInfo, force: bool):
        if not force and actor.has_overview:
            return
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(search_actor_info(actor))
        finally:
            loop.close()
        if result:
            actor.need_update_info = True


class SyncThread(QThread):
    progress = Signal(int, int, str)
    actor_done = Signal(str, bool, str)
    sync_done = Signal(int, int)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.actors = []
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            success, fail = sync_batch(
                self.actors,
                progress_callback=lambda c, t, m: self.progress.emit(c, t, m),
                actor_callback=lambda actor, ok, msg: self.actor_done.emit(actor.name, ok, msg),
            )
            self.sync_done.emit(success, fail)
        except Exception as e:
            self.error.emit(str(e))


class EmbyActorManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Emby 演员管理器")
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(self._load_stylesheet())
        self.cache_dir = Path("/tmp/emby_actor_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._actors: list[ActorInfo] = []
        self._gfriends_index = None
        self._preview_thread = None
        self._sync_thread = None
        self._fetch_thread = None
        self._avatar_cache: dict[str, QPixmap | None] = {}
        self._init_ui()
        self._connect_signals()

    def _load_stylesheet(self) -> str:
        return """
        QGroupBox { font-weight: bold; border: 1px solid #cccccc; border-radius: 4px; margin-top: 8px; padding-top: 14px; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
        QTableWidget { gridline-color: #e0e0e0; selection-background-color: #bbdefb; }
        QTableWidget::item:selected { background-color: #42a5f5; color: #ffffff; }
        QPushButton#btnSync { background-color: #2e7d32; color: #ffffff; font-weight: bold; }
        QPushButton#btnSync:hover { background-color: #388e3c; }
        QPushButton#btnDanger { background-color: #c62828; color: #ffffff; }
        QPushButton#btnDanger:hover { background-color: #d32f2f; }
        QPushButton#btnPrimary { background-color: #1565c0; color: #ffffff; }
        QPushButton#btnPrimary:hover { background-color: #1976d2; }
        """

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)
        self._build_connection_section(main_layout)
        splitter = QSplitter(Qt.Orientation.Vertical)
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        self._build_actor_list(list_layout)
        splitter.addWidget(list_widget)
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)
        self._build_log_section(log_layout)
        splitter.addWidget(log_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter, 1)

    def _build_connection_section(self, parent_layout: QVBoxLayout):
        group = QGroupBox("Emby 连接设置")
        grid = QGridLayout(group)
        grid.setSpacing(8)
        grid.addWidget(QLabel("Emby 地址:"), 0, 0)
        self.txt_url = QLineEdit(str(manager.config.emby_url or ""))
        self.txt_url.setPlaceholderText("http://192.168.1.100:8096")
        grid.addWidget(self.txt_url, 0, 1)
        grid.addWidget(QLabel("API 密钥:"), 0, 2)
        self.txt_api_key = QLineEdit(manager.config.api_key or "")
        self.txt_api_key.setPlaceholderText("Emby 管理后台 → 高级 → API 密钥")
        self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        grid.addWidget(self.txt_api_key, 0, 3)
        btn_layout = QHBoxLayout()
        self.btn_connect = QPushButton("连接 Emby")
        self.btn_connect.setObjectName("btnPrimary")
        btn_layout.addWidget(self.btn_connect)
        self.btn_fetch = QPushButton("获取演员列表")
        self.btn_fetch.setObjectName("btnPrimary")
        self.btn_fetch.setEnabled(False)
        btn_layout.addWidget(self.btn_fetch)
        self.cmb_fetch_mode = QComboBox()
        self.cmb_fetch_mode.addItems(
            [
                "仅全部缺失头像+简介",
                "仅全部缺失头像",
                "仅全部缺失简介",
                "全部头像+简介（重新获取）",
                "全部头像（重新获取）",
                "全部简介（重新获取）",
            ]
        )
        self.cmb_fetch_mode.setCurrentIndex(0)
        self.cmb_fetch_mode.setFixedWidth(220)
        btn_layout.addWidget(self.cmb_fetch_mode)
        self.btn_preview = QPushButton("获取数据")
        self.btn_preview.setObjectName("btnPrimary")
        self.btn_preview.setEnabled(False)
        btn_layout.addWidget(self.btn_preview)
        self.btn_sync = QPushButton("开始全部更新同步")
        self.btn_sync.setObjectName("btnSync")
        self.btn_sync.setEnabled(False)
        btn_layout.addWidget(self.btn_sync)
        btn_layout.addStretch()
        self.btn_test = QPushButton("测试连接")
        btn_layout.addWidget(self.btn_test)
        grid.addLayout(btn_layout, 1, 0, 1, 4)
        help_label = QLabel(
            "使用说明：① 填写地址和密钥 → ② 连接/获取演员列表 → ③ 选择模式获取数据 → "
            "④ 绿色行=待更新 → ⑤ 开始同步到 Emby。双击行可查看详情。"
        )
        help_label.setStyleSheet("color: #888888; font-size: 12px; padding: 2px 0;")
        grid.addWidget(help_label, 2, 0, 1, 4)
        parent_layout.addWidget(group)

    def _build_actor_list(self, parent_layout: QVBoxLayout):
        stats_layout = QHBoxLayout()
        self.lbl_total = QLabel("总数: -")
        self.lbl_has_both = QLabel("完整: -")
        self.lbl_missing_image = QLabel("缺头像: -")
        self.lbl_missing_info = QLabel("缺简介: -")
        self.lbl_missing_all = QLabel("全缺: -")
        self.lbl_backdrop = QLabel("有背景图: -")
        for lbl in (
            self.lbl_total,
            self.lbl_has_both,
            self.lbl_missing_image,
            self.lbl_missing_info,
            self.lbl_missing_all,
            self.lbl_backdrop,
        ):
            lbl.setStyleSheet("padding: 2px 8px;")
            stats_layout.addWidget(lbl)
        stats_layout.addStretch()
        parent_layout.addLayout(stats_layout)
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("筛选:"))
        self.cmb_filter = QComboBox()
        self.cmb_filter.addItems(["全部", "待同步", "缺头像", "缺简介", "缺头像和简介", "完整"])
        self.cmb_filter.currentTextChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.cmb_filter)
        filter_layout.addWidget(QLabel("  搜索:"))
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("输入演员名搜索...")
        self.txt_search.setMaximumWidth(200)
        self.txt_search.textChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.txt_search)
        self.chk_show_table_avatar = QCheckBox("表格显示头像")
        filter_layout.addWidget(self.chk_show_table_avatar)
        hint = QLabel("双击行可编辑")
        hint.setStyleSheet("color: #888888; font-size: 12px;")
        filter_layout.addWidget(hint)
        filter_layout.addStretch()
        parent_layout.addLayout(stats_layout)
        parent_layout.addLayout(filter_layout)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        parent_layout.addWidget(self.progress_bar)
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["状态", "姓名", "头像", "简介", "详情", "标签", "影片数"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 160)
        self.table.setColumnWidth(2, 55)
        self.table.setColumnWidth(3, 55)
        self.table.setColumnWidth(4, 350)
        self.table.setColumnWidth(5, 200)
        self.table.setColumnWidth(6, 60)
        self.table.cellDoubleClicked.connect(self._on_table_double_clicked)
        parent_layout.addWidget(self.table)

    def _build_log_section(self, parent_layout: QVBoxLayout):
        group = QGroupBox("运行日志")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(4, 4, 4, 4)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(500)
        layout.addWidget(self.log_text)
        parent_layout.addWidget(group)

    def _connect_signals(self):
        self.btn_connect.clicked.connect(self._on_connect)
        self.btn_fetch.clicked.connect(self._on_fetch)
        self.btn_preview.clicked.connect(self._on_prepare_preview)
        self.btn_sync.clicked.connect(self._on_sync)
        self.btn_test.clicked.connect(self._on_test_connection)

    def log(self, msg: str):
        import datetime

        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.appendPlainText(f"[{ts}] {msg}")

    def _set_buttons_enabled(self, enabled: bool):
        self.btn_connect.setEnabled(enabled)
        self.btn_fetch.setEnabled(enabled and hasattr(self, "_connected") and self._connected)
        self.btn_preview.setEnabled(enabled and len(self._actors) > 0)
        self.btn_sync.setEnabled(enabled)
        self.btn_test.setEnabled(enabled)

    def _on_test_connection(self):
        self._on_connect()

    def _on_connect(self):
        url = self.txt_url.text().strip()
        key = self.txt_api_key.text().strip()
        if not url or not key:
            QMessageBox.warning(self, "提示", "请输入 Emby 地址和 API 密钥")
            return
        import asyncio

        from ..models.computed import ComputedManager

        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            headers = {"Authorization": f'MediaBrowser Token="{key}"'}

            async def test():
                async with ComputedManager() as computed:
                    test_url = (
                        f"{url.rstrip('/')}/emby/System/Info?api_key={key}"
                        if "emby" in str(manager.config.server_type)
                        else f"{url.rstrip('/')}/System/Info?api_key={key}"
                    )
                    resp, err = await computed.async_client.get_json(test_url, headers=headers, use_proxy=False)
                    if resp:
                        name = resp.get("ServerName", "Emby")
                        version = resp.get("Version", "")
                        return True, f"连接成功！{name} v{version}"
                    return False, f"连接失败: {err}"

            ok, msg = loop.run_until_complete(test())
            if ok:
                self._connected = True
                self.btn_connect.setText("已连接")
                self.btn_fetch.setEnabled(True)
                manager.config.emby_url = url
                manager.config.api_key = key
                self.log(f"✅ {msg}")
            else:
                self.log(f"❌ {msg}")
                QMessageBox.critical(self, "连接失败", msg)
        finally:
            loop.close()

    def _on_fetch(self):
        if not hasattr(self, "_connected") or not self._connected:
            QMessageBox.warning(self, "提示", "请先连接 Emby 服务器")
            return
        loop = asyncio.new_event_loop()
        try:
            libraries = loop.run_until_complete(get_media_folders())
        finally:
            loop.close()
        if not libraries:
            self.log("❌ 无法获取媒体库列表")
            return
        dlg = LibrarySelectDialog(libraries, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.log("⏹ 用户取消")
            return
        selected_ids = dlg.get_selected_ids()
        if not selected_ids:
            QMessageBox.warning(self, "提示", "请至少选择一个媒体库")
            return
        library_ids = None if len(selected_ids) == len(libraries) else selected_ids
        self._set_buttons_enabled(False)
        self._avatar_cache.clear()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log("📜 开始获取演员列表...")
        self._fetch_thread = FetchActorsThread(self)
        self._fetch_thread.library_ids = library_ids
        self._fetch_thread.progress.connect(self._on_fetch_progress)
        self._fetch_thread.fetch_done.connect(self._on_fetch_finished)
        self._fetch_thread.error.connect(self._on_thread_error)
        self._fetch_thread.start()

    def _on_fetch_progress(self, current: int, total: int, msg: str):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
        self.setWindowTitle(f"Emby 演员管理器 - {msg}")

    def _on_fetch_finished(self, actors: list[ActorInfo]):
        self._actors = actors
        self.log(f"获取完成，共 {len(actors)} 个演员")
        self._populate_table(actors)
        self._update_statistics(actors)
        self.btn_preview.setEnabled(len(actors) > 0)
        self.progress_bar.setVisible(False)
        self._set_buttons_enabled(True)
        loop = asyncio.new_event_loop()
        try:
            self._gfriends_index = loop.run_until_complete(get_gfriends_index())
            if self._gfriends_index:
                self.log(f"✅ Gfriends 头像库加载完成，共 {len(self._gfriends_index)} 个头像")
        except Exception:
            pass
        finally:
            loop.close()

    def _on_prepare_preview(self):
        if self._preview_thread and self._preview_thread.isRunning():
            self._preview_thread.cancel()
            self.log("⏹️ 用户取消")
            self.btn_preview.setText("获取数据")
            return
        mode_map = {
            "仅全部缺失头像+简介": "missing_all",
            "仅全部缺失头像": "missing_image",
            "仅全部缺失简介": "missing_info",
            "全部头像+简介（重新获取）": "force_all",
            "全部头像（重新获取）": "force_image",
            "全部简介（重新获取）": "force_info",
        }
        mode = mode_map.get(self.cmb_fetch_mode.currentText(), "missing_all")
        self._set_buttons_enabled(False)
        self.btn_preview.setEnabled(True)
        self.btn_preview.setText("停止")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log(f"📥 正在获取数据（模式: {self.cmb_fetch_mode.currentText()}）")
        self._preview_thread = PreparePreviewThread(self)
        self._preview_thread.actors = self._actors
        self._preview_thread.mode = mode
        self._preview_thread.gfriends_index = self._gfriends_index
        self._preview_thread.cache_dir = self.cache_dir
        self._preview_thread.image_sources = ["gfriends", "minnano", "local"]
        self._preview_thread.info_sources = ["minnano", "local_db"]
        self._preview_thread.local_avatar_dir = (
            manager.config.actor_photo_folder if hasattr(manager.config, "actor_photo_folder") else ""
        )
        self._preview_thread.progress.connect(self._on_fetch_progress)
        self._preview_thread.preview_done.connect(self._on_preview_finished)
        self._preview_thread.error.connect(self._on_thread_error)
        self._preview_thread.start()

    def _on_preview_finished(self, actors: list[ActorInfo]):
        self._actors = actors
        self._populate_table(actors)
        self._update_statistics(actors)
        to_sync = [a for a in actors if a.need_update_info or a.need_update_image]
        self.btn_sync.setEnabled(len(to_sync) > 0)
        self.btn_sync.setText(f"开始全部更新同步({len(to_sync)} 项)")
        self.log(f"✅ 预览准备完成，{len(to_sync)} 项待同步")
        self.btn_preview.setText("获取数据")
        self.progress_bar.setVisible(False)
        self._set_buttons_enabled(True)

    def _on_sync(self):
        to_sync = [a for a in self._actors if a.need_update_info or a.need_update_image]
        if not to_sync:
            QMessageBox.information(self, "提示", "没有需要同步的项")
            return
        reply = QMessageBox.question(
            self,
            "确认同步",
            f"将同步 {len(to_sync)} 个演员的信息和头像到 Emby，\n此操作不可撤销，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._set_buttons_enabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.btn_sync.setText("同步中...")
        self.log(f"📛 开始同步 {len(to_sync)} 个演员...")
        self._sync_thread = SyncThread(self)
        self._sync_thread.actors = to_sync
        self._sync_thread.progress.connect(self._on_sync_progress)
        self._sync_thread.actor_done.connect(self._on_sync_actor_done)
        self._sync_thread.sync_done.connect(self._on_sync_finished)
        self._sync_thread.error.connect(self._on_thread_error)
        self._sync_thread.start()

    def _on_sync_progress(self, current: int, total: int, msg: str):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.setWindowTitle(f"Emby 演员管理器 - {msg}")

    def _on_sync_actor_done(self, name: str, success: bool, msg: str):
        if success:
            self.log(f"✅ {name} 同步成功")
        else:
            self.log(f"❌ {name} 同步失败: {msg}")

    def _on_sync_finished(self, success: int, fail: int):
        self.progress_bar.setVisible(False)
        self._set_buttons_enabled(True)
        self.btn_sync.setText("开始全部更新同步")
        self.log(f"同步完成！成功: {success}, 失败: {fail}")
        QMessageBox.information(self, "同步完成", f"✅ 成功: {success}\n❌ 失败: {fail}")
        for a in self._actors:
            if a.need_update_image:
                if a.new_image_path:
                    a.has_image = True
                else:
                    a.has_image = False
                a.need_update_image = False
            if a.need_update_info:
                a.has_overview = bool(a.new_overview and a.new_overview.strip())
                a.need_update_info = False
        self._populate_table(self._actors)
        self._update_statistics(self._actors)

    def _on_thread_error(self, msg: str):
        self.progress_bar.setVisible(False)
        self._set_buttons_enabled(True)
        self.log(f"🔶 错误: {msg}")
        QMessageBox.critical(self, "错误", msg)

    def _on_filter_changed(self):
        self._populate_table(self._actors)

    def _on_table_double_clicked(self, row: int, col: int):
        filtered = self._get_filtered_actors()
        if row < len(filtered):
            actor = filtered[row]

            msg = (
                f"演员: {actor.name}\n"
                f"状态: {actor.status_text}\n"
                f"服务器ID: {actor.server_id}\n\n"
                f"已有信息:\n"
                f"  简介: {'有' if actor.existing_overview else '无'}\n"
                f"  出生日期: {actor.existing_premiere_date[:10] if actor.existing_premiere_date else '无'}\n"
                f"  出生地: {', '.join(actor.existing_production_locations) if actor.existing_production_locations else '无'}\n"
                f"  标签: {', '.join(actor.existing_taglines[:3]) if actor.existing_taglines else '无'}\n\n"
                f"待更新:\n"
                f"  头像: {'是' if actor.need_update_image else '否'}\n"
                f"  信息: {'是' if actor.need_update_info else '否'}"
            )
            QMessageBox.information(self, f"演员详情 - {actor.name}", msg)

    def _get_filtered_actors(self) -> list[ActorInfo]:
        filter_mode = self.cmb_filter.currentText()
        search_text = self.txt_search.text().strip().lower()
        filtered = []
        for a in self._actors:
            if filter_mode == "缺头像" and a.has_image:
                continue
            elif filter_mode == "缺简介" and a.has_overview:
                continue
            elif filter_mode == "缺头像和简介" and a.has_image and a.has_overview:
                continue
            elif filter_mode == "完整" and not (a.has_image and a.has_overview):
                continue
            elif filter_mode == "待同步" and not (a.need_update_info or a.need_update_image):
                continue
            if search_text and search_text not in a.name.lower():
                continue
            filtered.append(a)
        return filtered

    def _populate_table(self, actors: list[ActorInfo]):
        self.table.setSortingEnabled(False)
        filtered = self._get_filtered_actors() if actors else []
        self.table.setRowCount(len(filtered))
        for row, actor in enumerate(filtered):
            icon_item = QTableWidgetItem(actor.status_icon)
            icon_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, icon_item)
            name_item = QTableWidgetItem(actor.name)
            name_item.setToolTip(f"ID: {actor.actor_id}")
            self.table.setItem(row, 1, name_item)
            img_item = QTableWidgetItem("✅" if actor.has_image else "❌")
            img_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if actor.need_update_image:
                img_item.setText("🔄")
            img_item.setToolTip(
                f"头像: {'有' if actor.has_image else '无'} | 背景图: {'有' if actor.has_backdrop else '无'}"
            )
            self.table.setItem(row, 2, img_item)
            info_item = QTableWidgetItem("✅" if actor.has_overview else "❌")
            info_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if actor.need_update_info:
                info_item.setText("🔄")
            self.table.setItem(row, 3, info_item)
            overview_text = (
                actor.existing_overview[:80] + "..."
                if len(actor.existing_overview) > 80
                else (actor.existing_overview or "（无）")
            )
            self.table.setItem(row, 4, QTableWidgetItem(overview_text))
            tags = ", ".join(actor.existing_taglines[:2]) if actor.existing_taglines else ""
            self.table.setItem(row, 5, QTableWidgetItem(tags))
            mc_item = QTableWidgetItem(str(actor.movie_count) if actor.movie_count > 0 else "0")
            mc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if actor.movie_titles:
                mc_item.setToolTip("\n".join(actor.movie_titles[:20]))
            self.table.setItem(row, 6, mc_item)
            if actor.need_update_info or actor.need_update_image:
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        item.setBackground(QColor("#c8e6c9"))
        self.table.setSortingEnabled(True)
        self._update_sync_button()

    def _update_statistics(self, actors: list[ActorInfo]):
        total = len(actors)
        has_both = sum(1 for a in actors if a.has_image and a.has_overview)
        has_image_only = sum(1 for a in actors if a.has_image and not a.has_overview)
        has_info_only = sum(1 for a in actors if not a.has_image and a.has_overview)
        has_none = sum(1 for a in actors if not a.has_image and not a.has_overview)
        backdrop_count = sum(1 for a in actors if a.has_backdrop)
        self.lbl_total.setText(f"总数: {total}")
        self.lbl_has_both.setText(f"完整: {has_both}")
        self.lbl_missing_image.setText(f"缺头像: {has_info_only}")
        self.lbl_missing_info.setText(f"缺简介: {has_image_only}")
        self.lbl_missing_all.setText(f"全缺: {has_none}")
        self.lbl_backdrop.setText(f"有背景图: {backdrop_count}")

    def _update_sync_button(self):
        to_sync = [a for a in self._actors if a.need_update_info or a.need_update_image]
        sync_count = len(to_sync)
        self.btn_sync.setEnabled(sync_count > 0)
        self.btn_sync.setText(f"开始全部更新同步({sync_count} 项)" if sync_count > 0 else "开始全部更新同步")


def open_emby_actor_manager(parent=None):
    dialog = EmbyActorManagerDialog(parent)
    dialog.exec()
