"""Qt-free 同步核心：桌面与移动端共用。"""

from __future__ import annotations

import json
import time
from typing import Callable

from .assignment_manager import AssignmentManager
from .auth import AuthManager
from .backend import SyncBackendConfig, SyncBackendError, create_sync_client, load_backend_config
from .contacts import ContactBook
from .engine import SyncEngine
from .paths import SyncPaths
from .phone import normalize_phone


class SyncCore:
    """登录、定时/防抖同步、任务派发（无 GUI 依赖）。"""

    def __init__(
        self,
        *,
        paths: SyncPaths,
        config,
        todo,
        notes,
        reminders,
        tr: Callable[..., str],
        enabled: bool = True,
        on_status: Callable[[str], None] | None = None,
        on_sync_applied: Callable[[], None] | None = None,
        on_assignments_changed: Callable[[], None] | None = None,
        on_login_finished: Callable[[bool, str], None] | None = None,
        on_config_saved: Callable[[bool, str], None] | None = None,
        on_assignment_accepted: Callable[[object], None] | None = None,
        on_assignment_event: Callable[[str, object], None] | None = None,
    ) -> None:
        self.paths = paths
        self.config = config
        self.todo = todo
        self.notes = notes
        self.reminders = reminders
        self._tr = tr
        self._enabled = enabled
        self._on_status = on_status or (lambda _t: None)
        self._on_sync_applied = on_sync_applied or (lambda: None)
        self._on_assignments_changed = on_assignments_changed or (lambda: None)
        self._on_login_finished = on_login_finished or (lambda _o, _m: None)
        self._on_config_saved = on_config_saved or (lambda _o, _m: None)
        self._on_assignment_accepted = on_assignment_accepted
        self._on_assignment_event = on_assignment_event

        self.auth = AuthManager(paths.auth)
        self.backend = self._load_backend()
        self.client = self._try_create_client()
        self.contacts = ContactBook(paths.contacts)
        self.engine = SyncEngine(
            self.client,
            config,
            todo,
            notes,
            reminders,
            self.contacts,
            sync_meta_path=paths.sync_meta,
        )
        self.assignments = AssignmentManager(
            self._ensure_client,
            assignments_path=paths.assignments,
            on_change=self._on_assignments_changed,
            on_event=self._emit_assignment_event,
        )

        self._status = tr("sync.status.offline")
        self._debounce_at = 0.0
        self._debounce_delay = 4.0
        self._periodic_interval = 15 * 60.0
        self._last_periodic = 0.0
        self._pending_verification_id = ""
        self._pending_verification_mode = "login"
        self._session_gen = 0

    def _emit_assignment_event(self, kind: str, assignment) -> None:
        if self._on_assignment_event:
            self._on_assignment_event(kind, assignment)

    def _load_backend(self) -> SyncBackendConfig:
        env_id = str(self.config.get("cloudbase_env_id", "") or "")
        return load_backend_config(self.paths.sync_config, env_id)

    def _reset_local_user_data(self) -> None:
        """清空本地待办/笔记/提醒/联系人/派发缓存，避免切换账号后残留上一账号数据。"""
        self.assignments.clear_local()
        self.todo.import_sync_records([])
        self.notes.import_sync_records([])
        self.reminders.import_sync_records([])
        self.contacts.import_sync_records([])
        self.engine.reset_sync_state()
        from ..config import DEFAULTS
        from .engine import SYNC_SETTINGS_KEYS

        reset = {k: DEFAULTS[k] for k in SYNC_SETTINGS_KEYS if k in DEFAULTS}
        reset["settings_updated_at"] = 0.0
        self.config.update(reset)

    def _should_reset_on_login(
        self,
        account: str,
        session,
        *,
        previous_user_id: str | None,
        previous_account: str | None,
    ) -> bool:
        if not session:
            return False
        if previous_user_id and previous_user_id != session.user_id:
            return True
        if previous_account and previous_account != account:
            return True
        meta_uid = self.engine.sync_user_id
        if meta_uid and meta_uid != session.user_id:
            return True
        return False

    def _ensure_sync_owner(self) -> bool:
        """校验 sync_meta 所属用户；不一致则清空本地用户数据。"""
        if not self.auth.is_logged_in or not self.auth.session:
            return False
        uid = self.auth.session.user_id
        meta_uid = self.engine.sync_user_id
        if meta_uid and meta_uid != uid:
            self._reset_local_user_data()
        self.engine.bind_sync_user(uid)
        return True

    def _finish_login(
        self,
        client,
        account: str,
        *,
        success_key: str = "sync.login.ok",
        previous_user_id: str | None = None,
        previous_account: str | None = None,
    ) -> tuple[bool, str]:
        if self._should_reset_on_login(
            account,
            client.auth.session,
            previous_user_id=previous_user_id,
            previous_account=previous_account,
        ):
            self._reset_local_user_data()
        elif client.auth.session:
            self.engine.bind_sync_user(client.auth.session.user_id)
        self.assignments.reset_sync_cursor()
        self.engine.client = client
        self._last_periodic = time.time()
        msg = self._tr(success_key)
        self._on_login_finished(True, msg)
        return True, msg

    def send_sms_code(self, phone: str) -> tuple[bool, str]:
        return self._send_sms_code(phone, target="USER", mode="login")

    def send_register_sms(self, phone: str) -> tuple[bool, str]:
        return self._send_sms_code(phone, target="ANY", mode="register")

    def _send_sms_code(self, phone: str, *, target: str, mode: str) -> tuple[bool, str]:
        if not self._enabled:
            msg = self._tr("sync.err.windows_only")
            return False, msg
        if not self.backend.configured:
            msg = self._tr("sync.err.need_config")
            return False, msg
        account = normalize_phone(phone)
        if not account:
            msg = self._tr("assign.err.bad_phone")
            return False, msg
        try:
            client = self._ensure_client()
            self._pending_verification_id = client.send_phone_verification(account, target=target)
            self._pending_verification_mode = mode
            return True, self._tr("sync.sms.sent")
        except SyncBackendError as exc:
            return False, self.friendly_error(str(exc))

    def register(self, phone: str, password: str, code: str) -> tuple[bool, str]:
        if not self._enabled:
            msg = self._tr("sync.err.windows_only")
            self._on_login_finished(False, msg)
            return False, msg
        if not self.backend.configured:
            msg = self._tr("sync.err.need_config")
            self._on_login_finished(False, msg)
            return False, msg
        account = normalize_phone(phone)
        code = code.strip()
        if not account or not password:
            msg = self._tr("sync.err.empty_password")
            self._on_login_finished(False, msg)
            return False, msg
        if not code:
            msg = self._tr("sync.err.empty_code")
            self._on_login_finished(False, msg)
            return False, msg
        if not self._pending_verification_id:
            msg = self._tr("sync.err.need_sms_first")
            self._on_login_finished(False, msg)
            return False, msg
        if self._pending_verification_mode != "register":
            msg = self._tr("sync.err.need_register_sms")
            self._on_login_finished(False, msg)
            return False, msg
        previous_user_id = self.auth.session.user_id if self.auth.session else None
        previous_account = self.auth.phone
        try:
            client = self._ensure_client()
            token = client.verify_phone_code(self._pending_verification_id, code)
            client.signup(account, password, token)
            self._pending_verification_id = ""
            self._pending_verification_mode = "login"
            return self._finish_login(
                client,
                account,
                success_key="sync.register.ok",
                previous_user_id=previous_user_id,
                previous_account=previous_account,
            )
        except SyncBackendError as exc:
            msg = self.friendly_error(str(exc))
            self._on_login_finished(False, msg)
            return False, msg
        except Exception as exc:
            msg = self.friendly_error(str(exc))
            self._on_login_finished(False, msg)
            return False, msg

    def login(self, phone: str, password: str) -> tuple[bool, str]:
        if not self._enabled:
            msg = self._tr("sync.err.windows_only")
            self._on_login_finished(False, msg)
            return False, msg
        if not self.backend.configured:
            msg = self._tr("sync.err.need_config")
            self._on_login_finished(False, msg)
            return False, msg
        account = normalize_phone(phone)
        if not account or not password:
            msg = self._tr("sync.err.empty_password")
            self._on_login_finished(False, msg)
            return False, msg
        previous_user_id = self.auth.session.user_id if self.auth.session else None
        previous_account = self.auth.phone
        try:
            client = self._ensure_client()
            client.login(account, password)
            return self._finish_login(
                client,
                account,
                previous_user_id=previous_user_id,
                previous_account=previous_account,
            )
        except SyncBackendError as exc:
            msg = self.friendly_error(str(exc))
            self._on_login_finished(False, msg)
            return False, msg
        except Exception as exc:
            msg = self.friendly_error(str(exc))
            self._on_login_finished(False, msg)
            return False, msg

    def login_with_sms_code(self, phone: str, code: str) -> tuple[bool, str]:
        if not self._enabled:
            msg = self._tr("sync.err.windows_only")
            self._on_login_finished(False, msg)
            return False, msg
        if not self.backend.configured:
            msg = self._tr("sync.err.need_config")
            self._on_login_finished(False, msg)
            return False, msg
        account = normalize_phone(phone)
        code = code.strip()
        if not account:
            msg = self._tr("assign.err.bad_phone")
            self._on_login_finished(False, msg)
            return False, msg
        if not code:
            msg = self._tr("sync.err.empty_code")
            self._on_login_finished(False, msg)
            return False, msg
        if not self._pending_verification_id:
            msg = self._tr("sync.err.need_sms_first")
            self._on_login_finished(False, msg)
            return False, msg
        if self._pending_verification_mode not in ("login", ""):
            msg = self._tr("sync.err.need_login_sms")
            self._on_login_finished(False, msg)
            return False, msg
        previous_user_id = self.auth.session.user_id if self.auth.session else None
        previous_account = self.auth.phone
        try:
            client = self._ensure_client()
            token = client.verify_phone_code(self._pending_verification_id, code)
            client.login_with_verification_token(token, account)
            self._pending_verification_id = ""
            self._pending_verification_mode = "login"
            return self._finish_login(
                client,
                account,
                previous_user_id=previous_user_id,
                previous_account=previous_account,
            )
        except SyncBackendError as exc:
            msg = self.friendly_error(str(exc))
            self._on_login_finished(False, msg)
            return False, msg
        except Exception as exc:
            msg = self.friendly_error(str(exc))
            self._on_login_finished(False, msg)
            return False, msg

    def reload_backend(self) -> None:
        self.backend = self._load_backend()
        self.client = self._try_create_client()
        self.engine.client = self.client

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def is_logged_in(self) -> bool:
        return self.auth.is_logged_in

    @property
    def phone(self) -> str | None:
        return self.auth.phone

    @property
    def backend_configured(self) -> bool:
        return self.backend.configured

    @property
    def user_cloudbase_env_id(self) -> str:
        """用户保存在 settings.json 中的授权码（不含安装目录模板配置）。"""
        return str(self.config.get("cloudbase_env_id", "") or "").strip()

    @property
    def user_env_saved(self) -> bool:
        return bool(self.user_cloudbase_env_id)

    @property
    def cloudbase_env_id(self) -> str:
        return self.user_cloudbase_env_id or str(self.backend.cloudbase_env_id or "").strip()

    @property
    def fallback_env_id(self) -> str:
        """sync_config.json 中的环境 ID（可能与 settings 不同）。"""
        from .backend import read_sync_config_env_id

        return read_sync_config_env_id(self.paths.sync_config)

    @property
    def env_mismatch(self) -> bool:
        user_env = self.user_cloudbase_env_id
        fallback = self.fallback_env_id
        return bool(user_env and fallback and user_env != fallback)

    def _persist_sync_config(self, env_id: str) -> None:
        payload = {
            "backend": self.backend.backend or "cloudbase",
            "cloudbase_env_id": env_id,
        }
        try:
            self.paths.sync_config.parent.mkdir(parents=True, exist_ok=True)
            self.paths.sync_config.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass

    def save_cloudbase_env_id(self, env_id: str) -> None:
        env_id = env_id.strip()
        if not env_id:
            self._on_config_saved(False, self._tr("sync.err.empty_env"))
            return
        previous_env = self.cloudbase_env_id
        env_changed = bool(previous_env and previous_env != env_id)
        if env_changed and self.auth.is_logged_in:
            self.logout()
        self.config.set("cloudbase_env_id", env_id)
        self._persist_sync_config(env_id)
        self.reload_backend()
        if self.backend.configured:
            msg = self._tr("sync.env.saved")
            if env_changed:
                msg = self._tr("sync.env.changed_relogin")
            self._on_config_saved(True, msg)
            if self.auth.is_logged_in:
                self.reset_sync_cursor()
                self._set_status(self._tr("sync.status.syncing"))
            else:
                self._set_status(self._tr("sync.status.need_login"))
        else:
            self._on_config_saved(False, self._tr("sync.err.need_config"))

    def start(self) -> None:
        if not self._enabled:
            self._set_status(self._tr("sync.status.disabled"))
            return
        if not self.backend.configured:
            self._set_status(self._tr("sync.status.need_env"))
            return
        if self.auth.is_logged_in:
            self._ensure_sync_owner()
            self.assignments.reset_sync_cursor()
            self._set_status(self._tr("sync.status.syncing"))
            self._last_periodic = time.time()
        else:
            self._set_status(self._tr("sync.status.need_login"))

    def schedule_push(self) -> None:
        if self._enabled and self.auth.is_logged_in and self.client is not None:
            self._debounce_at = time.time() + self._debounce_delay

    def tick(self, now: float | None = None) -> None:
        """由 UI 定时器调用：处理 debounce 与周期同步。"""
        if not self._enabled or not self.auth.is_logged_in:
            return
        ts = now if now is not None else time.time()
        if self._debounce_at and ts >= self._debounce_at:
            self._debounce_at = 0.0
            self.push_only()
        elif self._last_periodic and ts - self._last_periodic >= self._periodic_interval:
            self._last_periodic = ts
            self.sync_now()

    def _try_create_client(self):
        if not self.backend.configured:
            return None
        try:
            return create_sync_client(self.backend, self.auth, sync_meta_path=self.paths.sync_meta)
        except SyncBackendError:
            return None

    def _ensure_client(self):
        if self.client is None and self.backend.configured:
            self.client = self._try_create_client()
        if self.client is None:
            raise SyncBackendError("backend_not_configured")
        return self.client

    def logout(self) -> None:
        """退出登录：仅清除会话与派发缓存，保留本地待办/笔记以便同账号重登后继续使用。"""
        self._session_gen += 1
        self.auth.logout()
        self.assignments.clear_local()
        self._debounce_at = 0.0
        self._pending_verification_id = ""
        self._pending_verification_mode = "login"
        self._set_status(self._tr("sync.status.need_login"))
        self._on_assignments_changed()

    def _ensure_user_profile(self, client) -> None:
        """每次同步前写入/刷新自己的 user_profiles，便于他人按手机号派发。"""
        if not self.auth.is_logged_in:
            return
        account = self.phone or (self.auth.session.account if self.auth.session else "")
        if account and hasattr(client, "upsert_user_profile"):
            client.upsert_user_profile(account)

    def export_for_sync(self) -> tuple[dict, float]:
        """主线程：落盘并导出本地快照。"""
        if not self._ensure_sync_owner():
            raise SyncBackendError("not_logged_in")
        self.engine.prepare_local_for_sync()
        return self.engine.export_local(), self.engine._last_sync_at

    def network_sync_records(self, local: dict, since: float) -> tuple[dict, float, int]:
        """后台线程：拉取/合并/推送用户数据（不写本地 Qt 对象）。"""
        client = self._ensure_client()
        self.engine.client = client
        session = self.auth.session
        if session:
            self.engine.bind_sync_user(session.user_id)
        self._ensure_user_profile(client)
        return self.engine.network_sync(local, since)

    def network_push_records(self, local: dict, since: float) -> tuple[int, bool, float]:
        """后台线程：仅推送本地变更；返回 (上传条数, 是否需要完整同步, 推送游标)。"""
        client = self._ensure_client()
        self.engine.client = client
        session = self.auth.session
        if session:
            self.engine.bind_sync_user(session.user_id)
        self._ensure_user_profile(client)
        return self.engine.network_push_only(local, since)

    def reset_sync_cursor(self) -> None:
        """重置增量游标，下次同步会重新上传本地数据。"""
        self.engine._write_sync_meta(last_sync_at=0.0)

    def advance_push_cursor(self, max_pushed: float, since: float) -> None:
        if max_pushed > since:
            self.engine._write_sync_meta(last_sync_at=max_pushed)

    def apply_sync_records(self, merged: dict, max_updated: float, since: float) -> None:
        """主线程：写回合并结果。"""
        self.engine.commit_sync(merged, max_updated, since)
        self._on_sync_applied()

    def network_fetch_assignments(self) -> tuple[list[dict], float, float, dict[str, str]]:
        """后台线程：拉取派发变更。"""
        client = self._ensure_client()
        session = client.auth.session
        if session is None:
            raise SyncBackendError("not_logged_in")
        since = self.assignments._last_sync_at
        old_status = {aid: a.status for aid, a in self.assignments._items.items()}
        rows, max_updated = self.assignments.network_fetch(session.user_id, since)
        return rows, max_updated, since, old_status

    def apply_assignment_fetch(
        self,
        rows: list[dict],
        max_updated: float,
        since: float,
        old_status: dict[str, str],
    ) -> None:
        """主线程：合并派发并通知 UI。"""
        session = self.auth.session
        if session is None:
            return
        self.assignments.apply_fetch(rows, max_updated, since, old_status, session)
        self._on_assignments_changed()

    def push_only(self) -> bool:
        """仅上传本地变更；不拉取、不触发 sync_applied。"""
        if not self._enabled or not self.auth.is_logged_in:
            return True
        session_gen = self._session_gen
        try:
            if session_gen != self._session_gen or not self.auth.is_logged_in:
                return False
            local, since = self.export_for_sync()
            if session_gen != self._session_gen or not self.auth.is_logged_in:
                return False
            pushed, needs_full, max_pushed = self.network_push_records(local, since)
            if session_gen != self._session_gen or not self.auth.is_logged_in:
                return False
            if needs_full:
                self.reset_sync_cursor()
                return self.sync_now()
            if pushed > 0:
                self.advance_push_cursor(max_pushed, since)
            if pushed > 0 and session_gen == self._session_gen:
                self._set_status(self._tr("sync.status.ok"))
                return True
            return True
        except SyncBackendError as exc:
            if session_gen == self._session_gen:
                self._set_status(self._tr("sync.status.error", msg=self.friendly_error(str(exc))))
            return False

    def sync_assignments_only(self) -> bool:
        """仅拉取并合并派发任务。"""
        if not self._enabled or not self.auth.is_logged_in:
            return True
        session_gen = self._session_gen
        try:
            if session_gen != self._session_gen or not self.auth.is_logged_in:
                return False
            rows, assign_max, assign_since, old_status = self.network_fetch_assignments()
            if session_gen != self._session_gen or not self.auth.is_logged_in:
                return False
            self.apply_assignment_fetch(rows, assign_max, assign_since, old_status)
            if session_gen == self._session_gen:
                return True
            return False
        except SyncBackendError as exc:
            if session_gen == self._session_gen:
                self._set_status(self._tr("sync.status.error", msg=self.friendly_error(str(exc))))
            return False

    def sync_now(self) -> bool:
        """执行完整同步；成功返回 True，失败或中断返回 False。"""
        if not self._enabled or not self.auth.is_logged_in:
            return True
        session_gen = self._session_gen
        try:
            if session_gen != self._session_gen or not self.auth.is_logged_in:
                return False
            self._set_status(self._tr("sync.status.syncing"))
            local, since = self.export_for_sync()
            if session_gen != self._session_gen or not self.auth.is_logged_in:
                return False
            merged, max_updated, pushed = self.network_sync_records(local, since)
            apply_since = since
            if session_gen != self._session_gen or not self.auth.is_logged_in:
                return False
            if (
                pushed == 0
                and self.engine._has_local_sync_data(local)
                and since > 0
            ):
                self.reset_sync_cursor()
                merged, max_updated, pushed = self.network_sync_records(local, 0.0)
                apply_since = 0.0
            if session_gen != self._session_gen or not self.auth.is_logged_in:
                return False
            self.apply_sync_records(merged, max_updated, apply_since)
            if session_gen != self._session_gen or not self.auth.is_logged_in:
                return False
            rows, assign_max, assign_since, old_status = self.network_fetch_assignments()
            if session_gen != self._session_gen or not self.auth.is_logged_in:
                return False
            self.apply_assignment_fetch(rows, assign_max, assign_since, old_status)
            if session_gen == self._session_gen:
                self._set_status(self._tr("sync.status.ok"))
                return True
            return False
        except SyncBackendError as exc:
            if session_gen == self._session_gen:
                self._set_status(self._tr("sync.status.error", msg=self.friendly_error(str(exc))))
            return False

    def accept_assignment(self, assignment_id: str) -> None:
        assignment = self.assignments.accept(assignment_id)
        if self._on_assignment_accepted:
            self._on_assignment_accepted(assignment)

    def reject_assignment(self, assignment_id: str, note: str = "") -> None:
        self.assignments.reject(assignment_id, note)

    def complete_assignment(self, assignment_id: str) -> None:
        self.assignments.complete(assignment_id)

    def cancel_assignment(self, assignment_id: str, note: str = "") -> None:
        self.assignments.cancel(assignment_id, note)

    def dispatch_assignment(
        self,
        recipient: str,
        title: str,
        *,
        priority: int,
        description: str = "",
    ) -> None:
        phone = self.contacts.resolve_recipient(recipient)
        self.assignments.create(phone, title, priority=priority, description=description)

    def set_contact_nickname(self, phone: str, nickname: str) -> None:
        self.contacts.set_contact(phone, nickname)
        self.schedule_push()

    def remove_contact(self, phone: str) -> None:
        self.contacts.remove_contact(phone)
        self.schedule_push()

    def friendly_error(self, msg: str) -> str:
        lowered = msg.lower()
        if "invalid login credentials" in lowered or "password" in lowered and "incorrect" in lowered:
            return self._tr("sync.err.bad_credentials")
        if "backend_not_configured" in msg or "empty_credentials" in msg:
            return self._tr("sync.err.need_config")
        if "not_logged_in" in msg:
            return self._tr("sync.status.need_login")
        if "assign.err.need_login" in msg:
            return self._tr("assign.err.need_login")
        if "assignee_not_found" in msg:
            return self._tr("assign.err.not_found")
        if "cannot_assign_self" in msg:
            return self._tr("assign.err.self")
        if "invalid_phone" in msg:
            return self._tr("assign.err.bad_phone")
        if "empty_title" in msg:
            return self._tr("assign.err.empty_title")
        if "empty_recipient" in msg:
            return self._tr("assign.err.empty_recipient")
        if "contact_not_found" in msg:
            return self._tr("assign.err.contact_not_found")
        if "duplicate_nickname" in msg:
            return self._tr("assign.err.duplicate_nickname")
        if "empty_nickname" in msg:
            return self._tr("contacts.err.empty_nickname")
        if "empty_reject_reason" in msg:
            return self._tr("assign.err.empty_reject_reason")
        if "empty_cancel_reason" in msg:
            return self._tr("assign.err.empty_cancel_reason")
        if "assignment_not_finished" in msg:
            return self._tr("assign.err.not_finished")
        if "forbidden_action" in msg:
            return self._tr("assign.err.forbidden")
        if "invalid_verification_code" in msg or "invalid verification" in lowered:
            return self._tr("sync.err.bad_code")
        if "empty_verification" in msg:
            return self._tr("sync.err.empty_code")
        if "need_register_sms" in msg or "need_register_sms" in lowered:
            return self._tr("sync.err.need_register_sms")
        if "need_login_sms" in msg:
            return self._tr("sync.err.need_login_sms")
        if "already" in lowered and ("exist" in lowered or "registered" in lowered):
            return self._tr("sync.err.already_registered")
        if "user not found" in lowered or ("not exist" in lowered and "user" in lowered):
            return self._tr("sync.err.user_not_found")
        return msg[:200]

    def _set_status(self, text: str) -> None:
        self._status = text
        self._on_status(text)

    def status_text(self) -> str:
        return self._status
