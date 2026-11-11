import asyncio
import multiprocessing
import os
import string
import sys
import traceback


def log_uncaught_exceptions(exctype, value, tb):
    with open("crash.log", "w", encoding="utf-8") as f:
        traceback.print_exception(exctype, value, tb, file=f)
    traceback.print_exception(exctype, value, tb)


sys.excepthook = log_uncaught_exceptions

if getattr(sys, "frozen", False) or "__compiled__" in globals():
    app_dir = os.path.dirname(os.path.abspath(sys.executable))
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))

os.chdir(app_dir)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from PySide6.QtWidgets import QApplication
from main import WebantulaUI
from qasync import QEventLoop


def find_redis_on_drives():
    local_redis = os.path.join(app_dir, "redis-windows-8.8.0", "redis-server.exe")
    if os.path.exists(local_redis):
        return local_redis

    for drive_letter in string.ascii_uppercase:
        drive_path = f"{drive_letter}:\\"
        if os.path.exists(drive_path):
            candidate = os.path.join(
                drive_path, "redis-windows-8.8.0", "redis-server.exe"
            )
            if os.path.exists(candidate):
                return candidate
    return None


if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop=loop)

    window = WebantulaUI()
    redis_path = find_redis_on_drives()

    if redis_path:
        print(f"[INFO] Найден и запущен Redis: {redis_path}")
        os.startfile(redis_path)
    else:
        print("[WARN] Папка redis-windows-8.8.0 не найдена ни на одном диске!")

    window.show()
    with loop:
        loop.run_forever()
