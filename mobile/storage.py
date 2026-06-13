"""移动端数据目录（Android / 桌面调试通用）。"""

from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    try:
        from kivy.app import App

        app = App.get_running_app()
        if app is not None:
            base = Path(app.user_data_dir)
            base.mkdir(parents=True, exist_ok=True)
            return base
    except Exception:
        pass
    base = Path(os.environ.get("WALLE_MOBILE_DATA", Path.home() / ".walle-mobile"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def todos_path() -> Path:
    return data_dir() / "todos.json"
