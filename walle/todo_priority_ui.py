"""待办优先级：彩色电灯泡选择器。"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QWidget

from .todo_bulbs import PRIORITY_COLORS
from .todo_manager import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_MED

_PRIORITY_ORDER = (PRIORITY_HIGH, PRIORITY_MED, PRIORITY_LOW)


def _draw_bulb(p: QPainter, cx: float, cy: float, size: int, color: QColor, selected: bool) -> None:
    bulb_r = size * 0.28
    if selected:
        p.setPen(QPen(QColor(0xF3, 0xEB, 0xE0), 2))
    else:
        p.setPen(QPen(color.darker(120), 1))
    p.setBrush(QBrush(color))
    p.drawEllipse(QPoint(int(cx), int(cy)), int(bulb_r), int(bulb_r))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 160))
    p.drawEllipse(
        QPoint(int(cx - bulb_r * 0.25), int(cy - bulb_r * 0.25)),
        int(bulb_r * 0.32),
        int(bulb_r * 0.32),
    )
    base_w, base_h = bulb_r * 1.1, size * 0.14
    p.setBrush(QBrush(color.darker(140)))
    p.drawRoundedRect(
        int(cx - base_w / 2),
        int(cy + bulb_r * 0.75),
        int(base_w),
        int(base_h),
        2,
        2,
    )


class _BulbHit(QWidget):
    clicked = Signal(int)

    def __init__(self, priority: int, size: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.priority = priority
        self._size = size
        self._selected = False
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)

    def set_selected(self, on: bool) -> None:
        self._selected = on
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        color = PRIORITY_COLORS.get(self.priority, PRIORITY_COLORS[PRIORITY_MED])
        _draw_bulb(p, self._size / 2, self._size * 0.42, self._size, color, self._selected)
        p.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.priority)
            event.accept()


class PriorityBulbPicker(QWidget):
    changed = Signal(int)

    def __init__(self, priority: int = PRIORITY_MED, bulb_size: int = 28, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._priority = priority
        self._loading = False
        self._bulb_size = bulb_size

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self._hits: dict[int, _BulbHit] = {}
        for pri in _PRIORITY_ORDER:
            hit = _BulbHit(pri, bulb_size, self)
            hit.clicked.connect(self._on_bulb)
            lay.addWidget(hit)
            self._hits[pri] = hit

        self.set_priority(priority)

    def _on_bulb(self, priority: int) -> None:
        self.set_priority(priority)
        if not self._loading:
            self.changed.emit(priority)

    def set_loading(self, loading: bool) -> None:
        self._loading = loading

    def priority(self) -> int:
        return self._priority

    def set_priority(self, priority: int) -> None:
        self._priority = max(PRIORITY_LOW, min(PRIORITY_HIGH, int(priority)))
        for pri, hit in self._hits.items():
            hit.set_selected(pri == self._priority)

    def sizeHint(self) -> QSize:
        n = len(_PRIORITY_ORDER)
        w = n * self._bulb_size + (n - 1) * 4
        return QSize(w, self._bulb_size)
