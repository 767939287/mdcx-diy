#!/usr/bin/env python3
import json
import os
import platform
import sys

from PIL import ImageFile
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from mdcx.consts import IS_DOCKER, IS_MAC, IS_NFC, IS_PYINSTALLER, IS_WINDOWS, MAIN_PATH
from mdcx.controllers.main_window.main_window import MyMAinWindow
from mdcx.controllers.main_window.style import apply_application_palette
from mdcx.core.tmdb_actor import flush_tmdb_query_cache
from mdcx.utils.video import get_video_backend

ImageFile.LOAD_TRUNCATED_IMAGES = True


def _apply_ui_scale_factor():
    """读取用户配置的 UI 缩放比例并应用到 QT_SCALE_FACTOR。

    在 main() 早期执行，文件不可读/解析失败均不应阻断启动。
    """
    try:
        mark_file = MAIN_PATH / "MDCx.config"
        if not mark_file.is_file():
            return
        with open(mark_file, encoding="UTF-8") as f:
            config_path = f.read().strip()
        if not config_path or not os.path.isfile(config_path):
            return
        with open(config_path, encoding="UTF-8") as f:
            config = json.load(f)
        scale = config.get("ui_scale_factor", 0.0)
        if scale > 0:
            os.environ["QT_SCALE_FACTOR"] = str(scale)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(f"[warn] _apply_ui_scale_factor skipped: {e}")


def show_constants():
    """显示所有运行时常量"""
    constants = {
        "MAIN_PATH": MAIN_PATH,
        "IS_WINDOWS": IS_WINDOWS,
        "IS_MAC": IS_MAC,
        "IS_DOCKER": IS_DOCKER,
        "IS_NFC": IS_NFC,
        "IS_PYINSTALLER": IS_PYINSTALLER,
        "VIDEO_BACKEND": get_video_backend(),
    }
    print("Run time constants:")
    for key, value in constants.items():
        print(f"\t{key}: {value}")


def _create_application() -> tuple[QApplication, MyMAinWindow]:
    if os.path.isfile("highdpi_passthrough"):
        # Qt6 默认启用高 DPI，这里仅保留非整数缩放策略开关，避免 150% 缩放被取整。
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    if platform.system() != "Windows":
        app.setStyle("Fusion")
    apply_application_palette(False)
    if platform.system() != "Windows":
        app.setWindowIcon(QIcon("resources/Img/MDCx.ico"))  # 设置任务栏图标

    ui = MyMAinWindow()
    ui.show()
    app.installEventFilter(ui)
    return app, ui


def _enable_crash_dump() -> None:
    """注册崩溃转储：Python 异常 traceback + C 层 segfault 堆栈 + stdout/stderr 落盘。

    用于诊断 onefile 无控制台环境下程序静默退出的问题。仅诊断用，失败不阻断启动。
    日志写入 MAIN_PATH/crash/ 目录，正常运行时无任何文件生成。
    """
    try:
        import atexit
        import faulthandler
        import traceback as _tb
        from datetime import datetime

        log_dir = MAIN_PATH / "crash"
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存打开的文件句柄，程序正常退出时 flush+close，防 SIGKILL 时漏数据
        _crash_files: list[object] = []

        # 1) 重定向 stdout/stderr 到文件（onefile 无控制台时 print/异常输出会丢失）
        try:
            if sys.__stdout__ is not None:
                sys.stdout = sys.__stdout__
            else:
                stdout_file = open(log_dir / f"crash_{ts}.log", "w", encoding="utf-8")
                sys.stdout = stdout_file
                _crash_files.append(stdout_file)
            # 仅冻结(onefile 无控制台)时重定向 stderr；源码运行保留终端输出，便于调试期直接看 traceback
            if IS_PYINSTALLER:
                stderr_file = open(log_dir / f"crash_{ts}.log", "a", encoding="utf-8")
                sys.stderr = stderr_file
                _crash_files.append(stderr_file)
        except Exception:
            pass

        # 2) Python 未捕获异常写文件
        crash_path = log_dir / f"crash_{ts}_py.log"
        try:
            crash_path.write_text("", encoding="utf-8")
        except Exception:
            crash_path = None  # type: ignore[assignment]

        def _hook(etype, evalue, etb):
            try:
                text = "".join(_tb.format_exception(etype, evalue, etb))
                print("UNCAUGHT EXCEPTION:\n" + text)
                if crash_path is not None:
                    with open(crash_path, "a", encoding="utf-8") as f:
                        f.write(text)
            except Exception:
                pass
            sys.__excepthook__(etype, evalue, etb)

        sys.excepthook = _hook

        # 3) C 层崩溃 (segfault) 堆栈写文件
        try:
            faulthandler_file = open(log_dir / f"crash_{ts}_faulthandler.log", "w", encoding="utf-8")
            faulthandler.enable(file=faulthandler_file)
            _crash_files.append(faulthandler_file)
        except Exception:
            pass

        # 4) 进程退出时 flush/close，避免 SIGINT 等正常退出路径下缓冲日志丢失
        def _flush_and_close():
            for f in _crash_files:
                try:
                    f.flush()
                    f.close()
                except (AttributeError, OSError):
                    pass

        atexit.register(_flush_and_close)
    except Exception:
        pass


def main() -> int:
    _enable_crash_dump()
    show_constants()
    _apply_ui_scale_factor()
    app, _ui = _create_application()
    try:
        return_code = app.exec()
        return return_code
    except Exception as e:
        print("MAIN EXCEPTION:", e)
        try:
            import traceback as _tb

            _tb.print_exc()
        except Exception:
            pass
        return 1
    finally:
        flush_tmdb_query_cache()


if __name__ == "__main__":
    sys.exit(main())
