"""WALL-E 桌面宠物 主应用：整合所有组件并连接信号。"""

from __future__ import annotations

import sys

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .activity_monitor import ActivityMonitor
from .config import Config
from .icon_util import app_icon
from .i18n import init_language, on_language_changed, set_language, tr
from .control_panel import ControlPanel
from .notes_manager import NotesManager
from .pet_window import PetWindow
from .platform import is_desktop_sync_platform
from .pomodoro import PomodoroState, PomodoroTimer
from .reminder_manager import ReminderManager
from .rest_overlay import RestOverlay
from .sync.assignment_events import EVENT_COMPLETED
from .sync.assignment_notify import assignment_notify_messages
from .sync.service import SyncService
from .todo_manager import TodoManager


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
        self._quitting = False

        self.sync: SyncService | None = None
        if is_desktop_sync_platform():
            self.sync = SyncService(self.config, self.todo, self.notes, self.reminders)

        self.pet = PetWindow(self.config, self.todo)
        self.panel = ControlPanel(
            self.config, self.todo, self.notes, self.reminders, self.timer, sync=self.sync
        )
        self.overlay = RestOverlay()

        icon = app_icon()
        self.panel.setWindowIcon(icon)
        self.overlay.setWindowIcon(icon)

        self._build_tray()
        self._connect()

        on_language_changed(self._retranslate_ui)
        self.pet.show()
        self.pet.say(tr("pet.welcome"), 5000)

        if self.sync:
            self.sync.start()
            self.sync.sync_applied.connect(self._on_sync_applied)
            self.sync.assignment_event.connect(self._on_assignment_event)
            self.todo.changed.connect(self.sync.schedule_push)
            self.notes.changed.connect(self.sync.schedule_push)
            self.reminders.changed.connect(self.sync.schedule_push)
            self.panel.settings_applied.connect(self.sync.schedule_push)
            self._refresh_assignment_badges()

    def _build_tray(self) -> None:
        icon = app_icon()
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
        self.pet.navigate_assign.connect(self._show_assign_subtab)
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

        if self.sync:
            self.sync.assignments_changed.connect(self._refresh_assignment_badges)

    def _refresh_assignment_badges(self) -> None:
        if not self.sync or not self.sync.is_logged_in:
            self.pet.refresh_assignment_badges([], [], 0, 0)
            return
        inbox_priorities = self.sync.assignments.accepted_inbox_priorities()
        outbox_priorities = self.sync.assignments.accepted_outbox_priorities()
        inbox_count = len(inbox_priorities)
        outbox_count = len(outbox_priorities)
        inbox_tip = tr("pet.badge.inbox.tip", count=inbox_count) if inbox_count else ""
        outbox_tip = tr("pet.badge.outbox.tip", count=outbox_count) if outbox_count else ""
        self.pet.refresh_assignment_badges(
            inbox_priorities,
            outbox_priorities,
            inbox_count,
            outbox_count,
            inbox_tooltip=inbox_tip,
            outbox_tooltip=outbox_tip,
        )

    def _sync_activity_mode(self, state: PomodoroState) -> None:
        self.pet.set_activity_enabled(state != PomodoroState.RESTING)

    def _show_panel(self) -> None:
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()
        if self.sync and self.sync.is_logged_in and not self.sync.sync_paused:
            self.sync.sync_assignments_only()
        if self.pet.isVisible():
            self.pet.raise_to_front()

    def _show_assign_subtab(self, role: str) -> None:
        self.panel.show_assign_focus(role)
        self.panel.raise_()
        self.panel.activateWindow()
        if self.sync and self.sync.is_logged_in and not self.sync.sync_paused:
            self.sync.sync_assignments_only()
        if self.pet.isVisible():
            self.pet.raise_to_front()

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

    def _on_sync_applied(self) -> None:
        self.pet.refresh_bulbs()
        self._refresh_assignment_badges()
        self.panel.flush_all_lists()

    def _on_assignment_event(self, kind: str, assignment) -> None:
        if not self.sync or not self.sync.auth.session:
            return
        user_id = self.sync.auth.session.user_id
        messages = assignment_notify_messages(
            kind,
            assignment,
            user_id=user_id,
            display_name=self.sync.contact_display_name,
            tr=tr,
        )
        for i, text in enumerate(messages):
            duration = 8000 if i == 0 else 6000
            self.pet.say(text, duration)
            if kind == EVENT_COMPLETED:
                self.pet.play_once("cheer", then="idle")
            else:
                self.pet.play_once("talk", then="idle")
        if messages and hasattr(self.panel, "assign_inbox_scroll"):
            self.panel.refresh_assignments()
        self._refresh_assignment_badges()

    def _on_reminder_due(self, text: str, _rid: int) -> None:
        self.pet.say(tr("pet.reminder", text=text), 8000)
        self.pet.play_once("wave", then="idle")
        if self.config.get("rest_sound"):
            self.app.beep()
        self.tray.showMessage(tr("app.name"), tr("pet.tray_reminder", text=text), QSystemTrayIcon.Information, 5000)

    def quit(self) -> None:
        if self._quitting:
            return
        self._quitting = True

        self.timer.stop()
        if hasattr(self.activity, "_timer"):
            self.activity._timer.stop()
        if hasattr(self.reminders, "_timer"):
            self.reminders._timer.stop()
        if self.sync:
            self.sync.shutdown_for_quit()

        self.config.save()
        self.todo.save()
        self.notes.save()
        self.reminders.save()

        self.overlay.hide_overlay()
        self.tray.hide()
        self.pet.close()
        self.panel.close()
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
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)

    walle = WalleApp(app)
    _ = walle
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
