"""移动端设置（含授权码 / cloudbase_env_id）。"""

from __future__ import annotations

import json
import time
from typing import Any

from storage import settings_path

DEFAULTS: dict[str, Any] = {
    "work_minutes": 50,
    "rest_minutes": 10,
    "cycles": 3,
    "cloudbase_env_id": "",
    "language": "zh",
    "rest_sound": True,
    "settings_updated_at": 0.0,
}


class SettingsStore:
    def __init__(self) -> None:
        self._data = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        path = settings_path()
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self._data.update({k: loaded[k] for k in DEFAULTS if k in loaded})
                if "cloudbase_env_id" in loaded:
                    self._data["cloudbase_env_id"] = str(loaded["cloudbase_env_id"])
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    def save(self) -> None:
        try:
            with open(settings_path(), "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        from walle.sync.engine import SYNC_SETTINGS_KEYS

        if key in SYNC_SETTINGS_KEYS:
            self._data["settings_updated_at"] = time.time()
        self.save()

    def update(self, values: dict[str, Any]) -> None:
        self._data.update(values)
        self.save()

    def timer_values(self) -> tuple[int, int, int]:
        return (
            int(self.get("work_minutes", 50)),
            int(self.get("rest_minutes", 10)),
            int(self.get("cycles", 3)),
        )

    def save_timer(self, work: int, rest: int, cycles: int) -> None:
        self.update(
            {
                "work_minutes": work,
                "rest_minutes": rest,
                "cycles": cycles,
                "settings_updated_at": time.time(),
            }
        )

