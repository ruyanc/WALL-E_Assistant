"""桌面悬浮宠物窗口。"""

from __future__ import annotations

import random

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import QLabel, QMenu, QVBoxLayout, QWidget

from .activity_monitor import ActivityKind
from .animator import SpriteAnimator
from .config import Config
from .todo_bulbs import TodoBulbBar
from .i18n import priority_short, tr
from .todo_manager import TodoManager

MIN_PET_SIZE = 80
MAX_PET_SIZE = 420
FRAME_ASPECT = 201 / 179
RESIZE_HANDLE = 18

_ACTIVITY_ANIM = {
    ActivityKind.IDLE: "idle",
    ActivityKind.TYPING: "talk",
    ActivityKind.MOUSE_MOVE: "look",
    ActivityKind.CLICKING: "wave",
}

class SpeechBubble(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        self.label = QLabel("")
        self.label.setWordWrap(True)
        self.label.setFont(QFont("Microsoft YaHei UI", 10))
        self.label.setStyleSheet(
            "background:#f4ead4;color:#2b2622;border:2px solid #c88a3a;"
            "border-radius:10px;padding:8px 10px;"
        )
        lay.addWidget(self.label)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def pop(self, text: str, near: QPoint, duration: int = 4000) -> None:
        self.label.setText(text)
        self.adjustSize()
        self.move(near.x(), near.y() - self.height() - 6)
        self.show()
        self.raise_()
        self._timer.start(duration)


class PetWindow(QWidget):
    clicked = Signal()
    open_panel = Signal()
    start_timer = Signal()
    start_rest = Signal()
    quit_requested = Signal()
    size_changed = Signal(int)

    def __init__(self, config: Config, todo: TodoManager | None = None) -> None:
        super().__init__()
        self.config = config
        self.todo = todo
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._size = int(config.get("pet_size", 160))
        self._bulb_h = max(20, int(self._size * 0.16))
        self._apply_dimensions(self._size)

        self.bulb_bar = TodoBulbBar(self)
        self.bulb_bar.bulb_clicked.connect(self._on_bulb_clicked)

        self.label = QLabel(self)
        self.label.setAttribute(Qt.WA_TranslucentBackground, True)
        self.label.setStyleSheet("background: transparent;")
        self.label.setAlignment(Qt.AlignCenter)

        self.bubble = SpeechBubble()

        self._state = "idle"
        self._activity_enabled = True
        self._activity_kind = ActivityKind.IDLE
        self.animator = SpriteAnimator(self.label, size=self._win_h)
        self.animator.play("idle")

        self._drag_pos: QPoint | None = None
        self._resize_origin: QPoint | None = None
        self._resize_start_size = self._size
        self._moved = False
        self._resizing = False

        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._idle_action)
        self._idle_timer.start(6000)

        self._restore_position()
        self._layout_children()
        self.refresh_bulbs()

    def bind_todo(self, todo: TodoManager) -> None:
        self.todo = todo
        todo.changed.connect(self.refresh_bulbs)
        self.refresh_bulbs()

    # ------------------------------------------------------------------ 布局
    def _apply_dimensions(self, width: int) -> None:
        self._size = max(MIN_PET_SIZE, min(MAX_PET_SIZE, int(width)))
        self._win_w = self._size
        self._win_h = int(self._size * FRAME_ASPECT)
        self._bulb_h = max(20, int(self._size * 0.16))
        self.resize(self._win_w, self._bulb_h + self._win_h)

    def _layout_children(self) -> None:
        self.bulb_bar.set_bulb_size(self._size)
        bw = self.bulb_bar.width()
        self.bulb_bar.setGeometry((self._win_w - bw) // 2, 0, bw, self._bulb_h)
        self.label.setGeometry(0, self._bulb_h, self._win_w, self._win_h)
        self.animator.set_size(self._win_h)

    def refresh_bulbs(self) -> None:
        if self.todo is None:
            self.bulb_bar.set_tasks([])
            return
        self.bulb_bar.set_tasks(self.todo.pending())
        self._layout_children()

    def _on_bulb_clicked(self, task_id: int) -> None:
        if self.todo is None:
            return
        task = self.todo.find(task_id)
        if task is None:
            return
        pri = priority_short(task.priority)
        self.say(tr("pet.bulb_task", pri=pri, text=task.text), 5000)

    # ------------------------------------------------------------------ 尺寸
    @property
    def pet_size(self) -> int:
        return self._size

    def set_pet_size(self, width: int, *, save: bool = True) -> None:
        old_center = self.frameGeometry().center()
        self._apply_dimensions(width)
        self._layout_children()
        new_geo = self.frameGeometry()
        new_geo.moveCenter(old_center)
        screen = QGuiApplication.primaryScreen().availableGeometry()
        x = max(screen.left(), min(new_geo.x(), screen.right() - self._win_w))
        y = max(screen.top(), min(new_geo.y(), screen.bottom() - self._bulb_h - self._win_h))
        self.move(x, y)
        if save:
            self._save_size()
        self.size_changed.emit(self._size)

    def _save_size(self) -> None:
        self.config.set("pet_size", self._size)

    def _in_resize_zone(self, pos: QPoint) -> bool:
        return pos.x() >= self.width() - RESIZE_HANDLE and pos.y() >= self.height() - RESIZE_HANDLE

    # ------------------------------------------------------------------ 动画
    def set_state(self, state: str) -> None:
        self._state = state
        self._activity_enabled = state == "idle"
        self.animator.play(state)

    def play_once(self, name: str, then: str | None = None) -> None:
        self.animator.play_once(name, then=then or self._state)

    def set_activity_enabled(self, enabled: bool) -> None:
        self._activity_enabled = enabled

    def on_activity(self, kind: ActivityKind) -> None:
        if not self._activity_enabled or self._state != "idle":
            return
        self._activity_kind = kind
        anim = _ACTIVITY_ANIM.get(kind, "idle")
        if kind == ActivityKind.CLICKING:
            self.animator.play_once("wave", then="idle")
        else:
            self.animator.play(anim)

    def _idle_action(self) -> None:
        if self._state != "idle" or self._activity_kind != ActivityKind.IDLE:
            return
        choice = random.choice(["blink", "blink", "look", "talk"])
        self.animator.play_once(choice, then="idle")

    # ------------------------------------------------------------------ 位置
    def _restore_position(self) -> None:
        screen = QGuiApplication.primaryScreen().availableGeometry()
        x = self.config.get("pet_x")
        y = self.config.get("pet_y")
        total_h = self._bulb_h + self._win_h
        if x is None or y is None:
            x = screen.right() - self._win_w - 40
            y = screen.bottom() - total_h - 60
        x = max(screen.left(), min(int(x), screen.right() - self._win_w))
        y = max(screen.top(), min(int(y), screen.bottom() - total_h))
        self.move(int(x), int(y))

    def _save_position(self) -> None:
        self.config.update({"pet_x": self.x(), "pet_y": self.y()})

    def say(self, text: str, duration: int = 4000) -> None:
        top_center = self.mapToGlobal(QPoint(self.width() // 2 - 90, self._bulb_h))
        self.bubble.pop(text, top_center, duration)

    # ------------------------------------------------------------------ 鼠标
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            if self._in_resize_zone(pos):
                self._resizing = True
                self._resize_origin = event.globalPosition().toPoint()
                self._resize_start_size = self._size
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                self._moved = False
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = event.position().toPoint()
        if self._resizing and self._resize_origin is not None:
            delta = event.globalPosition().toPoint() - self._resize_origin
            self.set_pet_size(self._resize_start_size + max(delta.x(), delta.y()), save=False)
            self.bubble.hide()
            event.accept()
            return
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            self._moved = True
            self.bubble.hide()
            event.accept()
            return
        self.setCursor(Qt.SizeFDiagCursor if self._in_resize_zone(pos) else Qt.ArrowCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            if self._resizing:
                self._save_size()
                self.size_changed.emit(self._size)
                self._resizing = False
                self._resize_origin = None
                self.setCursor(Qt.ArrowCursor)
            elif self._moved:
                self._save_position()
            else:
                self.clicked.emit()
            self._drag_pos = None
            event.accept()

    def wheelEvent(self, event) -> None:  # noqa: N802
        if event.modifiers() & Qt.ControlModifier:
            step = 12 if event.angleDelta().y() > 0 else -12
            self.set_pet_size(self._size + step)
            event.accept()
            return
        super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.open_panel.emit()
        event.accept()

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#2b2622;color:#f1e9dc;border:1px solid #4a4138;"
            "font-family:'Microsoft YaHei UI';font-size:13px;padding:4px;}"
            "QMenu::item{padding:6px 24px;}"
            "QMenu::item:selected{background:#c88a3a;color:#2b2622;}"
        )
        menu.addAction(tr("pet.menu.open_panel"), self.open_panel.emit)
        menu.addSeparator()
        menu.addAction(tr("pet.menu.start_timer"), self.start_timer.emit)
        menu.addAction(tr("pet.menu.rest_now"), self.start_rest.emit)
        menu.addSeparator()
        menu.addAction(tr("pet.menu.zoom_in"), lambda: self.set_pet_size(self._size + 20))
        menu.addAction(tr("pet.menu.zoom_out"), lambda: self.set_pet_size(self._size - 20))
        menu.addSeparator()
        menu.addAction(tr("pet.menu.quit"), self.quit_requested.emit)
        menu.exec(event.globalPos())

    def closeEvent(self, event) -> None:  # noqa: N802
        self.bubble.hide()
        super().closeEvent(event)
