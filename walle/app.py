"""WALL-E 桌面宠物 主应用：整合所有组件并连接信号。"""

from __future__ import annotations

import sys

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .activity_monitor import ActivityMonitor
from .config import Config
from .i18n import init_language, on_language_changed, set_language, tr
from .control_panel import ControlPanel
from .notes_manager import NotesManager
from .pet_window import PetWindow
from .pomodoro import PomodoroState, PomodoroTimer
from .reminder_manager import ReminderManager
from .rest_overlay import RestOverlay
from .todo_manager import TodoManager
from .walle_sprite import render_walle


class WalleApp(QObject):
    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app = app
        self.config = Config()
        init_language(self.config.get("language"))
        self.todo = TodoManager()
        self.notes = NotesManager()
        self.reminders = ReminderManager()
        self.timer = PomodoroTimer()
        self.timer.configure(
            self.config.get("work_minutes"),
            self.config.get("rest_minutes"),
            self.config.get("cycles"),
        )
        self.activity = ActivityMonitor()

        self.pet = PetWindow(self.config, self.todo)
        self.panel = ControlPanel(self.config, self.todo, self.notes, self.reminders, self.timer)
        self.overlay = RestOverlay()

        self._build_tray()
        self._connect()

        on_language_changed(self._retranslate_ui)
        self.pet.show()
        self.pet.say(tr("pet.welcome"), 5000)

    def _build_tray(self) -> None:
        icon = QIcon(render_walle(64, state="idle"))
        if hasattr(self, "tray"):
            self.tray.hide()
        self.tray = QSystemTrayIcon(icon, self.app)
        self.tray.setToolTip(tr("app.name"))

        menu = QMenu()
        menu.addAction(tr("tray.open_panel"), self._show_panel)
        menu.addAction(tr("tray.toggle_pet"), self._toggle_pet)
        menu.addSeparator()
        menu.addAction(tr("tray.start_timer"), self._start_timer)
        menu.addAction(tr("tray.rest_now"), self._start_rest)
        menu.addAction(tr("tray.stop_timer"), self.timer.stop)
        menu.addSeparator()
        quit_action = QAction(tr("tray.quit"), self)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _retranslate_ui(self) -> None:
        self._build_tray()
        self.panel.retranslate_ui()
        self.overlay.retranslate_ui()
        self.app.setApplicationName(tr("app.name"))

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self._show_panel()

    def _connect(self) -> None:
        self.pet.clicked.connect(self._show_panel)
        self.pet.open_panel.connect(self._show_panel)
        self.pet.start_timer.connect(self._start_timer)
        self.pet.start_rest.connect(self._start_rest)
        self.pet.quit_requested.connect(self.quit)

        self.panel.start_timer_requested.connect(self._start_timer)
        self.panel.start_rest_requested.connect(self._start_rest)
        self.panel.end_rest_requested.connect(self._end_rest)

        self.timer.rest_started.connect(self._on_rest_started)
        self.timer.rest_approaching.connect(self._on_rest_approaching)
        self.timer.rest_ended.connect(self._on_rest_ended)
        self.timer.work_started.connect(self._on_work_started)
        self.timer.finished.connect(self._on_finished)
        self.timer.tick.connect(self._on_tick)

        self.overlay.end_rest_clicked.connect(self._end_rest)

        self.panel.pet_size_changed.connect(lambda s: self.pet.set_pet_size(s, save=True))
        self.pet.size_changed.connect(self.panel.set_pet_size_display)

        self.todo.changed.connect(self._on_todo_changed)
        self.reminders.due.connect(self._on_reminder_due)
        self.activity.activity_changed.connect(self.pet.on_activity)

        self.timer.state_changed.connect(self._sync_activity_mode)

    def _sync_activity_mode(self, state: PomodoroState) -> None:
        self.pet.set_activity_enabled(state != PomodoroState.RESTING)

    def _show_panel(self) -> None:
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

    def _toggle_pet(self) -> None:
        self.pet.setVisible(not self.pet.isVisible())

    def _start_timer(self) -> None:
        self.timer.start()
        self.pet.say(tr("pet.start_focus"))

    def _start_rest(self) -> None:
        self.timer.start_rest_now()

    def _end_rest(self) -> None:
        self.timer.end_rest_now()

    def _on_work_started(self, cycle: int, total: int) -> None:
        self.pet.set_state("idle")
        self.pet.set_activity_enabled(True)
        self.pet.say(tr("pet.work_start", cycle=cycle, total=total))

    def _on_rest_approaching(self) -> None:
        self.pet.say(tr("pet.rest_soon"), 6000)
        self.pet.play_once("talk", then="idle")

    def _on_rest_started(self, seconds: int) -> None:
        self.pet.set_state("rest")
        self.pet.set_activity_enabled(False)
        if self.config.get("rest_sound"):
            self.app.beep()
        self.overlay.show_overlay(seconds)

    def _on_rest_ended(self) -> None:
        self.overlay.hide_overlay()
        self.pet.set_state("idle")
        self.pet.set_activity_enabled(True)

    def _on_finished(self) -> None:
        self.overlay.hide_overlay()
        self.pet.set_state("happy")
        self.pet.set_activity_enabled(False)
        self.pet.say(tr("pet.all_done"), 6000)
        self.tray.showMessage(
            tr("app.name"), tr("pet.tray_all_done"),
            QSystemTrayIcon.Information, 4000,
        )

    def _on_tick(self, remaining, state, cycle, total) -> None:
        if state == PomodoroState.RESTING and self.overlay.isVisible():
            self.overlay.update_countdown(remaining)

    def _on_todo_changed(self) -> None:
        self.pet.refresh_bulbs()
        if self.timer.state != PomodoroState.RESTING and self.pet.isVisible():
            self.pet.play_once("cheer", then="idle")

    def _on_reminder_due(self, text: str, _rid: int) -> None:
        self.pet.say(tr("pet.reminder", text=text), 8000)
        self.pet.play_once("wave", then="idle")
        if self.config.get("rest_sound"):
            self.app.beep()
        self.tray.showMessage(tr("app.name"), tr("pet.tray_reminder", text=text), QSystemTrayIcon.Information, 5000)

    def quit(self) -> None:
        self.config.save()
        self.todo.save()
        self.notes.save()
        self.reminders.save()
        self.overlay.hide_overlay()
        self.tray.hide()
        self.app.quit()


def main() -> int:
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("WALL-E.DesktopPet")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("WALL-E")
    app.setQuitOnLastWindowClosed(False)

    walle = WalleApp(app)
    _ = walle
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
