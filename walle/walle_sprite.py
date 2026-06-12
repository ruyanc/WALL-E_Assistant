"""WALL-E 形象与动画加载。

优先使用 usr 参考精灵图裁切出的像素动画帧（walle/assets/frames），
通过 animations.json 定义的动作序列播放动画。
若资源缺失，则回退到内置矢量绘制（legacy_sprite）。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
FRAMES_DIR = ASSETS_DIR / "frames"
ANIM_FILE = ASSETS_DIR / "animations.json"


def assets_available() -> bool:
    return ANIM_FILE.exists() and FRAMES_DIR.exists()


@lru_cache(maxsize=1)
def _load_manifest() -> dict:
    if not ANIM_FILE.exists():
        return {"frame_size": [179, 201], "animations": {}}
    with open(ANIM_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=512)
def _load_frame(name: str) -> QPixmap:
    """加载单帧原始 pixmap（带缓存）。"""
    return QPixmap(str(FRAMES_DIR / f"{name}.png"))


def list_animations() -> List[str]:
    return list(_load_manifest().get("animations", {}).keys())


def get_animation(name: str) -> dict:
    anims = _load_manifest().get("animations", {})
    return anims.get(name) or anims.get("idle") or {"frames": [], "fps": 4, "loop": True}


@lru_cache(maxsize=2048)
def get_frame_scaled(name: str, size: int) -> QPixmap:
    """返回缩放到指定高度的帧（保持宽高比，带缓存）。"""
    pm = _load_frame(name)
    if pm.isNull():
        from .legacy_sprite import render_walle as _legacy
        return _legacy(size, state="idle")
    return pm.scaledToHeight(size, Qt.SmoothTransformation)


def render_walle(size: int, state: str = "idle", blink: bool = False) -> QPixmap:
    """兼容旧接口：返回某状态的代表性单帧（用于图标、托盘等静态场景）。"""
    if not assets_available():
        from .legacy_sprite import render_walle as _legacy
        return _legacy(size, state=state, blink=blink)
    anim = get_animation("blink" if blink else state)
    frames = anim.get("frames") or ["0_0"]
    return get_frame_scaled(frames[0], size)


def frames_of(name: str) -> List[str]:
    return list(get_animation(name).get("frames", []))


def fps_of(name: str) -> int:
    return int(get_animation(name).get("fps", 4))


def loops(name: str) -> bool:
    return bool(get_animation(name).get("loop", True))
