from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from PyQt6.QtCore import Qt, QThread
from PyQt6.QtCore import pyqtSignal as Signal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..config.manager import manager
from .emby_actor_manager import (
    ActorInfo,
    fetch_actor_detail,
    fetch_actor_info_from_source,
    fetch_all_actors,
    from_gfriends,
    from_graphis,
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
        self._checkboxes: list[QCheckBox] = []
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
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
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
                    filter_actor_only=manager.config.actor_filter_only,
                    deduplicate=manager.config.actor_deduplicate,
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
        self.cache_dir = Path(tempfile.gettempdir())
        self.image_sources = ["gfriends", "graphis", "minnano", "local"]
        self.local_avatar_dir = ""
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            from .minnano_crawler import load_cache as minnano_load_cache

            minnano_load_cache()
            total = len(self.actors)
            if total == 0:
                self.preview_done.emit(self.actors)
                return
            need_image = self.mode in ("missing_all", "missing_image", "force_all", "force_image")
            need_info = self.mode in ("missing_all", "missing_info", "force_all", "force_info")
            force = "force" in self.mode
            cancelled = False
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                cancelled = loop.run_until_complete(self._process_all(need_image, need_info, force, total))
            finally:
                loop.close()
            if not cancelled:
                self.progress.emit(total, total, "预览数据准备完成")
            self.preview_done.emit(self.actors)
        except Exception:
            import traceback

            self.error.emit(f"获取数据失败: {traceback.format_exc()}")

    async def _process_all(self, need_image: bool, need_info: bool, force: bool, total: int) -> bool:
        """在单个 event loop 内并发处理所有演员，避免多线程多 loop 并发共享 async_client。"""
        sem = asyncio.Semaphore(10)

        async def guarded(actor: ActorInfo) -> ActorInfo:
            async with sem:
                try:
                    if need_image:
                        await self._try_fetch_image(actor, force)
                    if need_info:
                        await self._try_fetch_info(actor, force)
                except Exception:
                    import traceback

                    from ..signals import signal

                    signal.show_log_text(f"🔶 演员处理异常: {actor.name}: {traceback.format_exc()}")
                return actor

        completed = 0
        cancelled = False
        tasks = [guarded(actor) for actor in self.actors]
        for coro in asyncio.as_completed(tasks):
            if self._cancel:
                cancelled = True
                break
            completed += 1
            actor = await coro
            self.progress.emit(completed, total, f"处理中: {actor.name} ({completed}/{total})")
        return cancelled

    async def _try_fetch_image(self, actor: ActorInfo, force: bool):
        if not force and actor.has_image:
            return
        for src in self.image_sources:
            if src == "gfriends" and self.gfriends_index:
                result = await from_gfriends(actor, self.gfriends_index, self.cache_dir)
                if result:
                    actor.new_image_path = result
                    actor.need_update_image = True
                    return
            elif src == "graphis":
                graphis_result = await from_graphis(actor, self.cache_dir)
                if isinstance(graphis_result, tuple):
                    avatar_path, backdrop_path = graphis_result
                    actor.new_image_path = avatar_path
                    actor.need_update_image = True
                    if backdrop_path:
                        actor.new_backdrop_path = backdrop_path
                        actor.need_update_backdrop = True
                    return
            elif src == "minnano":
                result = await from_minnano_image(actor, self.cache_dir)
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

    async def _try_fetch_info(self, actor: ActorInfo, force: bool):
        if not force and actor.has_overview:
            detail = await fetch_actor_detail(actor.name)
            if detail:
                overview = (detail.get("Overview") or "").strip()
                if overview and "无维基百科信息" not in overview:
                    return
        result = await search_actor_info(actor)
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
        self.cache_dir = Path(tempfile.gettempdir()) / "emby_actor_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._actors: list[ActorInfo] = []
        self._gfriends_index = None
        self._preview_thread = None
        self._sync_thread = None
        self._fetch_thread = None
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
        self.btn_settings = QPushButton("设置")
        btn_layout.addWidget(self.btn_settings)
        self.btn_test_source = QPushButton("数据源测试")
        btn_layout.addWidget(self.btn_test_source)
        grid.addLayout(btn_layout, 1, 0, 1, 4)
        help_label = QLabel(
            "使用说明：① 填写地址和密钥 → ② 连接/获取演员列表 → ③ 选择模式获取数据 → "
            "④ 绿色行=待更新 → ⑤ 开始同步到 Emby。双击行可查看当前头像/简介/出生日期/影片数等详情。"
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
        hint = QLabel("双击行可编辑")
        hint.setStyleSheet("color: #888888; font-size: 12px;")
        filter_layout.addWidget(hint)
        filter_layout.addStretch()
        parent_layout.addLayout(filter_layout)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        parent_layout.addWidget(self.progress_bar)
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["状态", "姓名", "头像", "简介", "详情", "标签", "影片数"])
        horizontal_header = self.table.horizontalHeader()
        assert horizontal_header is not None
        horizontal_header.setStretchLastSection(False)
        horizontal_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        vertical_header = self.table.verticalHeader()
        assert vertical_header is not None
        vertical_header.setVisible(False)
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
        self.btn_settings.clicked.connect(self._on_open_settings)
        self.btn_test_source.clicked.connect(self._on_open_test_source)

    def _on_open_settings(self):
        dialog = EmbyActorSettingsDialog(self)
        dialog.exec()

    def _on_open_test_source(self):
        dialog = ActorSourceTestDialog(self)
        dialog.exec()

    def log(self, msg: str):
        import datetime

        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.appendPlainText(f"[{ts}] {msg}")

    def _set_buttons_enabled(self, enabled: bool):
        self.btn_connect.setEnabled(enabled)
        self.btn_fetch.setEnabled(enabled and hasattr(self, "_connected") and self._connected)
        actors = getattr(self, "_actors", None) or []
        self.btn_preview.setEnabled(enabled and len(actors) > 0)
        pending = any(a.need_update_info or a.need_update_image or a.need_update_backdrop for a in actors)
        self.btn_sync.setEnabled(enabled and pending)
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

        loop = asyncio.new_event_loop()
        try:
            headers = {"Authorization": f'MediaBrowser Token="{key}"'}

            async def test():
                async with manager.acquire_computed() as computed:
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
            import traceback

            self.log(f"🔶 Gfriends 索引加载失败: {traceback.format_exc()}")
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
        self._preview_thread.image_sources = list(manager.config.actor_image_sources)

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
        to_sync = [a for a in actors if a.need_update_info or a.need_update_image or a.need_update_backdrop]
        self.btn_sync.setEnabled(len(to_sync) > 0)
        self.btn_sync.setText(f"开始全部更新同步({len(to_sync)} 项)")
        self.log(f"✅ 预览准备完成，{len(to_sync)} 项待同步")
        self.btn_preview.setText("获取数据")
        self.progress_bar.setVisible(False)
        self._set_buttons_enabled(True)

    def _on_sync(self):
        to_sync = [a for a in self._actors if a.need_update_info or a.need_update_image or a.need_update_backdrop]
        if not to_sync:
            QMessageBox.information(self, "提示", "没有需要同步的项")
            return
        reply = QMessageBox.question(
            self,
            "确认同步",
            f"将同步 {len(to_sync)} 个演员的信息/头像/背景图到 Emby，\n此操作不可撤销，是否继续？",
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
            if a.need_update_backdrop:
                a.has_backdrop = bool(a.new_backdrop_path)
                a.need_update_backdrop = False
        self._populate_table(self._actors)
        self._update_statistics(self._actors)

    def _on_thread_error(self, msg: str):
        self.progress_bar.setVisible(False)
        # 线程已结束，恢复按钮文本与状态，避免"停止/同步中..."残留
        self.btn_preview.setText("获取数据")
        self.btn_sync.setText("开始全部更新同步")
        self._set_buttons_enabled(True)
        self.log(f"🔶 错误: {msg}")
        QMessageBox.critical(self, "错误", msg)

    def closeEvent(self, event):
        # 线程运行中关闭窗口会触发 "QThread: Destroyed while thread is still running" 崩溃，
        # 关闭前先取消并等待各后台线程结束。
        for attr in ("_fetch_thread", "_preview_thread", "_sync_thread"):
            thread = getattr(self, attr, None)
            if thread is not None and thread.isRunning():
                if hasattr(thread, "cancel"):
                    thread.cancel()
                thread.wait(5000)
        super().closeEvent(event)

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
        to_sync = [a for a in self._actors if a.need_update_info or a.need_update_image or a.need_update_backdrop]
        sync_count = len(to_sync)
        self.btn_sync.setEnabled(sync_count > 0)
        self.btn_sync.setText(f"开始全部更新同步({sync_count} 项)" if sync_count > 0 else "开始全部更新同步")


IMAGE_SOURCE_NAMES = {
    "gfriends": "Gfriends 头像库",
    "graphis": "graphis 头像/背景",
    "minnano": "minnano-av 头像",
    "local": "本地头像",
}
INFO_SOURCE_NAMES = {
    "local": "本地演员库",
    "wiki": "维基百科",
    "minnano": "minnano-av 信息",
    "database": "本地数据库",
}


class EmbyActorSettingsDialog(QDialog):
    """Emby 演员数据源设置：数据源优先级排序 + 本地目录 + Gfriends + 数据库开关。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Emby 演员设置")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)

        filter_group = QGroupBox("Emby 演员获取过滤")
        filter_layout = QVBoxLayout(filter_group)
        self.filter_only_check = QCheckBox("只获取演员类型（不含导演/编剧/制片人）")
        self.filter_only_check.setChecked(manager.config.actor_filter_only)
        filter_layout.addWidget(self.filter_only_check)
        self.deduplicate_check = QCheckBox("重复演员去重（按名称合并）")
        self.deduplicate_check.setChecked(manager.config.actor_deduplicate)
        filter_layout.addWidget(self.deduplicate_check)
        layout.addWidget(filter_group)

        layout.addWidget(QLabel("头像数据源优先级（拖拽排序，上=优先）:"))
        self.image_list = QListWidget()
        self.image_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        for src in manager.config.actor_image_sources:
            item = QListWidgetItem(f"{src}（{IMAGE_SOURCE_NAMES.get(src, src)}）")
            item.setData(Qt.ItemDataRole.UserRole, src)
            self.image_list.addItem(item)
        layout.addWidget(self.image_list)

        layout.addWidget(QLabel("信息数据源优先级（拖拽排序，上=优先）:"))
        self.info_list = QListWidget()
        self.info_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        for src in manager.config.actor_info_sources:
            item = QListWidgetItem(f"{src}（{INFO_SOURCE_NAMES.get(src, src)}）")
            item.setData(Qt.ItemDataRole.UserRole, src)
            self.info_list.addItem(item)
        layout.addWidget(self.info_list)

        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("本地头像目录:"))
        self.photo_folder_edit = QLineEdit(manager.config.actor_photo_folder)
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_photo_folder)
        dir_row.addWidget(self.photo_folder_edit)
        dir_row.addWidget(browse_btn)
        layout.addLayout(dir_row)

        layout.addWidget(QLabel("Gfriends GitHub 地址:"))
        self.gfriends_edit = QLineEdit(str(manager.config.gfriends_github))
        layout.addWidget(self.gfriends_edit)

        self.use_db_check = QCheckBox("使用本地信息数据库")
        self.use_db_check.setChecked(manager.config.use_database)
        layout.addWidget(self.use_db_check)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _browse_photo_folder(self):
        path = QFileDialog.getExistingDirectory(self, "选择本地头像目录", self.photo_folder_edit.text())
        if path:
            self.photo_folder_edit.setText(path)

    def _save(self):
        image_sources = [item.data(Qt.ItemDataRole.UserRole) for item in self.image_list]
        info_sources = [item.data(Qt.ItemDataRole.UserRole) for item in self.info_list]
        cfg = manager.config.model_copy(deep=True)
        cfg.actor_image_sources = image_sources
        cfg.actor_info_sources = info_sources
        cfg.actor_filter_only = self.filter_only_check.isChecked()
        cfg.actor_deduplicate = self.deduplicate_check.isChecked()
        cfg.actor_photo_folder = self.photo_folder_edit.text().strip()
        cfg.use_database = self.use_db_check.isChecked()
        try:
            cfg.gfriends_github = self.gfriends_edit.text().strip()
        except Exception as e:
            QMessageBox.warning(self, "提示", f"Gfriends 地址无效: {e}")
            return
        manager._replace_config(cfg)
        self.accept()


class ActorSourceTestDialog(QDialog):
    """数据源测试窗口：按配置的数据源优先级逐源尝试获取头像/简介，展示各源结果。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("数据源测试")
        self.setMinimumSize(760, 560)
        root = QVBoxLayout(self)

        # 顶部：演员名输入 + 获取头像和简介
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("演员名:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入演员名（如：三上悠亚）")
        self.name_edit.returnPressed.connect(lambda: self._run(True, True))
        name_row.addWidget(self.name_edit)
        self.btn_both = QPushButton("获取头像和简介")
        self.btn_both.setObjectName("btnPrimary")
        name_row.addWidget(self.btn_both)
        root.addLayout(name_row)

        # 主体：左(头像) + 中(信息字段表) + 右(快速设置面板)
        main_row = QHBoxLayout()

        # 左列：头像预览 + 获取头像
        left_col = QVBoxLayout()
        self.avatar_label = QLabel("头像预览")
        self.avatar_label.setFixedSize(140, 190)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label.setStyleSheet("border: 1px solid #ccc; color: #888;")
        left_col.addWidget(self.avatar_label)
        self.btn_image = QPushButton("获取头像")
        self.btn_image.setObjectName("btnPrimary")
        left_col.addWidget(self.btn_image)
        main_row.addLayout(left_col)

        # 中列：详细信息预览（字段/值）+ 获取信息
        info_col = QVBoxLayout()
        info_col.addWidget(QLabel("详细信息预览:"))
        self.info_table = QTableWidget(0, 2)
        self.info_table.setHorizontalHeaderLabels(["字段", "值"])
        self.info_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.info_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.info_table.verticalHeader().setVisible(False)
        self.info_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        info_col.addWidget(self.info_table)
        self.btn_info = QPushButton("获取信息")
        self.btn_info.setObjectName("btnPrimary")
        info_col.addWidget(self.btn_info)
        main_row.addLayout(info_col, stretch=1)

        # 右列：快速设置面板（改即自动保存）
        panel = QGroupBox("快速设置")
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(QLabel("头像数据源（拖拽排序）:"))
        self.panel_image_list = QListWidget()
        self.panel_image_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._fill_source_list(self.panel_image_list, manager.config.actor_image_sources, IMAGE_SOURCE_NAMES)
        panel_layout.addWidget(self.panel_image_list)
        panel_layout.addWidget(QLabel("信息数据源（拖拽排序）:"))
        self.panel_info_list = QListWidget()
        self.panel_info_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._fill_source_list(self.panel_info_list, manager.config.actor_info_sources, INFO_SOURCE_NAMES)
        panel_layout.addWidget(self.panel_info_list)
        panel_layout.addWidget(QLabel("本地头像目录:"))
        folder_row = QHBoxLayout()
        self.panel_folder_edit = QLineEdit(manager.config.actor_photo_folder)
        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(self.panel_folder_edit)
        folder_row.addWidget(browse_btn)
        panel_layout.addLayout(folder_row)
        main_row.addWidget(panel)

        root.addLayout(main_row)

        # 底部：各数据源结果
        root.addWidget(QLabel("各数据源结果:"))
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(150)
        root.addWidget(self.result_text)

        self.btn_both.clicked.connect(lambda: self._run(True, True))
        self.btn_image.clicked.connect(lambda: self._run(True, False))
        self.btn_info.clicked.connect(lambda: self._run(False, True))

        # 快速面板改动即自动保存
        self.panel_image_list.model().rowsMoved.connect(self._save_quick_settings)
        self.panel_info_list.model().rowsMoved.connect(self._save_quick_settings)
        self.panel_folder_edit.textChanged.connect(self._save_quick_settings)

    @staticmethod
    def _fill_source_list(list_widget: QListWidget, sources: list[str], names: dict[str, str]):
        list_widget.clear()
        for src in sources:
            item = QListWidgetItem(f"{src}（{names.get(src, src)}）")
            item.setData(Qt.ItemDataRole.UserRole, src)
            list_widget.addItem(item)

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "选择本地头像目录", self.panel_folder_edit.text())
        if path:
            self.panel_folder_edit.setText(path)

    def _save_quick_settings(self, *args):
        cfg = manager.config.model_copy(deep=True)
        cfg.actor_image_sources = [item.data(Qt.ItemDataRole.UserRole) for item in self.panel_image_list]
        cfg.actor_info_sources = [item.data(Qt.ItemDataRole.UserRole) for item in self.panel_info_list]
        cfg.actor_photo_folder = self.panel_folder_edit.text().strip()
        manager._replace_config(cfg)

    def _run(self, need_image: bool, need_info: bool):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入演员名")
            return
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._execute(name, need_image, need_info))
        finally:
            loop.close()

    async def _execute(self, name: str, need_image: bool, need_info: bool):
        self.result_text.clear()
        self.info_table.setRowCount(0)
        self.avatar_label.clear()
        self.avatar_label.setText("头像预览")
        actor = ActorInfo(name=name, actor_id="", server_id="")

        if need_image:
            gfriends_index = None
            try:
                gfriends_index = await get_gfriends_index()
            except Exception:
                pass
            for src in manager.config.actor_image_sources:
                result: object = None
                try:
                    if src == "gfriends" and gfriends_index:
                        result = await from_gfriends(actor, gfriends_index, Path(tempfile.gettempdir()))
                    elif src == "graphis":
                        result = await from_graphis(actor, Path(tempfile.gettempdir()))
                    elif src == "minnano":
                        result = await from_minnano_image(actor, Path(tempfile.gettempdir()))
                    elif src == "local":
                        result = from_local_avatar(actor, manager.config.actor_photo_folder)
                    else:
                        self.result_text.append(f"头像[{src}]: 未知数据源")
                        continue
                except Exception as e:
                    self.result_text.append(f"头像[{src}]: 异常 {e}")
                    continue
                if result:
                    self.result_text.append(f"头像[{src}]: ✅ 命中")
                    if isinstance(result, (str, Path)) and Path(result).exists():
                        self._show_avatar(str(result))
                    elif isinstance(result, tuple) and result and Path(result[0]).exists():
                        self._show_avatar(str(result[0]))
                else:
                    self.result_text.append(f"头像[{src}]: 未命中")

        if need_info:
            for src in manager.config.actor_info_sources:
                try:
                    ok, desc, info = await fetch_actor_info_from_source(actor, src)
                except Exception as e:
                    self.result_text.append(f"信息[{src}]: 异常 {e}")
                    continue
                self.result_text.append(f"信息[{src}]: {'✅' if ok else '❌'} {desc}")
                if ok:
                    self._populate_info_table(info)

    def _populate_info_table(self, info: object):
        from ..models.emby import EMbyActressInfo

        if not isinstance(info, EMbyActressInfo):
            return
        rows = [
            ("生日", info.birthday),
            ("年份", str(info.year) if info.year else ""),
            ("出生地", ", ".join(info.locations or [])),
            ("标签", ", ".join(info.taglines or [])),
            ("简介", info.overview or ""),
        ]
        self.info_table.setRowCount(len(rows))
        for r, (field, value) in enumerate(rows):
            self.info_table.setItem(r, 0, QTableWidgetItem(field))
            self.info_table.setItem(r, 1, QTableWidgetItem(str(value)))

    def _show_avatar(self, path: str):
        from PyQt6.QtGui import QPixmap

        pix = QPixmap(path)
        if not pix.isNull():
            self.avatar_label.setPixmap(pix.scaled(self.avatar_label.size(), Qt.AspectRatioMode.KeepAspectRatio))


def open_emby_actor_manager(parent=None):
    dialog = EmbyActorManagerDialog(parent)
    dialog.exec()
