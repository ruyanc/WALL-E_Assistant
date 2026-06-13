"""休息全屏提醒覆盖层。

休息开始时，半透明覆盖整个屏幕，WALL-E 形象放大居中显示并提示休息，
显示倒计时；用户可点击「提前结束休息」按钮立即退出。倒计时结束后自动退出。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .animator import SpriteAnimator
from .i18n import on_language_changed, rest_tips, tr
from .pomodoro import PomodoroTimer


class RestOverlay(QWidget):
    """覆盖全屏的休息提醒。"""

    end_rest_clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._tip_index = 0

        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)
        root.setSpacing(18)

        self.sprite_label = QLabel()
        self.sprite_label.setAttribute(Qt.WA_TranslucentBackground, True)
        self.sprite_label.setStyleSheet("background: transparent;")
        self.sprite_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.sprite_label, 0, Qt.AlignCenter)

        self.title = QLabel(tr("rest.title"))
        tf = QFont()
        tf.setPointSize(34)
        tf.setBold(True)
        self.title.setFont(tf)
        self.title.setStyleSheet("color:#f4ead4;")
        self.title.setAlignment(Qt.AlignCenter)
        root.addWidget(self.title)

        self.tip = QLabel(rest_tips()[0])
        tipf = QFont()
        tipf.setPointSize(16)
        self.tip.setFont(tipf)
        self.tip.setStyleSheet("color:#d8cbb6;")
        self.tip.setAlignment(Qt.AlignCenter)
        root.addWidget(self.tip)

        self.countdown = QLabel("10:00")
        cf = QFont("Consolas")
        cf.setPointSize(56)
        cf.setBold(True)
        self.countdown.setFont(cf)
        self.countdown.setStyleSheet("color:#c88a3a;")
        self.countdown.setAlignment(Qt.AlignCenter)
        root.addWidget(self.countdown)

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)
        self.btn_end = QPushButton(tr("rest.end_btn"))
        self.btn_end.setStyleSheet(
            "QPushButton{background:#c88a3a;color:#2b2622;border:none;"
            "border-radius:10px;padding:14px 28px;font-size:16px;font-weight:bold;}"
            "QPushButton:hover{background:#dd9c46;}"
        )
        self.btn_end.clicked.connect(self.end_rest_clicked.emit)
        btn_row.addWidget(self.btn_end)
        root.addLayout(btn_row)

        # 提示语轮播
        self._tip_timer = QTimer(self)
        self._tip_timer.setInterval(5000)
        self._tip_timer.timeout.connect(self._rotate_tip)

        # 动画播放器（尺寸在 show_overlay 时根据屏幕设置）
        self.animator = SpriteAnimator(self.sprite_label, size=240)
        on_language_changed(self.retranslate_ui)

    def _tips(self) -> list[str]:
        return rest_tips()

    def retranslate_ui(self) -> None:
        self.title.setText(tr("rest.title"))
        self.btn_end.setText(tr("rest.end_btn"))
        tips = self._tips()
        if tips:
            self._tip_index = min(self._tip_index, len(tips) - 1)
            self.tip.setText(tips[self._tip_index])

    def _rotate_tip(self) -> None:
        tips = self._tips()
        if not tips:
            return
        self._tip_index = (self._tip_index + 1) % len(tips)
        self.tip.setText(tips[self._tip_index])

    def show_overlay(self, total_seconds: int) -> None:
        screen = QGuiApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        # 放大的瓦力：取屏幕较短边的 42%
        sprite_size = int(min(screen.width(), screen.height()) * 0.42)
        self.animator.set_size(sprite_size)
        self.animator.play("rest")
        self.update_countdown(total_seconds)
        self._tip_timer.start()
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def hide_overlay(self) -> None:
        self._tip_timer.stop()
        self.animator.stop()
        self.hide()

    def update_countdown(self, seconds: int) -> None:
        self.countdown.setText(PomodoroTimer.format_time(seconds))

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QColor, QPainter

        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(20, 17, 14, 235))
        super().paintEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        # 按 Esc 也可提前结束休息
        if event.key() == Qt.Key_Escape:
            self.end_rest_clicked.emit()
        else:
            super().keyPressEvent(event)
