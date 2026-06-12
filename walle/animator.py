"""动画播放器：把图集动作序列驱动到一个 QLabel 上。

用法：
    anim = SpriteAnimator(label, size=160)
    anim.play("idle")            # 循环待机
    anim.play_once("wave", then="idle")  # 播放一次后回到 idle
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer

from . import walle_sprite as sprite


class SpriteAnimator(QObject):
    def __init__(self, label, size: int = 160) -> None:
        super().__init__(label)
        self._label = label
        self._size = size
        self._frames: list[str] = []
        self._fps = 4
        self._loop = True
        self._index = 0
        self._current = ""
        self._then: str | None = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)

    def set_size(self, size: int) -> None:
        if size != self._size:
            self._size = size
            self._render()  # 立即用新尺寸刷新当前帧

    @property
    def current(self) -> str:
        return self._current

    def play(self, name: str, restart: bool = False) -> None:
        """循环播放某动作（若已在播放同一动作且 restart=False 则不打断）。"""
        if name == self._current and not restart and self._timer.isActive():
            return
        self._start(name, then=None)

    def play_once(self, name: str, then: str = "idle") -> None:
        """播放一次后切到 then 指定的循环动作。"""
        self._start(name, then=then)

    def stop(self) -> None:
        self._timer.stop()

    # ------------------------------------------------------------------ 内部
    def _start(self, name: str, then: str | None) -> None:
        self._frames = sprite.frames_of(name) or sprite.frames_of("idle")
        if not self._frames:
            return
        self._fps = max(1, sprite.fps_of(name))
        self._loop = sprite.loops(name)
        self._current = name
        self._then = then
        self._index = 0
        self._render()
        self._timer.start(int(1000 / self._fps))

    def _advance(self) -> None:
        self._index += 1
        if self._index >= len(self._frames):
            if self._loop and self._then is None:
                self._index = 0
            else:
                self._timer.stop()
                if self._then:
                    self.play(self._then)
                return
        self._render()

    def _render(self) -> None:
        if not self._frames:
            return
        frame = self._frames[min(self._index, len(self._frames) - 1)]
        self._label.setPixmap(sprite.get_frame_scaled(frame, self._size))
