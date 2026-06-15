"""Android 启动与未捕获异常日志（便于排查闪退）。"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def _crash_log_path() -> Path | None:
    priv = os.environ.get("ANDROID_PRIVATE")
    if not priv:
        return None
    return Path(priv) / "crash.log"


def log_boot_error(exc: BaseException) -> None:
    path = _crash_log_path()
    if path is None:
        return
    try:
        path.write_text(traceback.format_exception(type(exc), exc, exc.__traceback__), encoding="utf-8")
    except Exception:
        pass


def install_android_excepthook() -> None:
    if not os.environ.get("ANDROID_PRIVATE"):
        return

    log_path = _crash_log_path()
    if log_path is None:
        return

    def _hook(exc_type, exc, tb) -> None:
        try:
            log_path.write_text(
                traceback.format_exception(exc_type, exc, tb),
                encoding="utf-8",
            )
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook
