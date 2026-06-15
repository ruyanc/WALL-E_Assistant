"""验证移动端文案键完整性与主要控件显示文本。

用法：python scripts/verify_mobile_display.py
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import traceback
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(MOBILE) not in sys.path:
    sys.path.append(str(MOBILE))

os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")

# SyncCore / friendly_error 可能返回的文案键（移动端 sync_text 须覆盖）
_CORE_TR_KEYS = frozenset(
    {
        "sync.sms.sent",
        "sync.env.saved",
        "sync.env.changed_relogin",
        "sync.status.disabled",
        "sync.status.need_env",
        "sync.status.need_login",
        "sync.status.syncing",
        "sync.status.ok",
        "sync.status.error",
        "sync.err.windows_only",
        "sync.err.need_config",
        "sync.err.empty_env",
        "sync.err.empty_password",
        "sync.err.empty_code",
        "sync.err.need_sms_first",
        "sync.err.need_register_sms",
        "sync.err.need_login_sms",
        "sync.err.bad_code",
        "sync.err.bad_credentials",
        "sync.err.already_registered",
        "sync.err.user_not_found",
        "assign.err.need_login",
        "assign.err.not_found",
        "assign.err.self",
        "assign.err.bad_phone",
        "assign.err.empty_title",
        "assign.err.empty_recipient",
        "assign.err.contact_not_found",
        "assign.err.duplicate_nickname",
        "contacts.err.empty_nickname",
        "assign.err.empty_reject_reason",
        "assign.err.empty_cancel_reason",
        "assign.err.not_finished",
        "assign.err.forbidden",
    }
)

_ASSIGN_STATUSES = ("pending", "accepted", "rejected", "completed", "cancelled")
_TR_RE = re.compile(r"\b(?:tr|sync_tr)\(\s*(?:f)?[\"']([^\"']+)")


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def _collect_code_keys() -> set[str]:
    keys: set[str] = set()
    for path in MOBILE.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for m in _TR_RE.finditer(text):
            raw = m.group(1)
            if "{" in raw:
                continue
            keys.add(raw)
    keys.update(_CORE_TR_KEYS)
    for st in _ASSIGN_STATUSES:
        keys.add(f"assign.status.{st}")
    return keys


def test_sync_text_keys() -> None:
    from sync_text import _TEXTS, tr

    code_keys = _collect_code_keys()
    missing = sorted(k for k in code_keys if k not in _TEXTS)
    if missing:
        _fail(f"sync_text 缺少 {len(missing)} 个键: {missing[:12]}{'...' if len(missing) > 12 else ''}")

    # tr() 不应回传裸键
    for key in sorted(code_keys):
        out = tr(key, msg="x", datetime="2020-01-01", count=1, text="t", phone="138")
        if out == key:
            _fail(f"sync_text.tr('{key}') 仍返回键名")
    print(f"  OK sync_text 覆盖 {len(code_keys)} 个文案键")


def test_priority_labels() -> None:
    from sync_text import tr
    from todo_store import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_MED

    labels = {
        PRIORITY_HIGH: tr("prio.high"),
        PRIORITY_MED: tr("prio.med"),
        PRIORITY_LOW: tr("prio.low"),
    }
    values = {label: prio for prio, label in labels.items()}
    spinner_values = {tr("prio.high"), tr("prio.med"), tr("prio.low")}
    assert set(values.keys()) == spinner_values
    for label, prio in values.items():
        assert labels[prio] == label

    main_src = (MOBILE / "main.py").read_text(encoding="utf-8")
    for key in ("prio.high", "prio.med", "prio.low"):
        assert f"sync_tr(\"{key}\")" in main_src, f"main.py 应通过 sync_tr 引用 {key}"
    print("  OK 优先级文案与 Spinner 选项一致")


def _mock_sync():
    sync = MagicMock()
    sync.status_text.return_value = "未连接"
    sync.cloudbase_env_id = ""
    sync.is_logged_in = False
    sync.backend_configured = True
    sync.phone = None
    sync.sync_paused = False
    sync.contacts.list_contacts.return_value = []
    sync.friendly_error = lambda msg: msg
    return sync


def _visible(widget) -> bool:
    if getattr(widget, "opacity", 1) <= 0:
        return False
    h = getattr(widget, "height", None)
    if h is not None and h <= 0:
        return False
    return True


def _walk_widgets(root):
    stack = [root]
    seen: set[int] = set()
    while stack:
        w = stack.pop()
        wid = id(w)
        if wid in seen:
            continue
        seen.add(wid)
        yield w
        for child in getattr(w, "children", []):
            stack.append(child)


def test_screen_visible_text() -> None:
    try:
        from kivy.core.window import Window
    except ImportError:
        print("  SKIP 页面控件检查（未安装 Kivy，构建环境/WSL 中可运行完整验证）")
        return
    from kivy.uix.spinner import Spinner

    from account_screen import AccountScreen
    from fonts_setup import register_fonts
    from main import NotesScreen, ReminderScreen, TimerScreen, TodoScreen
    from notes_store import NotesStore
    from pomodoro_persist import PomodoroState
    from pomodoro_timer import PomodoroTimer
    from reminder_store import ReminderStore
    from settings_store import SettingsStore
    from todo_store import TodoStore
    from ui_widgets import Button, Label

    register_fonts()
    Window.size = (412, 915)

    screens: list[tuple[str, object]] = []
    with tempfile.TemporaryDirectory() as td:
        os.environ["WALLE_MOBILE_DATA"] = td
        todo = TodoStore(on_change=lambda: None)
        sync = _mock_sync()
        screens.append(("TodoScreen", TodoScreen(todo, sync=sync, name="todo")))
        screens.append(("NotesScreen", NotesScreen(NotesStore(on_change=lambda: None), name="notes")))
        screens.append(
            ("ReminderScreen", ReminderScreen(ReminderStore(on_change=lambda: None), name="remind"))
        )
        settings = SettingsStore()
        timer = PomodoroTimer(on_tick=lambda *_: None, on_state=lambda *_: None)
        screens.append(("TimerScreen", TimerScreen(timer, settings, name="timer")))
        screens.append(("AccountScreen", AccountScreen(_mock_sync(), name="account")))

    empty_labels = []
    empty_buttons = []
    bad_spinners = []
    for screen_name, screen in screens:
        for w in _walk_widgets(screen):
            if not _visible(w):
                continue
            if isinstance(w, Label):
                if not (w.text or "").strip():
                    empty_labels.append(f"{screen_name}:{w.__class__.__name__}")
            elif isinstance(w, Button):
                if not (w.text or "").strip():
                    empty_buttons.append(f"{screen_name}:{w.__class__.__name__}")
            elif isinstance(w, Spinner):
                text = (w.text or "").strip()
                values = [v.strip() for v in w.values if v and str(v).strip()]
                if not text or not values:
                    bad_spinners.append(f"{screen_name} Spinner 空 text/values")
                elif text not in values:
                    bad_spinners.append(f"{screen_name} Spinner text 不在 values: {text!r}")

    if empty_labels:
        _fail(f"可见 Label 无文本: {empty_labels[:8]}")
    if empty_buttons:
        _fail(f"可见 Button 无文本: {empty_buttons[:8]}")
    if bad_spinners:
        _fail(bad_spinners[0])

    # 待办页 Spinner 选项应为中文优先级
    todo_screen = screens[0][1]
    spinners = [w for w in _walk_widgets(todo_screen) if isinstance(w, Spinner) and _visible(w)]
    assert spinners, "待办页应有可见 Spinner"
    from sync_text import tr

    prio_set = {tr("prio.high"), tr("prio.med"), tr("prio.low")}
    for sp in spinners:
        if set(sp.values) == prio_set:
            break
    else:
        _fail("待办页优先级 Spinner values 应为 高级/中级/低级")

    print(f"  OK {len(screens)} 个页面可见 Label/Button/Spinner 文本完整")


def test_archive_day_header() -> None:
    from sync_text import tr

    out = tr("todo.archive.day_header", date="2024年1月2日", count=3)
    assert "2024" in out and "3" in out
    print("  OK todo.archive.day_header 格式化")


def main() -> int:
    print("=== 手机端显示与文案验证 ===")
    try:
        test_sync_text_keys()
        test_priority_labels()
        test_archive_day_header()
        test_screen_visible_text()
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
