"""移动端 CloudBase 同步服务（Kivy）。"""

from __future__ import annotations

import queue
import sys
import threading
from pathlib import Path
from typing import Any, Callable

from kivy.clock import Clock

_MOBILE = Path(__file__).resolve().parent
if str(_MOBILE) not in sys.path:
    sys.path.insert(0, str(_MOBILE))

from walle.sync.backend import SyncBackendError
from walle.sync.core import SyncCore
from walle.sync.paths import SyncPaths

from storage import data_dir
from sync_text import tr


class MobileSyncService:
  def __init__(
      self,
      settings,
      todo,
      notes,
      reminders,
      *,
      on_status: Callable[[str], None] | None = None,
      on_data_changed: Callable[[], None] | None = None,
      on_assignment_event: Callable[[str, object], None] | None = None,
  ) -> None:
      self.settings = settings
      self.todo = todo
      self.notes = notes
      self.reminders = reminders
      self._on_data_changed_cb = on_data_changed or (lambda: None)
      self._on_assignment_event_cb = on_assignment_event or (lambda _k, _a: None)
      self._on_status_cb = on_status
      self._status = tr("sync.status.offline")
      self._core_lock = threading.RLock()
      self._init_lock = threading.Lock()
      self._work_queue: queue.Queue = queue.Queue()
      self._core: SyncCore | None = None
      self._worker: threading.Thread | None = None
      self._tick_ev = None

  def _lazy_init(self) -> None:
      if self._core is not None:
          return
      with self._init_lock:
          if self._core is not None:
              return
          paths = SyncPaths.from_data_dir(data_dir())
          self._core = SyncCore(
              paths=paths,
              config=self.settings,
              todo=self.todo,
              notes=self.notes,
              reminders=self.reminders,
              tr=tr,
              enabled=True,
              on_status=lambda t: self._schedule_ui(self._emit_status, t),
              on_sync_applied=lambda: self._schedule_ui(self._on_data_changed_cb),
              on_assignments_changed=lambda: self._schedule_ui(self._on_data_changed_cb),
              on_login_finished=lambda ok, m: self._schedule_ui(self._on_login_finished_ui, ok, m),
              on_config_saved=lambda ok, m: self._schedule_ui(self._on_config_saved_ui, ok, m),
              on_assignment_event=lambda k, a: self._schedule_ui(self._on_assignment_event_cb, k, a),
          )
          self._emit_status(self._core.status_text())
          self._worker = threading.Thread(target=self._worker_loop, name="walle-sync", daemon=True)
          self._worker.start()
          self._tick_ev = Clock.schedule_interval(self._schedule_tick, 1.0)

  def _schedule_ui(self, fn: Callable[..., None], *args, **kwargs) -> None:
      def run(_dt: float) -> None:
          fn(*args, **kwargs)

      Clock.schedule_once(run, 0)

  def _worker_loop(self) -> None:
      while True:
          item = self._work_queue.get()
          if item is None:
              break
          fn, on_done = item
          try:
              self._lazy_init()
              with self._core_lock:
                  result = fn()
          except Exception as exc:
              result = exc
          if on_done is not None:
              Clock.schedule_once(lambda _dt, r=result: on_done(r), 0)
          self._work_queue.task_done()

  def _submit(self, fn: Callable[[], Any], on_done: Callable[[Any], None] | None = None) -> None:
      self._work_queue.put((fn, on_done))

  def flush(self, timeout: float = 15.0) -> None:
      import time

      self._lazy_init()
      deadline = time.time() + timeout
      while time.time() < deadline:
          if self._work_queue.unfinished_tasks == 0:
              time.sleep(0.05)
              if self._work_queue.unfinished_tasks == 0:
                  return
          time.sleep(0.02)

  def _schedule_tick(self, _dt: float) -> None:
      if self.sync_paused or self._core is None:
          return
      self._submit(lambda: self._core.tick())

  def _emit_status(self, text: str) -> None:
      self._status = text
      if self._on_status_cb:
          self._on_status_cb(text)

  def _on_login_finished_ui(self, ok: bool, message: str) -> None:
      self._emit_status(message)
      if ok:
          self._on_data_changed_cb()

  def _on_config_saved_ui(self, ok: bool, message: str) -> None:
      self._emit_status(message)

  @property
  def assignments(self):
      self._lazy_init()
      return self._core.assignments

  @property
  def contacts(self):
      self._lazy_init()
      return self._core.contacts

  @property
  def is_logged_in(self) -> bool:
      if self._core is None:
          return False
      return self._core.is_logged_in

  @property
  def backend_configured(self) -> bool:
      if self._core is None:
          return bool(str(self.settings.get("cloudbase_env_id", "") or "").strip())
      return self._core.backend_configured

  @property
  def cloudbase_env_id(self) -> str:
      if self._core is None:
          return str(self.settings.get("cloudbase_env_id", "") or "")
      return self._core.cloudbase_env_id

  @property
  def phone(self) -> str | None:
      if self._core is None:
          return None
      return self._core.phone

  @property
  def user_id(self) -> str:
      if self._core is None:
          return ""
      session = self._core.auth.session
      return str(session.user_id).strip() if session else ""

  @property
  def sync_paused(self) -> bool:
      return bool(self.settings.get("sync_paused", False))

  def set_sync_paused(self, paused: bool) -> None:
      if self.sync_paused == paused:
          return
      self.settings.set("sync_paused", paused)

  def contact_display_name(self, phone: str) -> str:
      self._lazy_init()
      return self._core.contacts.display_name(phone)

  def set_contact_nickname(self, phone: str, nickname: str) -> None:
      self._lazy_init()
      self._core.contacts.set_contact(phone, nickname)

  def remove_contact(self, phone: str) -> None:
      self._lazy_init()
      self._core.contacts.remove_contact(phone)

  def status_text(self) -> str:
      if self._core is None:
          return self._status
      return self._status or self._core.status_text()

  def start(self) -> None:
      self._lazy_init()
      self._core.start()

  def schedule_push(self) -> None:
      if self._core is None:
          return
      self._core.schedule_push()

  def save_cloudbase_env_id(self, env_id: str) -> None:
      self._lazy_init()
      self._submit(lambda: self._core.save_cloudbase_env_id(env_id))

  def login(self, phone: str, password: str) -> None:
      self._lazy_init()
      self._submit(lambda: self._core.login(phone, password))

  def send_sms_code(self, phone: str, on_done: Callable[[tuple[bool, str]], None] | None = None) -> None:
      self._lazy_init()

      def done(result: Any) -> None:
          if isinstance(result, Exception):
              pair = (False, self.friendly_error(str(result)))
          else:
              pair = result
          if on_done:
              on_done(pair)

      self._submit(lambda: self._core.send_sms_code(phone), done)

  def send_register_sms(self, phone: str, on_done: Callable[[tuple[bool, str]], None] | None = None) -> None:
      self._lazy_init()

      def done(result: Any) -> None:
          if isinstance(result, Exception):
              pair = (False, self.friendly_error(str(result)))
          else:
              pair = result
          if on_done:
              on_done(pair)

      self._submit(lambda: self._core.send_register_sms(phone), done)

  def register(self, phone: str, password: str, code: str) -> None:
      self._lazy_init()
      self._submit(lambda: self._core.register(phone, password, code))

  def login_with_sms_code(self, phone: str, code: str) -> None:
      self._lazy_init()
      self._submit(lambda: self._core.login_with_sms_code(phone, code))

  def logout(self) -> None:
      if self._core is None:
          return
      with self._core_lock:
          self._core.logout()
      self._schedule_ui(self._on_data_changed_cb)

  def sync_now(self) -> None:
      self._lazy_init()
      self._submit(lambda: self._core.sync_now())

  def sync_assignments_only(self) -> None:
      self._lazy_init()
      self._submit(lambda: self._core.sync_assignments_only())

  def friendly_error(self, msg: str) -> str:
      if self._core is None:
          return msg[:200]
      return self._core.friendly_error(msg)

  def accept_assignment(self, assignment_id: str) -> None:
      self._lazy_init()
      self._submit(lambda: self._core.accept_assignment(assignment_id))

  def reject_assignment(self, assignment_id: str, note: str) -> None:
      self._lazy_init()
      self._submit(lambda: self._core.reject_assignment(assignment_id, note))

  def complete_assignment(self, assignment_id: str) -> None:
      self._lazy_init()
      self._submit(lambda: self._core.complete_assignment(assignment_id))

  def cancel_assignment(self, assignment_id: str, note: str) -> None:
      self._lazy_init()
      self._submit(lambda: self._core.cancel_assignment(assignment_id, note))

  def dispatch_assignment(
      self,
      phone: str,
      title: str,
      *,
      priority: int,
      description: str = "",
      on_done: Callable[[bool, str], None] | None = None,
  ) -> None:
      self._lazy_init()

      def work() -> tuple[bool, str]:
          try:
              self._core.dispatch_assignment(phone, title, priority=priority, description=description)
              return True, ""
          except SyncBackendError as exc:
              return False, self.friendly_error(str(exc))

      def done(result: Any) -> None:
          if isinstance(result, Exception):
              ok, msg = False, self.friendly_error(str(result))
          else:
              ok, msg = result
          if not ok:
              self._emit_status(msg)
          if on_done:
              on_done(ok, msg)

      self._submit(work, done)
