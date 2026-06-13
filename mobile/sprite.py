"""瓦力帧动画（读取 assets/frames + animations.json）。"""

from __future__ import annotations

import json
from pathlib import Path

from kivy.clock import Clock
from kivy.uix.image import Image

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
FRAMES = ASSETS / "frames"
ANIM_FILE = ASSETS / "animations.json"


def _load_manifest() -> dict:
    if not ANIM_FILE.exists():
        return {"animations": {"idle": {"frames": ["0_0"], "fps": 4, "loop": True}}}
    with open(ANIM_FILE, encoding="utf-8") as f:
        return json.load(f)


class WalleSprite(Image):
    """循环播放指定动作序列。"""

    def __init__(self, anim: str = "idle", **kwargs):
        super().__init__(**kwargs)
        self.allow_stretch = True
        self.keep_ratio = True
        self._anim_name = anim
        self._frame_idx = 0
        self._ev = None
        self._frames: list[str] = []
        self._loop = True
        self._reload_anim(anim)

    def _reload_anim(self, name: str) -> None:
        anims = _load_manifest().get("animations", {})
        spec = anims.get(name) or anims.get("idle") or {"frames": ["0_0"], "fps": 4, "loop": True}
        self._frames = list(spec.get("frames") or ["0_0"])
        self._loop = bool(spec.get("loop", True))
        fps = max(1, int(spec.get("fps", 4)))
        self._frame_idx = 0
        if self._ev is not None:
            self._ev.cancel()
        self._show_frame()
        self._ev = Clock.schedule_interval(self._tick, 1.0 / fps)

    def set_anim(self, name: str) -> None:
        if name != self._anim_name:
            self._anim_name = name
            self._reload_anim(name)

    def _show_frame(self) -> None:
        if not self._frames:
            return
        name = self._frames[self._frame_idx % len(self._frames)]
        path = FRAMES / f"{name}.png"
        if path.is_file():
            self.source = str(path)
            self.reload()

    def _tick(self, _dt: float) -> bool:
        if not self._frames:
            return False
        self._frame_idx += 1
        if self._frame_idx >= len(self._frames):
            if self._loop:
                self._frame_idx = 0
            else:
                self._frame_idx = len(self._frames) - 1
                return False
        self._show_frame()
        return True

    def on_parent(self, widget, parent):  # noqa: N802
        super().on_parent(widget, parent)
        if parent is None and self._ev is not None:
            self._ev.cancel()
            self._ev = None
