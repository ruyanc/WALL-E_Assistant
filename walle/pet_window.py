"""桌面悬浮宠物窗口。

无边框、置顶、背景透明，显示 WALL-E 形象。支持：
    - 鼠标拖动移动位置（自动记忆）
    - 定时眨眼动画
    - 单击弹出/隐藏控制面板
    - 右键菜单（开始番茄钟、立即休息、设置、退出等）
    - 气泡消息提示
"""

from __future__ import annotations

import random

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import QLabel, QMenu, QVBoxLayout, QWidget

from .animator import SpriteAnimator
from .config import Config


class SpeechBubble(QWidget):
    """宠物头顶的气泡提示。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        self.label = QLabel("")
        self.label.setWordWrap(True)
        self.label.setFont(QFont("", 10))
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
    """桌面上的 WALL-E。"""

    clicked = Signal()
    open_panel = Signal()
    start_timer = Signal()
    start_rest = Signal()
    quit_requested = Signal()

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._size = int(config.get("pet_size", 160))
        # 帧为竖向比例(179x201)，窗口高度略大于宽度
        self._win_w = self._size
        self._win_h = int(self._size * 201 / 179)
        self.resize(self._win_w, self._win_h)

        self.label = QLabel(self)
        self.label.setGeometry(0, 0, self._win_w, self._win_h)
        self.label.setAlignment(Qt.AlignCenter)

        self.bubble = SpeechBubble()

        self._state = "idle"
        self.animator = SpriteAnimator(self.label, size=self._win_h)
        self.animator.play("idle")

        self._drag_pos: QPoint | None = None
        self._moved = False

        # 闲置时随机做点小动作（眨眼/张望），更生动
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._idle_action)
        self._idle_timer.start(6000)

        self._restore_position()

    # ------------------------------------------------------------------ 动画
    def set_state(self, state: str) -> None:
        """切换到某个持续状态动画（idle/rest/sleep/happy/love/tired...）。"""
        self._state = state
        self.animator.play(state)

    def play_once(self, name: str, then: str | None = None) -> None:
        self.animator.play_once(name, then=then or self._state)

    def _idle_action(self) -> None:
        # 仅在普通待机时插入随机小动作
        if self._state != "idle":
            return
        choice = random.choice(["blink", "blink", "look", "talk"])
        self.animator.play_once(choice, then="idle")

    # ------------------------------------------------------------------ 位置
    def _restore_position(self) -> None:
        screen = QGuiApplication.primaryScreen().availableGeometry()
        x = self.config.get("pet_x")
        y = self.config.get("pet_y")
        if x is None or y is None:
            x = screen.right() - self._win_w - 40
            y = screen.bottom() - self._win_h - 60
        # 防止移出屏幕
        x = max(screen.left(), min(int(x), screen.right() - self._win_w))
        y = max(screen.top(), min(int(y), screen.bottom() - self._win_h))
        self.move(int(x), int(y))

    def _save_position(self) -> None:
        self.config.update({"pet_x": self.x(), "pet_y": self.y()})

    # ------------------------------------------------------------------ 气泡
    def say(self, text: str, duration: int = 4000) -> None:
        top_center = self.mapToGlobal(QPoint(self.width() // 2 - 90, 0))
        self.bubble.pop(text, top_center, duration)

    # ------------------------------------------------------------------ 鼠标
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._moved = False
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            self._moved = True
            self.bubble.hide()
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            if self._moved:
                self._save_position()
            else:
                self.clicked.emit()
            self._drag_pos = None
            event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.open_panel.emit()
        event.accept()

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#2b2622;color:#f1e9dc;border:1px solid #4a4138;}"
            "QMenu::item:selected{background:#c88a3a;color:#2b2622;}"
        )
        menu.addAction("打开控制台", self.open_panel.emit)
        menu.addSeparator()
        menu.addAction("▶ 开始番茄钟", self.start_timer.emit)
        menu.addAction("☕ 立即休息", self.start_rest.emit)
        menu.addSeparator()
        menu.addAction("退出", self.quit_requested.emit)
        menu.exec(event.globalPos())

    def closeEvent(self, event) -> None:  # noqa: N802
        self.bubble.hide()
        super().closeEvent(event)
