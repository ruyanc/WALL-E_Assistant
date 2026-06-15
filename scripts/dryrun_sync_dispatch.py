"""Dry-run 集成测试：内存模拟 CloudBase，验证用户信息同步与任务派发/接收。

不访问真实 CloudBase，覆盖：
  - 双设备同账号数据同步（待办/笔记/联系人/设置）
  - 账号切换隔离、退出登录保留本地数据
  - user_profiles 写入与按手机号查找
  - A 派发 → B 收件箱 → B 接受 → A 发件箱状态更新
  - 旧版云端文档（无 user_id 字段）拉取
  - 分阶段同步（export / network / apply）与 sync_now 结果一致

用法：
  python scripts/dryrun_sync_dispatch.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from walle.config import Config  # noqa: E402
from walle.i18n import tr  # noqa: E402
from walle.notes_manager import NotesManager  # noqa: E402
from walle.reminder_manager import ReminderManager  # noqa: E402
from walle.sync.assignment_models import STATUS_ACCEPTED, STATUS_PENDING  # noqa: E402
from walle.sync.auth import AuthManager, AuthSession  # noqa: E402
from walle.sync.backend import SyncBackendConfig  # noqa: E402
from walle.sync.cloudbase_client import CloudBaseClient, TASK_ASSIGNMENTS, USER_PROFILES  # noqa: E402
from walle.sync.core import SyncCore  # noqa: E402
from walle.sync.engine import SETTINGS_RECORD_ID, SYNC_SETTINGS_KEYS  # noqa: E402
from walle.sync.merge import row_key  # noqa: E402
from walle.sync.paths import SyncPaths  # noqa: E402
from walle.sync.phone import normalize_phone  # noqa: E402
from walle.todo_manager import TodoManager  # noqa: E402


@dataclass
class ScenarioResult:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class InMemoryCloud:
    """共享「云端」存储，按 user_id / _owner_user_id 隔离。"""

    sync_docs: dict[str, dict[str, Any]] = field(default_factory=dict)
    assignments: dict[str, dict[str, Any]] = field(default_factory=dict)
    profiles: dict[str, dict[str, Any]] = field(default_factory=dict)
    auth_by_phone: dict[str, str] = field(default_factory=dict)

    def register_user(self, user_id: str, phone: str) -> None:
        normalized = normalize_phone(phone) or phone
        self.auth_by_phone[normalized] = user_id
        self.profiles[user_id] = {
            "user_id": user_id,
            "phone": normalized,
            "display_name": normalized,
            "updated_at": time.time(),
        }


class DryRunCloudClient:
    """可注入 SyncCore 的 CloudBase 模拟客户端。"""

    def __init__(self, cloud: InMemoryCloud, auth: AuthManager) -> None:
        self.cloud = cloud
        self.auth = auth
        self.config = SyncBackendConfig(cloudbase_env_id="dryrun-env")

    @property
    def db_base(self) -> str:
        return "dryrun/sync_records"

    def _session_user_id(self) -> str:
        session = self.auth.session
        return str(session.user_id).strip() if session else ""

    def upsert_user_profile(self, phone: str) -> None:
        session = self.auth.session
        if session is None:
            return
        normalized = normalize_phone(phone) or normalize_phone(session.account)
        if not normalized:
            return
        self.cloud.register_user(session.user_id, normalized)
        self.cloud.profiles[session.user_id] = {
            "user_id": session.user_id,
            "phone": normalized,
            "display_name": normalized,
            "updated_at": time.time(),
        }

    def find_user_by_phone(self, phone: str) -> dict[str, Any] | None:
        variants = {normalize_phone(phone), phone.strip()}
        for variant in variants:
            if not variant:
                continue
            uid = self.cloud.auth_by_phone.get(variant)
            if uid:
                profile = dict(self.cloud.profiles.get(uid, {}))
                profile["user_id"] = uid
                return profile
        local_digits = "".join(c for c in phone if c.isdigit())[-11:]
        for uid, profile in self.cloud.profiles.items():
            p = str(profile.get("phone", ""))
            if local_digits and local_digits in p:
                row = dict(profile)
                row["user_id"] = uid
                return row
        return None

    def fetch_changes(self, since: float) -> list[dict[str, Any]]:
        user_id = self._session_user_id()
        rows: list[dict[str, Any]] = []
        for doc in self.cloud.sync_docs.values():
            doc_user = str(doc.get("user_id", "") or "").strip()
            owner = str(doc.get("_owner_user_id", "") or "").strip()
            if doc_user and doc_user != user_id:
                continue
            if not doc_user and owner and owner != user_id:
                continue
            try:
                updated_at = float(doc.get("updated_at", 0))
            except (TypeError, ValueError):
                updated_at = 0.0
            if since > 0 and updated_at <= since:
                continue
            row = CloudBaseClient._normalize_sync_row(doc)
            if row:
                rows.append(row)
        return rows

    def upsert_records(self, rows: list[dict[str, Any]]) -> None:
        user_id = self._session_user_id()
        for row in rows:
            collection = str(row["collection"])
            record_id = str(row["record_id"])
            doc_id = CloudBaseClient._scoped_doc_id(user_id, collection, record_id)
            self.cloud.sync_docs[doc_id] = {
                "user_id": user_id,
                "_owner_user_id": user_id,
                "record_id": record_id,
                "collection": collection,
                "payload": row.get("payload") or {},
                "updated_at": float(row["updated_at"]),
                "deleted": bool(row.get("deleted", False)),
            }

    def fetch_assignment_changes(self, user_id: str, since: float) -> list[dict[str, Any]]:
        user_id = str(user_id or "").strip()
        if not user_id:
            return []
        merged: dict[str, dict[str, Any]] = {}
        for doc in self.cloud.assignments.values():
            assigner = str(doc.get("assigner_id", "") or "").strip()
            assignee = str(doc.get("assignee_id", "") or "").strip()
            if user_id not in (assigner, assignee):
                continue
            try:
                updated_at = float(doc.get("updated_at", 0))
            except (TypeError, ValueError):
                updated_at = 0.0
            if since > 0 and updated_at <= since:
                continue
            aid = CloudBaseClient._assignment_doc_id(doc)
            if aid:
                merged[aid] = doc
        return list(merged.values())

    def upsert_assignment(self, payload: dict[str, Any]) -> None:
        assignment_id = str(payload["id"])
        body = dict(payload)
        body["id"] = assignment_id
        body.setdefault("assignment_id", assignment_id)
        self.cloud.assignments[assignment_id] = body


def _set_data_paths(root: Path, suffix: str) -> None:
    """各 Manager 在 import 时绑定了 PATH 常量，需同步 patch 多个模块。"""
    import walle.config as cfg_mod
    import walle.notes_manager as notes_mod
    import walle.reminder_manager as rem_mod
    import walle.todo_manager as todo_mod

    mapping = {
        "CONFIG_PATH": root / f"settings{suffix}.json",
        "TODO_PATH": root / f"todos{suffix}.json",
        "NOTES_PATH": root / f"notes{suffix}.json",
        "NOTES_LEGACY_PATH": root / f"notes{suffix}.txt",
        "REMINDERS_PATH": root / f"reminders{suffix}.json",
    }
    for key, path in mapping.items():
        setattr(cfg_mod, key, path)
        for mod in (todo_mod, notes_mod, rem_mod):
            if hasattr(mod, key):
                setattr(mod, key, path)


@contextmanager
def isolated_data_dir(tmp: Path):
    import walle.config as cfg_mod
    import walle.notes_manager as notes_mod
    import walle.reminder_manager as rem_mod
    import walle.todo_manager as todo_mod

    keys = ("CONFIG_PATH", "TODO_PATH", "NOTES_PATH", "NOTES_LEGACY_PATH", "REMINDERS_PATH")
    old = {key: getattr(cfg_mod, key) for key in keys}
    _set_data_paths(tmp, "")
    try:
        yield
    finally:
        for key, value in old.items():
            setattr(cfg_mod, key, value)
            for mod in (todo_mod, notes_mod, rem_mod):
                if hasattr(mod, key):
                    setattr(mod, key, value)


def _ensure_empty_local_store(root: Path, suffix: str) -> None:
    """避免 TodoManager 在文件不存在时写入示例种子数据。"""
    empty_tasks = json.dumps({"tasks": []}, ensure_ascii=False, indent=2)
    empty_notes = json.dumps({"entries": []}, ensure_ascii=False, indent=2)
    empty_reminders = json.dumps({"reminders": []}, ensure_ascii=False, indent=2)
    empty_settings = json.dumps(
        {"work_minutes": 50, "rest_minutes": 10, "cycles": 3, "settings_updated_at": 0.0},
        ensure_ascii=False,
        indent=2,
    )
    (root / f"todos{suffix}.json").write_text(empty_tasks + "\n", encoding="utf-8")
    (root / f"notes{suffix}.json").write_text(empty_notes + "\n", encoding="utf-8")
    (root / f"reminders{suffix}.json").write_text(empty_reminders + "\n", encoding="utf-8")
    if not (root / f"settings{suffix}.json").exists():
        (root / f"settings{suffix}.json").write_text(empty_settings + "\n", encoding="utf-8")


def _make_config(env_id: str = "dryrun-env") -> Config:
    from walle.config import DEFAULTS

    cfg = Config.__new__(Config)
    cfg._data = dict(DEFAULTS)
    cfg._data["cloudbase_env_id"] = env_id
    cfg._data["settings_updated_at"] = 0.0
    cfg.get = Config.get.__get__(cfg, Config)  # type: ignore[method-assign]
    cfg.set = Config.set.__get__(cfg, Config)  # type: ignore[method-assign]
    cfg.update = Config.update.__get__(cfg, Config)  # type: ignore[method-assign]
    cfg.save = lambda: None  # type: ignore[method-assign]
    cfg.load = lambda: None  # type: ignore[method-assign]
    return cfg


def _make_core(
    root: Path,
    cloud: InMemoryCloud,
    *,
    user_id: str,
    phone: str,
    suffix: str = "",
) -> SyncCore:
    _set_data_paths(root, suffix)
    _ensure_empty_local_store(root, suffix)

    paths = SyncPaths(
        auth=root / f"auth{suffix}.json",
        sync_meta=root / f"sync_meta{suffix}.json",
        sync_config=root / "sync_config.json",
        assignments=root / f"assignments{suffix}.json",
        contacts=root / f"contacts{suffix}.json",
    )
    cfg = _make_config()
    auth = AuthManager(paths.auth)
    auth.set_session(
        user_id=user_id,
        account=phone,
        access_token=f"tok-{user_id}",
        refresh_token=f"ref-{user_id}",
        expires_in=7200,
    )
    cloud.register_user(user_id, phone)
    client = DryRunCloudClient(cloud, auth)

    core = SyncCore(
        paths=paths,
        config=cfg,
        todo=TodoManager(),
        notes=NotesManager(),
        reminders=ReminderManager(),
        tr=tr,
        enabled=True,
    )
    core.auth = auth
    core.client = client
    core.engine.client = client
    core.engine.bind_sync_user(user_id)
    core.assignments.reset_sync_cursor()
    return core


def _login_as(core: SyncCore, cloud: InMemoryCloud, user_id: str, phone: str) -> None:
    previous_uid = core.auth.session.user_id if core.auth.session else None
    previous_account = core.auth.phone
    auth = core.auth
    auth.set_session(
        user_id=user_id,
        account=phone,
        access_token=f"tok-{user_id}",
        refresh_token=f"ref-{user_id}",
        expires_in=7200,
    )
    cloud.register_user(user_id, phone)
    client = DryRunCloudClient(cloud, auth)
    core.client = client
    core.engine.client = client
    if previous_uid and previous_uid != user_id:
        core._reset_local_user_data()
    elif auth.session:
        core.engine.bind_sync_user(user_id)
    core.assignments.reset_sync_cursor()


def _run(name: str, fn: Callable[[], None]) -> ScenarioResult:
    try:
        fn()
        return ScenarioResult(name, True)
    except AssertionError as exc:
        return ScenarioResult(name, False, str(exc) or "断言失败")
    except Exception as exc:
        return ScenarioResult(name, False, f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")


def scenario_same_user_two_devices(cloud: InMemoryCloud, root: Path) -> None:
    phone = "+86 13800000001"
    uid = "user-a"
    dev1 = _make_core(root, cloud, user_id=uid, phone=phone, suffix="_d1")
    dev1.todo.add("设备1待办")
    dev1.notes.add("设备1笔记")
    dev1.contacts.set_contact("13800000002", "同事B")
    dev1.config.set("work_minutes", 42)
    dev1.config.set("settings_updated_at", time.time())
    dev1.sync_now()

    dev2 = _make_core(root, cloud, user_id=uid, phone=phone, suffix="_d2")
    assert len(dev2.todo.tasks) == 0, (
        f"设备2初始应为空，实际 {len(dev2.todo.tasks)} 条: "
        f"{[t.text for t in dev2.todo.tasks]}"
    )
    dev2.sync_now()

    texts = [t.text for t in dev2.todo.tasks]
    assert "设备1待办" in texts, f"设备2未拉到待办: {texts}"
    note_texts = [e.text for e in dev2.notes.entries]
    assert any("设备1笔记" in (t or "") for t in note_texts), f"设备2未拉到笔记: {note_texts}"
    assert dev2.contacts.display_name("+86 13800000002") == "同事B"
    assert dev2.config.get("work_minutes") == 42


def scenario_account_switch_isolation(cloud: InMemoryCloud, root: Path) -> None:
    core = _make_core(root, cloud, user_id="user-a", phone="+86 13800000001", suffix="_iso")
    core.todo.add("A的秘密待办")
    core.sync_now()
    assert len(cloud.sync_docs) >= 1

    _login_as(core, cloud, "user-b", "+86 13800000002")
    assert len(core.todo.tasks) == 0, "切换到 B 后应清空 A 的本地待办"
    core.sync_now()
    texts = [t.text for t in core.todo.tasks]
    assert "A的秘密待办" not in texts, "B 不应看到 A 的待办"


def scenario_logout_keeps_local(cloud: InMemoryCloud, root: Path) -> None:
    core = _make_core(root, cloud, user_id="user-a", phone="+86 13800000001", suffix="_logout")
    core.todo.add("退出后保留")
    core.sync_now()
    core.logout()
    assert len(core.todo.tasks) == 1, f"退出后待办应保留，实际 {len(core.todo.tasks)} 条"
    assert core.todo.tasks[0].text == "退出后保留"
    assert not core.is_logged_in


def scenario_user_profile_lookup(cloud: InMemoryCloud, root: Path) -> None:
    core_a = _make_core(root, cloud, user_id="user-a", phone="+86 13800000001", suffix="_prof_a")
    core_a.sync_now()
    assert "user-a" in cloud.profiles

    core_b = _make_core(root, cloud, user_id="user-b", phone="+86 13800000002", suffix="_prof_b")
    target = core_b.client.find_user_by_phone("13800000001")
    assert target is not None
    assert target["user_id"] == "user-a"


def scenario_dispatch_receive_accept(cloud: InMemoryCloud, root: Path) -> None:
    core_a = _make_core(root, cloud, user_id="user-a", phone="+86 13800000001", suffix="_disp_a")
    core_b = _make_core(root, cloud, user_id="user-b", phone="+86 13800000002", suffix="_disp_b")
    core_a.contacts.set_contact("13800000002", "接收人")
    core_a.sync_now()
    core_b.sync_now()

    core_a.dispatch_assignment("接收人", "跨账号任务", priority=1)
    assert len(core_a.assignments.outbox) == 1
    assert len(cloud.assignments) == 1

    assert len(core_b.assignments.inbox) == 0, "B 同步前应无本地收件"
    core_b.sync_now()
    inbox = core_b.assignments.inbox
    assert len(inbox) == 1, f"B 收件箱应有 1 条，实际 {len(inbox)}"
    assert inbox[0].title == "跨账号任务"
    assert inbox[0].status == STATUS_PENDING

    assignment_id = inbox[0].id
    core_b.accept_assignment(assignment_id)
    assert core_b.assignments.inbox[0].status == STATUS_ACCEPTED

    core_a.sync_now()
    outbox = core_a.assignments.outbox
    assert len(outbox) == 1
    assert outbox[0].status == STATUS_ACCEPTED, "A 发件箱应看到 B 已接受"


def scenario_assignment_sync_only_receive(cloud: InMemoryCloud, root: Path) -> None:
    core_a = _make_core(root, cloud, user_id="user-a", phone="+86 13800000001", suffix="_only_a")
    core_b = _make_core(root, cloud, user_id="user-b", phone="+86 13800000002", suffix="_only_b")
    core_a.contacts.set_contact("13800000002", "接收人")
    core_a.sync_now()
    core_b.sync_now()
    core_a.dispatch_assignment("接收人", "仅拉派发", priority=1)
    assert len(core_b.assignments.inbox) == 0
    core_b.sync_assignments_only()
    inbox = core_b.assignments.inbox
    assert len(inbox) == 1, f"B 应用 sync_assignments_only 后应有 1 条，实际 {len(inbox)}"
    assert inbox[0].title == "仅拉派发"


def scenario_settings_update_syncs(cloud: InMemoryCloud, root: Path) -> None:
    core = _make_core(root, cloud, user_id="user-a", phone="+86 13800000001", suffix="_settings")
    core.sync_now()
    core.config.update({"work_minutes": 33, "rest_minutes": 7})
    core.sync_now()
    settings_docs = [
        doc
        for doc in cloud.sync_docs.values()
        if str(doc.get("collection", "")) == "settings"
    ]
    assert settings_docs, "云端应有 settings 文档"
    payloads = [doc.get("payload") or {} for doc in settings_docs]
    assert any(p.get("work_minutes") == 33 for p in payloads), f"settings 未同步: {payloads}"


def scenario_legacy_docs_without_user_id(cloud: InMemoryCloud, root: Path) -> None:
    uid = "user-a"
    phone = "+86 13800000001"
    legacy_id = "todo_legacy001"
    cloud.sync_docs[legacy_id] = {
        "record_id": "legacy001",
        "collection": "todo",
        "payload": {"text": "旧版云端待办", "done": False, "priority": 1},
        "updated_at": time.time(),
        "deleted": False,
        "_owner_user_id": uid,
    }
    core = _make_core(root, cloud, user_id=uid, phone=phone, suffix="_legacy")
    core.engine._write_sync_meta(last_sync_at=0.0)
    core.sync_now()
    texts = [t.text for t in core.todo.tasks]
    assert "旧版云端待办" in texts, f"未合并旧版文档: {texts}"


def scenario_phased_sync_matches_sync_now(cloud: InMemoryCloud, root: Path) -> None:
    core = _make_core(root, cloud, user_id="user-a", phone="+86 13800000001", suffix="_phase")
    core.todo.add("分阶段测试")
    local, since = core.export_for_sync()
    merged, max_updated, _pushed = core.network_sync_records(local, since)
    core.apply_sync_records(merged, max_updated, since)
    rows, assign_max, assign_since, old_status = core.network_fetch_assignments()
    core.apply_assignment_fetch(rows, assign_max, assign_since, old_status)

    assert len(cloud.sync_docs) >= 1
    core.todo.add("第二条")
    core.sync_now()
    assert len(core.todo.tasks) == 2, f"应有 2 条待办，实际 {len(core.todo.tasks)}: {[t.text for t in core.todo.tasks]}"


def scenario_contact_nickname_sync(cloud: InMemoryCloud, root: Path) -> None:
    uid = "user-a"
    phone = "+86 13800000001"
    d1 = _make_core(root, cloud, user_id=uid, phone=phone, suffix="_nick1")
    d1.set_contact_nickname("13900001111", "老板")
    d1.sync_now()

    d2 = _make_core(root, cloud, user_id=uid, phone=phone, suffix="_nick2")
    d2.sync_now()
    assert d2.contacts.display_name("+86 13900001111") == "老板"


def scenario_logout_pushes_to_cloud(cloud: InMemoryCloud, root: Path) -> None:
    core = _make_core(root, cloud, user_id="user-a", phone="+86 13800000001", suffix="_push")
    core.sync_now()
    core.todo.add("退出前新增")
    # 与 SyncService.logout 一致：退出前先 sync_now_blocking
    core.sync_now()
    core.logout()
    assert len(core.todo.tasks) == 1
    todo_rows = [
        doc
        for doc in cloud.sync_docs.values()
        if doc.get("collection") == "todo" and not doc.get("deleted")
    ]
    texts = []
    for doc in todo_rows:
        payload = doc.get("payload") or {}
        if isinstance(payload, dict):
            texts.append(str(payload.get("text", "")))
    assert "退出前新增" in texts, f"退出前未上云: {texts}"


def scenario_relogin_same_user_pulls_cloud(cloud: InMemoryCloud, root: Path) -> None:
    uid = "user-a"
    phone = "+86 13800000001"
    core = _make_core(root, cloud, user_id=uid, phone=phone, suffix="_relogin")
    core.todo.add("云端数据")
    core.sync_now()
    core.logout()

    core.auth.set_session(
        user_id=uid,
        account=phone,
        access_token="tok2",
        refresh_token="ref2",
        expires_in=7200,
    )
    client = DryRunCloudClient(cloud, core.auth)
    core.client = client
    core.engine.client = client
    core.engine.bind_sync_user(uid)
    core.engine._write_sync_meta(last_sync_at=0.0)
    core.todo.import_sync_records([])
    core.assignments.reset_sync_cursor()
    assert len(core.todo.tasks) == 0
    core.sync_now()
    assert any(t.text == "云端数据" for t in core.todo.tasks)


def run_all_scenarios() -> list[ScenarioResult]:
    scenarios: list[tuple[str, Callable[[InMemoryCloud, Path], None]]] = [
        ("同账号双设备：待办/笔记/联系人/设置同步", scenario_same_user_two_devices),
        ("账号切换：本地数据隔离", scenario_account_switch_isolation),
        ("退出登录：保留本地待办", scenario_logout_keeps_local),
        ("用户资料：sync 写入后可按手机号查找", scenario_user_profile_lookup),
        ("任务派发：A 派发 → B 收件 → B 接受 → A 可见", scenario_dispatch_receive_accept),
        ("任务派发：B 仅 sync_assignments_only 可收件", scenario_assignment_sync_only_receive),
        ("设置变更：panel update 后同步到云端", scenario_settings_update_syncs),
        ("旧版云端文档（无 user_id）可拉取", scenario_legacy_docs_without_user_id),
        ("分阶段同步与 sync_now 等效", scenario_phased_sync_matches_sync_now),
        ("联系人昵称跨设备同步", scenario_contact_nickname_sync),
        ("退出登录前推送本地变更", scenario_logout_pushes_to_cloud),
        ("同账号重登：从云端拉回数据", scenario_relogin_same_user_pulls_cloud),
    ]
    results: list[ScenarioResult] = []
    for name, fn in scenarios:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with isolated_data_dir(root):
                cloud = InMemoryCloud()
                results.append(_run(name, lambda c=cloud, r=root, f=fn: f(c, r)))
    return results


def run_service_phased_dryrun() -> ScenarioResult:
    """验证 SyncService 分阶段同步在 Qt 环境下可完成。"""
    try:
        from PySide6.QtCore import QCoreApplication, QThreadPool
        from walle.sync.service import SyncService
    except ImportError as exc:
        return ScenarioResult("SyncService 分阶段同步（Qt）", False, f"缺少 PySide6: {exc}")

    app = QCoreApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QCoreApplication([])

    try:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with isolated_data_dir(root):
                cloud = InMemoryCloud()
                paths = SyncPaths(
                    auth=root / "auth.json",
                    sync_meta=root / "sync_meta.json",
                    sync_config=root / "sync_config.json",
                    assignments=root / "assignments.json",
                    contacts=root / "contacts.json",
                )
                cfg = _make_config()
                _set_data_paths(root, "_svc")
                _ensure_empty_local_store(root, "_svc")
                svc = SyncService(cfg, TodoManager(), NotesManager(), ReminderManager())
                svc._core.paths = paths
                auth = AuthManager(paths.auth)
                auth.set_session(
                    user_id="user-svc",
                    account="+86 13800000099",
                    access_token="tok",
                    refresh_token="ref",
                    expires_in=7200,
                )
                cloud.register_user("user-svc", "+86 13800000099")
                client = DryRunCloudClient(cloud, auth)
                svc._core.auth = auth
                svc._core.client = client
                svc._core.engine.client = client
                svc._core.engine.bind_sync_user("user-svc")

                svc.todo.add("Qt分阶段")
                svc.sync_now()
                QThreadPool.globalInstance().waitForDone(10000)
                for _ in range(30):
                    app.processEvents()

                assert not svc.sync_busy
                assert len(cloud.sync_docs) >= 1

                svc2_core = _make_core(
                    root,
                    cloud,
                    user_id="user-svc",
                    phone="+86 13800000099",
                    suffix="_svc2",
                )
                svc2_core.sync_now()
                assert any(t.text == "Qt分阶段" for t in svc2_core.todo.tasks)
        return ScenarioResult("SyncService 分阶段同步（Qt）", True)
    except AssertionError as exc:
        return ScenarioResult("SyncService 分阶段同步（Qt）", False, str(exc))
    except Exception as exc:
        return ScenarioResult(
            "SyncService 分阶段同步（Qt）",
            False,
            f"{type(exc).__name__}: {exc}",
        )
    finally:
        if owns_app and app is not None:
            app.quit()


def main() -> int:
    print("=== Dry-run 集成测试（内存 CloudBase 模拟）===\n")
    results = run_all_scenarios()
    results.append(run_service_phased_dryrun())

    passed = sum(1 for r in results if r.ok)
    failed = [r for r in results if not r.ok]

    for r in results:
        mark = "OK" if r.ok else "FAIL"
        print(f"[{mark}] {r.name}")
        if r.detail:
            for line in r.detail.strip().splitlines():
                print(f"       {line}")

    print(f"\n合计: {passed}/{len(results)} 通过")
    if failed:
        print("\n未通过场景:")
        for r in failed:
            print(f"  - {r.name}")
        return 1

    print("\n全部 Dry-run 场景通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
