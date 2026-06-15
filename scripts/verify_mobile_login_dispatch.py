"""验证手机端 MobileSyncService：登录会话与任务派发（内存模拟 CloudBase）。

用法：
  python scripts/verify_mobile_login_dispatch.py

不访问真实 CloudBase；与 scripts/dryrun_sync_dispatch.py 共用 DryRun 云端模拟。
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(MOBILE) not in sys.path:
    sys.path.append(str(MOBILE))

from walle.sync.assignment_models import STATUS_ACCEPTED, STATUS_PENDING  # noqa: E402
from walle.sync.backend import SyncBackendError  # noqa: E402
from walle.sync.phone import normalize_phone  # noqa: E402

from dryrun_sync_dispatch import DryRunCloudClient, InMemoryCloud  # noqa: E402


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def _inject_logged_in(service, cloud: InMemoryCloud, user_id: str, phone: str) -> DryRunCloudClient:
    auth = service._core.auth
    auth.set_session(
        user_id=user_id,
        account=phone,
        access_token=f"tok-{user_id}",
        refresh_token=f"ref-{user_id}",
        expires_in=7200,
    )
    cloud.register_user(user_id, phone)
    client = DryRunCloudClient(cloud, auth)
    service._core.client = client
    service._core.engine.client = client
    service._core.engine.bind_sync_user(user_id)
    service._core.assignments.reset_sync_cursor()
    return client


def _make_service(tmp: Path):
    os.environ["WALLE_MOBILE_DATA"] = str(tmp)
    from notes_store import NotesStore
    from reminder_store import ReminderStore
    from settings_store import SettingsStore
    from sync_service import MobileSyncService
    from todo_store import TodoStore

    settings = SettingsStore()
    settings.set("cloudbase_env_id", "dryrun-env")
    settings.save()
    todo = TodoStore(on_change=lambda: None)
    notes = NotesStore(on_change=lambda: None)
    reminders = ReminderStore(on_change=lambda: None)
    return MobileSyncService(settings, todo, notes, reminders)


def test_password_login_mock(tmp: Path, cloud: InMemoryCloud) -> None:
    """模拟 CloudBase 密码登录成功后，MobileSyncService 应进入已登录状态。"""
    svc = _make_service(tmp / "login")
    svc.save_cloudbase_env_id("dryrun-env")
    svc.flush()
    assert svc.backend_configured
    assert not svc.is_logged_in

    phone = "13800000001"
    _inject_logged_in(svc, cloud, "user-a", normalize_phone(phone) or f"+86 {phone}")
    svc.logout()
    assert not svc.is_logged_in

    class LoginClient(DryRunCloudClient):
        def login(self, account: str, password: str) -> None:
            if password != "TestPass123":
                raise SyncBackendError("invalid login credentials")
            normalized = normalize_phone(account) or account
            uid = self.cloud.auth_by_phone.get(normalized) or "user-a"
            self.cloud.register_user(uid, normalized)
            self.auth.set_session(
                user_id=uid,
                account=normalized,
                access_token=f"tok-{uid}",
                refresh_token=f"ref-{uid}",
                expires_in=7200,
            )
            self.upsert_user_profile(account)

    auth = svc._core.auth
    client = LoginClient(cloud, auth)
    svc._core.client = client
    svc._core.engine.client = client

    ok, msg = svc._core.login(phone, "TestPass123")
    assert ok, f"密码登录应成功: {msg}"
    assert svc.is_logged_in
    assert svc.phone
    print("  OK 密码登录（模拟 CloudBase）")


def test_dispatch_by_nickname(tmp: Path, cloud: InMemoryCloud) -> None:
    """A 通过联系人昵称派发 → B 收件箱可见（与桌面派发链路一致）。"""
    phone_a = "+86 13800000001"
    phone_b = "+86 13800000002"
    svc_a = _make_service(tmp / "a")
    svc_b = _make_service(tmp / "b")
    _inject_logged_in(svc_a, cloud, "user-a", phone_a)
    _inject_logged_in(svc_b, cloud, "user-b", phone_b)

    svc_a.set_contact_nickname("13800000002", "接收人")
    svc_a.sync_now()
    svc_b.sync_now()
    svc_a.flush()
    svc_b.flush()

    svc_a.dispatch_assignment("接收人", "手机端派发测试", priority=1, description="来自 verify_mobile")
    svc_a.flush()
    assert len(svc_a.assignments.outbox) == 1
    assert len(cloud.assignments) == 1

    assert len(svc_b.assignments.inbox) == 0
    svc_b.sync_now()
    svc_b.flush()
    inbox = svc_b.assignments.inbox
    assert len(inbox) == 1, f"B 收件箱应有 1 条，实际 {len(inbox)}"
    assert inbox[0].title == "手机端派发测试"
    assert inbox[0].status == STATUS_PENDING
    print("  OK 昵称派发 + 收件同步")

    svc_b.accept_assignment(inbox[0].id)
    svc_b.flush()
    assert svc_b.assignments.inbox[0].status == STATUS_ACCEPTED

    svc_a.sync_now()
    svc_a.flush()
    assert svc_a.assignments.outbox[0].status == STATUS_ACCEPTED
    print("  OK 接受后发件箱状态同步")


def test_dispatch_errors(tmp: Path, cloud: InMemoryCloud) -> None:
    svc = _make_service(tmp / "err")
    _inject_logged_in(svc, cloud, "user-a", "+86 13800000001")
    core = svc._core

    try:
        core.dispatch_assignment("", "标题", priority=1)
        _fail("空手机号应失败")
    except SyncBackendError as exc:
        assert "invalid_phone" in str(exc) or "empty_recipient" in str(exc)

    try:
        core.dispatch_assignment("19900000000", "标题", priority=1)
        _fail("未注册用户应失败")
    except SyncBackendError as exc:
        assert "assignee_not_found" in str(exc)

    try:
        core.dispatch_assignment("13800000001", "", priority=1)
        _fail("空标题应失败")
    except SyncBackendError as exc:
        assert "empty_title" in str(exc)

    print("  OK 派发参数校验")


def test_ui_dispatch_guard() -> None:
    """TodoScreen._dispatch 在未登录时不应调用云端。"""
    from unittest.mock import MagicMock, patch

    from main import TodoScreen  # noqa: E402

    store = MagicMock()
    screen = TodoScreen.__new__(TodoScreen)
    screen.sync = MagicMock()
    screen.sync.is_logged_in = False
    screen.dispatch_phone = MagicMock(text="13800000002")
    screen.dispatch_title = MagicMock(text="t")
    screen.dispatch_description = MagicMock(text="")
    screen.dispatch_prio = MagicMock(text="中")

    with patch("main.notify") as notify_mock:
        TodoScreen._dispatch(screen)
        screen.sync.dispatch_assignment.assert_not_called()
        notify_mock.assert_not_called()
    print("  OK 未登录时 UI 不派发")


def main() -> int:
    print("=== 手机端登录与派发验证（DryRun）===")
    cloud = InMemoryCloud()
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        try:
            test_password_login_mock(base / "login", cloud)
            test_dispatch_by_nickname(base, cloud)
            test_dispatch_errors(base, cloud)
            test_ui_dispatch_guard()
        except AssertionError as exc:
            print(f"FAIL: {exc}")
            traceback.print_exc()
            return 1
        except Exception as exc:
            print(f"ERROR: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            return 1

    print("=== 全部通过 ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
