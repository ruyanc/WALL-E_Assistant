"""移动端数据目录（Android / 桌面调试通用）。"""

from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    android_private = os.environ.get("ANDROID_PRIVATE")
    if android_private:
        base = Path(android_private)
        base.mkdir(parents=True, exist_ok=True)
        return base
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


def notes_path() -> Path:
    return data_dir() / "notes.json"


def reminders_path() -> Path:
    return data_dir() / "reminders.json"


def settings_path() -> Path:
    return data_dir() / "settings.json"


def auth_path() -> Path:
    return data_dir() / "auth.json"


def sync_meta_path() -> Path:
    return data_dir() / "sync_meta.json"


def assignments_path() -> Path:
    return data_dir() / "assignments.json"


def sync_config_path() -> Path:
    return data_dir() / "sync_config.json"


def pomodoro_state_path() -> Path:
    return data_dir() / "pomodoro_state.json"
