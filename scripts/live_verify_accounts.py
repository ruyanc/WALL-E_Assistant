"""真实账号联机验证：个人数据同步 + 用户资料 + 跨账号任务派发。

用法（密码勿写入仓库）：
  python scripts/live_verify_accounts.py <账号A密码> <账号B密码>

环境变量（可选）：
  WALLE_CLOUDBASE_ENV_ID   默认 wall-e-d2gkz50u90bf68fa9
  WALLE_PHONE_A            默认 13611019772
  WALLE_PHONE_B            默认 18851071884
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from walle.config import Config  # noqa: E402
from walle.i18n import tr  # noqa: E402
from walle.notes_manager import NotesManager  # noqa: E402
from walle.reminder_manager import ReminderManager  # noqa: E402
from walle.sync.assignment_models import STATUS_ACCEPTED, STATUS_PENDING  # noqa: E402
from walle.sync.backend import SyncBackendError  # noqa: E402
from walle.sync.core import SyncCore  # noqa: E402
from walle.sync.paths import SyncPaths  # noqa: E402
from walle.todo_manager import TodoManager  # noqa: E402

ENV = __import__("os").environ.get("WALLE_CLOUDBASE_ENV_ID", "wall-e-d2gkz50u90bf68fa9").strip()
PHONE_A = __import__("os").environ.get("WALLE_PHONE_A", "13611019772").strip()
PHONE_B = __import__("os").environ.get("WALLE_PHONE_B", "18851071884").strip()


def _mask_phone(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) >= 7:
        return f"{digits[:3]}****{digits[-4:]}"
    return "****"


def make_core(tmp: Path) -> SyncCore:
    paths = SyncPaths(
        auth=tmp / "auth.json",
        sync_meta=tmp / "sync_meta.json",
        sync_config=tmp / "sync_config.json",
        assignments=tmp / "assignments.json",
        contacts=tmp / "contact_nicknames.json",
    )
    cfg = Config.__new__(Config)
    cfg._data = {"cloudbase_env_id": ENV}
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


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failed = 0

    def ok(self, msg: str) -> None:
        self.lines.append(f"[OK] {msg}")

    def fail(self, msg: str) -> None:
        self.lines.append(f"[FAIL] {msg}")
        self.failed += 1

    def info(self, msg: str) -> None:
        self.lines.append(f"[INFO] {msg}")


def login(core: SyncCore, phone: str, password: str, report: Report, label: str) -> bool:
    ok, msg = core.login(phone, password)
    if ok:
        report.ok(f"{label} 密码登录（{_mask_phone(phone)}）")
        return True
    report.fail(f"{label} 密码登录 — {msg}")
    return False


def main() -> int:
    if len(sys.argv) < 3:
        print("用法: python scripts/live_verify_accounts.py <账号A密码> <账号B密码>")
        return 2

    pass_a, pass_b = sys.argv[1], sys.argv[2]
    report = Report()
    stamp = int(time.time())
    todo_marker = f"LIVE-TODO-{stamp}"
    dispatch_title = f"LIVE-DISPATCH-{stamp}"

    report.info(f"授权码 {ENV[:12]}…  账号A {_mask_phone(PHONE_A)}  账号B {_mask_phone(PHONE_B)}")

  # --- 登录 ---
    with tempfile.TemporaryDirectory() as td_a1:
        core_a1 = make_core(Path(td_a1))
        if not login(core_a1, PHONE_A, pass_a, report, "账号A"):
            for line in report.lines:
                print(line)
            return 1
        uid_a = core_a1.auth.session.user_id  # type: ignore[union-attr]

    with tempfile.TemporaryDirectory() as td_b:
        core_b = make_core(Path(td_b))
        if not login(core_b, PHONE_B, pass_b, report, "账号B"):
            for line in report.lines:
                print(line)
            return 1
        uid_b = core_b.auth.session.user_id  # type: ignore[union-attr]

    # --- 用户资料 / 手机号解析 ---
    with tempfile.TemporaryDirectory() as td_probe:
        core_probe = make_core(Path(td_probe))
        login(core_probe, PHONE_A, pass_a, report, "探测会话")
        client = core_probe._ensure_client()
        row_b = client.find_user_by_phone(PHONE_B)
        if row_b and str(row_b.get("user_id")) == uid_b:
            report.ok("按手机号查找派发对象 B（Auth / user_profiles）")
        else:
            report.fail("按手机号查找派发对象 B — UID 不匹配或未找到")
        row_a = client.find_user_by_phone(PHONE_A)
        if row_a and str(row_a.get("user_id")) == uid_a:
            report.ok("按手机号查找账号 A")
        else:
            report.fail("按手机号查找账号 A")

        try:
            client.upsert_user_profile(PHONE_A)
            rows = client.find_documents("user_profiles", {"phone_digits": PHONE_A[-11:] if len(PHONE_A) > 11 else PHONE_A}, limit=3)
            if any(str(r.get("user_id")) == uid_a for r in rows):
                report.ok("user_profiles 写入并可查询")
            else:
                report.fail("user_profiles 写入后查询不到当前用户")
        except SyncBackendError as exc:
            report.fail(f"user_profiles 读写 — {exc}")

    # --- 个人数据同步：设备1 上传 ---
    with tempfile.TemporaryDirectory() as td_a1:
        core_a1 = make_core(Path(td_a1))
        login(core_a1, PHONE_A, pass_a, report, "设备1")
        core_a1.todo.add(todo_marker, priority=1)
        if not core_a1.sync_now():
            report.fail("设备1 sync_now 上传待办失败")
        else:
            report.ok("设备1 创建待办并 sync_now 上传")

        client = core_a1._ensure_client()
        try:
            cloud_rows = client.fetch_changes(0.0)
            todo_cloud = [
                r for r in cloud_rows
                if r.get("collection") == "todo"
                and isinstance(r.get("payload"), dict)
                and any(todo_marker in str(v) for v in r["payload"].values())
            ]
            if todo_cloud:
                report.ok("云端 sync_records 含本次待办标记")
            else:
                report.fail("云端 sync_records 未找到本次待办（fetch_changes）")
        except SyncBackendError as exc:
            report.fail(f"云端拉取 sync_records — {exc}")

    # --- 个人数据同步：设备2 拉取 ---
    with tempfile.TemporaryDirectory() as td_a2:
        core_a2 = make_core(Path(td_a2))
        login(core_a2, PHONE_A, pass_a, report, "设备2")
        if not core_a2.sync_now():
            report.fail("设备2 sync_now 拉取失败")
        else:
            texts = [t.text for t in core_a2.todo.tasks]
            if any(todo_marker in t for t in texts):
                report.ok("设备2 拉取到设备1 上传的待办（同账号多设备）")
            else:
                report.fail("设备2 未拉取到设备1 的待办")

    # --- 跨账号派发 ---
    with tempfile.TemporaryDirectory() as td_a:
        core_a = make_core(Path(td_a))
        login(core_a, PHONE_A, pass_a, report, "派发方A")
        try:
            phone = core_a.contacts.resolve_recipient(PHONE_B)
            assignment = core_a.assignments.create(phone, dispatch_title, priority=1)
            report.ok(f"账号A 派发任务 id={assignment.id[:8]}…")
        except (SyncBackendError, OSError) as exc:
            report.fail(f"账号A 派发 — {exc}")
            assignment = None

    if assignment is not None:
        with tempfile.TemporaryDirectory() as td_b2:
            core_b2 = make_core(Path(td_b2))
            login(core_b2, PHONE_B, pass_b, report, "接收方B")
            if not core_b2.sync_now():
                report.fail("账号B sync_now 拉取派发失败")
            inbox = [
                a for a in core_b2.assignments._items.values()
                if a.title == dispatch_title and a.status == STATUS_PENDING
            ]
            if inbox:
                report.ok("账号B inbox 可见待处理任务")
                try:
                    core_b2.accept_assignment(inbox[0].id)
                    if not core_b2.sync_now():
                        report.fail("账号B 接受后 sync_now 失败")
                    else:
                        report.ok("账号B 接受任务并同步")
                except SyncBackendError as exc:
                    report.fail(f"账号B 接受 — {exc}")
            else:
                report.fail("账号B inbox 未见到派发任务")

        with tempfile.TemporaryDirectory() as td_a3:
            core_a3 = make_core(Path(td_a3))
            login(core_a3, PHONE_A, pass_a, report, "派发方A复查")
            if not core_a3.sync_now():
                report.fail("账号A 复查 sync_now 失败")
            out = core_a3.assignments._items.get(assignment.id)
            if out and out.status == STATUS_ACCEPTED:
                report.ok("账号A outbox 状态为 accepted")
            else:
                status = out.status if out else "MISSING"
                report.fail(f"账号A outbox 状态异常 — {status}")

    print("=== 真实账号联机验证 ===")
    for line in report.lines:
        print(line)
    passed = sum(1 for l in report.lines if l.startswith("[OK]"))
    total = passed + report.failed
    print(f"\n合计: {passed}/{total} 通过，{report.failed} 失败")
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
