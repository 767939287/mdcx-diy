import asyncio
import re
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
    executor.submit(asyncio.run, run_backfill())


def pushButton_actor_db_pick_dir_clicked(self):
    media_folder_path = self._get_select_folder_path(self.Ui.lineEdit_actor_db_dir)
    if media_folder_path:
        self.Ui.lineEdit_actor_db_dir.setText(media_folder_path)


def pushButton_actor_db_start_clicked(self):
    from mdcx.tools.actor_db_tool import collect_actors_from_nfo_dir, run

    self.pushButton_show_log_clicked()
    names_text = self.Ui.lineEdit_actor_db_names.text().strip()
    nfo_dir = self.Ui.lineEdit_actor_db_dir.text().strip()
    translate = self.Ui.checkBox_actor_db_translate.isChecked()
    link = self.Ui.checkBox_actor_db_link.isChecked()

    if not names_text and not nfo_dir:
        signal_qt.show_log_text("🔴 请输入演员名单或选择 nfo 目录")
        return

    if not self.Ui.pushButton_actor_db_start.isEnabled():
        return

    self.Ui.pushButton_actor_db_start.setEnabled(False)

    def _split_names(text: str) -> list[str]:
        return [n.strip() for n in re.split(r"[ ;；,，\n]+", text) if n.strip()]

    async def run_tool():
        try:
            actor_names = _split_names(names_text)
            if nfo_dir:
                collected = await collect_actors_from_nfo_dir(Path(nfo_dir))
                signal_qt.show_log_text(f"📂 从 nfo 目录收集到 {len(collected)} 个演员")
                seen = set(actor_names)
                actor_names.extend(n for n in collected if n not in seen)
            if not actor_names:
                signal_qt.show_log_text("🔴 未收集到任何演员")
                return
            await run(actor_names, translate=translate, link=link)
        except Exception as e:
            signal_qt.show_log_text(f"🔴 演员库维护异常: {e}")
        finally:
            self.Ui.pushButton_actor_db_start.setEnabled(True)
            self.pushButton_actor_db_start.emit("开始维护")

    self.pushButton_actor_db_start.emit("维护中...")
    executor.submit(asyncio.run, run_tool())


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
