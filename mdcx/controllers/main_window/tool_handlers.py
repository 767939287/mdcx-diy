import threading
import traceback
from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from mdcx.config.manager import manager
from mdcx.signals import signal_qt
from mdcx.utils import executor, get_current_time


def pushButton_cover_backfill_start_clicked(self):
    from scripts.cover_backfill import backfill_cover

    self.pushButton_show_log_clicked()
    numbers = self.Ui.lineEdit_cover_backfill_numbers.text().strip()
    if not numbers:
        signal_qt.show_log_text("🔴 请输入番号")
        return
    number_list = [n.strip() for n in numbers.split() if n.strip()]
    overwrite = self.Ui.checkBox_cover_backfill_overwrite.isChecked()
    watermark = self.Ui.checkBox_cover_backfill_watermark.isChecked()

    async def run_backfill():
        results = []
        for number in number_list:
            signal_qt.show_log_text(f"开始补图: {number}")
            try:
                result = await backfill_cover(
                    number,
                    output_dir=manager.data_folder,
                    overwrite=overwrite,
                    watermark=watermark,
                )
                results.append(result)
                signal_qt.show_log_text(f"  ✅ {result.number}: thumb={result.thumb_path}, poster={result.poster_path}")
            except Exception as e:
                signal_qt.show_log_text(f"  🔴 {number}: {e}")
        signal_qt.show_log_text("=" * 60)
        signal_qt.show_log_text(f"封面补图完成: {len(results)}/{len(number_list)} 成功")
        self.pushButton_cover_backfill_start.emit("开始补图")

    self.pushButton_cover_backfill_start.emit("补图中...")
    executor.submit(run_backfill())


def pushButton_emby_actor_manager_clicked(self):
    try:
        from mdcx.tools.emby_actor_manager_ui import EmbyActorManagerDialog

        self._emby_dialog = EmbyActorManagerDialog(self)
        self._emby_dialog.exec()
    except Exception as e:
        signal_qt.show_log_text(f"❌ Emby 演员管理器打开失败: {e}\n{traceback.format_exc()}")


# ============= 设置-演员 =============


def pushButton_select_gfriends_local_clicked(self):
    gfriends_path = self._get_select_folder_path(self.Ui.lineEdit_gfriends_local_path)
    if gfriends_path:
        self.Ui.lineEdit_gfriends_local_path.setText(gfriends_path)
        self.pushButton_save_config_clicked()


def pushButton_sync_gfriends_clicked(self):
    local_path = self.Ui.lineEdit_gfriends_local_path.text().strip()
    if not local_path:
        QMessageBox.warning(self, "提示", "请先选择 Gfriends 本地仓库目录")
        return
    from mdcx.tools.sync_gfriends import sync_gfriends as do_sync

    success, msg = do_sync(local_path)
    if success:
        signal_qt.show_scrape_info(f"✅ {msg}")
    else:
        QMessageBox.warning(self, "更新失败", msg)
    self.Ui.label_gfriends_update_time.setText(f"最后更新: {get_current_time()}")


def pushButton_select_actor_info_db_clicked(self):
    database_path, _ = QFileDialog.getOpenFileName(
        None, "选择数据库文件", manager.data_folder.as_posix(), options=self.options
    )
    if database_path:
        self.Ui.lineEdit_actor_db_path.setText(database_path)
        self.pushButton_save_config_clicked()


def pushButton_add_actor_info_clicked(self):
    from mdcx.tools.emby_actor_info import update_emby_actor_info

    self.pushButton_save_config_clicked()
    self.pushButton_show_log_clicked()
    try:
        executor.submit(update_emby_actor_info())
    except Exception:
        signal_qt.show_log_text(traceback.format_exc())


def pushButton_add_actor_pic_clicked(self):
    from mdcx.tools.emby_actor_image import update_emby_actor_photo

    self.pushButton_save_config_clicked()
    self.pushButton_show_log_clicked()
    try:
        executor.submit(update_emby_actor_photo())
    except Exception:
        signal_qt.show_log_text(traceback.format_exc())


def pushButton_add_actor_pic_kodi_clicked(self):
    from mdcx.tools.emby_actor_info import creat_kodi_actors

    self.pushButton_save_config_clicked()
    self.pushButton_show_log_clicked()
    try:
        executor.submit(creat_kodi_actors(True))
    except Exception:
        signal_qt.show_log_text(traceback.format_exc())


def pushButton_del_actor_folder_clicked(self):
    from mdcx.tools.emby_actor_info import creat_kodi_actors

    self.pushButton_show_log_clicked()
    try:
        executor.submit(creat_kodi_actors(False))
    except Exception:
        signal_qt.show_log_text(traceback.format_exc())


def pushButton_show_pic_actor_clicked(self):
    from mdcx.tools.emby_actor_info import show_emby_actor_list

    self.pushButton_show_log_clicked()
    try:
        executor.submit(show_emby_actor_list(self.Ui.comboBox_pic_actor.currentIndex()))
    except Exception:
        signal_qt.show_log_text(traceback.format_exc())


# ============= 通用目录选择 =============


def _pick_folder(self, line_edit_attr: str) -> None:
    """选择目录并设置到 lineEdit，同时保存配置。"""
    line_edit = getattr(self.Ui, line_edit_attr)
    path = self._get_select_folder_path(line_edit)
    if path:
        line_edit.setText(path)
        self.pushButton_save_config_clicked()


def pushButton_select_softlink_folder_clicked(self):
    _pick_folder(self, "lineEdit_movie_softlink_path")


def pushButton_select_sucess_folder_clicked(self):
    _pick_folder(self, "lineEdit_success")


def pushButton_select_failed_folder_clicked(self):
    _pick_folder(self, "lineEdit_fail")


def pushButton_select_subtitle_folder_clicked(self):
    _pick_folder(self, "lineEdit_sub_folder")


def pushButton_select_actor_photo_folder_clicked(self):
    _pick_folder(self, "lineEdit_actor_photo_folder")


def pushButton_select_local_library_clicked(self):
    _pick_folder(self, "lineEdit_local_library_path")


def pushButton_select_netdisk_path_clicked(self):
    _pick_folder(self, "lineEdit_netdisk_path")


def pushButton_select_localdisk_path_clicked(self):
    _pick_folder(self, "lineEdit_localdisk_path")


def pushButton_select_media_folder_clicked(self):
    _pick_folder(self, "lineEdit_movie_path")


# ============= 演员库维护（新三按钮） =============


def pushButton_actor_db_translate_clicked(self):
    self.pushButton_show_log_clicked()
    signal_qt.show_log_text("🔍 开始扫描 actor_database.xlsx：查找已有 TMDB ID 但缺少中文名的条目...")
    self._run_actor_db_tool("translate")


def pushButton_actor_db_link_clicked(self):
    self.pushButton_show_log_clicked()
    signal_qt.show_log_text("🔍 开始扫描 actor_database.xlsx：查找已有 TMDB ID 但缺少 LibreDMM 链接的条目...")
    self._run_actor_db_tool("link")


def pushButton_actor_db_sync_aliases_clicked(self):
    self.pushButton_show_log_clicked()
    signal_qt.show_log_text("🔍 开始扫描 actor_database.xlsx：同步 TMDB 最新别名到 keyword 列...")
    self._run_actor_db_tool("sync_aliases")


def pushButton_actor_db_open_clicked(self):
    from mdcx.config.resources import resources

    db_path = Path(resources.u("actor_database.xlsx"))
    if not db_path.exists():
        signal_qt.show_log_text("🔴 actor_database.xlsx 不存在，请先刮削或执行一次演员库维护生成数据库")
        return
    signal_qt.show_log_text(f"📂 正在用系统默认程序打开: {db_path}")
    threading.Thread(target=_open_file_thread, args=(db_path,), daemon=True).start()


def _open_file_thread(db_path):
    from mdcx.utils.file import open_file_thread

    try:
        open_file_thread(Path(db_path), False)
        signal_qt.show_log_text(f"✅ 已打开 actor_database.xlsx: {db_path}")
    except Exception as e:
        signal_qt.show_log_text(
            f"🔴 无法打开 actor_database.xlsx（{e}）。请先安装 Excel/WPS 或 LibreOffice 等文字处理软件后重试"
        )


_HINT = {
    0: "通过 cdn.jsdelivr.net 拉取，最快",
    1: "从 GitHub raw 直连，可能需要稳定网络",
    2: "输入任意可访问的下载地址，如自建镜像",
    3: "选择本地的 actor-mapping.xml 文件导入",
}


def comboBox_actor_db_sync_source_changed(self, index: int):
    """数据源切换：更新输入框/选择按钮可用状态与提示。"""
    line_edit = self.Ui.lineEdit_actor_db_sync_value
    pick_btn = self.Ui.pushButton_actor_db_pick_xml
    hint = self.Ui.label_actor_db_sync_source_hint

    if index in (2, 3):
        line_edit.setEnabled(True)
    else:
        line_edit.setEnabled(False)
        line_edit.clear()

    pick_btn.setVisible(index == 3)
    hint.setText(_HINT.get(index, ""))


def pushButton_actor_db_pick_xml_clicked(self):
    """选择本地 actor-mapping.xml 文件并切入『本地 xml 文件』数据源。"""
    path, _ = QFileDialog.getOpenFileName(
        self,
        "选择 AVdb actor-mapping.xml 文件",
        "",
        "XML 文件 (*.xml);;所有文件 (*)",
    )
    if not path:
        return
    self.Ui.lineEdit_actor_db_sync_value.setText(path)
    self.Ui.comboBox_actor_db_sync_source.setCurrentIndex(3)


def pushButton_actor_db_sync_start_clicked(self):
    from mdcx.tools.actor_db_tool import AVDB_MAPPING_URL_MIRROR

    self.pushButton_show_log_clicked()
    source = self.Ui.comboBox_actor_db_sync_source.currentIndex()
    source_name = {
        0: "jsDelivr 加速",
        1: "GitHub 直连",
        2: "自定义下载地址",
        3: "本地 xml 文件",
    }.get(source, "jsDelivr 加速")
    if source == 3:
        value = self.Ui.lineEdit_actor_db_sync_value.text().strip()
        signal_qt.show_log_text(f"🎬 从 {source_name} 同步 AVdb 演员映射... (文件: {value})")
        self._run_actor_db_sync()
        return
    url = (
        self.Ui.lineEdit_actor_db_sync_value.text().strip()
        if source == 2
        else AVDB_MAPPING_URL_MIRROR
        if source == 0
        else "GitHub raw"
    )
    signal_qt.show_log_text(f"🎬 从 {source_name} 同步 AVdb 演员映射... ({url})")
    self._run_actor_db_sync()


def pushButton_actor_db_clean_male_clicked(self):
    self.pushButton_show_log_clicked()
    signal_qt.show_log_text("🎬 开始剔除男演员（按 tmdbid 校验 TMDB gender，删除男优）...")
    self._run_actor_db_clean_male()


def pushButton_actor_db_verify_tmdbid_clicked(self):
    self.pushButton_show_log_clicked()
    signal_qt.show_log_text("🎬 开始校验 tmdbid 有效性（404 失效 id 清除回无 id 状态）...")
    self._run_actor_db_verify_tmdbid()


def pushButton_actor_db_pick_nfo_dir_clicked(self):
    from PyQt6.QtWidgets import QFileDialog

    folder = QFileDialog.getExistingDirectory(
        None,
        "选择 nfo 目录",
        "",
        QFileDialog.Option.ShowDirsOnly,
    )
    if folder:
        self.Ui.lineEdit_actor_db_nfo_dir.setText(folder)


def pushButton_actor_db_update_nfo_tmdbid_clicked(self):
    self.pushButton_show_log_clicked()
    signal_qt.show_log_text("🎬 开始更新 nfo tmdbid（用本地库新 id 覆盖 nfo 旧 id）...")
    self._run_actor_db_update_nfo()
