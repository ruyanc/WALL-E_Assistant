"""移动端 walle.config 模板（由 prepare_sync.py 复制到 mobile/walle/config.py）。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

DEFAULTS: Dict[str, Any] = {
    "work_minutes": 50,
    "rest_minutes": 10,
    "cycles": 3,
    "cloudbase_env_id": "",
    "language": "zh",
    "rest_sound": True,
    "settings_updated_at": 0.0,
    "sync_paused": False,
}


def get_data_dir() -> Path:
    android_private = os.environ.get("ANDROID_PRIVATE")
    if android_private:
        base = Path(android_private)
        base.mkdir(parents=True, exist_ok=True)
        return base
    base = Path(os.environ.get("WALLE_MOBILE_DATA", Path.home() / ".walle-mobile"))
    base.mkdir(parents=True, exist_ok=True)
    return base


_DATA = get_data_dir()
CONFIG_PATH = _DATA / "settings.json"
TODO_PATH = _DATA / "todos.json"
NOTES_PATH = _DATA / "notes.json"
REMINDERS_PATH = _DATA / "reminders.json"
AUTH_PATH = _DATA / "auth.json"
SYNC_META_PATH = _DATA / "sync_meta.json"
SYNC_CONFIG_PATH = _DATA / "sync_config.json"
