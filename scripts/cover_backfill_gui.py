# ruff: noqa: E402, I001
import asyncio
import contextlib
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
import traceback
from pathlib import Path
from typing import TextIO
from tkinter import filedialog, messagebox, ttk

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.cover_backfill import backfill_cover  # noqa: E402


DEFAULT_OUTPUT_DIR = Path.home() / "Desktop" / "MDCxCoverOutput"


class QueueWriter:
    def __init__(self, output_queue: "queue.Queue[tuple[str, str]]", log_file: TextIO | None = None):
        self.output_queue = output_queue
        self.log_file = log_file

    def write(self, text: str) -> int:
        if text:
            self.output_queue.put(("log", text))
            if self.log_file:
                self.log_file.write(text)
                self.log_file.flush()
        return len(text)

    def flush(self) -> None:
        pass


class CoverBackfillApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MDCx 封面补图")
        self.geometry("760x560")
        self.minsize(680, 460)
        self.output_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.worker: threading.Thread | None = None

        self.output_dir = tk.StringVar(value=str(DEFAULT_OUTPUT_DIR))
        self.overwrite = tk.BooleanVar(value=True)

        self._build_ui()
        self.after(100, self._poll_queue)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        main = ttk.Frame(self, padding=14)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)

        ttk.Label(main, text="番号 / 文件名 / 文件路径").grid(row=0, column=0, sticky="w")
        self.input_text = tk.Text(main, height=5, wrap="word", undo=True)
        self.input_text.grid(row=1, column=0, sticky="ew", pady=(6, 4))
        self.input_text.focus_set()

        tip = "例：NACT-141.(mp4).strm，也可以一行一个批量输入。程序会自动解析番号、抓高清图、裁切有码封面并加水印。"
        ttk.Label(main, text=tip, foreground="#666666").grid(row=2, column=0, sticky="w", pady=(0, 12))

        output_frame = ttk.Frame(main)
        output_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        output_frame.columnconfigure(1, weight=1)
        ttk.Label(output_frame, text="输出目录").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(output_frame, textvariable=self.output_dir).grid(row=0, column=1, sticky="ew")
        ttk.Button(output_frame, text="选择", command=self._choose_output_dir).grid(row=0, column=2, padx=(8, 0))

        actions = ttk.Frame(main)
        actions.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        self.start_button = ttk.Button(actions, text="开始下载", command=self._start)
        self.start_button.grid(row=0, column=0, padx=(0, 8))
        ttk.Checkbutton(actions, text="覆盖已有图片以更新高清图", variable=self.overwrite).grid(row=0, column=1)
        ttk.Button(actions, text="清空日志", command=self._clear_log).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(actions, text="打开目录", command=self._open_output_dir).grid(row=0, column=3, padx=(8, 0))

        self.status = tk.StringVar(value="就绪")
        ttk.Label(main, textvariable=self.status, foreground="#444444").grid(row=5, column=0, sticky="w")

        log_frame = ttk.Frame(self, padding=(14, 0, 14, 14))
        log_frame.grid(row=2, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, wrap="word", state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _choose_output_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.output_dir.get() or str(DEFAULT_OUTPUT_DIR))
        if chosen:
            self.output_dir.set(chosen)

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _open_output_dir(self) -> None:
        output_dir = Path(self.output_dir.get().strip() or DEFAULT_OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(output_dir)])
        else:
            messagebox.showinfo("MDCx 封面补图", f"输出目录：{output_dir}")

    def _items(self) -> list[str]:
        raw = self.input_text.get("1.0", "end").strip()
        return [item.strip() for item in re.split(r"[\r\n;]+", raw) if item.strip()]

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            return

        items = self._items()
        if not items:
            messagebox.showinfo("MDCx 封面补图", "先输入一个番号或文件名。")
            return

        output_dir = Path(self.output_dir.get().strip() or DEFAULT_OUTPUT_DIR)
        self.start_button.configure(state="disabled")
        self.status.set("正在补图...")
        self._append_log("\n" + "=" * 72 + "\n")
        self._append_log(f"输出目录：{output_dir}\n")
        self._append_log(f"任务数量：{len(items)}\n")

        self.worker = threading.Thread(
            target=self._run_worker,
            args=(items, output_dir, self.overwrite.get()),
            daemon=True,
        )
        self.worker.start()

    def _run_worker(self, items: list[str], output_dir: Path, overwrite: bool) -> None:
        async def run_all() -> tuple[int, int]:
            ok_count = 0
            fail_count = 0
            for index, item in enumerate(items, 1):
                print(f"\n[{index}/{len(items)}] {item}")
                try:
                    result = await backfill_cover(
                        item,
                        output_dir=output_dir,
                        overwrite=overwrite,
                        watermark=True,
                        crawl_timeout=90,
                    )
                    ok_count += 1
                    print(f"\n完成：{result.number}")
                    if result.thumb_path:
                        print(f"  thumb : {result.thumb_path}")
                    if result.poster_path:
                        print(f"  poster: {result.poster_path}")
                except Exception as exc:
                    fail_count += 1
                    print(f"\n失败：{item}\n  {exc}")
            return ok_count, fail_count

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            log_path = output_dir / "cover_backfill.log"
            with log_path.open("a", encoding="utf-8") as log_file:
                writer = QueueWriter(self.output_queue, log_file)
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    print("\n" + "=" * 72)
                    print(f"输出目录：{output_dir}")
                    ok_count, fail_count = asyncio.run(run_all())
            self.output_queue.put(("done", f"完成 {ok_count} 个，失败 {fail_count} 个"))
        except Exception as exc:
            self.output_queue.put(("done", f"运行失败：{exc}"))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, text = self.output_queue.get_nowait()
                if kind == "log":
                    self._append_log(text)
                elif kind == "done":
                    self._append_log(f"\n{text}\n")
                    self.status.set(text)
                    self.start_button.configure(state="normal")
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)


def _error_log_path() -> Path:
    return Path.home() / "Desktop" / "MDCxCoverBackfill-error.log"


def main() -> None:
    app = CoverBackfillApp()
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        error_path = _error_log_path()
        error_path.write_text(traceback.format_exc(), encoding="utf-8")
        try:
            messagebox.showerror("MDCx 封面补图", f"程序启动失败，错误日志已写入：\n{error_path}")
        except Exception:
            pass
