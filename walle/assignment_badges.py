"""派发任务状态标识：左侧信封（已接受的收件）、右侧旗子（对方已接受的派出）。"""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .todo_bulbs import PRIORITY_COLORS
from .todo_manager import PRIORITY_MED


def _draw_envelope(p: QPainter, color: QColor, s: float) -> None:
    margin = s * 0.1
    body_w = s - 2 * margin
    body_h = s * 0.52
    body_top = s * 0.34
    cx = s / 2

    p.setPen(QPen(color.darker(125), max(1, int(s * 0.06))))
    p.setBrush(QBrush(color))
    p.drawRoundedRect(
        int(margin), int(body_top), int(body_w), int(body_h), 3, 3,
    )

    flap_bottom = body_top + body_h * 0.38
    flap = QPainterPath()
    flap.moveTo(margin, body_top)
    flap.lineTo(cx, flap_bottom)
    flap.lineTo(margin + body_w, body_top)
    flap.closeSubpath()
    p.drawPath(flap)

    p.setPen(QPen(color.darker(140), max(1, int(s * 0.05))))
    p.drawLine(int(cx), int(body_top), int(cx), int(body_top + body_h))


def _draw_flag(p: QPainter, color: QColor, s: float) -> None:
    pole_x = s * 0.26
    pole_top = s * 0.14
    pole_bottom = s * 0.86
    pole_w = max(2, int(s * 0.1))

    p.setPen(Qt.NoPen)
    p.setBrush(QColor(70, 62, 54))
    p.drawRoundedRect(
        int(pole_x - pole_w / 2), int(pole_top),
        pole_w, int(pole_bottom - pole_top), 1, 1,
    )

    flag_top = pole_top + s * 0.06
    flag_h = s * 0.42
    flag_w = s * 0.58
    flag = QPainterPath()
    flag.moveTo(pole_x, flag_top)
    flag.lineTo(pole_x + flag_w, flag_top + flag_h * 0.45)
    flag.lineTo(pole_x, flag_top + flag_h)
    flag.closeSubpath()
    p.setPen(QPen(color.darker(125), max(1, int(s * 0.06))))
    p.setBrush(QBrush(color))
    p.drawPath(flag)


class _SingleAssignmentBadge(QWidget):
    clicked = Signal()

    def __init__(self, kind: Literal["envelope", "flag"], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._kind = kind
        self._size = 22
        self._priority: int | None = None
        self._color = PRIORITY_COLORS[PRIORITY_MED]
        self.setCursor(Qt.PointingHandCursor)

    def set_badge_size(self, size: int) -> None:
        self._size = max(12, min(28, int(size)))
        self.setFixedSize(self._size, self._size)

    def set_priority(self, priority: int) -> None:
        self._priority = priority
        self._color = PRIORITY_COLORS.get(priority, PRIORITY_COLORS[PRIORITY_MED])
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if self._priority is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        if self._kind == "envelope":
            _draw_envelope(p, self._color, self._size)
        else:
            _draw_flag(p, self._color, self._size)
        p.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()


class AssignmentBadgeColumn(QWidget):
    """侧栏一列：按任务数量与优先级各显示一枚信封或旗子。"""

    clicked = Signal()

    def __init__(
        self,
        kind: Literal["envelope", "flag"],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._kind = kind
        self._badges: list[_SingleAssignmentBadge] = []
        self._badge_size = 22

    def set_badge_size(self, size: int) -> None:
        self._badge_size = max(12, min(28, int(size)))

    def set_priorities(self, priorities: list[int], tooltip: str = "") -> None:
        for badge in self._badges:
            badge.deleteLater()
        self._badges.clear()
        self.setToolTip(tooltip)

        if not priorities:
            self.setFixedSize(0, 0)
            self.hide()
            return

        gap = max(2, self._badge_size // 8)
        count = len(priorities)
        col_w = self._badge_size
        col_h = count * self._badge_size + (count - 1) * gap
        self.setFixedSize(col_w, col_h)
        self.show()

        y = 0
        for priority in priorities:
            badge = _SingleAssignmentBadge(self._kind, self)
            badge.set_badge_size(self._badge_size)
            badge.set_priority(priority)
            badge.setGeometry(0, y, self._badge_size, self._badge_size)
            badge.clicked.connect(self.clicked.emit)
            badge.show()
            self._badges.append(badge)
            y += self._badge_size + gap
