"""验证手机端所有输入框可写入、聚焦，且滚动容器为 FormScrollView。

用法：python scripts/verify_mobile_inputs.py
"""

from __future__ import annotations

import os
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


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def test_textinput_core() -> None:
    from ui_widgets import TextInput

    single = TextInput()
    single.text = "auth-code-xyz"
    assert single.text == "auth-code-xyz", "单行输入应保留全文"

    multi = TextInput(multiline=True)
    multi.text = "第一行\n第二行"
    assert "第一行" in multi.text and "第二行" in multi.text, "多行输入应保留换行"

    single2 = TextInput()
    single2.insert_text("a\nb")
    assert "\n" not in single2.text, "单行输入应过滤换行"
    print("  OK TextInput 单行/多行写入")


def test_scroll_containers() -> None:
    from layout import FormScrollView, scroll_list, scroll_screen

    _, _ = scroll_screen()
    _, _ = scroll_list()
    scroll, _ = scroll_screen()
    assert isinstance(scroll, FormScrollView), "scroll_screen 应使用 FormScrollView"
    scroll2, _ = scroll_list()
    assert isinstance(scroll2, FormScrollView), "scroll_list 应使用 FormScrollView"
    print("  OK 表单/列表滚动容器为 FormScrollView")


def _collect_text_inputs(widget, path: str = "", _seen: set[int] | None = None) -> list[tuple[str, object]]:
    from kivy.uix.screenmanager import ScreenManager
    from ui_widgets import TextInput

    if _seen is None:
        _seen = set()
    wid = id(widget)
    if wid in _seen:
        return []
    _seen.add(wid)

    found: list[tuple[str, object]] = []
    name = getattr(widget, "name", "") or widget.__class__.__name__
    cur = f"{path}/{name}" if path else name
    if isinstance(widget, TextInput):
        found.append((cur, widget))
    if isinstance(widget, ScreenManager):
        for screen in widget.screens:
            found.extend(_collect_text_inputs(screen, f"{cur}/{screen.name}", _seen))
    for child in getattr(widget, "children", []):
        found.extend(_collect_text_inputs(child, cur, _seen))
    return found


def _mock_sync():
    sync = MagicMock()
    sync.status_text.return_value = "offline"
    sync.cloudbase_env_id = ""
    sync.is_logged_in = False
    sync.backend_configured = True
    sync.phone = None
    sync.sync_paused = False
    sync.contacts.list_contacts.return_value = []
    return sync


def test_screen_inputs() -> None:
    from kivy.core.window import Window

    from layout import FormScrollView
    from main import NotesScreen, ReminderScreen, TimerScreen, TodoScreen
    from notes_store import NotesStore
    from pomodoro_persist import PomodoroState
    from pomodoro_timer import PomodoroTimer
    from reminder_store import ReminderStore
    from settings_store import SettingsStore
    from todo_store import TodoStore
    from account_screen import AccountScreen

    Window.size = (412, 915)

    cases: list[tuple[str, object, int]] = []
    with tempfile.TemporaryDirectory() as td:
        os.environ["WALLE_MOBILE_DATA"] = td
        todo = TodoStore(on_change=lambda: None)
        sync = _mock_sync()
        cases.append(
            (
                "TodoScreen",
                TodoScreen(todo, sync=sync, name="todo"),
                4,  # input + 3 dispatch (sync path)
            )
        )
        cases.append(("NotesScreen", NotesScreen(NotesStore(on_change=lambda: None), name="notes"), 1))
        cases.append(
            (
                "ReminderScreen",
                ReminderScreen(ReminderStore(on_change=lambda: None), name="remind"),
                2,
            )
        )
        settings = SettingsStore()
        timer = PomodoroTimer(on_tick=lambda *_: None, on_state=lambda *_: None)
        cases.append(("TimerScreen", TimerScreen(timer, settings, name="timer"), 3))
        cases.append(("AccountScreen", AccountScreen(_mock_sync(), name="account"), 6))

    for label, screen, min_count in cases:
        inputs = _collect_text_inputs(screen)
        assert len(inputs) >= min_count, f"{label} 输入框数量不足: {len(inputs)} < {min_count}"
        in_form_scroll = 0
        editable = 0
        for path, ti in inputs:
            if ti.disabled:
                continue
            editable += 1
            sample = "测试文字"
            ti.text = sample
            assert ti.text == sample, f"{label} {path} 无法写入"
            ti.focus = True
            assert ti.focus, f"{label} {path} 无法聚焦"
            ti.focus = False
            parent = ti.parent
            while parent is not None:
                if isinstance(parent, FormScrollView):
                    in_form_scroll += 1
                    break
                parent = parent.parent
        scroll_inputs = [
            p
            for p, ti in inputs
            if not ti.disabled and ("scroll" in p.lower() or "list" in p.lower() or "outbox" in p.lower())
        ]
        if scroll_inputs:
            assert in_form_scroll > 0, f"{label} 滚动区内输入框未置于 FormScrollView 下"
        assert editable > 0, f"{label} 无可用输入框"
        print(f"  OK {label}: {len(inputs)} 个输入框，{editable} 个可编辑")

    # 记事本列表内编辑框（滚动区）
    with tempfile.TemporaryDirectory() as td2:
        os.environ["WALLE_MOBILE_DATA"] = td2
        store = NotesStore(on_change=lambda: None)
        store.add("line1")
        notes = NotesScreen(store, name="notes2")
        notes.refresh()
        list_inputs = _collect_text_inputs(notes)
        assert len(list_inputs) >= 2, "记事本应含顶部输入 + 列表编辑框"
        for path, ti in list_inputs:
            if ti is notes.input:
                continue
            ti.text = "编辑后内容"
            assert ti.text == "编辑后内容", f"记事编辑框 {path} 无法写入"
    print("  OK 记事本列表内编辑框可写")


def test_reason_popup_field() -> None:
    from kivy.core.window import Window
    from kivy.uix.popup import Popup

    from layout import reason_popup
    from ui_widgets import TextInput

    captured: list[str] = []

    def on_confirm(text: str) -> None:
        captured.append(text)

    reason_popup("标题", "说明", on_confirm)
    popup = None
    for w in Window.children:
        if isinstance(w, Popup):
            popup = w
            break
    assert popup is not None, "reason_popup 应打开 Popup"
    fields = [x for x in popup.walk() if isinstance(x, TextInput)]
    assert fields, "弹窗内应有输入框"
    fields[0].text = "拒绝理由"
    assert fields[0].text == "拒绝理由"
    # 点确定
    for w in popup.walk():
        if hasattr(w, "text") and w.text == "确定":
            w.dispatch("on_release")
            break
    assert captured == ["拒绝理由"], "弹窗应回传理由"
    print("  OK reason_popup 输入框可写")


def main() -> int:
    print("=== 手机端输入框验证 ===")
    try:
        test_textinput_core()
        test_scroll_containers()
        test_screen_inputs()
        test_reason_popup_field()
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
