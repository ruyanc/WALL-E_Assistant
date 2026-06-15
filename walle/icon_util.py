"""应用图标：与桌面快捷方式 / exe 嵌入图标保持一致。"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QIcon


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ico_candidates() -> list[Path]:
    paths: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            paths.append(Path(meipass) / "assets" / "walle.ico")
        exe_dir = Path(sys.executable).resolve().parent
        paths.append(exe_dir / "walle.ico")
        paths.append(Path(sys.executable))
    else:
        paths.append(_project_root() / "assets" / "walle.ico")
    return paths


@lru_cache(maxsize=1)
def app_icon() -> QIcon:
    """加载 assets/walle.ico；打包后优先与 exe / 安装目录 walle.ico 一致。"""
    for path in _ico_candidates():
        if not path.is_file():
            continue
        icon = QIcon(str(path))
        if not icon.isNull():
            return icon
    from .walle_sprite import render_walle

    return QIcon(render_walle(64, state="idle"))
