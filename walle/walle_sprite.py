"""WALL-E 形象与动画加载。

优先使用像素动画帧（walle/assets/frames），通过 animations.json 播放动画。
若资源缺失，则回退到内置矢量绘制（legacy_sprite）。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
FRAMES_DIR = ASSETS_DIR / "frames"
ANIM_FILE = ASSETS_DIR / "animations.json"

_NATIVE_W, _NATIVE_H = 179, 201

_WHITE_KEY = 235
_HALO_KEY = 195
_EYE_WHITE = QColor(255, 255, 255, 255)


def assets_available() -> bool:
    return ANIM_FILE.exists() and FRAMES_DIR.exists()


@lru_cache(maxsize=1)
def _load_manifest() -> dict:
    if not ANIM_FILE.exists():
        return {"frame_size": [_NATIVE_W, _NATIVE_H], "animations": {}}
    with open(ANIM_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _lum(c: QColor) -> float:
    return (c.red() + c.green() + c.blue()) / 3.0


def _has_transparent_neighbor(img: QImage, x: int, y: int) -> bool:
    w, h = img.width(), img.height()
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
        nx, ny = x + dx, y + dy
        if nx < 0 or ny < 0 or nx >= w or ny >= h:
            return True
        if img.pixelColor(nx, ny).alpha() == 0:
            return True
    return False


def _defringe_pixmap(pm: QPixmap) -> QPixmap:
    """仅去除贴图外缘白边/光晕。"""
    if pm.isNull():
        return pm
    img = pm.toImage().convertToFormat(QImage.Format_ARGB32)
    w, h = img.width(), img.height()
    transparent = QColor(0, 0, 0, 0)
    for y in range(h):
        for x in range(w):
            c = img.pixelColor(x, y)
            if c.alpha() == 0:
                continue
            r, g, b, a = c.red(), c.green(), c.blue(), c.alpha()
            avg = (r + g + b) / 3
            if not _has_transparent_neighbor(img, x, y):
                continue
            if r >= _WHITE_KEY and g >= _WHITE_KEY and b >= _WHITE_KEY:
                img.setPixelColor(x, y, transparent)
            elif avg >= _HALO_KEY:
                factor = min(1.0, (avg - _HALO_KEY) / (_WHITE_KEY - _HALO_KEY))
                c.setAlpha(max(0, int(a * (1.0 - factor * 0.95))))
                img.setPixelColor(x, y, c)
    return QPixmap.fromImage(img)


def _lens_radius(w: int, h: int) -> int:
    """镜片白色底衬半径（随帧尺寸等比缩放，不超出眼睛范围）。"""
    return max(7, int(round(min(w, h) * 0.036)))


def _refine_eye_center(img: QImage, x: int, y: int, radius: int = 6) -> Tuple[int, int]:
    w, h = img.width(), img.height()
    best = (x, y, 255.0)
    r2 = radius * radius
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy > r2:
                continue
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h):
                continue
            c = img.pixelColor(nx, ny)
            if c.alpha() < 80:
                continue
            lum = _lum(c)
            if lum < best[2]:
                best = (nx, ny, lum)
    return best[0], best[1]


def _find_eye_centers(img: QImage) -> List[Tuple[int, int]]:
    """在左右眼区域各找一个暗色镜片中心（随动画帧移动）。"""
    w, h = img.width(), img.height()
    mid = w // 2
    y_max = int(h * 0.45)
    sample_r = max(4, int(round(min(w, h) * 0.028)))
    sample_r2 = sample_r * sample_r
    ring_r = sample_r * 0.55

    centers: List[Tuple[int, int]] = []
    for x_lo, x_hi in ((4, mid - 4), (mid + 4, w - 4)):
        best_score = -1
        best_xy: Tuple[int, int] | None = None
        for y in range(6, y_max):
            for x in range(x_lo + sample_r, x_hi - sample_r):
                score = 0
                ring = 0
                for dy in range(-sample_r, sample_r + 1):
                    for dx in range(-sample_r, sample_r + 1):
                        d2 = dx * dx + dy * dy
                        if d2 > sample_r2:
                            continue
                        c = img.pixelColor(x + dx, y + dy)
                        if c.alpha() < 80:
                            continue
                        lum = _lum(c)
                        if lum < 12:
                            score += 3
                        elif lum < 35:
                            score += 1
                        dist = d2 ** 0.5
                        if dist >= ring_r and lum < 45:
                            ring += 1
                score += min(ring, 24)
                if score > best_score:
                    best_score = score
                    best_xy = (x, y)
        if best_xy and best_score >= 18:
            centers.append(_refine_eye_center(img, best_xy[0], best_xy[1]))

    if len(centers) == 2 and abs(centers[0][1] - centers[1][1]) > max(22, int(h * 0.12)):
        return []
    return centers


def _apply_eye_backing(pm: QPixmap, centers: List[Tuple[int, int]]) -> QPixmap:
    """在眼睛镜片范围内铺白色底衬，再叠加上方精灵图层。"""
    if pm.isNull() or not centers:
        return pm

    src = pm.toImage().convertToFormat(QImage.Format_ARGB32)
    w, h = src.width(), src.height()
    lens_r = _lens_radius(w, h)

    out = QImage(w, h, QImage.Format_ARGB32)
    out.fill(0)

    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_EYE_WHITE)
    for cx, cy in centers:
        painter.drawEllipse(cx - lens_r, cy - lens_r, lens_r * 2, lens_r * 2)
    painter.drawImage(0, 0, src)
    painter.end()

    return QPixmap.fromImage(out)


@lru_cache(maxsize=512)
def _eye_centers_for_frame(name: str) -> Tuple[Tuple[int, int], ...]:
    pm = QPixmap(str(FRAMES_DIR / f"{name}.png"))
    if pm.isNull():
        return ()
    return tuple(_find_eye_centers(_defringe_pixmap(pm).toImage()))


@lru_cache(maxsize=512)
def _load_frame(name: str) -> QPixmap:
    pm = QPixmap(str(FRAMES_DIR / f"{name}.png"))
    if pm.isNull():
        return pm
    defringed = _defringe_pixmap(pm)
    centers = _find_eye_centers(defringed.toImage())
    return _apply_eye_backing(defringed, list(centers))


def list_animations() -> List[str]:
    return list(_load_manifest().get("animations", {}).keys())


def get_animation(name: str) -> dict:
    anims = _load_manifest().get("animations", {})
    return anims.get(name) or anims.get("idle") or {"frames": [], "fps": 4, "loop": True}


@lru_cache(maxsize=2048)
def get_frame_scaled(name: str, size: int) -> QPixmap:
    pm = _load_frame(name)
    if pm.isNull():
        from .legacy_sprite import render_walle as _legacy
        return _legacy(size, state="idle")
    return pm.scaledToHeight(size, Qt.TransformationMode.FastTransformation)


def render_walle(size: int, state: str = "idle", blink: bool = False) -> QPixmap:
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
