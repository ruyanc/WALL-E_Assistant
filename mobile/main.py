"""WALL-E 安卓版：控制台功能（待办 / 记事本 / 提醒 / 番茄钟 / 账号同步）。"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

_MOBILE_DIR = Path(__file__).resolve().parent
_ROOT = _MOBILE_DIR.parent
_IS_ANDROID = bool(os.environ.get("ANDROID_PRIVATE"))


def _ensure_mobile_walle_bundle() -> None:
    """本地预览前确保 mobile/walle 存在（不含桌面 PySide6 SyncService）。"""
    if (_MOBILE_DIR / "walle" / "sync" / "core.py").is_file():
        return
    prep = _MOBILE_DIR / "prepare_sync.py"
    if not prep.is_file():
        return
    import subprocess

    env = os.environ.copy()
    env.setdefault("WALLE_PROJECT_ROOT", str(_ROOT))
    subprocess.run([sys.executable, str(prep)], env=env, check=False)


if str(_MOBILE_DIR) not in sys.path:
    sys.path.insert(0, str(_MOBILE_DIR))
if not _IS_ANDROID:
    _ensure_mobile_walle_bundle()
# 勿将仓库根置于 sys.path 前部，否则会加载桌面 walle.sync → PySide6 SyncService 导致闪退

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen, ScreenManager

from android_platform import is_android, request_runtime_permissions, sync_background_service
from floating_banner import BannerHost, register_banner_host
from background_engine import has_active_reminders
from fonts_setup import register_fonts
from layout import (
    BottomNav,
    ItemCard,
    Metrics,
    SegmentedBar,
    bind_label_wrap,
    compact_btn,
    danger_btn,
    field_input,
    field_input_row,
    ghost_btn,
    hint_label,
    info_bar,
    primary_btn,
    priority_stripe,
    reason_popup,
    screen_root,
    scroll_list,
    scroll_screen,
    section_title,
    success_btn,
    sync_status_label,
    _attach_rounded_bg,
)
from walle_widgets import PAGE_ANIMS, walle_empty, walle_page_header, walle_section_title, WalleMascotPanel, set_screen_mascots_active
from ui_widgets import Label, Spinner, TextInput

from notify_util import ensure_notification_channels, notify
from notes_store import NotesStore
from pomodoro_persist import PomodoroState
from pomodoro_timer import PomodoroTimer
from reminder_store import REPEAT_DAILY, REPEAT_LABELS, ReminderStore
from settings_store import SettingsStore
from sync_text import tr as sync_tr
from theme import ACCENT, BG, HINT, INPUT_BG, MASCOT_BG, PAGE_ACCOUNT_TINT, PAGE_NOTES_TINT, PAGE_REMIND_TINT, PAGE_TIMER_TINT, PAGE_TODO_TINT, TEXT, TEXT_DONE, TEXT_MUTED
from todo_store import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_MED, TodoStore

from walle.sync.assignment_events import (
    EVENT_ACCEPTED,
    EVENT_COMPLETED,
    EVENT_DISPATCHED,
    EVENT_REJECTED,
    EVENT_WITHDRAWN,
)
from walle.sync.assignment_models import STATUS_ACCEPTED, STATUS_CANCELLED, STATUS_PENDING, STATUS_REJECTED
from walle.sync.assignment_notify import assignment_notify_messages
from walle.sync.backend import SyncBackendError

try:
    from account_screen import AccountScreen
    from sync_service import MobileSyncService
except ImportError:
    AccountScreen = None  # type: ignore
    MobileSyncService = None  # type: ignore


_PRIO_LABELS = {
    PRIORITY_HIGH: sync_tr("prio.high"),
    PRIORITY_MED: sync_tr("prio.med"),
    PRIORITY_LOW: sync_tr("prio.low"),
}
_PRIO_VALUES = {label: prio for prio, label in _PRIO_LABELS.items()}


def _format_archive_day(day_key: str) -> str:
    dt = datetime.strptime(day_key, "%Y-%m-%d")
    return f"{dt.year}年{dt.month}月{dt.day}日"


def _assignment_status(status: str) -> str:
    return sync_tr(f"assign.status.{status}")


def _format_ts(ts: float) -> str:
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return ""


def _format_todo_times(task) -> str:
    lines = [sync_tr("todo.created_at", datetime=_format_ts(task.created))]
    if task.done:
        ts = task.completed_at or task.updated_at or task.created
        lines.append(sync_tr("todo.completed_at", datetime=_format_ts(ts)))
    return "\n".join(lines)


def _format_assignment_times(assignment, *, archive: bool = False) -> str:
    lines = [sync_tr("assign.dispatched_at", datetime=_format_ts(assignment.created_at))]
    if archive:
        ts = assignment.completed_at or assignment.updated_at
        if ts:
            lines.append(sync_tr("assign.completed_at", datetime=_format_ts(ts)))
    return "\n".join(lines)


class TodoScreen(Screen):
    def __init__(self, store: TodoStore, sync: "MobileSyncService | None" = None, **kwargs):
        super().__init__(**kwargs)
        self.store = store
        self.sync = sync
        self._current_subtab = "active"
        root = screen_root(page_tint=PAGE_TODO_TINT)
        root.add_widget(
            walle_page_header("待办", sync_tr("todo.hint"), anim=PAGE_ANIMS["todo"])
        )

        if sync is not None:
            sync_row = info_bar()
            self.sync_status_lbl = sync_status_label()
            self.sync_retry_btn = ghost_btn(sync_tr("sync.retry"), size_hint_x=None, width=dp(88))
            self.sync_retry_btn.bind(on_release=lambda *_: self._retry_sync())
            sync_row.add_widget(self.sync_status_lbl)
            sync_row.add_widget(self.sync_retry_btn)
            root.add_widget(sync_row)
            self.set_sync_status(sync.status_text())

        if sync is not None:
            seg_items = [
                (sync_tr("todo.tab.personal"), "active"),
                (sync_tr("todo.tab.inbox"), "inbox"),
                (sync_tr("todo.tab.outbox"), "outbox"),
                (sync_tr("todo.tab.archive"), "archive"),
            ]
        else:
            seg_items = [
                (sync_tr("todo.tab.personal"), "active"),
                (sync_tr("todo.tab.archive"), "archive"),
            ]

        self.subtabs = ScreenManager(size_hint_y=1)

        active = Screen(name="active")
        active_root = BoxLayout(orientation="vertical", spacing=dp(8))
        active_root.add_widget(walle_section_title("添加任务", anim="talk"))
        self._build_form(active_root)
        self.active_scroll, self.active_list = scroll_list()
        active_root.add_widget(self.active_scroll)
        active.add_widget(active_root)
        self.subtabs.add_widget(active)

        if sync is not None:
            inbox = Screen(name="inbox")
            inbox_root = BoxLayout(orientation="vertical", spacing=dp(8))
            inbox_root.add_widget(hint_label(sync_tr("assign.hint.inbox")))
            self.inbox_scroll, self.inbox_list = scroll_list()
            inbox_root.add_widget(self.inbox_scroll)
            inbox.add_widget(inbox_root)
            self.subtabs.add_widget(inbox)

            outbox = Screen(name="outbox")
            self.outbox_scroll, self.outbox_inner = scroll_screen()
            self.outbox_inner.add_widget(hint_label(sync_tr("assign.hint.outbox")))
            self.outbox_inner.add_widget(walle_section_title(sync_tr("assign.dispatch"), anim="cheer"))
            self.dispatch_phone = field_input(hint_text="对方手机号或昵称", size_hint_x=1)
            self.dispatch_title = field_input(hint_text="任务标题", size_hint_x=1)
            self.dispatch_title.bind(on_text_validate=lambda *_: self._dispatch())
            self.dispatch_description = field_input(
                hint_text=sync_tr("assign.description.placeholder"),
                multiline=True,
                size_hint_y=None,
                height=max(dp(72), Metrics.field_h),
            )
            dispatch_actions = BoxLayout(size_hint_y=None, height=Metrics.field_h, spacing=dp(8))
            self.dispatch_prio = Spinner(
                text=sync_tr("prio.med"),
                values=(sync_tr("prio.high"), sync_tr("prio.med"), sync_tr("prio.low")),
                font_size=Metrics.font_md,
                size_hint_x=None,
                width=dp(96),
                size_hint_y=None,
                height=Metrics.field_h,
            )
            self.dispatch_btn = primary_btn(sync_tr("assign.dispatch"), size_hint_x=None, width=dp(96))
            self.dispatch_btn.bind(on_release=self._dispatch)
            dispatch_actions.add_widget(self.dispatch_prio)
            dispatch_actions.add_widget(self.dispatch_btn)
            self.outbox_inner.add_widget(field_input_row(self.dispatch_phone, with_paste=True))
            self.outbox_inner.add_widget(field_input_row(self.dispatch_title, with_paste=True))
            self.outbox_inner.add_widget(self.dispatch_description)
            self.outbox_inner.add_widget(dispatch_actions)
            self.outbox_list = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                spacing=dp(8),
                padding=(0, dp(4)),
            )
            self.outbox_list.bind(minimum_height=self.outbox_list.setter("height"))
            self.outbox_inner.add_widget(self.outbox_list)
            outbox.add_widget(self.outbox_scroll)
            self.subtabs.add_widget(outbox)

        archive = Screen(name="archive")
        archive_root = BoxLayout(orientation="vertical", spacing=dp(8))
        archive_root.add_widget(hint_label(sync_tr("todo.archive.hint")))
        self.archive_scroll, self.archive_list = scroll_list()
        archive_root.add_widget(self.archive_scroll)
        clear_arch = ghost_btn(sync_tr("todo.archive.clear"))
        clear_arch.bind(on_release=lambda *_: self._clear_archive())
        archive_root.add_widget(clear_arch)
        archive.add_widget(archive_root)
        self.subtabs.add_widget(archive)

        self.segment = SegmentedBar(seg_items, on_select=self._on_subtab_select)
        root.add_widget(self.segment)
        root.add_widget(self.subtabs)
        self.add_widget(root)
        self.refresh()

    def _on_subtab_select(self, key: str) -> None:
        self._current_subtab = key
        if not hasattr(self, "subtabs"):
            return
        self.subtabs.current = key
        if self.sync and key in ("inbox", "outbox") and self.sync.is_logged_in:
            self.sync.sync_assignments_only()
        self._update_sync_controls()

    def focus_subtab(self, key: str) -> None:
        if hasattr(self, "segment"):
            self.segment.select(key)

    def set_sync_status(self, text: str) -> None:
        if hasattr(self, "sync_status_lbl"):
            self.sync_status_lbl.text = text
        self._update_sync_controls()

    def _update_sync_controls(self) -> None:
        if not hasattr(self, "sync_retry_btn") or not self.sync:
            return
        can_sync = (
            self.sync.is_logged_in
            and self.sync.backend_configured
            and not self.sync.sync_paused
        )
        self.sync_retry_btn.disabled = not can_sync
        if hasattr(self, "dispatch_btn"):
            self.dispatch_btn.disabled = not can_sync
            self.dispatch_phone.disabled = not can_sync
            self.dispatch_title.disabled = not can_sync
            self.dispatch_description.disabled = not can_sync
            self.dispatch_prio.disabled = not can_sync

    def _retry_sync(self) -> None:
        if self.sync:
            self.sync.sync_now()

    def _show_feedback(self, text: str, *, error: bool = False) -> None:
        notify("WALL-E", text)
        if error and self.sync:
            self.set_sync_status(self.sync.friendly_error(text))

    def _section_header(self, text: str) -> Label:
        lbl = Label(
            text=text,
            color=TEXT,
            bold=True,
            font_size=Metrics.font_sm,
            size_hint_y=None,
            halign="left",
            valign="top",
        )
        bind_label_wrap(lbl)
        return lbl

    def _day_header(self, day_key: str, count: int) -> Label:
        lbl = Label(
            text=sync_tr(
                "todo.archive.day_header",
                date=_format_archive_day(day_key),
                count=count,
            ),
            color=TEXT_MUTED,
            font_size=Metrics.font_sm,
            size_hint_y=None,
            halign="left",
            valign="top",
        )
        bind_label_wrap(lbl)
        return lbl

    def _build_form(self, root: BoxLayout) -> None:
        m = Metrics
        self.input = field_input(hint_text="输入新任务，回车添加")
        self.input.bind(on_text_validate=lambda *_: self._add())
        self.prio = Spinner(
            text=sync_tr("prio.med"),
            values=(sync_tr("prio.high"), sync_tr("prio.med"), sync_tr("prio.low")),
            font_size=m.font_md,
            size_hint_x=None,
            width=dp(96),
            size_hint_y=None,
            height=m.field_h,
        )
        add_btn = primary_btn(sync_tr("todo.add"), size_hint_x=None, width=dp(76))

        if m.narrow:
            row1 = BoxLayout(size_hint_y=None, height=m.field_h)
            row1.add_widget(self.input)
            row2 = BoxLayout(size_hint_y=None, height=m.field_h, spacing=dp(8))
            row2.add_widget(self.prio)
            row2.add_widget(add_btn)
            root.add_widget(row1)
            root.add_widget(row2)
        else:
            row = BoxLayout(size_hint_y=None, height=m.field_h, spacing=dp(8))
            row.add_widget(self.input)
            row.add_widget(self.prio)
            row.add_widget(add_btn)
            root.add_widget(row)
        add_btn.bind(on_release=self._add)

    def _prio_value(self) -> int:
        return _PRIO_VALUES.get(self.prio.text, PRIORITY_MED)

    def _dispatch_prio_value(self) -> int:
        return _PRIO_VALUES.get(self.dispatch_prio.text, PRIORITY_MED)

    def _dispatch(self, *_args) -> None:
        if not self.sync or not self.sync.is_logged_in:
            return

        def on_done(ok: bool, msg: str) -> None:
            if not ok:
                self._show_feedback(msg, error=True)
                return
            self.dispatch_title.text = ""
            self.dispatch_phone.text = ""
            self.dispatch_description.text = ""
            notify("WALL-E", sync_tr("assign.dispatch.ok"))
            self.refresh()

        self.sync.dispatch_assignment(
            self.dispatch_phone.text,
            self.dispatch_title.text,
            priority=self._dispatch_prio_value(),
            description=self.dispatch_description.text.strip(),
            on_done=on_done,
        )

    def _run_dismiss(self, assignment_id: str, role: str) -> None:
        if not self.sync:
            return
        try:
            self.sync.assignments.dismiss(assignment_id, role=role)
        except SyncBackendError as exc:
            self._show_feedback(str(exc), error=True)
        self.refresh()

    def _clear_archive(self) -> None:
        removed = self.store.clear_completed()
        assign_removed = 0
        if self.sync and self.sync.is_logged_in:
            assign_removed = self.sync.assignments.clear_archive()
        total = removed + assign_removed
        if total:
            notify("WALL-E", sync_tr("todo.archive.clear.summary", count=total))
        else:
            notify("WALL-E", sync_tr("todo.archive.clear.none"))
        self.refresh()

    def _populate_assign_sections(self, list_box, role: str) -> bool:
        am = self.sync.assignments
        if role == "inbox":
            sections = [
                (sync_tr("assign.section.inbox_pending"), am.inbox_pending),
                (sync_tr("assign.section.inbox_accepted"), am.accepted_inbox),
                (sync_tr("assign.section.inbox_rejected"), am.inbox_rejected),
                (sync_tr("assign.section.inbox_cancelled"), am.inbox_cancelled),
            ]
        else:
            sections = [
                (sync_tr("assign.section.outbox_pending"), am.outbox_pending),
                (sync_tr("assign.section.outbox_accepted"), am.accepted_outbox),
                (sync_tr("assign.section.outbox_rejected"), am.outbox_rejected),
                (sync_tr("assign.section.outbox_cancelled"), am.outbox_cancelled),
            ]
        has_any = False
        for title, items in sections:
            if not items:
                continue
            has_any = True
            list_box.add_widget(self._section_header(title))
            for item in items:
                list_box.add_widget(self._assignment_row(item, role))
        return has_any

    def _run_assign(self, action: str, assignment_id: str, note: str = "") -> None:
        if not self.sync:
            return
        try:
            if action == "accept":
                self.sync.accept_assignment(assignment_id)
            elif action == "reject":
                self.sync.reject_assignment(assignment_id, note)
            elif action == "complete":
                self.sync.complete_assignment(assignment_id)
            elif action == "cancel":
                self.sync.cancel_assignment(assignment_id, note)
        except SyncBackendError as exc:
            self._show_feedback(str(exc), error=True)
        self.refresh()

    def _prompt_reject(self, assignment_id: str) -> None:
        reason_popup(
            "拒绝任务",
            "请填写拒绝理由（必填）",
            lambda note: self._run_assign("reject", assignment_id, note),
        )

    def _prompt_cancel(self, assignment_id: str) -> None:
        reason_popup(
            "撤回任务",
            "请填写撤回理由（必填，将通知对方）",
            lambda note: self._run_assign("cancel", assignment_id, note),
        )

    def _assignment_row(self, assignment, role: str, *, archive: bool = False) -> ItemCard:
        card = ItemCard()
        phone = assignment.assigner_phone if role == "inbox" else assignment.assignee_phone
        display = self.sync.contact_display_name(phone) if self.sync else phone
        meta = f"{'来自' if role == 'inbox' else '派给'} {display}"
        if not archive:
            meta += f" · {_assignment_status(assignment.status)}"
        if role == "outbox" and assignment.status == STATUS_REJECTED and assignment.assignee_note:
            meta += f"\n回退理由：{assignment.assignee_note}"
        elif role == "inbox" and assignment.status == STATUS_CANCELLED and assignment.assigner_note:
            meta += f"\n撤回理由：{assignment.assigner_note}"
        desc = (assignment.description or "").strip()
        if desc:
            meta += f"\n{sync_tr('assign.description.show', text=desc)}"
        meta += f"\n{_format_assignment_times(assignment, archive=archive)}"
        title_lbl = Label(
            text=assignment.title,
            color=TEXT,
            font_size=Metrics.font_md,
            bold=True,
            halign="left",
            valign="top",
            size_hint_x=1,
            size_hint_y=None,
        )
        meta_lbl = Label(
            text=meta,
            color=TEXT_MUTED,
            font_size=Metrics.font_sm,
            halign="left",
            valign="top",
            size_hint_x=1,
            size_hint_y=None,
        )
        text_w = Metrics.inner_width(dp(20))
        bind_label_wrap(title_lbl, text_w)
        bind_label_wrap(meta_lbl, text_w)
        body = BoxLayout(orientation="vertical", size_hint_x=1, size_hint_y=None, spacing=dp(2))
        body.add_widget(title_lbl)
        body.add_widget(meta_lbl)
        body.bind(minimum_height=body.setter("height"))
        stripe = priority_stripe(assignment.priority)
        card.set_body(stripe, body)

        actions: list = []
        if archive:
            clear = ghost_btn(sync_tr("assign.clear_one"), size_hint_x=None, width=dp(68))
            clear.bind(on_release=lambda *_: self._run_dismiss(assignment.id, role))
            actions = [clear]
        elif role == "inbox":
            if assignment.status == STATUS_PENDING:
                acc = success_btn("接受")
                acc.bind(on_release=lambda *_: self._run_assign("accept", assignment.id))
                rej = danger_btn("拒绝")
                rej.bind(on_release=lambda *_: self._prompt_reject(assignment.id))
                actions = [acc, rej]
            elif assignment.status == STATUS_ACCEPTED:
                done = primary_btn("标记完成", font_size=Metrics.font_sm, height=Metrics.btn_h_sm)
                done.bind(on_release=lambda *_: self._run_assign("complete", assignment.id))
                actions = [done]
            elif assignment.status in (STATUS_REJECTED, STATUS_CANCELLED):
                clear = ghost_btn(sync_tr("assign.clear_one"), size_hint_x=None, width=dp(68))
                clear.bind(on_release=lambda *_: self._run_dismiss(assignment.id, role))
                actions = [clear]
        elif role == "outbox":
            if assignment.status in (STATUS_PENDING, STATUS_ACCEPTED):
                cancel = danger_btn("撤回")
                cancel.bind(on_release=lambda *_: self._prompt_cancel(assignment.id))
                actions = [cancel]
            elif assignment.status in (STATUS_REJECTED, STATUS_CANCELLED):
                clear = ghost_btn(sync_tr("assign.clear_one"), size_hint_x=None, width=dp(68))
                clear.bind(on_release=lambda *_: self._run_dismiss(assignment.id, role))
                actions = [clear]
        card.set_actions(actions)

        def _resize(*_args) -> None:
            body.height = title_lbl.height + meta_lbl.height + dp(4)
            card._body_row.height = body.height
            extra = Metrics.btn_h_sm + dp(8) if actions else 0
            card.height = max(dp(64), body.height + dp(20) + extra)

        title_lbl.bind(height=_resize)
        meta_lbl.bind(height=_resize)
        _resize()
        return card

    def _add(self, *_args) -> None:
        self.store.add(self.input.text, self._prio_value())
        self.input.text = ""

    def _task_row(self, task, on_toggle, on_remove) -> ItemCard:
        card = ItemCard()
        title_lbl = Label(
            text=(f"✓ {task.text}" if task.done else task.text),
            color=TEXT_DONE if task.done else TEXT,
            font_size=Metrics.font_md,
            bold=True,
            halign="left",
            valign="top",
            size_hint_x=1,
            size_hint_y=None,
        )
        meta_lbl = Label(
            text=_format_todo_times(task),
            color=TEXT_MUTED,
            font_size=Metrics.font_sm,
            halign="left",
            valign="top",
            size_hint_x=1,
            size_hint_y=None,
        )
        text_w = Metrics.inner_width(dp(20))
        bind_label_wrap(title_lbl, text_w)
        bind_label_wrap(meta_lbl, text_w)
        body = BoxLayout(orientation="vertical", size_hint_x=1, size_hint_y=None, spacing=dp(2))
        body.add_widget(title_lbl)
        body.add_widget(meta_lbl)
        body.bind(minimum_height=body.setter("height"))
        stripe = priority_stripe(task.priority)
        card.set_body(stripe, body)

        done_btn = compact_btn("完成" if not task.done else "还原", size_hint_x=1)
        done_btn.bind(on_release=lambda *_: on_toggle(task.id))
        del_btn = danger_btn("删除", size_hint_x=None, width=dp(68))
        del_btn.bind(on_release=lambda *_: on_remove(task.id))
        actions: list = [done_btn, del_btn]
        if not task.done:
            prio_spin = Spinner(
                text=_PRIO_LABELS.get(task.priority, sync_tr("prio.med")),
                values=(sync_tr("prio.high"), sync_tr("prio.med"), sync_tr("prio.low")),
                font_size=Metrics.font_sm,
                size_hint_x=None,
                width=dp(96),
                size_hint_y=None,
                height=Metrics.btn_h_sm,
            )
            prio_spin.bind(
                text=lambda _sp, val, tid=task.id: self.store.set_priority(
                    tid, _PRIO_VALUES.get(val, PRIORITY_MED)
                )
            )
            actions.insert(0, prio_spin)
        card.set_actions(actions)

        def _resize(*_args) -> None:
            body.height = title_lbl.height + meta_lbl.height + dp(4)
            card._body_row.height = body.height
            extra = Metrics.btn_h_sm + dp(8)
            card.height = max(dp(64), body.height + dp(20) + extra)

        title_lbl.bind(height=_resize)
        meta_lbl.bind(height=_resize)
        _resize()
        return card

    def refresh(self) -> None:
        self.active_list.clear_widgets()
        pending = self.store.pending()
        if pending:
            for t in pending:
                self.active_list.add_widget(self._task_row(t, self.store.toggle, self.store.remove))
        else:
            self.active_list.add_widget(walle_empty(sync_tr("todo.empty.personal"), anim="idle"))

        if self.sync is not None:
            self.inbox_list.clear_widgets()
            if self.sync.is_logged_in:
                if not self._populate_assign_sections(self.inbox_list, "inbox"):
                    self.inbox_list.add_widget(walle_empty(sync_tr("todo.empty.inbox"), anim="look"))
            else:
                self.inbox_list.add_widget(
                    walle_empty(sync_tr("sync.status.need_login"), anim=PAGE_ANIMS["login"])
                )

            self.outbox_list.clear_widgets()
            if self.sync.is_logged_in:
                if not self._populate_assign_sections(self.outbox_list, "outbox"):
                    self.outbox_list.add_widget(walle_empty(sync_tr("todo.empty.outbox"), anim="cheer"))
            else:
                self.outbox_list.add_widget(
                    walle_empty(sync_tr("sync.status.need_login"), anim=PAGE_ANIMS["login"])
                )

        self.archive_list.clear_widgets()
        personal_groups = self.store.completed_groups()
        inbox_groups: list = []
        outbox_groups: list = []
        if self.sync and self.sync.is_logged_in:
            inbox_groups = self.sync.assignments.archive_groups("inbox")
            outbox_groups = self.sync.assignments.archive_groups("outbox")

        if not personal_groups and not inbox_groups and not outbox_groups:
            self.archive_list.add_widget(walle_empty(sync_tr("todo.archive.empty"), anim="tired"))
            return

        if personal_groups:
            self.archive_list.add_widget(self._section_header(sync_tr("todo.archive.section.personal")))
            for day_key, tasks in personal_groups:
                self.archive_list.add_widget(self._day_header(day_key, len(tasks)))
                for t in tasks:
                    self.archive_list.add_widget(self._task_row(t, self.store.toggle, self.store.remove))

        if inbox_groups:
            self.archive_list.add_widget(self._section_header(sync_tr("todo.archive.section.inbox")))
            for day_key, assignments in inbox_groups:
                self.archive_list.add_widget(self._day_header(day_key, len(assignments)))
                for item in assignments:
                    self.archive_list.add_widget(self._assignment_row(item, "inbox", archive=True))

        if outbox_groups:
            self.archive_list.add_widget(self._section_header(sync_tr("todo.archive.section.outbox")))
            for day_key, assignments in outbox_groups:
                self.archive_list.add_widget(self._day_header(day_key, len(assignments)))
                for item in assignments:
                    self.archive_list.add_widget(self._assignment_row(item, "outbox", archive=True))

        self._update_sync_controls()


class NotesScreen(Screen):
    def __init__(self, store: NotesStore, **kwargs):
        super().__init__(**kwargs)
        self.store = store
        root = screen_root(page_tint=PAGE_NOTES_TINT)
        root.add_widget(
            walle_page_header("记事本", "随手记下灵感与备忘", anim=PAGE_ANIMS["notes"])
        )
        root.add_widget(walle_section_title("新建备忘", anim="talk"))

        form = BoxLayout(size_hint_y=None, height=Metrics.field_h, spacing=dp(8))
        self.input = field_input(hint_text="输入备忘内容")
        add_btn = primary_btn("添加", size_hint_x=None, width=dp(76))
        add_btn.bind(on_release=self._add)
        form.add_widget(self.input)
        form.add_widget(add_btn)
        root.add_widget(form)

        self.scroll, self.list_box = scroll_list()
        root.add_widget(self.scroll)
        self.add_widget(root)
        self.refresh()

    def _add(self, *_args) -> None:
        self.store.add(self.input.text)
        self.input.text = ""

    def refresh(self) -> None:
        self.list_box.clear_widgets()
        if not self.store.entries:
            self.list_box.add_widget(walle_empty("还没有条目", anim="talk"))
            return
        for entry in self.store.entries:
            card = ItemCard()
            editor = field_input(
                text=entry.text,
                multiline=True,
                size_hint_y=None,
                height=max(dp(100), Metrics.field_h * 2),
            )
            editor.bind(focus=lambda inst, focus, eid=entry.id: (not focus) and self.store.update(eid, inst.text))
            card.set_body(None, editor)
            del_btn = danger_btn("删除", size_hint_x=None, width=dp(80))
            del_btn.bind(on_release=lambda *_e, eid=entry.id: self.store.remove(eid))
            card.set_actions([del_btn])
            card.fit_widget(editor, min_body_h=max(dp(100), Metrics.field_h * 2))
            self.list_box.add_widget(card)


class ReminderScreen(Screen):
    def __init__(self, store: ReminderStore, **kwargs):
        super().__init__(**kwargs)
        self.store = store
        root = screen_root(page_tint=PAGE_REMIND_TINT)
        root.add_widget(
            walle_page_header("提醒", "按时提醒，不再错过", anim=PAGE_ANIMS["remind"])
        )
        root.add_widget(walle_section_title("新建提醒", anim="look"))

        self.text_input = field_input(hint_text="提醒内容")
        root.add_widget(self.text_input)

        self.time_input = field_input(text="09:00", hint_text="HH:MM", time_field=True)
        self.repeat = Spinner(
            text="每天",
            values=tuple(REPEAT_LABELS.values()),
            font_size=Metrics.font_md,
            size_hint_x=None,
            width=dp(96),
            size_hint_y=None,
            height=Metrics.field_h,
        )
        add_btn = primary_btn("添加", size_hint_x=None, width=dp(76))
        add_btn.bind(on_release=self._add)

        if Metrics.narrow:
            row = BoxLayout(size_hint_y=None, height=Metrics.field_h, spacing=dp(8))
            row.add_widget(self.time_input)
            row.add_widget(self.repeat)
            root.add_widget(row)
            root.add_widget(add_btn)
        else:
            row = BoxLayout(size_hint_y=None, height=Metrics.field_h, spacing=dp(8))
            row.add_widget(self.time_input)
            row.add_widget(self.repeat)
            row.add_widget(add_btn)
            root.add_widget(row)

        self.scroll, self.list_box = scroll_list()
        root.add_widget(self.scroll)
        self.add_widget(root)
        self.refresh()

    def _add(self, *_args) -> None:
        text = self.text_input.text.strip()
        parts = self.time_input.text.strip().split(":")
        if not text or len(parts) != 2:
            return
        try:
            hour, minute = int(parts[0]), int(parts[1])
        except ValueError:
            return
        repeat = next((k for k, v in REPEAT_LABELS.items() if v == self.repeat.text), REPEAT_DAILY)
        self.store.add(text, hour, minute, repeat)
        self.text_input.text = ""

    def refresh(self) -> None:
        self.list_box.clear_widgets()
        if not self.store.items:
            self.list_box.add_widget(walle_empty("暂无提醒", anim="look"))
            return
        for r in self.store.items:
            row = ItemCard()
            label = Label(
                text=self.store.format_item(r),
                color=TEXT,
                font_size=Metrics.font_md,
                halign="left",
                valign="top",
                size_hint_x=1,
                size_hint_y=None,
            )
            bind_label_wrap(label, Metrics.inner_width())
            row.set_body(None, label)
            del_btn = danger_btn("删除", size_hint_x=None, width=dp(72))
            del_btn.bind(on_release=lambda *_a, rid=r.id: self.store.remove(rid))
            row.set_actions([del_btn])
            row.fit_label(label)
            self.list_box.add_widget(row)


class TimerScreen(Screen):
    def __init__(self, timer: PomodoroTimer, settings: SettingsStore, **kwargs):
        super().__init__(**kwargs)
        self.timer = timer
        self.settings = settings
        work, rest, cycles = settings.timer_values()
        root = screen_root(page_tint=PAGE_TIMER_TINT)
        root.add_widget(
            walle_page_header("番茄钟", "专注工作，劳逸结合", anim=PAGE_ANIMS["timer"])
        )
        root.add_widget(walle_section_title("番茄钟设置", anim="idle"))

        cfg = BoxLayout(size_hint_y=None, height=Metrics.field_h, spacing=dp(8))
        self.work_in = field_input(text=str(work), hint_text="工作(分)", numeric=True)
        self.rest_in = field_input(text=str(rest), hint_text="休息(分)", numeric=True)
        self.cycles_in = field_input(text=str(cycles), hint_text="轮数", numeric=True)
        cfg.add_widget(self.work_in)
        cfg.add_widget(self.rest_in)
        cfg.add_widget(self.cycles_in)
        root.add_widget(cfg)

        body = BoxLayout(orientation="vertical", size_hint_y=1, padding=(0, dp(8)))
        mascot_row = BoxLayout(size_hint_y=None, height=dp(108))
        mascot_row.add_widget(Label())
        self._walle_mascot = WalleMascotPanel(anim="idle", size=dp(96))
        _attach_rounded_bg(mascot_row, MASCOT_BG, radius=dp(16))
        mascot_row.add_widget(self._walle_mascot)
        mascot_row.add_widget(Label())
        body.add_widget(mascot_row)
        self.status = Label(
            text="准备开始",
            font_size=Metrics.font_lg,
            color=TEXT_MUTED,
            size_hint_y=None,
            height=dp(36),
        )
        self.clock_lbl = Label(
            text="50:00",
            font_size=Metrics.font_clock,
            bold=True,
            color=ACCENT,
            size_hint_y=None,
            height=Metrics.font_clock + dp(16),
        )
        body.add_widget(self.status)
        body.add_widget(self.clock_lbl)
        body.add_widget(Label(text="", size_hint_y=0.08))

        row = BoxLayout(size_hint_y=None, height=Metrics.btn_h + dp(4), spacing=dp(8))
        start = primary_btn("开始", size_hint_x=1)
        start.bind(on_release=self._start)
        rest = ghost_btn("休息", size_hint_x=1)
        rest.bind(on_release=self._rest)
        stop = ghost_btn("停止", size_hint_x=1)
        stop.bind(on_release=self._stop)
        row.add_widget(start)
        row.add_widget(rest)
        row.add_widget(stop)
        body.add_widget(row)
        root.add_widget(body)
        self.add_widget(root)

    def _apply_settings(self) -> None:
        try:
            work = int(self.work_in.text or 50)
            rest = int(self.rest_in.text or 10)
            cycles = int(self.cycles_in.text or 3)
        except ValueError:
            work, rest, cycles = 50, 10, 3
        self.timer.configure(work, rest, cycles)
        self.settings.save_timer(work, rest, cycles)

    def _start(self, *_a) -> None:
        self._apply_settings()
        self.timer.start()

    def _rest(self, *_a) -> None:
        self._apply_settings()
        self.timer.start_rest_now()

    def _stop(self, *_a) -> None:
        self.timer.stop()

    def on_tick(self, remaining, state, cycle, total) -> None:
        self.clock_lbl.text = PomodoroTimer.format_time(remaining)
        if state == PomodoroState.IDLE:
            self.status.text = "准备开始"
            anim = "wave"
        elif state == PomodoroState.WORKING:
            self.status.text = f"专注中 · 第 {cycle}/{total} 轮"
            anim = "look"
        elif state == PomodoroState.RESTING:
            self.status.text = f"休息中 · 第 {cycle}/{total} 轮"
            anim = "rest"
        elif state == PomodoroState.FINISHED:
            self.status.text = "全部完成！"
            anim = "cheer"
        else:
            anim = "idle"
        if hasattr(self, "_walle_mascot"):
            self._walle_mascot.set_anim(anim)


class ConsoleApp(App):
    title = "WALL-E"

    def build(self):
        register_fonts()
        Metrics.refresh()
        Window.clearcolor = BG

        self.settings = SettingsStore()
        self._sync_ref: list[MobileSyncService | None] = [None]

        def _schedule_ui(fn):
            Clock.schedule_once(lambda _dt: fn(), 0)

        def _todo_change():
            _schedule_ui(self._todo_change_body)

        def _notes_change():
            _schedule_ui(self._notes_change_body)

        def _reminders_change():
            _schedule_ui(self._reminders_change_body)

        self.todo = TodoStore(on_change=_todo_change)
        self.notes = NotesStore(on_change=_notes_change)
        self.reminders = ReminderStore(on_change=_reminders_change, on_due=self._on_reminder_due)

        self.sync = None
        if MobileSyncService is not None:
            try:
                self.sync = MobileSyncService(
                    self.settings,
                    self.todo,
                    self.notes,
                    self.reminders,
                    on_status=self._on_sync_status,
                    on_data_changed=self._on_sync_data,
                    on_assignment_event=self._on_assignment_event,
                )
                self._sync_ref[0] = self.sync
            except Exception as exc:
                self._log_boot_error(exc)

        self.pomodoro = PomodoroTimer(on_tick=self._on_pomo_tick, on_state=self._on_pomo_state)
        work, rest, cycles = self.settings.timer_values()
        self.pomodoro.configure(work, rest, cycles)

        sm = ScreenManager()
        self.sm = sm
        self.todo_screen = TodoScreen(self.todo, sync=self.sync, name="todo")
        self.notes_screen = NotesScreen(self.notes, name="notes")
        self.reminder_screen = ReminderScreen(self.reminders, name="remind")
        self.timer_screen = TimerScreen(self.pomodoro, self.settings, name="timer")
        sm.add_widget(self.todo_screen)
        sm.add_widget(self.notes_screen)
        sm.add_widget(self.reminder_screen)
        sm.add_widget(self.timer_screen)

        nav_items = [
            ("待办", "todo"),
            ("记事", "notes"),
            ("提醒", "remind"),
            ("番茄钟", "timer"),
        ]
        if self.sync and AccountScreen is not None:
            self.account_screen = AccountScreen(self.sync, name="account")
            sm.add_widget(self.account_screen)
            nav_items.append(("账号", "account"))

        nav = BoxLayout(orientation="vertical")
        nav.add_widget(sm)
        nav.add_widget(BottomNav(sm, nav_items))

        def _on_screen_change(_inst, name: str) -> None:
            for screen in sm.screens:
                set_screen_mascots_active(screen, screen.name == name)

        sm.bind(current=_on_screen_change)
        _on_screen_change(sm, sm.current)

        if self.sync:
            Clock.schedule_once(lambda _dt: self._safe_sync_start(), 0.5)

        if is_android():
            request_runtime_permissions()
            Clock.schedule_once(lambda _dt: ensure_notification_channels(), 1.0)
            Clock.schedule_interval(lambda _dt: self._android_ui_sync(), 1)
        else:
            Clock.schedule_interval(lambda _dt: self.reminders.check_due(), 15)
            Clock.schedule_interval(lambda _dt: self.pomodoro.tick(), 1)
        Window.bind(on_resize=self._on_resize)
        host = BannerHost(nav)
        register_banner_host(host)
        return host

    def _todo_change_body(self) -> None:
        self._refresh_todo()
        if self._sync_ref[0]:
            self._sync_ref[0].schedule_push()

    def _notes_change_body(self) -> None:
        self._refresh_notes()
        if self._sync_ref[0]:
            self._sync_ref[0].schedule_push()

    def _reminders_change_body(self) -> None:
        self._on_reminders_changed()
        if self._sync_ref[0]:
            self._sync_ref[0].schedule_push()

    def _on_resize(self, *_args) -> None:
        Metrics.refresh()
        self._refresh_todo()
        self._refresh_notes()
        self._refresh_reminders()

    def _log_boot_error(self, exc: BaseException) -> None:
        import traceback

        traceback.print_exc()
        if _IS_ANDROID:
            try:
                from android_safe import log_boot_error

                log_boot_error(exc)
            except Exception:
                pass

    def _safe_sync_start(self) -> None:
        if not self.sync:
            return
        try:
            self.sync.start()
        except Exception as exc:
            self._log_boot_error(exc)

    def _on_sync_status(self, text: str) -> None:
        if hasattr(self, "account_screen"):
            self.account_screen.on_status(text)
        if hasattr(self, "todo_screen"):
            self.todo_screen.set_sync_status(text)

    def _on_sync_data(self) -> None:
        self._refresh_todo()
        self._refresh_notes()
        self._refresh_reminders()
        if hasattr(self, "account_screen"):
            self.account_screen.refresh()

    def _on_assignment_event(self, kind: str, assignment) -> None:
        if not self.sync:
            return
        messages = assignment_notify_messages(
            kind,
            assignment,
            user_id=self.sync.user_id,
            display_name=self.sync.contact_display_name,
            tr=sync_tr,
        )
        for text in messages:
            notify("WALL-E", text, urgent=True)
        if messages and hasattr(self, "todo_screen"):
            if hasattr(self, "sm"):
                self.sm.current = "todo"
            if kind in (EVENT_DISPATCHED, EVENT_WITHDRAWN):
                self.todo_screen.focus_subtab("inbox")
            elif kind in (EVENT_ACCEPTED, EVENT_REJECTED, EVENT_COMPLETED):
                self.todo_screen.focus_subtab("outbox")
        if messages:
            self._refresh_todo()

    def _sync_android_background(self) -> None:
        sync_background_service(self.pomodoro.is_active(), has_active_reminders())

    def _on_reminders_changed(self) -> None:
        self._refresh_reminders()
        self._sync_android_background()

    def _android_ui_sync(self) -> None:
        self.pomodoro.tick()
        self.reminders.check_due()
        self._sync_android_background()

    def _refresh_todo(self) -> None:
        if hasattr(self, "todo_screen"):
            self.todo_screen.refresh()

    def _refresh_notes(self) -> None:
        if hasattr(self, "notes_screen"):
            self.notes_screen.refresh()

    def _refresh_reminders(self) -> None:
        if hasattr(self, "reminder_screen"):
            self.reminder_screen.refresh()

    def _on_reminder_due(self, text: str) -> None:
        Clock.schedule_once(lambda _dt: notify("WALL-E 提醒", text, urgent=True), 0)

    def _on_pomo_tick(self, remaining, state, cycle, total) -> None:
        if hasattr(self, "timer_screen"):
            self.timer_screen.on_tick(remaining, state, cycle, total)

    def _on_pomo_state(self, _state) -> None:
        self._sync_android_background()

    def on_pause(self):
        self._sync_android_background()
        return True

    def on_resume(self):
        self.pomodoro.sync_from_disk()
        self._refresh_reminders()
        if self.sync and self.sync.is_logged_in:
            self.sync.sync_now()
        self._sync_android_background()
        return super().on_resume() if hasattr(super(), "on_resume") else None


if __name__ == "__main__":
    if _IS_ANDROID:
        from android_safe import install_android_excepthook

        install_android_excepthook()
    else:
        import traceback

        def _preview_excepthook(exc_type, exc, tb) -> None:
            traceback.print_exception(exc_type, exc, tb)
            if sys.stdin is not None and sys.stdin.isatty():
                try:
                    input("\n[预览异常] 按 Enter 退出…")
                except EOFError:
                    pass

        sys.excepthook = _preview_excepthook

    try:
        ConsoleApp().run()
    except Exception:
        if not _IS_ANDROID:
            traceback.print_exc()
            if sys.stdin is not None and sys.stdin.isatty():
                try:
                    input("\n[预览异常] 按 Enter 退出…")
                except EOFError:
                    pass
        raise
