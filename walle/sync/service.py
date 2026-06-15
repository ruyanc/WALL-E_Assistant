"""同步服务：Qt 包装层（Windows / macOS 桌面端）。"""



from __future__ import annotations



import sys

import threading

from typing import TYPE_CHECKING



from PySide6.QtCore import QObject, QRunnable, QThread, QThreadPool, QTimer, Qt, Signal, Slot, QEventLoop



from ..config import SYNC_CONFIG_PATH, get_data_dir
from ..platform import is_desktop_sync_platform

from ..i18n import tr

from .backend import SyncBackendError
from .core import SyncCore

from .paths import SyncPaths

LOGOUT_SYNC_TIMEOUT_SEC = 5.0



if TYPE_CHECKING:

    from ..config import Config

    from ..notes_manager import NotesManager

    from ..reminder_manager import ReminderManager

    from ..todo_manager import TodoManager





class SyncService(QObject):

    sync_applied = Signal()

    assignments_changed = Signal()

    status_changed = Signal(str)

    login_finished = Signal(bool, str)

    config_saved = Signal(bool, str)

    sms_sent = Signal(bool, str)

    contacts_changed = Signal()

    assignment_event = Signal(str, object)

    sync_busy_changed = Signal(bool)

    sync_paused_changed = Signal(bool)

    assignment_action_finished = Signal(bool, str)

    _main_invoker = Signal(object)



    def __init__(

        self,

        config: "Config",

        todo: "TodoManager",

        notes: "NotesManager",

        reminders: "ReminderManager",

    ) -> None:

        super().__init__()

        self.config = config

        self.todo = todo

        self.notes = notes

        self.reminders = reminders



        paths = SyncPaths.from_data_dir(get_data_dir())

        self._core = SyncCore(

            paths=paths,

            config=config,

            todo=todo,

            notes=notes,

            reminders=reminders,

            tr=tr,

            enabled=is_desktop_sync_platform(),

            on_status=self._emit_status,

            on_sync_applied=self._emit_sync_applied,

            on_assignments_changed=self._emit_assignments_changed,

            on_login_finished=self._emit_login_finished,

            on_config_saved=self._emit_config_saved,

            on_assignment_event=self.assignment_event.emit,

        )



        self._debounce = QTimer(self)

        self._debounce.setSingleShot(True)

        self._debounce.setInterval(4000)

        self._debounce.timeout.connect(self.push_only)



        self._periodic = QTimer(self)

        self._periodic.setInterval(15 * 60 * 1000)

        self._periodic.timeout.connect(self.sync_now)

        self._assign_periodic = QTimer(self)
        self._assign_periodic.setInterval(2 * 60 * 1000)
        self._assign_periodic.timeout.connect(self.sync_assignments_only)

        self._thread_pool = QThreadPool.globalInstance()

        # 保护 SyncCore：后台同步线程与主线程的核心操作（登出/联系人/后端）互斥，
        # 配合 _sync_busy 保证同一时刻只有一个同步在跑，避免数据竞争。
        self._core_lock = threading.RLock()

        self._auth_busy = False

        self._auth_gen = 0

        self._session_gen = 0

        self._sync_busy = False

        self._sync_pending = False

        self._push_pending = False

        self._assign_sync_pending = False

        self._logout_pending = False

        self._main_invoker.connect(self._invoke_on_main, Qt.QueuedConnection)



    @Slot(object)
    def _invoke_on_main(self, fn) -> None:
        fn()

    def _run_on_main(self, fn) -> None:
        ui_thread = self.thread()
        if ui_thread is None or QThread.currentThread() is ui_thread:
            fn()
        else:
            self._main_invoker.emit(fn)



    def _emit_status(self, text: str) -> None:

        self._run_on_main(lambda t=text: self.status_changed.emit(t))



    def _emit_sync_applied(self) -> None:

        self._run_on_main(self.sync_applied.emit)



    def _emit_assignments_changed(self) -> None:

        self._run_on_main(self.assignments_changed.emit)



    def _emit_login_finished(self, ok: bool, msg: str) -> None:

        self._run_on_main(lambda o=ok, m=msg: self.login_finished.emit(o, m))



    def _emit_config_saved(self, ok: bool, msg: str) -> None:

        self._run_on_main(lambda o=ok, m=msg: self.config_saved.emit(o, m))



    def _start_auth(self, work) -> None:

        if self._auth_busy:

            self.status_changed.emit(tr("sync.status.logging_in"))

            return

        self._auth_busy = True

        self.status_changed.emit(tr("sync.status.logging_in"))

        service = self

        gen = self._auth_gen



        class AuthTask(QRunnable):

            def run(self) -> None:

                try:

                    ok, _msg = work()

                    if gen != service._auth_gen:

                        if service._core.is_logged_in:

                            service._core.auth.logout()

                        return

                    if ok:

                        service._run_on_main(service._after_login_success)

                except Exception as exc:

                    if gen == service._auth_gen:

                        service._emit_login_finished(

                            False, service.friendly_error(str(exc))

                        )

                finally:

                    if gen == service._auth_gen:

                        service._run_on_main(lambda: setattr(service, "_auth_busy", False))



        self._thread_pool.start(AuthTask())



    def _after_login_success(self) -> None:

        self._periodic.start()
        self._assign_periodic.start()
        if self.sync_paused:
            self._emit_status(tr("sync.status.paused"))
            return
        self.status_changed.emit(tr("sync.status.syncing"))

        QTimer.singleShot(0, self.sync_now)



    def _start_sms(self, work) -> None:

        service = self



        class SmsTask(QRunnable):

            def run(self) -> None:

                try:

                    ok, msg = work()

                except Exception as exc:

                    ok, msg = False, service.friendly_error(str(exc))

                service._run_on_main(

                    lambda o=ok, m=msg: (

                        service.sms_sent.emit(o, m),

                        service.status_changed.emit(m),

                    )

                )



        self._thread_pool.start(SmsTask())

    def _set_sync_busy(self, busy: bool) -> None:
        if self._sync_busy == busy:
            return
        self._sync_busy = busy
        self.sync_busy_changed.emit(busy)

    def _drain_pending_sync(self) -> None:
        if self._sync_pending:
            self._sync_pending = False
            self._push_pending = False
            self._assign_sync_pending = False
            self._start_sync()
        elif self._assign_sync_pending:
            self._assign_sync_pending = False
            self._start_assignments_sync()
        elif self._push_pending:
            self._push_pending = False
            self._start_push_only()

    def _start_push_only(self) -> None:
        if not self._core.enabled or not self._core.is_logged_in or self.sync_paused:
            return
        if self._sync_busy:
            self._push_pending = True
            return
        self._push_pending = False
        self._set_sync_busy(True)
        service = self
        gen = self._session_gen

        try:
            with service._core_lock:
                if gen != service._session_gen or not service._core.is_logged_in:
                    service._set_sync_busy(False)
                    return
                local, since = service._core.export_for_sync()
        except SyncBackendError as exc:
            service._emit_status(service.friendly_error(str(exc)))
            service._set_sync_busy(False)
            return
        except Exception as exc:
            service._emit_status(service.friendly_error(str(exc)))
            service._set_sync_busy(False)
            return

        captured_local = local
        captured_since = since

        class PushTask(QRunnable):
            def run(self) -> None:
                err_msg = ""
                pushed = 0
                needs_full = False
                max_pushed = captured_since
                try:
                    if gen != service._session_gen:
                        return
                    with service._core_lock:
                        if gen != service._session_gen or not service._core.is_logged_in:
                            return
                        pushed, needs_full, max_pushed = service._core.network_push_records(
                            captured_local, captured_since
                        )
                except SyncBackendError as exc:
                    err_msg = service.friendly_error(str(exc))
                except Exception as exc:
                    err_msg = service.friendly_error(str(exc))

                def finish() -> None:
                    try:
                        if gen != service._session_gen:
                            return
                        if err_msg:
                            service._emit_status(err_msg)
                            return
                        if needs_full:
                            with service._core_lock:
                                if gen == service._session_gen and service._core.is_logged_in:
                                    service._core.reset_sync_cursor()
                            service._sync_pending = True
                            return
                        if pushed > 0:
                            with service._core_lock:
                                if gen == service._session_gen and service._core.is_logged_in:
                                    service._core.advance_push_cursor(
                                        max_pushed, captured_since
                                    )
                            service._core._set_status(tr("sync.status.ok"))
                    finally:
                        service._set_sync_busy(False)
                        service._drain_pending_sync()

                service._run_on_main(finish)

        self._thread_pool.start(PushTask())

    def _start_assignments_sync(self) -> None:
        if not self._core.enabled or not self._core.is_logged_in or self.sync_paused:
            return
        if self._sync_busy:
            self._assign_sync_pending = True
            return
        self._assign_sync_pending = False
        self._set_sync_busy(True)
        service = self
        gen = self._session_gen

        class AssignSyncTask(QRunnable):
            def run(self) -> None:
                assign_rows: list = []
                assign_max = 0.0
                assign_since = 0.0
                old_status: dict = {}
                err_msg = ""
                try:
                    if gen != service._session_gen:
                        return
                    with service._core_lock:
                        if gen != service._session_gen or not service._core.is_logged_in:
                            return
                        assign_rows, assign_max, assign_since, old_status = (
                            service._core.network_fetch_assignments()
                        )
                except SyncBackendError as exc:
                    err_msg = service.friendly_error(str(exc))
                except Exception as exc:
                    err_msg = service.friendly_error(str(exc))

                def finish() -> None:
                    try:
                        if gen != service._session_gen:
                            return
                        if err_msg:
                            service._emit_status(err_msg)
                            return
                        with service._core_lock:
                            if gen != service._session_gen or not service._core.is_logged_in:
                                return
                            service._core.apply_assignment_fetch(
                                assign_rows, assign_max, assign_since, old_status
                            )
                    finally:
                        service._set_sync_busy(False)
                        service._drain_pending_sync()

                service._run_on_main(finish)

        self._thread_pool.start(AssignSyncTask())

    def _start_sync(self) -> None:
        if not self._core.enabled or not self._core.is_logged_in:
            return
        if self._sync_busy:
            self._sync_pending = True
            return
        self._sync_pending = False
        self._set_sync_busy(True)
        service = self
        gen = self._session_gen

        try:
            with service._core_lock:
                if gen != service._session_gen or not service._core.is_logged_in:
                    service._set_sync_busy(False)
                    return
                service._core._set_status(tr("sync.status.syncing"))
                local, since = service._core.export_for_sync()
        except SyncBackendError as exc:
            service._emit_status(service.friendly_error(str(exc)))
            service._set_sync_busy(False)
            return
        except Exception as exc:
            service._emit_status(service.friendly_error(str(exc)))
            service._set_sync_busy(False)
            return

        captured_local = local
        captured_since = since

        class SyncTask(QRunnable):
            def run(self) -> None:
                merged = None
                max_updated = captured_since
                apply_since = captured_since
                assign_rows: list = []
                assign_max = captured_since
                assign_since = 0.0
                old_status: dict = {}
                err_msg = ""
                try:
                    if gen != service._session_gen:
                        return
                    with service._core_lock:
                        if gen != service._session_gen or not service._core.is_logged_in:
                            return
                        merged, max_updated, pushed = service._core.network_sync_records(
                            captured_local, captured_since
                        )
                        if (
                            pushed == 0
                            and service._core.engine._has_local_sync_data(captured_local)
                            and captured_since > 0
                        ):
                            service._core.reset_sync_cursor()
                            merged, max_updated, pushed = service._core.network_sync_records(
                                captured_local, 0.0
                            )
                            apply_since = 0.0
                        assign_rows, assign_max, assign_since, old_status = (
                            service._core.network_fetch_assignments()
                        )
                except SyncBackendError as exc:
                    err_msg = service.friendly_error(str(exc))
                except Exception as exc:
                    err_msg = service.friendly_error(str(exc))

                def finish() -> None:
                    try:
                        if gen != service._session_gen:
                            return
                        if err_msg:
                            service._emit_status(err_msg)
                            return
                        with service._core_lock:
                            if gen != service._session_gen or not service._core.is_logged_in:
                                return
                            service._core.apply_sync_records(merged, max_updated, apply_since)
                            service._core.apply_assignment_fetch(
                                assign_rows, assign_max, assign_since, old_status
                            )
                            service._core._set_status(tr("sync.status.ok"))
                    finally:
                        service._set_sync_busy(False)
                        service._drain_pending_sync()

                service._run_on_main(finish)

        self._thread_pool.start(SyncTask())

    def _start_background(self, work, *, on_success=None) -> None:
        service = self
        gen = self._session_gen

        class BackgroundTask(QRunnable):
            def run(self) -> None:
                if gen != service._session_gen:
                    return
                ok, msg = True, ""
                try:
                    with service._core_lock:
                        if gen != service._session_gen:
                            return
                        work()
                except SyncBackendError as exc:
                    ok, msg = False, service.friendly_error(str(exc))
                except Exception as exc:
                    ok, msg = False, service.friendly_error(str(exc))
                if ok and on_success:
                    on_success()

                def finish(o: bool = ok, m: str = msg) -> None:
                    if not o:
                        service.status_changed.emit(m)
                    service.assignment_action_finished.emit(o, m)

                service._run_on_main(finish)

        self._thread_pool.start(BackgroundTask())

    @property

    def auth(self):

        return self._core.auth



    @property

    def assignments(self):

        return self._core.assignments



    @property

    def enabled(self) -> bool:

        return self._core.enabled



    @property

    def is_logged_in(self) -> bool:

        return self._core.is_logged_in



    @property

    def phone(self) -> str | None:

        return self._core.phone



    @property

    def email(self) -> str | None:

        return self._core.phone



    @property

    def backend_configured(self) -> bool:

        return self._core.backend_configured



    @property

    def user_cloudbase_env_id(self) -> str:

        return self._core.user_cloudbase_env_id



    @property

    def user_env_saved(self) -> bool:

        return self._core.user_env_saved



    @property

    def cloudbase_env_id(self) -> str:

        return self._core.cloudbase_env_id

    @property
    def env_mismatch(self) -> bool:
        return self._core.env_mismatch



    def reload_backend(self) -> None:

        with self._core_lock:
            self._core.reload_backend()



    def save_cloudbase_env_id(self, env_id: str) -> None:
        with self._core_lock:
            self._core.save_cloudbase_env_id(env_id)
        if self._core.is_logged_in and self._core.backend_configured and not self.sync_paused:
            self.sync_now()

    def start(self) -> None:
        with self._core_lock:
            self._core.start()
        if self._core.is_logged_in and self._core.backend_configured:
            self._periodic.start()
            self._assign_periodic.start()
            if not self.sync_paused:
                self.sync_now()
            else:
                self._emit_status(tr("sync.status.paused"))



    def schedule_push(self) -> None:

        if self._core.enabled and self._core.is_logged_in and not self.sync_paused:

            self._debounce.start()

    def push_only(self) -> None:
        if self.sync_paused:
            return
        self._start_push_only()

    def sync_assignments_only(self) -> None:
        if self.sync_paused:
            return
        self._start_assignments_sync()

    @property
    def sync_paused(self) -> bool:
        return bool(self.config.get("sync_paused"))

    def set_sync_paused(self, paused: bool) -> None:
        paused = bool(paused)
        if self.sync_paused == paused:
            return
        self.config.set("sync_paused", paused)
        self._debounce.stop()
        if paused:
            self._periodic.stop()
            self._assign_periodic.stop()
            self._push_pending = False
            self._assign_sync_pending = False
            if self._core.is_logged_in:
                self._emit_status(tr("sync.status.paused"))
        elif self._core.is_logged_in and self._core.backend_configured:
            self._periodic.start()
            self._assign_periodic.start()
            if not self._sync_busy:
                self._emit_status(self._core.status_text() or tr("sync.status.ok"))
        self.sync_paused_changed.emit(paused)

    def login(self, phone: str, password: str) -> None:

        self._start_auth(lambda: self._core.login(phone, password))

    def send_sms_code(self, phone: str) -> None:

        self._start_sms(lambda: self._core.send_sms_code(phone))

    def send_register_sms(self, phone: str) -> None:

        self._start_sms(lambda: self._core.send_register_sms(phone))

    def login_with_sms_code(self, phone: str, code: str) -> None:

        self._start_auth(lambda: self._core.login_with_sms_code(phone, code))

    def register(self, phone: str, password: str, code: str) -> None:

        self._start_auth(lambda: self._core.register(phone, password, code))



    def _finalize_logout(self) -> None:
        self._auth_gen += 1
        self._session_gen += 1
        self._auth_busy = False
        self._sync_pending = False
        self._push_pending = False
        self._assign_sync_pending = False
        self._logout_pending = False
        self._set_sync_busy(False)
        with self._core_lock:
            self._core.logout()
        self._periodic.stop()
        self._assign_periodic.stop()
        self._debounce.stop()
        self.status_changed.emit(self._core.status_text())
        self.assignments_changed.emit()

    def begin_logout(
        self,
        *,
        sync_timeout: float = LOGOUT_SYNC_TIMEOUT_SEC,
        on_finished=None,
    ) -> None:
        """尝试同步后退出；超过 sync_timeout 秒未完成同步也会立即退出。"""
        if self._logout_pending:
            return
        if not self._core.is_logged_in:
            if on_finished:
                self._run_on_main(on_finished)
            return

        self._logout_pending = True
        service = self
        gen = self._session_gen
        state = {"done": False}

        def finish() -> None:
            if state["done"]:
                return
            state["done"] = True
            service._finalize_logout()
            if on_finished:
                on_finished()

        try:
            with self._core_lock:
                if gen != self._session_gen or not self._core.is_logged_in:
                    finish()
                    return
                self._core._set_status(tr("sync.status.syncing"))
                local, since = self._core.export_for_sync()
        except Exception:
            finish()
            return

        captured_local = local
        captured_since = since

        class LogoutSyncTask(QRunnable):
            def run(self) -> None:
                merged = None
                max_updated = captured_since
                apply_since = captured_since
                assign_rows: list = []
                assign_max = captured_since
                assign_since = 0.0
                old_status: dict = {}
                try:
                    if gen != service._session_gen:
                        return
                    with service._core_lock:
                        if gen != service._session_gen or not service._core.is_logged_in:
                            return
                        merged, max_updated, pushed = service._core.network_sync_records(
                            captured_local, captured_since
                        )
                        if (
                            pushed == 0
                            and service._core.engine._has_local_sync_data(captured_local)
                            and captured_since > 0
                        ):
                            service._core.reset_sync_cursor()
                            merged, max_updated, pushed = service._core.network_sync_records(
                                captured_local, 0.0
                            )
                            apply_since = 0.0
                        assign_rows, assign_max, assign_since, old_status = (
                            service._core.network_fetch_assignments()
                        )
                except Exception:
                    pass

                def apply_and_finish() -> None:
                    if state["done"]:
                        return
                    if (
                        merged is not None
                        and gen == service._session_gen
                        and service._core.is_logged_in
                    ):
                        try:
                            with service._core_lock:
                                if gen != service._session_gen or not service._core.is_logged_in:
                                    finish()
                                    return
                                service._core.apply_sync_records(
                                    merged, max_updated, apply_since
                                )
                                service._core.apply_assignment_fetch(
                                    assign_rows, assign_max, assign_since, old_status
                                )
                        except Exception:
                            pass
                    finish()

                service._run_on_main(apply_and_finish)

        QTimer.singleShot(int(max(0.0, sync_timeout) * 1000), finish)
        self._thread_pool.start(LogoutSyncTask())

    def logout(self) -> None:
        """立即退出（不等待同步）。"""
        if self._core.is_logged_in:
            self._finalize_logout()
        else:
            self._logout_pending = False

    def shutdown_for_quit(self) -> None:
        """应用关闭：停止定时器与后台任务，本地登出，避免退出时长时间阻塞。"""
        self._debounce.stop()
        self._periodic.stop()
        self._assign_periodic.stop()
        self._push_pending = False
        self._assign_sync_pending = False
        self._sync_pending = False
        self._logout_pending = False
        self._auth_busy = False
        self._auth_gen += 1
        self._session_gen += 1
        self._set_sync_busy(False)
        if self._core.is_logged_in:
            self._finalize_logout()
        self._thread_pool.clear()

    def sync_now_blocking(self) -> tuple[bool, str]:
        """主线程阻塞同步（短时尽力推送）。"""
        if not self._core.enabled or not self._core.is_logged_in:
            return True, ""
        with self._core_lock:
            ok = self._core.sync_now()
            return ok, self._core.status_text()

    def wait_for_logout(self, *, sync_timeout: float = LOGOUT_SYNC_TIMEOUT_SEC) -> None:
        """阻塞直到退出流程结束（供需要同步后登出的场景；勿在 UI 退出路径调用）。"""
        if not self._core.is_logged_in:
            return
        loop = QEventLoop()

        def done() -> None:
            if loop.isRunning():
                loop.quit()

        self.begin_logout(sync_timeout=sync_timeout, on_finished=done)
        QTimer.singleShot(int(max(0.0, sync_timeout) * 1000) + 500, done)
        loop.exec()

    def sync_now(self) -> None:
        if self._sync_busy:
            self._sync_pending = True
            return
        self._start_sync()

    @property
    def sync_busy(self) -> bool:
        return self._sync_busy



    def friendly_error(self, msg: str) -> str:

        return self._core.friendly_error(msg)

    def accept_assignment(self, assignment_id: str) -> None:
        self._start_background(
            lambda: self._core.accept_assignment(assignment_id),
        )

    def reject_assignment(self, assignment_id: str, note: str = "") -> None:
        self._start_background(
            lambda: self._core.reject_assignment(assignment_id, note),
        )

    def complete_assignment(self, assignment_id: str) -> None:
        self._start_background(
            lambda: self._core.complete_assignment(assignment_id),
        )

    def cancel_assignment(self, assignment_id: str, note: str = "") -> None:
        self._start_background(
            lambda: self._core.cancel_assignment(assignment_id, note),
        )

    @property

    def contacts(self):

        return self._core.contacts



    def set_contact_nickname(self, phone: str, nickname: str) -> None:

        with self._core_lock:

            self._core.set_contact_nickname(phone, nickname)

        self.contacts_changed.emit()

        if hasattr(self, "assignments_changed"):

            self.assignments_changed.emit()



    def remove_contact(self, phone: str) -> None:

        with self._core_lock:

            self._core.remove_contact(phone)

        self.contacts_changed.emit()

        if hasattr(self, "assignments_changed"):

            self.assignments_changed.emit()



    def contact_display_name(self, phone: str) -> str:

        return self._core.contacts.display_name(phone)



    def dispatch_assignment(
        self,
        recipient: str,
        title: str,
        *,
        priority: int,
        description: str = "",
    ) -> None:
        self._start_background(
            lambda: self._core.dispatch_assignment(
                recipient, title, priority=priority, description=description
            ),
            on_success=self._emit_assignments_changed,
        )

    def status_text(self) -> str:

        return self._core.status_text()


