import asyncio
import re
import traceback
from pathlib import Path

from mdcx.config.manager import manager
from mdcx.signals import signal_qt
from mdcx.utils import executor


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
