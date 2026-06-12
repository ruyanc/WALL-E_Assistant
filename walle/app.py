"""WALL-E 桌面宠物 主应用：整合所有组件并连接信号。"""

from __future__ import annotations

import sys

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import APP_NAME
from .config import Config
from .control_panel import ControlPanel
from .pet_window import PetWindow
from .pomodoro import PomodoroState, PomodoroTimer
from .rest_overlay import RestOverlay
from .todo_manager import TodoManager
from .walle_sprite import render_walle


class WalleApp(QObject):
    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app = app
        self.config = Config()
        self.todo = TodoManager()
        self.timer = PomodoroTimer()
        self.timer.configure(
            self.config.get("work_minutes"),
            self.config.get("rest_minutes"),
            self.config.get("cycles"),
        )

        self.pet = PetWindow(self.config)
        self.panel = ControlPanel(self.config, self.todo, self.timer)
        self.overlay = RestOverlay()

        self._build_tray()
        self._connect()

        self.pet.show()
        self.pet.say("哇—力！点我打开控制台～", 5000)

    # ------------------------------------------------------------------ 托盘
    def _build_tray(self) -> None:
        icon = QIcon(render_walle(64, state="idle"))
        self.tray = QSystemTrayIcon(icon, self.app)
        self.tray.setToolTip(APP_NAME)

        menu = QMenu()
        menu.addAction("打开控制台", self._show_panel)
        menu.addAction("显示/隐藏宠物", self._toggle_pet)
        menu.addSeparator()
        menu.addAction("▶ 开始番茄钟", self._start_timer)
        menu.addAction("☕ 立即休息", self._start_rest)
        menu.addAction("■ 停止计时", self.timer.stop)
        menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:  # 单击
            self._show_panel()

    # ------------------------------------------------------------------ 信号
    def _connect(self) -> None:
        # 宠物交互
        self.pet.clicked.connect(self._show_panel)
        self.pet.open_panel.connect(self._show_panel)
        self.pet.start_timer.connect(self._start_timer)
        self.pet.start_rest.connect(self._start_rest)
        self.pet.quit_requested.connect(self.quit)

        # 控制面板
        self.panel.start_timer_requested.connect(self._start_timer)
        self.panel.start_rest_requested.connect(self._start_rest)
        self.panel.end_rest_requested.connect(self._end_rest)

        # 番茄钟
        self.timer.rest_started.connect(self._on_rest_started)
        self.timer.rest_ended.connect(self._on_rest_ended)
        self.timer.work_started.connect(self._on_work_started)
        self.timer.finished.connect(self._on_finished)
        self.timer.tick.connect(self._on_tick)

        # 休息覆盖层
        self.overlay.end_rest_clicked.connect(self._end_rest)

        # 聊天表情
        self.panel.emote_requested.connect(self._on_emote)

        # 待办完成时宠物开心
        self.todo.changed.connect(self._on_todo_changed)

    # ------------------------------------------------------------------ 动作
    def _show_panel(self) -> None:
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

    def _toggle_pet(self) -> None:
        self.pet.setVisible(not self.pet.isVisible())

    def _start_timer(self) -> None:
        self.timer.start()
        self.pet.say("开始专注！瓦力陪你一起努力 ⏱️")

    def _start_rest(self) -> None:
        self.timer.start_rest_now()

    def _end_rest(self) -> None:
        self.timer.end_rest_now()

    def _on_emote(self, name: str) -> None:
        """聊天触发的表情：休息状态下不打断，其余播一次后回到待机。"""
        if self.timer.state == PomodoroState.RESTING:
            return
        loop_states = {"rest", "tired", "love", "sleep"}
        if name in loop_states:
            self.pet.set_state(name)
        else:
            self.pet.play_once(name, then="idle")

    # ------------------------------------------------------------------ 计时回调
    def _on_work_started(self, cycle: int, total: int) -> None:
        self.pet.set_state("idle")
        self.pet.say(f"第 {cycle}/{total} 轮专注开始，加油！💪")

    def _on_rest_started(self, seconds: int) -> None:
        self.pet.set_state("rest")
        if self.config.get("rest_sound"):
            self.app.beep()
        self.overlay.show_overlay(seconds)

    def _on_rest_ended(self) -> None:
        self.overlay.hide_overlay()
        self.pet.set_state("idle")

    def _on_finished(self) -> None:
        self.overlay.hide_overlay()
        self.pet.set_state("happy")
        self.pet.say("全部完成啦，你真棒！🎉 记得好好休息～", 6000)
        self.tray.showMessage(APP_NAME, "番茄钟全部完成，干得漂亮！🎉",
                              QSystemTrayIcon.Information, 4000)

    def _on_tick(self, remaining, state, cycle, total) -> None:
        if state == PomodoroState.RESTING and self.overlay.isVisible():
            self.overlay.update_countdown(remaining)

    def _on_todo_changed(self) -> None:
        # 刚有任务被划掉时，宠物欢呼一下（休息中不打断）
        if self.timer.state != PomodoroState.RESTING and self.pet.isVisible():
            self.pet.play_once("cheer", then="idle")

    # ------------------------------------------------------------------ 退出
    def quit(self) -> None:
        self.config.save()
        self.todo.save()
        self.overlay.hide_overlay()
        self.tray.hide()
        self.app.quit()


def main() -> int:
    # 让任务栏正确归组与显示图标（Windows）
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("WALL-E.DesktopPet")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)  # 关闭面板不退出，仍驻留托盘

    if not QSystemTrayIcon.isSystemTrayAvailable():
        # 没有托盘也能跑，只是少了托盘菜单
        pass

    walle = WalleApp(app)
    _ = walle  # 保持引用
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
