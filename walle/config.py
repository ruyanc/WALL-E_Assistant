"""配置与数据持久化模块。

负责把用户设置（番茄钟参数、宠物位置等）以及待办列表保存到
用户目录 %APPDATA%\\WALL-E 下，保证重启后状态不丢失。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict


def get_data_dir() -> Path:
    """返回应用的数据目录，不存在时自动创建。"""
    base = os.environ.get("APPDATA") or str(Path.home())
    data_dir = Path(base) / "WALL-E"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


CONFIG_PATH = get_data_dir() / "settings.json"
TODO_PATH = get_data_dir() / "todos.json"

# 默认设置
DEFAULTS: Dict[str, Any] = {
    # 番茄钟：工作分钟、休息分钟、循环次数
    "work_minutes": 50,
    "rest_minutes": 10,
    "cycles": 3,
    # 宠物窗口位置（None 表示首次启动放到右下角）
    "pet_x": None,
    "pet_y": None,
    # 宠物尺寸（像素，正方形边长）
    "pet_size": 160,
    # 开机自启动（仅作为标记，实际由安装程序/快捷方式控制）
    "autostart": False,
    # 休息提醒是否带声音提示
    "rest_sound": True,
}


class Config:
    """简单的 key-value 配置封装，自动落盘。"""

    def __init__(self) -> None:
        self._data: Dict[str, Any] = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    self._data.update(loaded)
            except (json.JSONDecodeError, OSError):
                # 配置损坏时回退到默认值，避免程序无法启动
                self._data = dict(DEFAULTS)

    def save(self) -> None:
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def update(self, values: Dict[str, Any]) -> None:
        self._data.update(values)
        self.save()
