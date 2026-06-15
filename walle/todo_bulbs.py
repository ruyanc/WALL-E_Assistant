"""待办优先级电灯泡指示器（显示在宠物头部上方）。"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .todo_manager import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_MED, Task

# 高 / 中 / 低 → 红 / 蓝 / 绿
PRIORITY_COLORS = {
    PRIORITY_HIGH: QColor(0xE7, 0x4C, 0x3C),
    PRIORITY_MED: QColor(0x34, 0x98, 0xDB),
    PRIORITY_LOW: QColor(0x2E, 0xCC, 0x71),
}


class BulbButton(QWidget):
    """单个可点击电灯泡。"""

    clicked_bulb = Signal(str)

    def __init__(self, task: Task, size: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._task = task
        self._size = size
        self._color = PRIORITY_COLORS.get(task.priority, PRIORITY_COLORS[PRIORITY_MED])
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(task.text)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        s = self._size
        cx, cy = s / 2, s * 0.42
        bulb_r = s * 0.28

        # 灯泡主体
        p.setPen(QPen(self._color.darker(120), 1))
        p.setBrush(QBrush(self._color))
        p.drawEllipse(QPoint(int(cx), int(cy)), int(bulb_r), int(bulb_r))

        # 灯丝高光
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 180))
        p.drawEllipse(QPoint(int(cx - bulb_r * 0.25), int(cy - bulb_r * 0.25)), int(bulb_r * 0.35), int(bulb_r * 0.35))

        # 底座
        base_w, base_h = bulb_r * 1.1, s * 0.14
        p.setBrush(QBrush(self._color.darker(140)))
        p.drawRoundedRect(
            int(cx - base_w / 2), int(cy + bulb_r * 0.75),
            int(base_w), int(base_h), 2, 2,
        )
        p.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked_bulb.emit(self._task.id)
            event.accept()


class TodoBulbBar(QWidget):
    """一排电灯泡，居中对齐。"""

    bulb_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._bulbs: list[BulbButton] = []
        self._tasks: list[Task] = []
        self._bulb_size = 22
        self.setFixedHeight(self._bulb_size + 4)

    def set_bulb_size(self, pet_width: int) -> None:
        self._bulb_size = max(16, min(30, int(pet_width * 0.14)))
        self.setFixedHeight(self._bulb_size + 4)
        self._rebuild()

    def set_tasks(self, tasks: list[Task]) -> None:
        self._tasks = tasks
        self._rebuild()

    def _rebuild(self) -> None:
        for b in self._bulbs:
            b.deleteLater()
        self._bulbs.clear()

        if not self._tasks:
            self.setFixedWidth(0)
            self.hide()
            return

        gap = max(2, self._bulb_size // 6)
        width = len(self._tasks) * self._bulb_size + (len(self._tasks) - 1) * gap
        self.setFixedWidth(width)
        self.show()

        x = 0
        for task in self._tasks:
            bulb = BulbButton(task, self._bulb_size, self)
            bulb.move(x, 0)
            bulb.clicked_bulb.connect(self.bulb_clicked.emit)
            bulb.show()
            self._bulbs.append(bulb)
            x += self._bulb_size + gap
