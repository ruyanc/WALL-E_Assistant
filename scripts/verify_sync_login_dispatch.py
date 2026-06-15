"""验证码登录、自助注册与任务派发验证脚本。

用法：
  python scripts/verify_sync_login_dispatch.py           # 单元测试 + 本地联机探测
  python scripts/verify_sync_login_dispatch.py --live    # 额外执行 CloudBase 联机测试

联机测试可选环境变量：
  WALLE_TEST_PHONE       接收验证码的手机号（登录）
  WALLE_TEST_SMS_CODE    短信验证码（与 --live 联用完成验证码登录）
  WALLE_REGISTER_PHONE   新用户注册手机号（须未注册）
  WALLE_REGISTER_PASSWORD 注册密码（默认 TestPass123）
  WALLE_REGISTER_SMS_CODE 注册短信验证码
  WALLE_ASSIGN_PHONE     派发目标手机号（需已在 CloudBase 登录过）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from walle.config import AUTH_PATH, CONFIG_PATH, get_data_dir  # noqa: E402
from walle.sync.assignment_events import (  # noqa: E402
    EVENT_ACCEPTED,
    EVENT_COMPLETED,
    EVENT_DISPATCHED,
    EVENT_REJECTED,
    EVENT_WITHDRAWN,
)
from walle.sync.assignment_manager import AssignmentManager  # noqa: E402
from walle.sync.assignment_models import STATUS_ACCEPTED, STATUS_CANCELLED, STATUS_COMPLETED, STATUS_PENDING, STATUS_REJECTED, Assignment  # noqa: E402
from walle.sync.assignment_notify import assignment_notify_messages  # noqa: E402
from walle.sync.contacts import ContactBook  # noqa: E402
from walle.sync.auth import AuthManager, AuthSession  # noqa: E402
from walle.sync.backend import SyncBackendConfig, SyncBackendError  # noqa: E402
from walle.sync.cloudbase_client import CloudBaseClient  # noqa: E402
from walle.sync.core import SyncCore  # noqa: E402
from walle.sync.engine import SyncEngine  # noqa: E402
from walle.sync.paths import SyncPaths  # noqa: E402
from walle.sync.phone import normalize_phone, phone_lookup_variants  # noqa: E402
from walle.todo_manager import TodoManager  # noqa: E402
from walle.notes_manager import NotesManager  # noqa: E402
from walle.reminder_manager import ReminderManager  # noqa: E402
from walle.config import Config  # noqa: E402
from walle.i18n import tr  # noqa: E402


def _mask_phone(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) >= 7:
        return f"{digits[:3]}****{digits[-4:]}"
    return "****"


class PhoneNormalizeTests(unittest.TestCase):
    def test_normalize_cn_mobile(self) -> None:
        self.assertEqual(normalize_phone("13800138000"), "+86 13800138000")
        self.assertEqual(normalize_phone("+86 13800138000"), "+86 13800138000")

    def test_phone_lookup_variants(self) -> None:
        variants = phone_lookup_variants("13611019772")
        self.assertIn("+86 13611019772", variants)
        self.assertIn("13611019772", variants)
        self.assertIn("+8613611019772", variants)


class CloudBaseClientSmsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.auth = AuthManager()
        cfg = SyncBackendConfig(cloudbase_env_id="test-env")
        self.client = CloudBaseClient(cfg, self.auth)

    @patch.object(CloudBaseClient, "_request")
    def test_send_phone_verification(self, mock_req: MagicMock) -> None:
        mock_req.return_value = {"verification_id": "vid-123"}
        vid = self.client.send_phone_verification("13800138000")
        self.assertEqual(vid, "vid-123")
        mock_req.assert_called_once()
        args, kwargs = mock_req.call_args
        self.assertEqual(args[0], "POST")
        self.assertIn("/auth/v1/verification", args[1])
        self.assertEqual(kwargs["body"]["phone_number"], "+86 13800138000")

    @patch.object(CloudBaseClient, "_request")
    def test_verify_phone_code(self, mock_req: MagicMock) -> None:
        mock_req.return_value = {"verification_token": "vtok-abc"}
        token = self.client.verify_phone_code("vid-123", "654321")
        self.assertEqual(token, "vtok-abc")
        body = mock_req.call_args.kwargs["body"]
        self.assertEqual(body["verification_id"], "vid-123")
        self.assertEqual(body["verification_code"], "654321")

    @patch.object(CloudBaseClient, "_request")
    def test_send_phone_verification_register_target(self, mock_req: MagicMock) -> None:
        mock_req.return_value = {"verification_id": "vid-reg"}
        vid = self.client.send_phone_verification("13800138000", target="ANY")
        self.assertEqual(vid, "vid-reg")
        body = mock_req.call_args.kwargs["body"]
        self.assertEqual(body["target"], "ANY")

    @patch.object(CloudBaseClient, "upsert_user_profile")
    @patch.object(CloudBaseClient, "_request")
    def test_signup(self, mock_req: MagicMock, _profile: MagicMock) -> None:
        mock_req.return_value = {
            "sub": "user-new",
            "access_token": "acc-new",
            "refresh_token": "ref-new",
            "expires_in": 7200,
        }
        session = self.client.signup("13800138000", "Secret123", "vtok-reg")
        self.assertEqual(session.user_id, "user-new")
        body = mock_req.call_args.kwargs["body"]
        self.assertEqual(body["phone_number"], "+86 13800138000")
        self.assertEqual(body["verification_token"], "vtok-reg")
        self.assertEqual(body["password"], "Secret123")

    @patch.object(CloudBaseClient, "upsert_user_profile")
    @patch.object(CloudBaseClient, "_request")
    def test_login_with_verification_token(self, mock_req: MagicMock, _profile: MagicMock) -> None:
        mock_req.return_value = {
            "sub": "user-1",
            "access_token": "acc",
            "refresh_token": "ref",
            "expires_in": 7200,
        }
        session = self.client.login_with_verification_token("vtok-abc", "13800138000")
        self.assertEqual(session.user_id, "user-1")
        self.assertEqual(session.account, "+86 13800138000")
        body = mock_req.call_args.kwargs["body"]
        self.assertEqual(body["verification_token"], "vtok-abc")

    @patch.object(CloudBaseClient, "put_document")
    def test_upsert_user_profile_normalizes_phone(self, mock_put: MagicMock) -> None:
        self.auth.set_session(
            user_id="user-1",
            account="+86 13800138000",
            access_token="acc",
            refresh_token="ref",
            expires_in=3600,
        )
        self.client.upsert_user_profile("13800138000")
        payload = mock_put.call_args.args[2]
        self.assertEqual(payload["phone"], "+86 13800138000")
        self.assertEqual(payload["phone_digits"], "13800138000")

    @patch.object(CloudBaseClient, "_query_auth_user")
    def test_find_user_by_phone_prefers_auth_query(self, mock_auth: MagicMock) -> None:
        mock_auth.return_value = {"user_id": "user-b", "phone": "+86 13611019772"}
        row = self.client.find_user_by_phone("13611019772")
        self.assertEqual(row["user_id"], "user-b")
        mock_auth.assert_called()

    @patch.object(CloudBaseClient, "_query_auth_user", return_value=None)
    @patch.object(CloudBaseClient, "find_documents")
    def test_find_user_by_phone_uses_variants(self, mock_find: MagicMock, _auth: MagicMock) -> None:
        mock_find.side_effect = [
            [],
            [{"user_id": "user-b", "phone": "+86 13611019772", "phone_digits": "13611019772"}],
        ]
        row = self.client.find_user_by_phone("13611019772")
        self.assertEqual(row["user_id"], "user-b")
        self.assertGreaterEqual(mock_find.call_count, 2)
        digits_filt = mock_find.call_args_list[0].args[1]
        self.assertEqual(digits_filt, {"phone_digits": "13611019772"})

    @patch.object(CloudBaseClient, "_request")
    def test_upsert_records_scopes_by_user(self, mock_req: MagicMock) -> None:
        self.auth.set_session(
            user_id="user-1",
            account="+86 13800138000",
            access_token="acc",
            refresh_token="ref",
            expires_in=3600,
        )
        mock_req.side_effect = [{"matched": 0}, None]
        self.client.upsert_records(
            [
                {"record_id": "global", "collection": "settings", "payload": {"a": 1}, "updated_at": 100.0, "deleted": False},
            ]
        )
        patch_call = mock_req.call_args_list[0]
        self.assertEqual(patch_call.args[0], "PATCH")
        patch_body = patch_call.kwargs["body"]
        self.assertEqual(patch_body["query"]["_id"], "user-1_settings_global")
        self.assertEqual(patch_body["query"]["user_id"], "user-1")
        post_call = mock_req.call_args_list[1]
        self.assertEqual(post_call.args[0], "POST")
        doc = post_call.kwargs["body"]["data"][0]
        self.assertEqual(doc["_id"], "user-1_settings_global")
        self.assertEqual(doc["user_id"], "user-1")
        self.assertEqual(doc["record_id"], "global")

    @patch.object(CloudBaseClient, "_request")
    def test_fetch_changes_filters_by_user(self, mock_req: MagicMock) -> None:
        self.auth.set_session(
            user_id="user-1",
            account="+86 13800138000",
            access_token="acc",
            refresh_token="ref",
            expires_in=3600,
        )
        mock_req.return_value = {
            "list": [
                {"user_id": "user-1", "record_id": "t1", "collection": "todo", "payload": {}, "updated_at": 200.0},
                {"user_id": "user-2", "record_id": "t2", "collection": "todo", "payload": {}, "updated_at": 300.0},
            ]
        }
        rows = self.client.fetch_changes(50.0)
        method, url = mock_req.call_args.args[0], mock_req.call_args.args[1]
        self.assertEqual(method, "GET")
        self.assertIn("user_id", url)
        # 即使云端返回了其他账号的记录，也必须在客户端过滤掉。
        ids = {r["record_id"] for r in rows}
        self.assertIn("t1", ids)
        self.assertNotIn("t2", ids)



class SyncCoreSmsFlowTests(unittest.TestCase):
    def _make_core(self, tmp: Path) -> SyncCore:
        paths = SyncPaths(
            auth=tmp / "auth.json",
            sync_meta=tmp / "sync_meta.json",
            sync_config=tmp / "sync_config.json",
            assignments=tmp / "assignments.json",
            contacts=tmp / "contact_nicknames.json",
        )
        cfg = Config.__new__(Config)
        cfg._data = {"cloudbase_env_id": "live-env-id"}
        cfg.get = lambda key, default=None: cfg._data.get(key, default)  # type: ignore[method-assign]
        cfg.set = lambda key, value: cfg._data.__setitem__(key, value)  # type: ignore[method-assign]
        return SyncCore(
            paths=paths,
            config=cfg,
            todo=TodoManager(),
            notes=NotesManager(),
            reminders=ReminderManager(),
            tr=tr,
            enabled=True,
        )

    @patch.object(SyncCore, "_ensure_client")
    def test_send_sms_code_stores_verification_id(self, mock_client_fn: MagicMock) -> None:
        client = MagicMock()
        client.send_phone_verification.return_value = "vid-999"
        mock_client_fn.return_value = client
        with tempfile.TemporaryDirectory() as td:
            core = self._make_core(Path(td))
            ok, msg = core.send_sms_code("13800138000")
            self.assertTrue(ok)
            self.assertIn("验证码", msg)
            self.assertEqual(core._pending_verification_id, "vid-999")

    @patch.object(SyncCore, "_finish_login")
    @patch.object(SyncCore, "_ensure_client")
    def test_login_with_sms_code_full_chain(
        self, mock_client_fn: MagicMock, mock_finish: MagicMock
    ) -> None:
        client = MagicMock()
        client.verify_phone_code.return_value = "vtok"
        mock_client_fn.return_value = client
        mock_finish.return_value = (True, "ok")
        with tempfile.TemporaryDirectory() as td:
            core = self._make_core(Path(td))
            core._pending_verification_id = "vid-999"
            ok, _ = core.login_with_sms_code("13800138000", "123456")
            self.assertTrue(ok)
            client.verify_phone_code.assert_called_once_with("vid-999", "123456")
            client.login_with_verification_token.assert_called_once_with("vtok", "+86 13800138000")
            self.assertEqual(core._pending_verification_id, "")

    @patch.object(SyncCore, "_ensure_client")
    def test_login_with_sms_code_requires_send_first(self, mock_client_fn: MagicMock) -> None:
        mock_client_fn.return_value = MagicMock()
        with tempfile.TemporaryDirectory() as td:
            core = self._make_core(Path(td))
            ok, msg = core.login_with_sms_code("13800138000", "123456")
            self.assertFalse(ok)
            self.assertIn("验证码", core.friendly_error(msg))


class SyncCoreRegisterFlowTests(unittest.TestCase):
    def _make_core(self, tmp: Path) -> SyncCore:
        paths = SyncPaths(
            auth=tmp / "auth.json",
            sync_meta=tmp / "sync_meta.json",
            sync_config=tmp / "sync_config.json",
            assignments=tmp / "assignments.json",
            contacts=tmp / "contact_nicknames.json",
        )
        cfg = Config.__new__(Config)
        cfg._data = {"cloudbase_env_id": "live-env-id"}
        cfg.get = lambda key, default=None: cfg._data.get(key, default)  # type: ignore[method-assign]
        cfg.set = lambda key, value: cfg._data.__setitem__(key, value)  # type: ignore[method-assign]
        return SyncCore(
            paths=paths,
            config=cfg,
            todo=TodoManager(),
            notes=NotesManager(),
            reminders=ReminderManager(),
            tr=tr,
            enabled=True,
        )

    @patch.object(SyncCore, "_ensure_client")
    def test_send_register_sms_sets_mode(self, mock_client_fn: MagicMock) -> None:
        client = MagicMock()
        client.send_phone_verification.return_value = "vid-reg"
        mock_client_fn.return_value = client
        with tempfile.TemporaryDirectory() as td:
            core = self._make_core(Path(td))
            ok, msg = core.send_register_sms("13800138000")
            self.assertTrue(ok)
            self.assertIn("验证码", msg)
            self.assertEqual(core._pending_verification_id, "vid-reg")
            self.assertEqual(core._pending_verification_mode, "register")
            client.send_phone_verification.assert_called_once_with("+86 13800138000", target="ANY")

    @patch.object(SyncCore, "_finish_login")
    @patch.object(SyncCore, "_ensure_client")
    def test_register_full_chain(self, mock_client_fn: MagicMock, mock_finish: MagicMock) -> None:
        client = MagicMock()
        client.verify_phone_code.return_value = "vtok-reg"
        mock_client_fn.return_value = client
        mock_finish.return_value = (True, tr("sync.register.ok"))
        with tempfile.TemporaryDirectory() as td:
            core = self._make_core(Path(td))
            core._pending_verification_id = "vid-reg"
            core._pending_verification_mode = "register"
            ok, msg = core.register("13800138000", "Pass1234", "654321")
            self.assertTrue(ok)
            client.verify_phone_code.assert_called_once_with("vid-reg", "654321")
            client.signup.assert_called_once_with("+86 13800138000", "Pass1234", "vtok-reg")
            self.assertEqual(core._pending_verification_id, "")
            self.assertEqual(core._pending_verification_mode, "login")
            mock_finish.assert_called_once()
            self.assertEqual(mock_finish.call_args.kwargs.get("success_key"), "sync.register.ok")

    @patch.object(SyncCore, "_ensure_client")
    def test_register_rejects_login_sms_mode(self, mock_client_fn: MagicMock) -> None:
        mock_client_fn.return_value = MagicMock()
        with tempfile.TemporaryDirectory() as td:
            core = self._make_core(Path(td))
            core._pending_verification_id = "vid-login"
            core._pending_verification_mode = "login"
            ok, msg = core.register("13800138000", "Pass1234", "123456")
            self.assertFalse(ok)
            self.assertIn("注册", core.friendly_error(msg))

    @patch.object(SyncCore, "_ensure_client")
    def test_login_sms_rejects_register_mode(self, mock_client_fn: MagicMock) -> None:
        mock_client_fn.return_value = MagicMock()
        with tempfile.TemporaryDirectory() as td:
            core = self._make_core(Path(td))
            core._pending_verification_id = "vid-reg"
            core._pending_verification_mode = "register"
            ok, msg = core.login_with_sms_code("13800138000", "123456")
            self.assertFalse(ok)
            self.assertIn("登录", core.friendly_error(msg))

    def test_friendly_error_mappings(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            core = self._make_core(Path(td))
            self.assertIn("注册", core.friendly_error("need_register_sms"))
            self.assertIn("登录", core.friendly_error("need_login_sms"))
            self.assertIn("已注册", core.friendly_error("User already registered"))
            self.assertIn("尚未注册", core.friendly_error("user not found"))
            self.assertIn("尚未注册", core.friendly_error("user does not exist in system"))

    @patch.object(SyncCore, "_ensure_client")
    def test_logout_clears_pending_verification(self, mock_client_fn: MagicMock) -> None:
        mock_client_fn.return_value = MagicMock()
        with tempfile.TemporaryDirectory() as td:
            core = self._make_core(Path(td))
            core._pending_verification_id = "vid-x"
            core._pending_verification_mode = "register"
            core.logout()
            self.assertEqual(core._pending_verification_id, "")
            self.assertEqual(core._pending_verification_mode, "login")

    @patch.object(SyncCore, "_ensure_client")
    def test_logout_keeps_local_user_data(self, mock_client_fn: MagicMock) -> None:
        mock_client_fn.return_value = MagicMock()
        with tempfile.TemporaryDirectory() as td:
            core = self._make_core(Path(td))
            core.auth.set_session(
                user_id="user-a",
                account="+86 13800000001",
                access_token="tok",
                refresh_token="ref",
                expires_in=3600,
            )
            core.todo.add("退出后应保留")
            core.logout()
            self.assertEqual(len(core.todo.tasks), 1)
            self.assertEqual(core.todo.tasks[0].text, "退出后应保留")

    @patch.object(SyncCore, "_ensure_client")
    def test_sync_now_upserts_user_profile(self, mock_client_fn: MagicMock) -> None:
        client = MagicMock()
        client.auth.is_logged_in = True
        mock_client_fn.return_value = client
        with tempfile.TemporaryDirectory() as td:
            core = self._make_core(Path(td))
            core.auth.set_session(
                user_id="user-a",
                account="+86 18851071884",
                access_token="tok",
                refresh_token="ref",
                expires_in=3600,
            )
            core.engine.sync = MagicMock()
            core.assignments.sync = MagicMock()
            core.sync_now()
            client.upsert_user_profile.assert_called_once_with("+86 18851071884")

    @patch.object(SyncCore, "sync_now")
    @patch.object(SyncCore, "_ensure_client")
    def test_account_switch_clears_local_todos(self, mock_client_fn: MagicMock, _sync: MagicMock) -> None:
        client = MagicMock()
        session = AuthSession(
            user_id="user-b",
            account="+86 13800000002",
            access_token="tok",
            refresh_token="ref",
            expires_at=time.time() + 3600,
        )
        client.auth.session = session
        mock_client_fn.return_value = client
        with tempfile.TemporaryDirectory() as td:
            core = self._make_core(Path(td))
            core.auth.set_session(
                user_id="user-a",
                account="+86 13800000001",
                access_token="tok-a",
                refresh_token="ref-a",
                expires_in=3600,
            )
            core.todo.add("旧账号待办")
            core.notes.add("旧账号笔记")
            core.contacts.set_contact("13800000003", "旧联系人")
            core._finish_login(
                client,
                "+86 13800000002",
                previous_user_id="user-a",
                previous_account="+86 13800000001",
            )
            self.assertEqual(len(core.todo.tasks), 0)
            self.assertEqual(len(core.notes.entries), 0)
            self.assertEqual(core.contacts.list_contacts(), [])

    @patch.object(SyncCore, "_ensure_client")
    def test_dispatch_resolves_contact_nickname(self, mock_client_fn: MagicMock) -> None:
        client = MagicMock()
        session = AuthSession(
            user_id="user-a",
            account="+86 13800000001",
            access_token="tok",
            refresh_token="ref",
            expires_at=time.time() + 3600,
        )
        client.auth.session = session
        client.find_user_by_phone.return_value = {
            "user_id": "user-b",
            "phone": "+86 13800000002",
        }
        mock_client_fn.return_value = client
        with tempfile.TemporaryDirectory() as td:
            core = self._make_core(Path(td))
            core.contacts.set_contact("13800000002", "同事")
            core.dispatch_assignment("同事", "通过昵称派发", priority=1)
            client.find_user_by_phone.assert_called_once_with("+86 13800000002")


class SyncServiceAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def _make_service(self, tmp: Path):
        from walle.config import Config
        from walle.sync.service import SyncService

        paths = SyncPaths(
            auth=tmp / "auth.json",
            sync_meta=tmp / "sync_meta.json",
            sync_config=tmp / "sync_config.json",
            assignments=tmp / "assignments.json",
            contacts=tmp / "contact_nicknames.json",
        )
        cfg = Config.__new__(Config)
        cfg._data = {"cloudbase_env_id": "live-env-id"}
        cfg.get = lambda key, default=None: cfg._data.get(key, default)  # type: ignore[method-assign]
        cfg.set = lambda key, value: cfg._data.__setitem__(key, value)  # type: ignore[method-assign]
        cfg.update = lambda values: cfg._data.update(values)  # type: ignore[method-assign]
        svc = SyncService(cfg, TodoManager(), NotesManager(), ReminderManager())
        svc._core.paths = paths
        return svc

    def test_logout_resets_auth_busy_and_generation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            svc = self._make_service(Path(td))
            svc._auth_busy = True
            gen = svc._auth_gen
            session_gen = svc._session_gen
            svc.logout()
            self.assertFalse(svc._auth_busy)
            self.assertEqual(svc._auth_gen, gen + 1)
            self.assertEqual(svc._session_gen, session_gen + 1)
            self.assertFalse(svc.sync_busy)

    def test_sync_now_runs_in_background_without_blocking(self) -> None:
        from PySide6.QtCore import QCoreApplication, QThreadPool

        with tempfile.TemporaryDirectory() as td:
            svc = self._make_service(Path(td))
            svc._core.auth.set_session(
                user_id="u1",
                account="+86 1",
                access_token="tok",
                refresh_token="ref",
                expires_in=3600,
            )
            calls: list[str] = []

            svc._core.export_for_sync = lambda: ({}, 0.0)  # type: ignore[method-assign]

            def fake_network(_local, _since):
                calls.append("network")
                return {}, 0.0, 1

            svc._core.network_sync_records = fake_network  # type: ignore[method-assign]
            svc._core.apply_sync_records = lambda *_a: calls.append("apply")  # type: ignore[method-assign]
            svc._core.network_fetch_assignments = lambda: ([], 0.0, 0.0, {})  # type: ignore[method-assign]
            svc._core.apply_assignment_fetch = lambda *_a: None  # type: ignore[method-assign]
            svc.sync_now()
            self.assertTrue(svc.sync_busy)
            self.assertEqual(calls, [])
            QThreadPool.globalInstance().waitForDone(5000)
            for _ in range(20):
                QCoreApplication.processEvents()
            self.assertIn("network", calls)
            self.assertIn("apply", calls)
            self.assertFalse(svc.sync_busy)


class I18nPanelTitleTests(unittest.TestCase):
    def test_zh_panel_titles(self) -> None:
        from walle.i18n import set_language, tr

        set_language("zh")
        self.assertEqual(tr("panel.header"), "瓦力桌面助手")
        self.assertEqual(
            tr("panel.header.logged_in", account="+86 13800138000"),
            "+86 13800138000的瓦力桌面助手",
        )


class ContactBookTests(unittest.TestCase):
    def test_resolve_by_nickname(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            book = ContactBook(Path(td) / "contacts.json")
            book.set_contact("13800001111", "小明")
            self.assertEqual(book.resolve_recipient("小明"), "+86 13800001111")
            self.assertEqual(book.display_name("+86 13800001111"), "小明")

    def test_duplicate_nickname_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            book = ContactBook(Path(td) / "contacts.json")
            book.set_contact("13800001111", "小明")
            with self.assertRaises(SyncBackendError):
                book.set_contact("13800002222", "小明")

    def test_import_sync_records_clears_contacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            book = ContactBook(Path(td) / "contacts.json")
            book.set_contact("13800001111", "小明")
            book.import_sync_records([])
            self.assertEqual(book.list_contacts(), [])

    def test_export_import_sync_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            book = ContactBook(Path(td) / "contacts.json")
            book.set_contact("13800001111", "小明")
            rows = book.export_sync_records()
            other = ContactBook(Path(td) / "contacts2.json")
            other.import_sync_records(rows)
            self.assertEqual(other.list_contacts(), book.list_contacts())


class AccountIsolationTests(unittest.TestCase):
    def _make_core(self, tmp: Path) -> SyncCore:
        paths = SyncPaths(
            auth=tmp / "auth.json",
            sync_meta=tmp / "sync_meta.json",
            sync_config=tmp / "sync_config.json",
            assignments=tmp / "assignments.json",
            contacts=tmp / "contact_nicknames.json",
        )
        cfg = Config.__new__(Config)
        cfg._data = {"cloudbase_env_id": "live-env-id"}
        cfg.get = lambda key, default=None: cfg._data.get(key, default)  # type: ignore[method-assign]
        cfg.set = lambda key, value: cfg._data.__setitem__(key, value)  # type: ignore[method-assign]
        cfg.update = lambda values: cfg._data.update(values)  # type: ignore[method-assign]
        return SyncCore(
            paths=paths,
            config=cfg,
            todo=TodoManager(),
            notes=NotesManager(),
            reminders=ReminderManager(),
            tr=tr,
            enabled=True,
        )

    def test_empty_import_clears_notes_and_todos(self) -> None:
        todo = TodoManager()
        notes = NotesManager()
        todo.add("待删除")
        notes.add("待删除笔记")
        todo.import_sync_records([])
        notes.import_sync_records([])
        self.assertEqual(len(todo.tasks), 0)
        self.assertEqual(len(notes.entries), 0)

    def test_sync_meta_user_mismatch_resets_on_start(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            core = self._make_core(Path(td))
            core.auth.set_session(
                user_id="user-a",
                account="+86 13800000001",
                access_token="tok",
                refresh_token="ref",
                expires_in=3600,
            )
            core.engine._write_sync_meta(last_sync_at=time.time(), user_id="user-b")
            core.todo.add("串号待办")
            core.start()
            self.assertEqual(len(core.todo.tasks), 0)
            self.assertEqual(core.engine.sync_user_id, "user-a")

    def test_engine_exports_contacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = SyncPaths(
                auth=root / "auth.json",
                sync_meta=root / "sync_meta.json",
                sync_config=root / "sync_config.json",
                assignments=root / "assignments.json",
                contacts=root / "contact_nicknames.json",
            )
            cfg = Config.__new__(Config)
            cfg._data = {}
            cfg.get = lambda key, default=None: cfg._data.get(key, default)  # type: ignore[method-assign]
            cfg.set = lambda key, value: cfg._data.__setitem__(key, value)  # type: ignore[method-assign]
            cfg.update = lambda values: cfg._data.update(values)  # type: ignore[method-assign]
            contacts = ContactBook(paths.contacts)
            contacts.set_contact("13800001111", "同事")
            engine = SyncEngine(
                None,
                cfg,
                TodoManager(),
                NotesManager(),
                ReminderManager(),
                contacts,
                sync_meta_path=paths.sync_meta,
            )
            rows = engine.export_local()
            contact_rows = [r for r in rows.values() if r["collection"] == "contact"]
            self.assertEqual(len(contact_rows), 1)
            self.assertEqual(contact_rows[0]["payload"]["nickname"], "同事")


class AssignmentModelTests(unittest.TestCase):
    def test_from_cloud_accepts_document_id(self) -> None:
        row = {
            "_id": "asg-123",
            "title": "测试",
            "assigner_id": "user-a",
            "assignee_id": "user-b",
            "status": STATUS_PENDING,
        }
        assignment = Assignment.from_cloud(row)
        self.assertIsNotNone(assignment)
        assert assignment is not None
        self.assertEqual(assignment.id, "asg-123")


class PushOnlyRecoveryTests(unittest.TestCase):
    def _make_engine(self, tmp: Path) -> tuple[SyncEngine, MagicMock]:
        cfg = Config.__new__(Config)
        cfg._data = {}
        cfg.get = lambda key, default=None: cfg._data.get(key, default)  # type: ignore[method-assign]
        cfg.set = lambda key, value: cfg._data.__setitem__(key, value)  # type: ignore[method-assign]
        cfg.update = lambda values: cfg._data.update(values)  # type: ignore[method-assign]
        client = MagicMock()
        client.auth.is_logged_in = True
        client.auth.session = AuthSession(
            user_id="user-a",
            account="+86 13800000001",
            access_token="tok",
            refresh_token="ref",
            expires_at=time.time() + 3600,
        )
        client.fetch_changes.return_value = []
        todo = TodoManager()
        todo.add("待上传")
        engine = SyncEngine(
            client,
            cfg,
            todo,
            NotesManager(),
            ReminderManager(),
            ContactBook(tmp / "contacts.json"),
            sync_meta_path=tmp / "sync_meta.json",
        )
        return engine, client

    def test_network_push_only_requests_full_sync_when_cloud_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            engine, client = self._make_engine(Path(td))
            engine._write_sync_meta(last_sync_at=time.time() + 1000)
            local = engine.export_local()
            pushed, needs_full, _max_pushed = engine.network_push_only(local, engine._last_sync_at)
            self.assertEqual(pushed, 0)
            self.assertTrue(needs_full)
            client.upsert_records.assert_not_called()
            client.fetch_changes.assert_called_once_with(0)

    def test_network_push_only_uploads_without_false_ok_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            engine, client = self._make_engine(Path(td))
            local = engine.export_local()
            pushed, needs_full, max_pushed = engine.network_push_only(local, 0.0)
            self.assertGreater(pushed, 0)
            self.assertFalse(needs_full)
            self.assertGreater(max_pushed, 0)
            client.upsert_records.assert_called_once()

    def test_network_sync_recovers_when_cursor_ahead_of_cloud(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            engine, client = self._make_engine(Path(td))
            engine._write_sync_meta(last_sync_at=time.time() + 1000)
            local = engine.export_local()
            client.fetch_changes.return_value = []
            merged, _max_updated, _pushed = engine.network_sync(local, engine._last_sync_at)
            self.assertTrue(merged)
            client.upsert_records.assert_called_once()
            pushed_rows = client.upsert_records.call_args[0][0]
            self.assertGreater(len(pushed_rows), 0)


class ConfigSettingsSyncTests(unittest.TestCase):
    def test_get_returns_default_when_stored_null(self) -> None:
        from walle.config import DEFAULTS

        cfg = Config.__new__(Config)
        cfg._data = dict(DEFAULTS)
        cfg._data["work_minutes"] = None
        cfg.save = lambda: None  # type: ignore[method-assign]
        self.assertEqual(cfg.get("work_minutes"), 50)

    def test_update_bumps_settings_updated_at(self) -> None:
        from walle.config import DEFAULTS

        cfg = Config.__new__(Config)
        cfg._data = dict(DEFAULTS)
        cfg.save = lambda: None  # type: ignore[method-assign]
        before = float(cfg.get("settings_updated_at") or 0)
        cfg.update({"work_minutes": 42})
        after = float(cfg.get("settings_updated_at") or 0)
        self.assertGreater(after, before)
        self.assertEqual(cfg.get("work_minutes"), 42)


class DesktopSyncPlatformTests(unittest.TestCase):
    def test_macos_enables_desktop_sync(self) -> None:
        from walle.platform import is_desktop_sync_platform

        with patch("walle.platform.sys.platform", "darwin"):
            self.assertTrue(is_desktop_sync_platform())

    def test_windows_enables_desktop_sync(self) -> None:
        from walle.platform import is_desktop_sync_platform

        with patch("walle.platform.sys.platform", "win32"):
            self.assertTrue(is_desktop_sync_platform())

    def test_linux_disables_desktop_sync(self) -> None:
        from walle.platform import is_desktop_sync_platform

        with patch("walle.platform.sys.platform", "linux"):
            self.assertFalse(is_desktop_sync_platform())


class EnvChangeTests(unittest.TestCase):
    def test_changing_env_logs_out(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            paths = SyncPaths(
                auth=Path(td) / "auth.json",
                sync_meta=Path(td) / "sync_meta.json",
                sync_config=Path(td) / "sync_config.json",
                assignments=Path(td) / "assignments.json",
                contacts=Path(td) / "contacts.json",
            )
            cfg = Config.__new__(Config)
            cfg._data = {"cloudbase_env_id": "env-a"}
            cfg.get = lambda key, default=None: cfg._data.get(key, default)  # type: ignore[method-assign]
            cfg.set = lambda key, value: cfg._data.__setitem__(key, value)  # type: ignore[method-assign]
            cfg.update = lambda values: cfg._data.update(values)  # type: ignore[method-assign]
            cfg.save = lambda: None  # type: ignore[method-assign]
            core = SyncCore(
                paths=paths,
                config=cfg,
                todo=TodoManager(),
                notes=NotesManager(),
                reminders=ReminderManager(),
                tr=tr,
                enabled=True,
            )
            core.auth.set_session(
                user_id="u1",
                account="+86 13800000001",
                access_token="tok",
                refresh_token="ref",
                expires_in=3600,
            )
            core.backend = SyncBackendConfig(backend="cloudbase", cloudbase_env_id="env-a")
            core.save_cloudbase_env_id("env-b")
            self.assertFalse(core.is_logged_in)
            self.assertEqual(cfg._data["cloudbase_env_id"], "env-b")
            self.assertTrue(paths.sync_config.exists())


class CloudBaseAssignmentFetchTests(unittest.TestCase):
    def test_parse_document_promotes_id_from_underscore_id(self) -> None:
        doc = CloudBaseClient._parse_document({"_id": "abc", "title": "x"})
        self.assertEqual(doc.get("id"), "abc")

    def test_assignment_doc_id_fallback(self) -> None:
        self.assertEqual(
            CloudBaseClient._assignment_doc_id({"_id": "remote-1", "title": "t"}),
            "remote-1",
        )


class AssignmentNotifyTests(unittest.TestCase):
    def _assignment(self) -> Assignment:
        return Assignment(
            id="a1",
            title="写报告",
            assigner_id="user-a",
            assignee_id="user-b",
            assigner_phone="+86 13800000001",
            assignee_phone="+86 13800000002",
            assignee_note="太忙了",
            assigner_note="发错了",
        )

    def test_dispatched_inbox_uses_nickname(self) -> None:
        a = self._assignment()
        msgs = assignment_notify_messages(
            EVENT_DISPATCHED,
            a,
            user_id="user-b",
            display_name=lambda p: "老板" if "0001" in p else p,
            tr=tr,
        )
        self.assertEqual(len(msgs), 1)
        self.assertIn("老板", msgs[0])
        self.assertIn("写报告", msgs[0])

    def test_rejected_assigner_includes_note(self) -> None:
        a = self._assignment()
        msgs = assignment_notify_messages(
            EVENT_REJECTED,
            a,
            user_id="user-a",
            display_name=lambda p: p,
            tr=tr,
        )
        self.assertEqual(len(msgs), 1)
        self.assertIn("太忙了", msgs[0])


class AssignmentDispatchTests(unittest.TestCase):
    def _client_with_session(self, user_id: str, phone: str) -> MagicMock:
        client = MagicMock()
        session = AuthSession(
            user_id=user_id,
            account=phone,
            access_token="tok",
            refresh_token="ref",
            expires_at=time.time() + 3600,
        )
        client.auth.session = session
        return client

    def test_create_assignment_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "assignments.json"
            holder: dict[str, MagicMock] = {}

            def getter() -> MagicMock:
                return holder["client"]

            client = self._client_with_session("user-a", "+86 13800000001")
            client.find_user_by_phone.return_value = {
                "user_id": "user-b",
                "phone": "+86 13800000002",
            }
            holder["client"] = client
            mgr = AssignmentManager(getter, assignments_path=path)
            assignment = mgr.create("+86 13800000002", "测试任务", priority=1)
            self.assertEqual(assignment.status, STATUS_PENDING)
            self.assertEqual(assignment.assignee_id, "user-b")
            client.upsert_assignment.assert_called_once()
            payload = client.upsert_assignment.call_args[0][0]
            self.assertEqual(payload["title"], "测试任务")

    def test_cannot_assign_self(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "assignments.json"
            client = self._client_with_session("user-a", "+86 13800000001")
            client.find_user_by_phone.return_value = {
                "user_id": "user-a",
                "phone": "+86 13800000001",
            }
            mgr = AssignmentManager(lambda: client, assignments_path=path)
            with self.assertRaises(SyncBackendError) as ctx:
                mgr.create("13800000001", "给自己")
            self.assertIn("cannot_assign_self", str(ctx.exception))

    def test_assignee_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "assignments.json"
            client = self._client_with_session("user-a", "+86 13800000001")
            client.find_user_by_phone.return_value = None
            mgr = AssignmentManager(lambda: client, assignments_path=path)
            with self.assertRaises(SyncBackendError) as ctx:
                mgr.create("13999999999", "无人")
            self.assertIn("assignee_not_found", str(ctx.exception))

    def test_reject_requires_reason(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "assignments.json"
            client = self._client_with_session("user-b", "+86 13800000002")
            client.find_user_by_phone.return_value = None
            mgr = AssignmentManager(lambda: client, assignments_path=path)
            assignment = Assignment(
                id="x1",
                title="任务",
                assigner_id="user-a",
                assignee_id="user-b",
                status=STATUS_PENDING,
            )
            mgr._items[assignment.id] = assignment
            with self.assertRaises(SyncBackendError) as ctx:
                mgr.reject("x1", "")
            self.assertIn("empty_reject_reason", str(ctx.exception))

    def test_cancel_requires_reason(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "assignments.json"
            client = self._client_with_session("user-a", "+86 13800000001")
            mgr = AssignmentManager(lambda: client, assignments_path=path)
            assignment = Assignment(
                id="x2",
                title="任务",
                assigner_id="user-a",
                assignee_id="user-b",
                status=STATUS_PENDING,
            )
            mgr._items[assignment.id] = assignment
            with self.assertRaises(SyncBackendError) as ctx:
                mgr.cancel("x2", "")
            self.assertIn("empty_cancel_reason", str(ctx.exception))

    def _mgr_with_assignment(
        self,
        td: str,
        *,
        assigner: str = "user-a",
        assignee: str = "user-b",
        status: str = STATUS_PENDING,
        session_user: str = "user-b",
        session_phone: str = "+86 13800000002",
    ) -> tuple[AssignmentManager, Assignment, MagicMock]:
        path = Path(td) / "assignments.json"
        client = self._client_with_session(session_user, session_phone)
        assignment = Assignment(
            id="aid-1",
            title="联调任务",
            assigner_id=assigner,
            assignee_id=assignee,
            assigner_phone="+86 13800000001",
            assignee_phone="+86 13800000002",
            status=status,
        )
        mgr = AssignmentManager(lambda: client, assignments_path=path)
        mgr._items[assignment.id] = assignment
        return mgr, assignment, client

    def test_accept_emits_event_and_updates_cloud(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            events: list[str] = []
            mgr, assignment, client = self._mgr_with_assignment(td)
            mgr._on_event = lambda kind, _a: events.append(kind)
            updated = mgr.accept(assignment.id)
            self.assertEqual(updated.status, STATUS_ACCEPTED)
            self.assertEqual(events, [EVENT_ACCEPTED])
            client.upsert_assignment.assert_called_once()

    def test_reject_with_reason(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr, assignment, client = self._mgr_with_assignment(td)
            updated = mgr.reject(assignment.id, "时间不够")
            self.assertEqual(updated.status, STATUS_REJECTED)
            self.assertEqual(updated.assignee_note, "时间不够")
            client.upsert_assignment.assert_called_once()

    def test_complete_after_accept(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr, assignment, _client = self._mgr_with_assignment(td, status=STATUS_ACCEPTED)
            updated = mgr.complete(assignment.id)
            self.assertEqual(updated.status, STATUS_COMPLETED)
            self.assertIsNotNone(updated.completed_at)

    def test_cancel_with_reason(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr, assignment, client = self._mgr_with_assignment(
                td, session_user="user-a", session_phone="+86 13800000001"
            )
            updated = mgr.cancel(assignment.id, "发错了")
            self.assertEqual(updated.status, STATUS_CANCELLED)
            self.assertEqual(updated.assigner_note, "发错了")
            client.upsert_assignment.assert_called_once()

    def test_dismiss_and_clear_archive(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "assignments.json"
            client = self._client_with_session("user-b", "+86 13800000002")
            mgr = AssignmentManager(lambda: client, assignments_path=path)
            done = Assignment(
                id="done-1",
                title="已完成",
                assigner_id="user-a",
                assignee_id="user-b",
                status=STATUS_COMPLETED,
            )
            active = Assignment(
                id="active-1",
                title="进行中",
                assigner_id="user-a",
                assignee_id="user-b",
                status=STATUS_PENDING,
            )
            rejected = Assignment(
                id="reject-1",
                title="已退回",
                assigner_id="user-a",
                assignee_id="user-b",
                status=STATUS_REJECTED,
            )
            mgr._items[done.id] = done
            mgr._items[active.id] = active
            mgr._items[rejected.id] = rejected
            self.assertEqual(len(mgr.inbox), 2)
            self.assertEqual(len(mgr.archive_inbox), 1)
            mgr.dismiss(done.id, role="inbox")
            self.assertEqual(len(mgr.inbox), 2)
            self.assertEqual(len(mgr.archive_inbox), 0)
            cleared = mgr.clear_archive()
            self.assertEqual(cleared, 0)
            with self.assertRaises(SyncBackendError) as ctx:
                mgr.dismiss(active.id, role="inbox")
            self.assertIn("assignment_not_finished", str(ctx.exception))
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("done-1", raw.get("dismissed_ids", []))

    def test_complete_requires_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr, assignment, _client = self._mgr_with_assignment(td)
            with self.assertRaises(SyncBackendError) as ctx:
                mgr.complete(assignment.id)
            self.assertIn("forbidden_action", str(ctx.exception))

    def test_empty_title_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "assignments.json"
            client = self._client_with_session("user-a", "+86 13800000001")
            client.find_user_by_phone.return_value = {"user_id": "user-b", "phone": "+86 13800000002"}
            mgr = AssignmentManager(lambda: client, assignments_path=path)
            with self.assertRaises(SyncBackendError) as ctx:
                mgr.create("13800000002", "   ")
            self.assertIn("empty_title", str(ctx.exception))

    def test_sync_emits_inbox_event_on_remote_pending(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "assignments.json"
            client = self._client_with_session("user-b", "+86 13800000002")
            mgr = AssignmentManager(lambda: client, assignments_path=path)
            mgr._last_sync_at = time.time() - 60
            now = time.time()
            client.fetch_assignment_changes.return_value = [
                {
                    "id": "remote-1",
                    "title": "远程派发",
                    "assigner_id": "user-a",
                    "assignee_id": "user-b",
                    "assigner_phone": "+86 13800000001",
                    "assignee_phone": "+86 13800000002",
                    "status": STATUS_PENDING,
                    "updated_at": now,
                    "created_at": now,
                }
            ]
            events: list[str] = []
            mgr._on_event = lambda kind, _a: events.append(kind)
            mgr.sync()
            self.assertEqual(events, [EVENT_DISPATCHED])
            self.assertIn("remote-1", mgr._items)

    def test_inbox_outbox_filter(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr, assignment, _client = self._mgr_with_assignment(td)
            mgr._items["out-1"] = Assignment(
                id="out-1",
                title="发出",
                assigner_id="user-b",
                assignee_id="user-a",
                status=STATUS_PENDING,
            )
            assignment.assigner_id = "user-a"
            assignment.assignee_id = "user-b"
            inbox = mgr.inbox
            outbox = mgr.outbox
            self.assertEqual(len(inbox), 1)
            self.assertEqual(inbox[0].id, assignment.id)
            self.assertEqual(len(outbox), 1)
            self.assertEqual(outbox[0].id, "out-1")
            completed = Assignment(
                id="done-inbox",
                title="已完成收件",
                assigner_id="user-a",
                assignee_id="user-b",
                status=STATUS_COMPLETED,
            )
            mgr._items[completed.id] = completed
            self.assertEqual(len(mgr.inbox), 1)
            self.assertEqual(len(mgr.archive_inbox), 1)
            self.assertEqual(mgr.archive_inbox[0].id, "done-inbox")

    def test_accepted_inbox_outbox_badges(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr, assignment, _client = self._mgr_with_assignment(td)
            assignment.status = STATUS_ACCEPTED
            assignment.priority = 0
            out_accepted = Assignment(
                id="out-accepted",
                title="已接受派出",
                assigner_id="user-a",
                assignee_id="user-b",
                status=STATUS_ACCEPTED,
                priority=2,
            )
            mgr._items[out_accepted.id] = out_accepted
            self.assertEqual(mgr.accepted_inbox_priorities(), [0])
            self.assertEqual(len(mgr.inbox_panel), 0)
            self.assertEqual(mgr.accepted_outbox_priorities(), [2])
            pending_only = Assignment(
                id="pending-inbox",
                title="待处理",
                assigner_id="user-c",
                assignee_id="user-b",
                status=STATUS_PENDING,
                priority=2,
            )
            mgr._items[pending_only.id] = pending_only
            self.assertEqual(len(mgr.inbox_panel), 1)
            self.assertEqual(mgr.accepted_inbox_priorities(), [0])

    def test_dismiss_rejected_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "assignments.json"
            client = self._client_with_session("user-a", "+86 13800000001")
            mgr = AssignmentManager(lambda: client, assignments_path=path)
            rejected = Assignment(
                id="rej-1",
                title="已退回",
                assigner_id="user-a",
                assignee_id="user-b",
                status=STATUS_REJECTED,
            )
            mgr._items[rejected.id] = rejected
            self.assertTrue(AssignmentManager.is_dismissible(rejected))
            mgr.dismiss(rejected.id, role="outbox")
            self.assertEqual(len(mgr.outbox_panel), 0)


class AssignmentNotifyFullTests(unittest.TestCase):
    def _assignment(self, **kwargs) -> Assignment:
        base = dict(
            id="a1",
            title="写报告",
            assigner_id="user-a",
            assignee_id="user-b",
            assigner_phone="+86 13800000001",
            assignee_phone="+86 13800000002",
            assignee_note="太忙",
            assigner_note="发错了",
        )
        base.update(kwargs)
        return Assignment(**base)

    def test_all_status_notifications_non_empty(self) -> None:
        a = self._assignment()
        cases = [
            (EVENT_DISPATCHED, "user-b", 1),
            (EVENT_DISPATCHED, "user-a", 1),
            (EVENT_ACCEPTED, "user-a", 1),
            (EVENT_ACCEPTED, "user-b", 1),
            (EVENT_REJECTED, "user-a", 1),
            (EVENT_COMPLETED, "user-a", 1),
            (EVENT_COMPLETED, "user-b", 1),
            (EVENT_WITHDRAWN, "user-b", 1),
            (EVENT_WITHDRAWN, "user-a", 1),
        ]
        for kind, uid, expected in cases:
            msgs = assignment_notify_messages(
                kind, a, user_id=uid, display_name=lambda p: p, tr=tr
            )
            self.assertEqual(len(msgs), expected, msg=f"{kind} for {uid}")

    def test_unrelated_user_gets_no_message(self) -> None:
        a = self._assignment()
        msgs = assignment_notify_messages(
            EVENT_DISPATCHED, a, user_id="user-x", display_name=lambda p: p, tr=tr
        )
        self.assertEqual(msgs, [])


def _load_env_id() -> str:
    if not CONFIG_PATH.exists():
        return ""
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
        return str(data.get("cloudbase_env_id", "") or "").strip()
    except (json.JSONDecodeError, OSError):
        return ""


def _load_session_phone() -> tuple[bool, str, list[str]]:
    if not AUTH_PATH.exists():
        return False, "", ["未找到 auth.json"]
    try:
        raw = json.loads(AUTH_PATH.read_text(encoding="utf-8-sig"))
        account = str(raw.get("account") or raw.get("phone") or "")
        access = str(raw.get("access_token") or "")
        refresh = str(raw.get("refresh_token") or "")
        user_id = str(raw.get("user_id") or "")
        issues: list[str] = []
        if len(access) < 20:
            issues.append("access_token 过短或无效，请重新登录")
        if len(refresh) < 20:
            issues.append("refresh_token 过短或无效，请重新登录")
        if len(user_id) < 8:
            issues.append("user_id 异常，请重新登录")
        ok = bool(account and access and not issues)
        return ok, account, issues
    except (json.JSONDecodeError, OSError):
        return False, "", ["auth.json 无法解析"]


def run_live_checks() -> list[str]:
    """对真实 CloudBase 做只读/可控写入探测，不打印密钥。"""
    results: list[str] = []
    env_id = _load_env_id()
    if not env_id:
        results.append("[SKIP] 联机：未配置 cloudbase_env_id")
        return results

    results.append(f"[OK] 联机：已配置授权码（{env_id[:8]}…）")
    logged_in, phone, auth_issues = _load_session_phone()
    if auth_issues:
        for issue in auth_issues:
            results.append(f"[WARN] 联机：{issue}")
    if not logged_in:
        results.append("[SKIP] 联机：会话无效，请在 WALL-E 账号页重新登录后再测")
        return results
    results.append(f"[OK] 联机：已登录 {_mask_phone(phone)}")

    cfg = SyncBackendConfig(cloudbase_env_id=env_id)
    auth = AuthManager(AUTH_PATH)
    client = CloudBaseClient(cfg, auth, sync_meta_path=get_data_dir() / "sync_meta.json")

    if logged_in:
        try:
            token = client.ensure_token()
            results.append("[OK] 联机：access_token 有效" if len(token) >= 20 else "[FAIL] 联机：token 过短")
        except SyncBackendError as exc:
            results.append(f"[FAIL] 联机：token 刷新失败 — {exc}")
            return results

        try:
            client.fetch_assignment_changes(auth.session.user_id, 0)  # type: ignore[union-attr]
            results.append("[OK] 联机：task_assignments 查询成功")
        except SyncBackendError as exc:
            results.append(f"[FAIL] 联机：task_assignments 查询失败 — {exc}")
            results.append("[HINT] 请确认已创建 task_assignments 集合并配置安全规则（见 CLOUDBASE_SETUP.md）")

    test_phone = os.environ.get("WALLE_TEST_PHONE", "").strip()
    sms_code = os.environ.get("WALLE_TEST_SMS_CODE", "").strip()
    if test_phone:
        with tempfile.TemporaryDirectory() as td:
            paths = SyncPaths(
                auth=Path(td) / "auth.json",
                sync_meta=Path(td) / "sync_meta.json",
                sync_config=Path(td) / "sync_config.json",
                assignments=Path(td) / "assignments.json",
                contacts=Path(td) / "contact_nicknames.json",
            )
            cfg_obj = Config.__new__(Config)
            cfg_obj._data = {"cloudbase_env_id": env_id}
            cfg_obj.get = lambda key, default=None: cfg_obj._data.get(key, default)  # type: ignore[method-assign]
            cfg_obj.set = lambda key, value: cfg_obj._data.__setitem__(key, value)  # type: ignore[method-assign]
            core = SyncCore(
                paths=paths,
                config=cfg_obj,
                todo=TodoManager(),
                notes=NotesManager(),
                reminders=ReminderManager(),
                tr=tr,
                enabled=True,
            )
            ok, msg = core.send_sms_code(test_phone)
            if ok:
                results.append(f"[OK] 联机：已向 {_mask_phone(test_phone)} 发送验证码")
            else:
                results.append(f"[FAIL] 联机：发送验证码失败 — {msg}")
                return results

            if sms_code:
                ok, msg = core.login_with_sms_code(test_phone, sms_code)
                if ok:
                    results.append(f"[OK] 联机：验证码登录成功 {_mask_phone(test_phone)}")
                else:
                    results.append(f"[FAIL] 联机：验证码登录失败 — {msg}")
            else:
                results.append("[INFO] 联机：已发送验证码，设置 WALLE_TEST_SMS_CODE 可完成登录验证")

    assign_phone = os.environ.get("WALLE_ASSIGN_PHONE", "").strip()
    if logged_in and assign_phone:
        try:
            target = client.find_user_by_phone(assign_phone)
            if not target:
                results.append(f"[FAIL] 联机：派发目标 {_mask_phone(assign_phone)} 未在 user_profiles 中找到")
            elif str(target.get("user_id")) == auth.session.user_id:  # type: ignore[union-attr]
                results.append("[SKIP] 联机：派发目标与当前账号相同，跳过写入")
            else:
                title = f"WALL-E验证-{int(time.time())}"
                with tempfile.TemporaryDirectory() as td:
                    path = Path(td) / "assignments.json"
                    mgr = AssignmentManager(lambda: client, assignments_path=path)
                    assignment = mgr.create(assign_phone, title, priority=1)
                    results.append(f"[OK] 联机：任务派发成功 id={assignment.id[:8]}…")
                    mgr.sync()
                    results.append("[OK] 联机：派发后 sync 拉取成功")
        except SyncBackendError as exc:
            results.append(f"[FAIL] 联机：任务派发失败 — {exc}")
    elif logged_in:
        results.append("[INFO] 联机：设置 WALLE_ASSIGN_PHONE 可验证真实派发")

    reg_phone = os.environ.get("WALLE_REGISTER_PHONE", "").strip()
    reg_code = os.environ.get("WALLE_REGISTER_SMS_CODE", "").strip()
    reg_password = os.environ.get("WALLE_REGISTER_PASSWORD", "TestPass123").strip()
    if reg_phone:
        with tempfile.TemporaryDirectory() as td:
            paths = SyncPaths(
                auth=Path(td) / "auth.json",
                sync_meta=Path(td) / "sync_meta.json",
                sync_config=Path(td) / "sync_config.json",
                assignments=Path(td) / "assignments.json",
                contacts=Path(td) / "contact_nicknames.json",
            )
            cfg_obj = Config.__new__(Config)
            cfg_obj._data = {"cloudbase_env_id": env_id}
            cfg_obj.get = lambda key, default=None: cfg_obj._data.get(key, default)  # type: ignore[method-assign]
            cfg_obj.set = lambda key, value: cfg_obj._data.__setitem__(key, value)  # type: ignore[method-assign]
            core = SyncCore(
                paths=paths,
                config=cfg_obj,
                todo=TodoManager(),
                notes=NotesManager(),
                reminders=ReminderManager(),
                tr=tr,
                enabled=True,
            )
            ok, msg = core.send_register_sms(reg_phone)
            if ok:
                results.append(f"[OK] 联机：已向 {_mask_phone(reg_phone)} 发送注册验证码")
            else:
                results.append(f"[FAIL] 联机：发送注册验证码失败 — {msg}")
                return results

            if reg_code:
                ok, msg = core.register(reg_phone, reg_password, reg_code)
                if ok:
                    results.append(f"[OK] 联机：注册成功 {_mask_phone(reg_phone)}")
                    if paths.auth.exists():
                        raw = json.loads(paths.auth.read_text(encoding="utf-8-sig"))
                        if len(str(raw.get("access_token", ""))) >= 20:
                            results.append("[OK] 联机：注册后会话 token 有效")
                        else:
                            results.append("[FAIL] 联机：注册后会话 token 异常")
                else:
                    results.append(f"[FAIL] 联机：注册失败 — {msg}")
            else:
                results.append("[INFO] 联机：已发送注册验证码，设置 WALLE_REGISTER_SMS_CODE 可完成注册验证")
    else:
        results.append("[INFO] 联机：设置 WALLE_REGISTER_PHONE 可验证自助注册")

    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="执行 CloudBase 联机探测")
    args = parser.parse_args()

    print("=== 单元测试 ===")
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        print("\n单元测试未全部通过。")
        return 1

    if args.live:
        print("\n=== CloudBase 联机探测 ===")
        for line in run_live_checks():
            print(line)

    print("\n全部单元测试通过 OK")
    if not args.live:
        print("提示：运行 `python scripts/verify_sync_login_dispatch.py --live` 进行联机验证")

    print("\n=== Dry-run 集成测试 ===")
    dryrun_path = ROOT / "scripts" / "dryrun_sync_dispatch.py"
    import importlib.util

    spec = importlib.util.spec_from_file_location("dryrun_sync_dispatch", dryrun_path)
    if spec is None or spec.loader is None:
        print("[FAIL] 无法加载 dryrun_sync_dispatch.py")
        return 1
    dryrun = importlib.util.module_from_spec(spec)
    sys.modules["dryrun_sync_dispatch"] = dryrun
    spec.loader.exec_module(dryrun)
    dryrun_results = dryrun.run_all_scenarios()
    dryrun_results.append(dryrun.run_service_phased_dryrun())
    failed = [r for r in dryrun_results if not r.ok]
    passed = sum(1 for r in dryrun_results if r.ok)
    for r in dryrun_results:
        mark = "OK" if r.ok else "FAIL"
        print(f"[{mark}] {r.name}")
        if r.detail:
            for line in r.detail.strip().splitlines():
                print(f"       {line}")
    print(f"\nDry-run 合计: {passed}/{len(dryrun_results)} 通过")
    if failed:
        print("\nDry-run 集成测试未全部通过。")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
