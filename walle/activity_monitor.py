"""全局键鼠活动监测（Windows），驱动宠物联动动画。"""

from __future__ import annotations

import sys
from enum import Enum

from PySide6.QtCore import QObject, QPoint, QTimer, Signal


class ActivityKind(Enum):
    IDLE = "idle"
    TYPING = "typing"
    MOUSE_MOVE = "mouse_move"
    CLICKING = "clicking"


class ActivityMonitor(QObject):
    """轮询系统键鼠状态，发出当前活动类型。"""

    activity_changed = Signal(object)  # ActivityKind

    def __init__(self, poll_ms: int = 80, idle_seconds: float = 2.0) -> None:
        super().__init__()
        self._poll_ms = poll_ms
        self._idle_ms = int(idle_seconds * 1000)
        self._last_pos = QPoint(0, 0)
        self._last_active_ms = 0
        self._current = ActivityKind.IDLE
        self._enabled = sys.platform == "win32"

        self._timer = QTimer(self)
        self._timer.setInterval(self._poll_ms)
        self._timer.timeout.connect(self._poll)
        if self._enabled:
            self._timer.start()

    @property
    def current(self) -> ActivityKind:
        return self._current

    def _poll(self) -> None:
        import ctypes

        user32 = ctypes.windll.user32
        now_ms = int(__import__("time").time() * 1000)

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        pos = QPoint(pt.x, pt.y)

        clicking = (
            (user32.GetAsyncKeyState(0x01) & 0x8000)
            or (user32.GetAsyncKeyState(0x02) & 0x8000)
        )
        typing = False
        for vk in range(0x08, 0xFE):
            if vk in (0x01, 0x02, 0x04, 0x05, 0x06):
                continue
            if user32.GetAsyncKeyState(vk) & 0x8000:
                typing = True
                break

        moved = pos != self._last_pos
        self._last_pos = pos

        if clicking:
            kind = ActivityKind.CLICKING
            self._last_active_ms = now_ms
        elif typing:
            kind = ActivityKind.TYPING
            self._last_active_ms = now_ms
        elif moved:
            kind = ActivityKind.MOUSE_MOVE
            self._last_active_ms = now_ms
        elif now_ms - self._last_active_ms > self._idle_ms:
            kind = ActivityKind.IDLE
        else:
            kind = self._current

        if kind != self._current:
            self._current = kind
            self.activity_changed.emit(kind)
