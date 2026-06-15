"""控制面板窗口：待办、记事本、提醒、番茄钟。"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QDate, QSize, Qt, QTime, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QInputDialog,
    QMessageBox,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from .todo_manager import Task

from .config import Config
from .i18n import current, format_todo_archive_day, priority_labels, remind_repeat_options, set_language, tr
from .notes_manager import NoteEntry, NotesManager, format_note_timestamp
from .pet_window import MAX_PET_SIZE, MIN_PET_SIZE
from .pomodoro import PomodoroState, PomodoroTimer
from .reminder_manager import (
    REPEAT_DAILY,
    REPEAT_ONCE,
    REPEAT_WEEKDAYS,
    REPEAT_WEEKLY,
    ReminderManager,
)
from .sync.assignment_models import (
    STATUS_ACCEPTED,
    STATUS_CANCELLED,
    STATUS_PENDING,
    STATUS_REJECTED,
    Assignment,
)
from .sync.backend import SyncBackendError
from .todo_bulbs import PRIORITY_COLORS
from .todo_manager import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_MED, TodoManager

if TYPE_CHECKING:
    from .sync.service import SyncService

FONT_FAMILY = '"Microsoft YaHei UI", "PingFang SC", "Segoe UI", sans-serif'

PRIORITY_VALUES = (PRIORITY_HIGH, PRIORITY_MED, PRIORITY_LOW)
PRIORITY_INDEX = {PRIORITY_HIGH: 0, PRIORITY_MED: 1, PRIORITY_LOW: 2}

_ACCOUNT_INPUT_WIDTH = {
    "auth": 300,
    "phone": 240,
    "password": 240,
    "code": 144,
    "nickname": 200,
}
_ACCOUNT_FIELD_HEIGHT = 34


def _account_field(edit: QLineEdit, kind: str) -> QLineEdit:
    width = _ACCOUNT_INPUT_WIDTH.get(kind, 240)
    edit.setObjectName("accountField")
    edit.setMaximumWidth(width)
    edit.setMinimumWidth(min(width, 168))
    edit.setFixedHeight(_ACCOUNT_FIELD_HEIGHT)
    return edit


def _account_row_widget(widget) -> None:
    if hasattr(widget, "setFixedHeight"):
        widget.setFixedHeight(_ACCOUNT_FIELD_HEIGHT)


def _field_row(*widgets) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(8)
    for widget in widgets:
        row.addWidget(widget)
    row.addStretch(1)
    return row


def _account_divider() -> QFrame:
    line = QFrame()
    line.setObjectName("divider")
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    return line


def _account_section(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("section")
    return lbl


def _make_priority_combo(priority: int = PRIORITY_MED, *, compact: bool = False) -> QComboBox:
    combo = QComboBox()
    combo.addItems(priority_labels())
    combo.setCurrentIndex(PRIORITY_INDEX.get(priority, 1))
    if compact:
        combo.setMinimumWidth(76)
        combo.setMaximumWidth(84)
        combo.setStyleSheet("font-size: 12px; padding: 4px 6px;")
    else:
        combo.setMinimumWidth(88)
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    return combo

STYLE = f"""
QWidget {{
    background: #252220;
    color: #f3ebe0;
    font-family: {FONT_FAMILY};
    font-size: 14px;
}}
QTabWidget::pane {{
    border: 1px solid #4a4138;
    border-radius: 8px;
    top: -1px;
    padding: 4px;
}}
QTabBar::tab {{
    background: #35302a;
    padding: 10px 18px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 3px;
    color: #c8baa6;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    background: #c88a3a;
    color: #1f1b18;
    font-weight: bold;
}}
QTabBar::tab:hover:!selected {{
    background: #423a32;
}}
QLineEdit, QSpinBox, QPlainTextEdit, QComboBox, QTimeEdit, QDateEdit {{
    background: #1a1714;
    border: 1px solid #4a4138;
    border-radius: 8px;
    padding: 8px 10px;
    color: #f3ebe0;
    selection-background-color: #c88a3a;
    selection-color: #1f1b18;
}}
QLineEdit#accountField, QComboBox#accountField {{
    padding: 4px 10px;
}}
QLineEdit:focus, QSpinBox:focus, QPlainTextEdit:focus, QComboBox:focus,
QTimeEdit:focus, QDateEdit:focus {{
    border-color: #c88a3a;
}}
QPushButton {{
    background: #c88a3a;
    color: #1f1b18;
    border: none;
    border-radius: 8px;
    padding: 9px 16px;
    font-weight: bold;
    font-size: 13px;
}}
QPushButton:hover {{ background: #dd9c46; }}
QPushButton:pressed {{ background: #b07a32; }}
QPushButton#ghost {{
    background: #35302a;
    color: #e7dcc8;
    font-weight: normal;
}}
QPushButton#ghost:hover {{ background: #4a4138; }}
QListWidget {{
    background: #1a1714;
    border: 1px solid #4a4138;
    border-radius: 8px;
    padding: 6px;
    font-size: 14px;
}}
QListWidget::item {{
    padding: 0;
    margin: 0;
    border: none;
    background: transparent;
}}
QListWidget::item:hover {{ background: transparent; }}
QListWidget::item:selected {{ background: transparent; color: #f3ebe0; }}
QCheckBox {{
    spacing: 8px;
    font-size: 14px;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #4a4138;
    background: #1a1714;
}}
QCheckBox::indicator:checked {{
    background: #c88a3a;
    border-color: #c88a3a;
}}
QLabel#hint {{ color: #a89a82; font-size: 12px; }}
QLabel#section {{
    color: #c88a3a;
    font-size: 13px;
    font-weight: bold;
    padding-top: 4px;
}}
QSlider::groove:horizontal {{
    height: 6px;
    background: #35302a;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    width: 16px;
    margin: -5px 0;
    background: #c88a3a;
    border-radius: 8px;
}}
QFrame#divider {{
    color: #4a4138;
    max-height: 1px;
    margin: 10px 0 6px 0;
}}
QFrame#todoCard {{
    background: #1f1c19;
    border: 1px solid #3d3630;
    border-radius: 8px;
}}
QFrame#todoCardDone {{
    background: #1a1816;
    border: 1px solid #33302c;
    border-radius: 8px;
}}
QLabel#todoText {{
    font-size: 14px;
    color: #f3ebe0;
    background: transparent;
}}
QLabel#todoTextDone {{
    font-size: 14px;
    color: #6e6a64;
    background: transparent;
}}
QComboBox QAbstractItemView {{
    background: #1a1714;
    color: #f3ebe0;
    selection-background-color: #c88a3a;
    selection-color: #1f1b18;
    min-width: 120px;
}}
"""

class SquareCheckBox(QWidget):
    """方块勾选框：完成时显示打勾。"""

    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checked = checked
        self.setFixedSize(22, 22)
        self.setCursor(Qt.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        checked = bool(checked)
        if self._checked != checked:
            self._checked = checked
            self.update()
            self.toggled.emit(checked)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(2, 2, -2, -2)
        if self._checked:
            p.setPen(QPen(QColor(0x88, 0x88, 0x88), 2))
            p.setBrush(QColor(0x35, 0x30, 0x2A))
        else:
            p.setPen(QPen(QColor(0x6A, 0x60, 0x58), 2))
            p.setBrush(QColor(0x1A, 0x17, 0x14))
        p.drawRoundedRect(rect, 4, 4)
        if self._checked:
            p.setPen(QPen(QColor(0xC8, 0xBA, 0xA6), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            x1, y1 = rect.left() + 4, rect.center().y()
            x2, y2 = rect.center().x() - 1, rect.bottom() - 4
            x3, y3 = rect.right() - 3, rect.top() + 5
            p.drawLine(x1, y1, x2, y2)
            p.drawLine(x2, y2, x3, y3)
        p.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
            event.accept()


class NoteEntryWidget(QWidget):
    """单条记事：小文本框 + 日期 + 删除。"""

    text_changed = Signal(str, str)
    delete_requested = Signal(str)

    def __init__(self, entry: NoteEntry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._note_id = entry.id
        self._loading = False
        self._created = float(entry.created)
        self._updated_at = float(entry.updated_at)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(4)

        self.edit = QPlainTextEdit(entry.text)
        self.edit.setPlaceholderText(tr("notes.entry_placeholder"))
        self.edit.setMaximumHeight(80)
        self.edit.setMinimumHeight(52)
        nf = QFont("Microsoft YaHei UI", 13)
        self.edit.setFont(nf)
        self.edit.textChanged.connect(self._on_text)

        self.dates_label = QLabel()
        self.dates_label.setObjectName("hint")
        df = QFont("Microsoft YaHei UI", 10)
        self.dates_label.setFont(df)
        self._refresh_dates()

        content.addWidget(self.edit)
        content.addWidget(self.dates_label)

        del_btn = QPushButton("×")
        del_btn.setObjectName("ghost")
        del_btn.setFixedSize(32, 32)
        del_btn.setToolTip(tr("notes.delete_tip"))
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self._note_id))

        lay.addLayout(content, 1)
        lay.addWidget(del_btn, 0, Qt.AlignTop)

    def _refresh_dates(self) -> None:
        created_s = format_note_timestamp(self._created)
        updated_s = format_note_timestamp(self._updated_at)
        if abs(self._updated_at - self._created) < 1.0:
            self.dates_label.setText(tr("notes.created_at", datetime=created_s))
        else:
            self.dates_label.setText(
                tr("notes.created_updated", created=created_s, updated=updated_s)
            )

    def _on_text(self) -> None:
        if self._loading:
            return
        self._updated_at = time.time()
        self._refresh_dates()
        self.text_changed.emit(self._note_id, self.edit.toPlainText())

    def set_loading(self, loading: bool) -> None:
        self._loading = loading

    def focus_edit(self) -> None:
        self.edit.setFocus()


class PriorityBar(QWidget):
    """待办左侧优先级色条。"""

    def __init__(self, priority: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._priority = priority
        self.setFixedWidth(4)

    def set_priority(self, priority: int) -> None:
        self._priority = priority
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        color = PRIORITY_COLORS.get(self._priority, PRIORITY_COLORS[PRIORITY_MED])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(self.rect(), 2, 2)
        p.end()


class TodoItemWidget(QFrame):
    """待办卡片：勾选 + 色条 + 文本 + 优先级下拉。"""

    done_changed = Signal(str, bool)
    priority_changed = Signal(str, int)
    delete_requested = Signal(str)

    _SIDE = 22 + 4 + 10 + 84 + 28 + 40  # 勾选、色条、间距、下拉、边距、删除钮

    def __init__(self, task: Task, list_width: int = 480, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._task_id = task.id
        self._loading = True
        self._list_width = list_width
        self._apply_card_style(task.done)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(10)

        self.check = SquareCheckBox(task.done)
        self.check.toggled.connect(self._on_check)

        self.stripe = PriorityBar(task.priority)

        body = QVBoxLayout()
        body.setSpacing(6)
        body.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(task.text)
        self.label.setObjectName("todoTextDone" if task.done else "todoText")
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._apply_done_style(task.done)

        self.time_label = QLabel(_format_todo_time_lines(task))
        self.time_label.setObjectName("hint")
        self.time_label.setWordWrap(True)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addStretch(1)
        self.prio_combo = _make_priority_combo(task.priority, compact=True)
        self.prio_combo.currentIndexChanged.connect(self._on_priority_index)
        footer.addWidget(self.prio_combo, 0, Qt.AlignRight)

        body.addWidget(self.label)
        body.addWidget(self.time_label)
        body.addLayout(footer)

        outer.addWidget(self.check, 0, Qt.AlignTop | Qt.AlignHCenter)
        outer.addWidget(self.stripe, 0, Qt.AlignTop)
        outer.addLayout(body, 1)

        self.delete_btn = QPushButton("×")
        self.delete_btn.setObjectName("ghost")
        self.delete_btn.setFixedSize(32, 32)
        self.delete_btn.setToolTip(tr("todo.delete_tip"))
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self._task_id))
        outer.addWidget(self.delete_btn, 0, Qt.AlignTop)

        self._loading = False
        self._sync_label_width()

    def _apply_card_style(self, done: bool) -> None:
        self.setObjectName("todoCardDone" if done else "todoCard")

    def _text_width(self) -> int:
        return max(120, self._list_width - self._SIDE)

    def _sync_label_width(self) -> None:
        width = self._text_width()
        self.label.setFixedWidth(width)
        self.time_label.setMaximumWidth(width)

    def _apply_done_style(self, done: bool) -> None:
        f = self.label.font()
        f.setStrikeOut(done)
        self.label.setFont(f)
        self.label.setObjectName("todoTextDone" if done else "todoText")

    def _on_check(self, done: bool) -> None:
        if self._loading:
            return
        self._apply_done_style(done)
        self._apply_card_style(done)
        self.style().unpolish(self)
        self.style().polish(self)
        self.done_changed.emit(self._task_id, done)

    def _on_priority_index(self, index: int) -> None:
        if self._loading:
            return
        if 0 <= index < len(PRIORITY_VALUES):
            pri = PRIORITY_VALUES[index]
            self.stripe.set_priority(pri)
            self.priority_changed.emit(self._task_id, pri)

    def set_loading(self, loading: bool) -> None:
        self._loading = loading

    def height_hint(self) -> int:
        self._sync_label_width()
        self.label.adjustSize()
        self.time_label.adjustSize()
        self.adjustSize()
        return max(56, self.sizeHint().height())

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        super().mouseDoubleClickEvent(event)
        self.delete_requested.emit(self._task_id)


def _assignment_status_text(status: str) -> str:
    key = f"assign.status.{status}"
    text = tr(key)
    return text if text != key else status


def _format_todo_time_lines(task: Task) -> str:
    lines = [tr("todo.created_at", datetime=format_note_timestamp(task.created))]
    if task.done:
        ts = task.completed_at or task.updated_at or task.created
        lines.append(tr("todo.completed_at", datetime=format_note_timestamp(ts)))
    return "\n".join(lines)


def _format_assignment_time_lines(assignment: Assignment, *, archive: bool) -> str:
    lines = [
        tr("assign.dispatched_at", datetime=format_note_timestamp(assignment.created_at)),
    ]
    if archive:
        ts = assignment.completed_at or assignment.updated_at
        if ts:
            lines.append(tr("assign.completed_at", datetime=format_note_timestamp(ts)))
    return "\n".join(lines)


class AssignmentItemWidget(QFrame):
    """跨账号任务卡片。"""

    accept_requested = Signal(str)
    reject_requested = Signal(str)
    complete_requested = Signal(str)
    cancel_requested = Signal(str)
    dismiss_requested = Signal(str)

    # 色条(4) + 外边距左右(10+10) + 色条与正文间距(10)
    _SIDE = 4 + 10 + 10 + 10

    def __init__(
        self,
        assignment: Assignment,
        *,
        role: str,
        list_width: int = 480,
        party_display: str | None = None,
        archive: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._assignment_id = assignment.id
        self._list_width = list_width
        self.setObjectName("todoCard")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(10)

        self.stripe = PriorityBar(assignment.priority)

        body = QVBoxLayout()
        body.setSpacing(6)
        body.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel(assignment.title)
        if archive:
            self.title_label.setObjectName("todoTextDone")
        self.title_label.setWordWrap(True)
        self.title_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.description_label = QLabel()
        self.description_label.setObjectName("hint")
        self.description_label.setWordWrap(True)
        self.description_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        if assignment.description.strip():
            self.description_label.setText(tr("assign.description.show", text=assignment.description.strip()))
            self.description_label.setVisible(True)
        else:
            self.description_label.setVisible(False)

        phone = assignment.assigner_phone if role == "inbox" else assignment.assignee_phone
        display = party_display or phone
        phone_text = tr("assign.from", name=display) if role == "inbox" else tr("assign.to", name=display)
        meta = f"{phone_text} · {_assignment_status_text(assignment.status)}"
        meta += f"\n{_format_assignment_time_lines(assignment, archive=archive)}"
        if role == "outbox" and assignment.status == STATUS_REJECTED and assignment.assignee_note:
            meta += f"\n{tr('assign.note.returned', note=assignment.assignee_note)}"
        elif role == "inbox" and assignment.status == STATUS_CANCELLED and assignment.assigner_note:
            meta += f"\n{tr('assign.note.withdrawn', note=assignment.assigner_note)}"
        self.meta_label = QLabel(meta)
        self.meta_label.setObjectName("hint")
        self.meta_label.setWordWrap(True)

        body.addWidget(self.title_label)
        if self.description_label.isVisible():
            body.addWidget(self.description_label)
        body.addWidget(self.meta_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.setContentsMargins(0, 0, 0, 0)
        if archive:
            dismiss_btn = QPushButton(tr("assign.clear_one"))
            dismiss_btn.setObjectName("ghost")
            dismiss_btn.setMinimumWidth(56)
            dismiss_btn.clicked.connect(lambda: self.dismiss_requested.emit(self._assignment_id))
            btn_row.addWidget(dismiss_btn)
        elif role == "inbox":
            if assignment.status == STATUS_PENDING:
                accept_btn = QPushButton(tr("assign.accept"))
                accept_btn.setMinimumWidth(56)
                accept_btn.clicked.connect(lambda: self.accept_requested.emit(self._assignment_id))
                return_btn = QPushButton(tr("assign.return"))
                return_btn.setObjectName("ghost")
                return_btn.setMinimumWidth(56)
                return_btn.clicked.connect(lambda: self.reject_requested.emit(self._assignment_id))
                btn_row.addWidget(accept_btn)
                btn_row.addWidget(return_btn)
            elif assignment.status == STATUS_ACCEPTED:
                complete_btn = QPushButton(tr("assign.complete"))
                complete_btn.setMinimumWidth(56)
                complete_btn.clicked.connect(lambda: self.complete_requested.emit(self._assignment_id))
                btn_row.addWidget(complete_btn)
        elif role == "outbox" and assignment.status in (STATUS_PENDING, STATUS_ACCEPTED):
            cancel_btn = QPushButton(tr("assign.cancel"))
            cancel_btn.setObjectName("ghost")
            cancel_btn.setMinimumWidth(72)
            cancel_btn.clicked.connect(lambda: self.cancel_requested.emit(self._assignment_id))
            btn_row.addWidget(cancel_btn)
        if not archive and assignment.status in (STATUS_REJECTED, STATUS_CANCELLED):
            dismiss_btn = QPushButton(tr("assign.clear_one"))
            dismiss_btn.setObjectName("ghost")
            dismiss_btn.setMinimumWidth(56)
            dismiss_btn.clicked.connect(lambda: self.dismiss_requested.emit(self._assignment_id))
            btn_row.addWidget(dismiss_btn)
        btn_row.addStretch(1)
        body.addLayout(btn_row)

        outer.addWidget(self.stripe, 0, Qt.AlignTop)
        outer.addLayout(body, 1)
        self._sync_label_width()

    def _text_width(self) -> int:
        return max(120, self._list_width - self._SIDE)

    def _sync_label_width(self) -> None:
        width = self._text_width()
        self.title_label.setMaximumWidth(width)
        if self.description_label.isVisible():
            self.description_label.setMaximumWidth(width)
        self.meta_label.setMaximumWidth(width)

    def height_hint(self) -> int:
        self._sync_label_width()
        self.ensurePolished()
        self.title_label.adjustSize()
        if self.description_label.isVisible():
            self.description_label.adjustSize()
        self.meta_label.adjustSize()
        layout = self.layout()
        if layout is not None:
            layout.activate()
        self.adjustSize()
        return max(72, self.sizeHint().height())


class ControlPanel(QWidget):
    """主控制面板。"""

    start_timer_requested = Signal()
    start_rest_requested = Signal()
    end_rest_requested = Signal()
    settings_applied = Signal()
    pet_size_changed = Signal(int)

    def __init__(
        self,
        config: Config,
        todo: TodoManager,
        notes: NotesManager,
        reminders: ReminderManager,
        timer: PomodoroTimer,
        sync: "SyncService | None" = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.todo = todo
        self.notes = notes
        self.reminders = reminders
        self.timer = timer
        self.sync = sync
        self._account_tab_index = -1
        self._assign_action_pending = False

        self._todo_refresh_timer = QTimer(self)
        self._todo_refresh_timer.setSingleShot(True)
        self._todo_refresh_timer.setInterval(50)
        self._todo_refresh_timer.timeout.connect(self._flush_refresh_todo)

        self._notes_refresh_timer = QTimer(self)
        self._notes_refresh_timer.setSingleShot(True)
        self._notes_refresh_timer.setInterval(50)
        self._notes_refresh_timer.timeout.connect(self._flush_refresh_notes)

        self._reminders_refresh_timer = QTimer(self)
        self._reminders_refresh_timer.setSingleShot(True)
        self._reminders_refresh_timer.setInterval(50)
        self._reminders_refresh_timer.timeout.connect(self._flush_refresh_reminders)

        self._assign_refresh_timer = QTimer(self)
        self._assign_refresh_timer.setSingleShot(True)
        self._assign_refresh_timer.setInterval(50)
        self._assign_refresh_timer.timeout.connect(self._flush_refresh_assignments)

        self._pending_notes_focus_id: int | None = None
        self._layout_refresh_timer = QTimer(self)
        self._layout_refresh_timer.setSingleShot(True)
        self._layout_refresh_timer.setInterval(80)
        self._layout_refresh_timer.timeout.connect(self._flush_layout_sensitive_lists)
        self._env_editing = not (self.sync and self.sync.user_env_saved)

        self.setWindowTitle(tr("panel.title"))
        self.resize(600, 820)
        self.setMinimumSize(560, 680)
        self.setStyleSheet(STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        self.header = QLabel(tr("panel.header"))
        hf = QFont("Microsoft YaHei UI", 16)
        hf.setBold(True)
        self.header.setFont(hf)
        self.header.setStyleSheet("color: #c88a3a; padding-bottom: 2px;")
        root.addWidget(self.header)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.tabs.addTab(self._build_todo_tab(), tr("tab.todo"))
        self.tabs.addTab(self._build_notes_tab(), tr("tab.notes"))
        self.tabs.addTab(self._build_reminders_tab(), tr("tab.reminders"))
        self.tabs.addTab(self._build_timer_tab(), tr("tab.timer"))
        if self.sync and self.sync.enabled:
            self._account_tab_index = self.tabs.count()
            self.tabs.addTab(self._build_account_tab(), tr("tab.account"))
            self.sync.status_changed.connect(self._on_sync_status)
            self.sync.login_finished.connect(self._on_login_finished)
            self.sync.sms_sent.connect(self._on_sms_sent)
            self.sync.assignments_changed.connect(self.refresh_assignments)
            self.sync.contacts_changed.connect(self.refresh_assignments)
            self.sync.config_saved.connect(self._on_env_saved)
            self.sync.sync_busy_changed.connect(self._on_sync_busy)
            self.sync.sync_paused_changed.connect(self._refresh_account_ui)
            self.sync.assignment_action_finished.connect(self._on_assignment_action_finished)
            self._refresh_account_ui()

        self.todo.changed.connect(self.refresh_todo)
        self.notes.changed.connect(self.refresh_notes)
        self.reminders.changed.connect(self.refresh_reminders)
        self.timer.tick.connect(self._on_tick)
        self.timer.state_changed.connect(self._on_state)
        self.refresh_todo()
        self.refresh_notes()
        self.refresh_reminders()
        if hasattr(self, "assign_inbox_scroll"):
            self.refresh_assignments()
        self._update_workbench_title()

    def flush_all_lists(self) -> None:
        """立即刷新各列表（账号切换/同步后避免错位）。"""
        for timer in (
            self._todo_refresh_timer,
            self._notes_refresh_timer,
            self._reminders_refresh_timer,
            self._assign_refresh_timer,
            self._layout_refresh_timer,
        ):
            timer.stop()
        self._flush_refresh_todo()
        self._flush_refresh_notes()
        self._flush_refresh_reminders()
        if hasattr(self, "assign_inbox_scroll"):
            self._flush_refresh_assignments()
        if hasattr(self, "contacts_list"):
            self._refresh_contacts_list()

    def _flush_layout_sensitive_lists(self) -> None:
        if hasattr(self, "todo_list"):
            self._flush_refresh_todo()
        if hasattr(self, "assign_inbox_scroll"):
            self._flush_refresh_assignments()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "todo_list"):
            self._layout_refresh_timer.start()

    def _workbench_header_text(self) -> str:
        if self.sync and self.sync.is_logged_in and self.sync.phone:
            return tr("panel.header.logged_in", account=self.sync.phone)
        return tr("panel.header")

    def _update_workbench_title(self) -> None:
        text = self._workbench_header_text()
        if hasattr(self, "header"):
            self.header.setText(text)
        self.setWindowTitle(text)

    def show_assign_focus(self, role: str) -> None:
        """瓦力信封/旗子点击：打开待办页并聚焦派发给/我派出的已接受分组。"""
        if not hasattr(self, "todo_subtabs"):
            return
        self.tabs.setCurrentIndex(0)
        tab_idx = (
            getattr(self, "_assign_inbox_tab_index", -1)
            if role == "inbox"
            else getattr(self, "_assign_outbox_tab_index", -1)
        )
        if tab_idx < 0:
            return
        self.todo_subtabs.setCurrentIndex(tab_idx)
        label = (
            self.assign_inbox_accepted_label
            if role == "inbox"
            else self.assign_outbox_accepted_label
        )
        scroll = (
            self.assign_inbox_scroll
            if role == "inbox"
            else self.assign_outbox_scroll
        )
        if label.isVisible():
            QTimer.singleShot(80, lambda: scroll.ensureWidgetVisible(label, 0, 20))

    def _on_todo_sync_retry(self) -> None:
        if self.sync and self.sync.is_logged_in:
            self.sync.sync_now()

    def _update_todo_sync_status(self, text: str) -> None:
        if hasattr(self, "todo_sync_status"):
            self.todo_sync_status.setText(text)
        if hasattr(self, "todo_sync_retry_btn") and self.sync:
            self.todo_sync_retry_btn.setEnabled(
                self.sync.is_logged_in
                and self.sync.backend_configured
                and not self.sync.sync_busy
            )

    # =============================================================== 待办页
    def _build_todo_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.todo_input = QLineEdit()
        self.todo_input.setPlaceholderText(tr("todo.placeholder"))
        self.todo_input.returnPressed.connect(self._add_todo)
        self.priority_combo = _make_priority_combo(PRIORITY_MED)
        add = QPushButton(tr("todo.add"))
        self.todo_add_btn = add
        add.setMinimumWidth(72)
        add.clicked.connect(self._add_todo)
        row.addWidget(self.todo_input, 1)
        row.addWidget(self.priority_combo)
        row.addWidget(add)
        lay.addLayout(row)

        if self.sync and self.sync.enabled:
            sync_row = QHBoxLayout()
            sync_row.setSpacing(8)
            self.todo_sync_status = QLabel()
            self.todo_sync_status.setObjectName("hint")
            self.todo_sync_status.setWordWrap(True)
            self.todo_sync_retry_btn = QPushButton(tr("sync.retry"))
            self.todo_sync_retry_btn.setObjectName("ghost")
            self.todo_sync_retry_btn.clicked.connect(self._on_todo_sync_retry)
            sync_row.addWidget(self.todo_sync_status, 1)
            sync_row.addWidget(self.todo_sync_retry_btn)
            lay.addLayout(sync_row)
            self._update_todo_sync_status(self.sync.status_text())

        self.todo_subtabs = QTabWidget()
        lay.addWidget(self.todo_subtabs, 1)

        active_w = QWidget()
        active_lay = QVBoxLayout(active_w)
        active_lay.setSpacing(8)
        self.todo_hint = QLabel(tr("todo.hint"))
        self.todo_hint.setObjectName("hint")
        active_lay.addWidget(self.todo_hint)
        self.todo_list = QListWidget()
        self.todo_list.setUniformItemSizes(False)
        self.todo_list.setSpacing(6)
        self.todo_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.todo_list.itemDoubleClicked.connect(self._on_item_double)
        active_lay.addWidget(self.todo_list, 1)
        self.todo_subtabs.addTab(active_w, tr("todo.subtab.active"))

        if self.sync and self.sync.enabled:
            inbox_w = QWidget()
            inbox_lay = QVBoxLayout(inbox_w)
            inbox_lay.setSpacing(8)
            self.assign_inbox_hint = QLabel(tr("assign.hint.inbox"))
            self.assign_inbox_hint.setObjectName("hint")
            inbox_lay.addWidget(self.assign_inbox_hint)
            self.assign_inbox_scroll = QScrollArea()
            self.assign_inbox_scroll.setWidgetResizable(True)
            self.assign_inbox_scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            inbox_sections_w = QWidget()
            self.assign_inbox_sections_lay = QVBoxLayout(inbox_sections_w)
            self.assign_inbox_sections_lay.setSpacing(8)
            self.assign_inbox_sections_lay.setContentsMargins(0, 0, 0, 0)

            self.assign_inbox_pending_label = QLabel(tr("assign.section.inbox_pending"))
            self.assign_inbox_pending_label.setObjectName("section")
            self.assign_inbox_sections_lay.addWidget(self.assign_inbox_pending_label)
            self.assign_inbox_pending_list = QListWidget()
            self.assign_inbox_pending_list.setUniformItemSizes(False)
            self.assign_inbox_pending_list.setSpacing(6)
            self.assign_inbox_pending_list.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self.assign_inbox_sections_lay.addWidget(self.assign_inbox_pending_list)

            self.assign_inbox_accepted_label = QLabel(tr("assign.section.inbox_accepted"))
            self.assign_inbox_accepted_label.setObjectName("section")
            self.assign_inbox_sections_lay.addWidget(self.assign_inbox_accepted_label)
            self.assign_inbox_accepted_list = QListWidget()
            self.assign_inbox_accepted_list.setUniformItemSizes(False)
            self.assign_inbox_accepted_list.setSpacing(6)
            self.assign_inbox_accepted_list.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self.assign_inbox_sections_lay.addWidget(self.assign_inbox_accepted_list)

            self.assign_inbox_rejected_label = QLabel(tr("assign.section.inbox_rejected"))
            self.assign_inbox_rejected_label.setObjectName("section")
            self.assign_inbox_sections_lay.addWidget(self.assign_inbox_rejected_label)
            self.assign_inbox_rejected_list = QListWidget()
            self.assign_inbox_rejected_list.setUniformItemSizes(False)
            self.assign_inbox_rejected_list.setSpacing(6)
            self.assign_inbox_rejected_list.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self.assign_inbox_sections_lay.addWidget(self.assign_inbox_rejected_list)

            self.assign_inbox_cancelled_label = QLabel(tr("assign.section.inbox_cancelled"))
            self.assign_inbox_cancelled_label.setObjectName("section")
            self.assign_inbox_sections_lay.addWidget(self.assign_inbox_cancelled_label)
            self.assign_inbox_cancelled_list = QListWidget()
            self.assign_inbox_cancelled_list.setUniformItemSizes(False)
            self.assign_inbox_cancelled_list.setSpacing(6)
            self.assign_inbox_cancelled_list.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self.assign_inbox_sections_lay.addWidget(self.assign_inbox_cancelled_list)

            self.assign_inbox_empty = QLabel(tr("assign.empty.inbox"))
            self.assign_inbox_empty.setObjectName("hint")
            self.assign_inbox_empty.setAlignment(Qt.AlignCenter)
            self.assign_inbox_sections_lay.addWidget(self.assign_inbox_empty)
            self.assign_inbox_sections_lay.addStretch(1)

            self.assign_inbox_scroll.setWidget(inbox_sections_w)
            inbox_lay.addWidget(self.assign_inbox_scroll, 1)
            self._assign_inbox_tab_index = self.todo_subtabs.addTab(
                inbox_w, tr("todo.subtab.inbox")
            )

            outbox_w = QWidget()
            outbox_lay = QVBoxLayout(outbox_w)
            outbox_lay.setSpacing(8)
            self.assign_outbox_hint = QLabel(tr("assign.hint.outbox"))
            self.assign_outbox_hint.setObjectName("hint")
            outbox_lay.addWidget(self.assign_outbox_hint)
            dispatch_row = QHBoxLayout()
            dispatch_row.setSpacing(8)
            self.assign_phone_input = _account_field(QLineEdit(), "phone")
            self.assign_phone_input.setPlaceholderText(tr("assign.phone"))
            self.assign_title_input = QLineEdit()
            self.assign_title_input.setPlaceholderText(tr("assign.title"))
            self.assign_title_input.returnPressed.connect(self._on_dispatch_assignment)
            self.assign_priority_combo = _make_priority_combo(PRIORITY_MED, compact=True)
            self.assign_dispatch_btn = QPushButton(tr("assign.dispatch"))
            self.assign_dispatch_btn.clicked.connect(self._on_dispatch_assignment)
            dispatch_row.addWidget(self.assign_phone_input, 0)
            dispatch_row.addWidget(self.assign_title_input, 1)
            dispatch_row.addWidget(self.assign_priority_combo)
            dispatch_row.addWidget(self.assign_dispatch_btn)
            outbox_lay.addLayout(dispatch_row)
            self.assign_description_input = QPlainTextEdit()
            self.assign_description_input.setPlaceholderText(tr("assign.description.placeholder"))
            self.assign_description_input.setMaximumHeight(72)
            self.assign_description_input.setMinimumHeight(48)
            outbox_lay.addWidget(self.assign_description_input)
            self.assign_outbox_scroll = QScrollArea()
            self.assign_outbox_scroll.setWidgetResizable(True)
            self.assign_outbox_scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            outbox_sections_w = QWidget()
            self.assign_outbox_sections_lay = QVBoxLayout(outbox_sections_w)
            self.assign_outbox_sections_lay.setSpacing(8)
            self.assign_outbox_sections_lay.setContentsMargins(0, 0, 0, 0)

            self.assign_outbox_pending_label = QLabel(tr("assign.section.outbox_pending"))
            self.assign_outbox_pending_label.setObjectName("section")
            self.assign_outbox_sections_lay.addWidget(self.assign_outbox_pending_label)
            self.assign_outbox_pending_list = QListWidget()
            self.assign_outbox_pending_list.setUniformItemSizes(False)
            self.assign_outbox_pending_list.setSpacing(6)
            self.assign_outbox_pending_list.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self.assign_outbox_sections_lay.addWidget(self.assign_outbox_pending_list)

            self.assign_outbox_accepted_label = QLabel(tr("assign.section.outbox_accepted"))
            self.assign_outbox_accepted_label.setObjectName("section")
            self.assign_outbox_sections_lay.addWidget(self.assign_outbox_accepted_label)
            self.assign_outbox_accepted_list = QListWidget()
            self.assign_outbox_accepted_list.setUniformItemSizes(False)
            self.assign_outbox_accepted_list.setSpacing(6)
            self.assign_outbox_accepted_list.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self.assign_outbox_sections_lay.addWidget(self.assign_outbox_accepted_list)

            self.assign_outbox_rejected_label = QLabel(tr("assign.section.outbox_rejected"))
            self.assign_outbox_rejected_label.setObjectName("section")
            self.assign_outbox_sections_lay.addWidget(self.assign_outbox_rejected_label)
            self.assign_outbox_rejected_list = QListWidget()
            self.assign_outbox_rejected_list.setUniformItemSizes(False)
            self.assign_outbox_rejected_list.setSpacing(6)
            self.assign_outbox_rejected_list.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self.assign_outbox_sections_lay.addWidget(self.assign_outbox_rejected_list)

            self.assign_outbox_cancelled_label = QLabel(tr("assign.section.outbox_cancelled"))
            self.assign_outbox_cancelled_label.setObjectName("section")
            self.assign_outbox_sections_lay.addWidget(self.assign_outbox_cancelled_label)
            self.assign_outbox_cancelled_list = QListWidget()
            self.assign_outbox_cancelled_list.setUniformItemSizes(False)
            self.assign_outbox_cancelled_list.setSpacing(6)
            self.assign_outbox_cancelled_list.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self.assign_outbox_sections_lay.addWidget(self.assign_outbox_cancelled_list)

            self.assign_outbox_empty = QLabel(tr("assign.empty.outbox"))
            self.assign_outbox_empty.setObjectName("hint")
            self.assign_outbox_empty.setAlignment(Qt.AlignCenter)
            self.assign_outbox_sections_lay.addWidget(self.assign_outbox_empty)
            self.assign_outbox_sections_lay.addStretch(1)

            self.assign_outbox_scroll.setWidget(outbox_sections_w)
            outbox_lay.addWidget(self.assign_outbox_scroll, 1)
            self._assign_outbox_tab_index = self.todo_subtabs.addTab(
                outbox_w, tr("todo.subtab.outbox")
            )
            self.todo_subtabs.currentChanged.connect(self._on_todo_subtab_changed)

        archive_w = QWidget()
        archive_lay = QVBoxLayout(archive_w)
        archive_lay.setSpacing(8)
        self.todo_archive_hint = QLabel(tr("todo.archive.hint"))
        self.todo_archive_hint.setObjectName("hint")
        archive_lay.addWidget(self.todo_archive_hint)
        self.todo_archive_scroll = QScrollArea()
        self.todo_archive_scroll.setWidgetResizable(True)
        self.todo_archive_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.todo_archive_container = QWidget()
        self.todo_archive_layout = QVBoxLayout(self.todo_archive_container)
        self.todo_archive_layout.setSpacing(8)
        self.todo_archive_layout.setContentsMargins(0, 0, 0, 0)
        self.todo_archive_layout.addStretch(1)
        self.todo_archive_scroll.setWidget(self.todo_archive_container)
        archive_lay.addWidget(self.todo_archive_scroll, 1)
        archive_clear_row = QHBoxLayout()
        archive_clear_row.setSpacing(8)
        self.todo_archive_clear_btn = QPushButton(tr("todo.archive.clear"))
        self.todo_archive_clear_btn.setObjectName("ghost")
        self.todo_archive_clear_btn.clicked.connect(self._clear_archive)
        archive_clear_row.addWidget(self.todo_archive_clear_btn)
        archive_clear_row.addStretch(1)
        archive_lay.addLayout(archive_clear_row)
        self.todo_subtabs.addTab(archive_w, tr("todo.subtab.archive"))

        return w

    def _add_todo(self) -> None:
        text = self.todo_input.text().strip()
        if text:
            idx = self.priority_combo.currentIndex()
            pri = PRIORITY_VALUES[idx] if 0 <= idx < len(PRIORITY_VALUES) else PRIORITY_MED
            self.todo.add(text, priority=pri)
            self.todo_input.clear()

    def _on_todo_done(self, task_id: str, done: bool) -> None:
        task = self.todo.find(task_id)
        if task and task.done != done:
            self.todo.set_done(task_id, done)

    def _on_todo_priority(self, task_id: str, priority: int) -> None:
        self.todo.set_priority(task_id, priority)

    def _on_item_double(self, item: QListWidgetItem) -> None:
        task_id = item.data(Qt.UserRole)
        if task_id is not None:
            self.todo.remove(task_id)

    def _on_todo_delete(self, task_id: str) -> None:
        self.todo.remove(task_id)

    def _clear_archive(self) -> None:
        removed = self.todo.clear_completed()
        assign_removed = 0
        if self.sync and self.sync.is_logged_in:
            assign_removed = self.sync.assignments.clear_archive()
        total = removed + assign_removed
        if total:
            QMessageBox.information(
                self,
                tr("todo.archive.clear"),
                tr("todo.archive.clear.summary", count=total),
            )
        else:
            QMessageBox.information(
                self, tr("todo.archive.clear"), tr("todo.archive.clear.none")
            )
        self.refresh_todo()
        self.refresh_assignments()

    def _on_assign_dismiss(self, assignment_id: str, role: str) -> None:
        if not self.sync or not self.sync.is_logged_in:
            return
        try:
            self.sync.assignments.dismiss(assignment_id, role=role)
            self.refresh_assignments()
        except SyncBackendError as exc:
            msg = self.sync.friendly_error(str(exc)) if self.sync else str(exc)
            QMessageBox.warning(self, tr("assign.clear_one"), msg)

    def _assign_list_width(self, viewport) -> int:
        return max(300, viewport.width())

    def _make_assignment_row(
        self,
        assignment: Assignment,
        *,
        role: str,
        list_width: int,
        archive: bool = False,
    ) -> AssignmentItemWidget:
        phone = assignment.assigner_phone if role == "inbox" else assignment.assignee_phone
        display = self.sync.contact_display_name(phone) if self.sync else phone
        row = AssignmentItemWidget(
            assignment,
            role=role,
            list_width=list_width,
            party_display=display,
            archive=archive,
        )
        row.accept_requested.connect(self._on_assign_accept)
        row.reject_requested.connect(self._on_assign_reject)
        row.complete_requested.connect(self._on_assign_complete)
        row.cancel_requested.connect(self._on_assign_cancel)
        row.dismiss_requested.connect(
            lambda aid: self._on_assign_dismiss(aid, role)
        )
        return row

    def _run_assign_action(self, action: str, assignment_id: str) -> None:
        if not self.sync or not self.sync.is_logged_in:
            return
        method_map = {
            "accept": "accept_assignment",
            "reject": "reject_assignment",
            "complete": "complete_assignment",
            "cancel": "cancel_assignment",
        }
        method_name = method_map.get(action, action)
        getattr(self.sync, method_name)(assignment_id)

    def _on_assign_accept(self, assignment_id: str) -> None:
        self._run_assign_action("accept", assignment_id)

    def _on_assign_reject(self, assignment_id: str) -> None:
        note, ok = QInputDialog.getMultiLineText(
            self,
            tr("assign.reject.title"),
            tr("assign.reject.prompt"),
            "",
        )
        if not ok or not note.strip():
            return
        self.sync.reject_assignment(assignment_id, note.strip())  # type: ignore[union-attr]

    def _on_assign_complete(self, assignment_id: str) -> None:
        self._run_assign_action("complete", assignment_id)

    def _on_assign_cancel(self, assignment_id: str) -> None:
        note, ok = QInputDialog.getMultiLineText(
            self,
            tr("assign.cancel.title"),
            tr("assign.cancel.prompt"),
            "",
        )
        if not ok or not note.strip():
            return
        self.sync.cancel_assignment(assignment_id, note.strip())  # type: ignore[union-attr]

    def _assign_feedback(self, message: str, *, error: bool = False) -> None:
        if hasattr(self, "sync_status_label"):
            self.sync_status_label.setText(message)
        if hasattr(self, "assign_outbox_hint"):
            self.assign_outbox_hint.setText(message)
        if error:
            QMessageBox.warning(self, tr("assign.dispatch"), message)

    def _on_dispatch_assignment(self) -> None:
        if not self.sync:
            return
        if not self.sync.is_logged_in:
            self._assign_feedback(tr("assign.err.need_login"), error=True)
            return
        if not self.sync.backend_configured:
            self._assign_feedback(tr("sync.err.need_config"), error=True)
            return
        idx = self.assign_priority_combo.currentIndex()
        pri = PRIORITY_VALUES[idx] if 0 <= idx < len(PRIORITY_VALUES) else PRIORITY_MED
        self._assign_action_pending = True
        self._update_assign_action_enabled()
        self.sync.dispatch_assignment(
            self.assign_phone_input.text(),
            self.assign_title_input.text(),
            priority=pri,
            description=self.assign_description_input.toPlainText(),
        )

    def refresh_assignments(self) -> None:
        if not hasattr(self, "assign_inbox_scroll"):
            return
        self._assign_refresh_timer.start()

    def _on_todo_subtab_changed(self, index: int) -> None:
        """切换到「派给我的」「我派出的」时主动拉取派发，避免漏掉新任务。"""
        if not self.sync or not self.sync.is_logged_in:
            return
        if index in (
            getattr(self, "_assign_inbox_tab_index", -1),
            getattr(self, "_assign_outbox_tab_index", -1),
        ):
            if not self.sync.sync_paused:
                self.sync.sync_assignments_only()

    def _on_sync_pause_toggled(self, checked: bool) -> None:
        if self.sync:
            self.sync.set_sync_paused(checked)

    def _fill_assignment_list(
        self,
        list_widget: QListWidget,
        assignments: list[Assignment],
        *,
        role: str,
        empty_text: str,
    ) -> None:
        list_w = self._assign_list_width(list_widget.viewport())
        list_widget.clear()
        if not assignments:
            if empty_text:
                empty = QListWidgetItem(empty_text)
                empty.setFlags(Qt.ItemFlag.NoItemFlags)
                list_widget.addItem(empty)
            return
        for assignment in assignments:
            row = self._make_assignment_row(assignment, role=role, list_width=list_w)
            item = QListWidgetItem()
            item.setData(Qt.UserRole, assignment.id)
            list_widget.addItem(item)
            list_widget.setItemWidget(item, row)
            item.setSizeHint(QSize(list_w, row.height_hint()))

    def _show_assignment_section(
        self,
        label: QLabel,
        list_widget: QListWidget,
        assignments: list[Assignment],
        *,
        role: str,
    ) -> bool:
        show = bool(assignments)
        label.setVisible(show)
        list_widget.setVisible(show)
        if show:
            self._fill_assignment_list(
                list_widget,
                assignments,
                role=role,
                empty_text="",
            )
        else:
            list_widget.clear()
        return show

    def _flush_refresh_assignments(self) -> None:
        if not hasattr(self, "assign_inbox_scroll") or not self.sync:
            return
        if self.sync.is_logged_in:
            inbox_pending = self.sync.assignments.inbox_pending
            inbox_accepted = self.sync.assignments.accepted_inbox
            inbox_rejected = self.sync.assignments.inbox_rejected
            inbox_cancelled = self.sync.assignments.inbox_cancelled
            outbox_pending = self.sync.assignments.outbox_pending
            outbox_accepted = self.sync.assignments.accepted_outbox
            outbox_rejected = self.sync.assignments.outbox_rejected
            outbox_cancelled = self.sync.assignments.outbox_cancelled
        else:
            inbox_pending = []
            inbox_accepted = []
            inbox_rejected = []
            inbox_cancelled = []
            outbox_pending = []
            outbox_accepted = []
            outbox_rejected = []
            outbox_cancelled = []

        inbox_has = False
        inbox_has |= self._show_assignment_section(
            self.assign_inbox_pending_label,
            self.assign_inbox_pending_list,
            inbox_pending,
            role="inbox",
        )
        inbox_has |= self._show_assignment_section(
            self.assign_inbox_accepted_label,
            self.assign_inbox_accepted_list,
            inbox_accepted,
            role="inbox",
        )
        inbox_has |= self._show_assignment_section(
            self.assign_inbox_rejected_label,
            self.assign_inbox_rejected_list,
            inbox_rejected,
            role="inbox",
        )
        inbox_has |= self._show_assignment_section(
            self.assign_inbox_cancelled_label,
            self.assign_inbox_cancelled_list,
            inbox_cancelled,
            role="inbox",
        )
        self.assign_inbox_empty.setVisible(not inbox_has)

        outbox_has = False
        outbox_has |= self._show_assignment_section(
            self.assign_outbox_pending_label,
            self.assign_outbox_pending_list,
            outbox_pending,
            role="outbox",
        )
        outbox_has |= self._show_assignment_section(
            self.assign_outbox_accepted_label,
            self.assign_outbox_accepted_list,
            outbox_accepted,
            role="outbox",
        )
        outbox_has |= self._show_assignment_section(
            self.assign_outbox_rejected_label,
            self.assign_outbox_rejected_list,
            outbox_rejected,
            role="outbox",
        )
        outbox_has |= self._show_assignment_section(
            self.assign_outbox_cancelled_label,
            self.assign_outbox_cancelled_list,
            outbox_cancelled,
            role="outbox",
        )
        self.assign_outbox_empty.setVisible(not outbox_has)

        self._update_assign_action_enabled()
        self._refresh_todo_archive()

    def _update_assign_action_enabled(self) -> None:
        if not hasattr(self, "assign_dispatch_btn") or not self.sync:
            return
        enabled = (
            self.sync.is_logged_in
            and self.sync.backend_configured
            and not self.sync.sync_busy
            and not self._assign_action_pending
        )
        self.assign_dispatch_btn.setEnabled(enabled)
        self.assign_phone_input.setEnabled(enabled)
        self.assign_title_input.setEnabled(enabled)
        if hasattr(self, "assign_description_input"):
            self.assign_description_input.setEnabled(enabled)
        self.assign_priority_combo.setEnabled(enabled)

    def _on_sync_busy(self, busy: bool) -> None:
        self._update_assign_action_enabled()
        if hasattr(self, "sync_now_btn") and self.sync:
            logged_in = self.sync.is_logged_in
            env_saved = self.sync.backend_configured
            self.sync_now_btn.setEnabled(logged_in and env_saved and not busy)
        if self.sync:
            self._update_todo_sync_status(self.sync.status_text())

    def _on_assignment_action_finished(self, ok: bool, message: str) -> None:
        pending_dispatch = self._assign_action_pending
        self._assign_action_pending = False
        if pending_dispatch:
            if ok:
                self.assign_title_input.clear()
                self.assign_phone_input.clear()
                if hasattr(self, "assign_description_input"):
                    self.assign_description_input.clear()
                self.refresh_assignments()
                if hasattr(self, "sync_status_label"):
                    self.sync_status_label.setText(tr("assign.dispatch.ok"))
                if hasattr(self, "assign_outbox_hint"):
                    self.assign_outbox_hint.setText(tr("assign.hint.outbox"))
            else:
                self._assign_feedback(message, error=True)
        elif not ok and hasattr(self, "sync_status_label"):
            self.sync_status_label.setText(message)
        self._update_assign_action_enabled()

    def _todo_list_width(self, viewport) -> int:
        return max(300, viewport.width())

    def _make_todo_row(self, task: Task, list_width: int) -> TodoItemWidget:
        row = TodoItemWidget(task, list_width=list_width)
        row.done_changed.connect(self._on_todo_done)
        row.priority_changed.connect(self._on_todo_priority)
        row.delete_requested.connect(self._on_todo_delete)
        return row

    def refresh_todo(self) -> None:
        if not hasattr(self, "todo_list"):
            return
        self._todo_refresh_timer.start()

    def _flush_refresh_todo(self) -> None:
        if not hasattr(self, "todo_list"):
            return
        self.todo_list.clear()
        list_w = self._todo_list_width(self.todo_list.viewport())
        for t in self.todo.pending():
            row = self._make_todo_row(t, list_w)
            item = QListWidgetItem()
            item.setData(Qt.UserRole, t.id)
            item.setSizeHint(QSize(list_w, row.height_hint()))
            self.todo_list.addItem(item)
            self.todo_list.setItemWidget(item, row)
        self._refresh_todo_archive()

    def _refresh_todo_archive(self) -> None:
        if not hasattr(self, "todo_archive_layout"):
            return
        while self.todo_archive_layout.count() > 1:
            item = self.todo_archive_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        personal_groups = self.todo.completed_groups()
        inbox_groups: list[tuple[str, list[Assignment]]] = []
        outbox_groups: list[tuple[str, list[Assignment]]] = []
        if self.sync and self.sync.is_logged_in:
            inbox_groups = self.sync.assignments.archive_groups("inbox")
            outbox_groups = self.sync.assignments.archive_groups("outbox")

        if not personal_groups and not inbox_groups and not outbox_groups:
            empty = QLabel(tr("todo.archive.empty"))
            empty.setObjectName("hint")
            empty.setAlignment(Qt.AlignCenter)
            self.todo_archive_layout.insertWidget(0, empty)
            return

        list_w = self._todo_list_width(self.todo_archive_scroll.viewport())
        insert_at = 0

        def add_section_header(text: str) -> None:
            nonlocal insert_at
            header = QLabel(text)
            header.setObjectName("section")
            self.todo_archive_layout.insertWidget(insert_at, header)
            insert_at += 1

        def add_day_header(day_key: str, count: int) -> None:
            nonlocal insert_at
            header = QLabel(
                tr(
                    "todo.archive.day_header",
                    date=format_todo_archive_day(day_key),
                    count=count,
                )
            )
            header.setObjectName("section")
            self.todo_archive_layout.insertWidget(insert_at, header)
            insert_at += 1

        if personal_groups:
            add_section_header(tr("todo.archive.section.personal"))
            for day_key, tasks in personal_groups:
                add_day_header(day_key, len(tasks))
                for task in tasks:
                    row = self._make_todo_row(task, list_w)
                    self.todo_archive_layout.insertWidget(insert_at, row)
                    insert_at += 1

        if inbox_groups:
            add_section_header(tr("todo.archive.section.inbox"))
            for day_key, assignments in inbox_groups:
                add_day_header(day_key, len(assignments))
                for assignment in assignments:
                    row = self._make_assignment_row(
                        assignment,
                        role="inbox",
                        list_width=list_w,
                        archive=True,
                    )
                    self.todo_archive_layout.insertWidget(insert_at, row)
                    insert_at += 1

        if outbox_groups:
            add_section_header(tr("todo.archive.section.outbox"))
            for day_key, assignments in outbox_groups:
                add_day_header(day_key, len(assignments))
                for assignment in assignments:
                    row = self._make_assignment_row(
                        assignment,
                        role="outbox",
                        list_width=list_w,
                        archive=True,
                    )
                    self.todo_archive_layout.insertWidget(insert_at, row)
                    insert_at += 1

    # =============================================================== 提醒页
    def _build_reminders_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(10)

        self.remind_hint = QLabel(tr("remind.hint"))
        self.remind_hint.setObjectName("hint")
        lay.addWidget(self.remind_hint)

        self.remind_text = QLineEdit()
        self.remind_text.setPlaceholderText(tr("remind.placeholder"))
        self.remind_text.returnPressed.connect(self._add_reminder)
        lay.addWidget(self.remind_text)

        form_row = QHBoxLayout()
        form_row.setSpacing(8)

        self.remind_time_lbl = QLabel(tr("remind.time"))
        self.remind_time_lbl.setMinimumWidth(56)
        self.remind_time = QTimeEdit()
        self.remind_time.setDisplayFormat("HH:mm")
        self.remind_time.setTime(QTime.currentTime())
        self.remind_time.setMinimumWidth(88)
        self.remind_time.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.remind_time.setKeyboardTracking(True)

        self.remind_repeat_lbl = QLabel(tr("remind.repeat"))
        self.remind_repeat_lbl.setMinimumWidth(32)
        self.remind_repeat = QComboBox()
        self.remind_repeat.addItems(remind_repeat_options())
        self.remind_repeat.setMinimumWidth(148)
        self.remind_repeat.currentIndexChanged.connect(self._on_remind_repeat_changed)

        self.remind_date = QDateEdit()
        self.remind_date.setCalendarPopup(True)
        self.remind_date.setDisplayFormat("yyyy-MM-dd")
        self.remind_date.setDate(QDate.currentDate())
        self.remind_date.setMinimumWidth(120)
        self.remind_date.setVisible(False)

        add_btn = QPushButton(tr("remind.add"))
        self.remind_add_btn = add_btn
        add_btn.setMinimumWidth(88)
        add_btn.clicked.connect(self._add_reminder)

        form_row.addWidget(self.remind_time_lbl)
        form_row.addWidget(self.remind_time)
        form_row.addWidget(self.remind_repeat_lbl)
        form_row.addWidget(self.remind_repeat, 1)
        form_row.addWidget(self.remind_date)
        form_row.addWidget(add_btn)
        lay.addLayout(form_row)

        self.remind_list_hint = QLabel(tr("remind.list_hint"))
        self.remind_list_hint.setObjectName("hint")
        lay.addWidget(self.remind_list_hint)

        self.reminder_list = QListWidget()
        lay.addWidget(self.reminder_list, 1)

        btn_row = QHBoxLayout()
        del_btn = QPushButton(tr("remind.delete_sel"))
        self.remind_del_btn = del_btn
        del_btn.setObjectName("ghost")
        del_btn.clicked.connect(self._delete_reminder)
        btn_row.addWidget(del_btn)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)
        return w

    def _on_remind_repeat_changed(self, index: int) -> None:
        # 最后一项为「单次」时显示日期选择
        self.remind_date.setVisible(index == self.remind_repeat.count() - 1)

    def _add_reminder(self) -> None:
        text = self.remind_text.text().strip()
        if not text:
            self.remind_text.setFocus()
            return
        t = self.remind_time.time()
        hour, minute = t.hour(), t.minute()
        idx = self.remind_repeat.currentIndex()

        if idx == 0:
            self.reminders.add(text, hour, minute, repeat=REPEAT_DAILY)
        elif idx == 1:
            self.reminders.add(text, hour, minute, repeat=REPEAT_WEEKDAYS)
        elif idx <= 8:
            self.reminders.add(text, hour, minute, repeat=REPEAT_WEEKLY, weekday=idx - 2)
        else:
            target = self.remind_date.date().toString("yyyy-MM-dd")
            self.reminders.add(text, hour, minute, repeat=REPEAT_ONCE, target_date=target)

        self.remind_text.clear()

    def _delete_reminder(self) -> None:
        item = self.reminder_list.currentItem()
        if item is None:
            return
        rid = item.data(Qt.UserRole)
        if rid is not None:
            self.reminders.remove(int(rid))

    def refresh_reminders(self) -> None:
        if not hasattr(self, "reminder_list"):
            return
        self._reminders_refresh_timer.start()

    def _flush_refresh_reminders(self) -> None:
        if not hasattr(self, "reminder_list"):
            return
        self.reminder_list.clear()
        for r in self.reminders.active():
            item = QListWidgetItem(self.reminders.format_item(r))
            item.setData(Qt.UserRole, r.id)
            self.reminder_list.addItem(item)

    # =============================================================== 记事本页
    def _build_notes_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(10)

        self.notes_hint = QLabel(tr("notes.hint"))
        self.notes_hint.setObjectName("hint")
        lay.addWidget(self.notes_hint)

        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText(tr("notes.placeholder"))
        self.note_input.returnPressed.connect(self._add_note_entry)
        add_btn = QPushButton(tr("notes.add"))
        self.notes_add_btn = add_btn
        add_btn.setMinimumWidth(88)
        add_btn.clicked.connect(self._add_note_entry)
        add_row.addWidget(self.note_input, 1)
        add_row.addWidget(add_btn)
        lay.addLayout(add_row)

        self.notes_scroll = QScrollArea()
        self.notes_scroll.setWidgetResizable(True)
        self.notes_scroll.setFrameShape(QFrame.NoFrame)
        self.notes_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.notes_container = QWidget()
        self.notes_layout = QVBoxLayout(self.notes_container)
        self.notes_layout.setContentsMargins(0, 0, 0, 0)
        self.notes_layout.setSpacing(8)
        self.notes_layout.addStretch(1)
        self.notes_scroll.setWidget(self.notes_container)
        lay.addWidget(self.notes_scroll, 1)

        status_row = QHBoxLayout()
        save_btn = QPushButton(tr("notes.save_all"))
        self.notes_save_btn = save_btn
        save_btn.setObjectName("ghost")
        save_btn.clicked.connect(self._save_notes_now)
        self.notes_status = QLabel("")
        self.notes_status.setObjectName("hint")
        status_row.addWidget(save_btn)
        status_row.addStretch(1)
        status_row.addWidget(self.notes_status)
        lay.addLayout(status_row)
        return w

    def _add_note_entry(self) -> None:
        text = self.note_input.text().strip()
        entry = self.notes.add(text)
        self.note_input.clear()
        self.refresh_notes(focus_id=entry.id)

    def _on_note_text(self, note_id: str, text: str) -> None:
        self.notes.update_text(note_id, text)
        self.notes_status.setText(tr("notes.auto_saved"))

    def _on_note_delete(self, note_id: str) -> None:
        self.notes.remove(note_id)

    def refresh_notes(self, focus_id: int | None = None) -> None:
        if not hasattr(self, "notes_layout"):
            return
        if focus_id is not None:
            self._pending_notes_focus_id = focus_id
        self._notes_refresh_timer.start()

    def _flush_refresh_notes(self) -> None:
        focus_id = self._pending_notes_focus_id
        self._pending_notes_focus_id = None
        if not hasattr(self, "notes_layout"):
            return
        while self.notes_layout.count() > 1:
            item = self.notes_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        focus_widget: NoteEntryWidget | None = None
        for entry in self.notes.entries:
            row = NoteEntryWidget(entry)
            row.set_loading(True)
            row.text_changed.connect(self._on_note_text)
            row.delete_requested.connect(self._on_note_delete)
            row.set_loading(False)
            self.notes_layout.insertWidget(self.notes_layout.count() - 1, row)
            if entry.id == focus_id:
                focus_widget = row

        if not self.notes.entries:
            empty = QLabel(tr("notes.empty"))
            empty.setObjectName("hint")
            empty.setAlignment(Qt.AlignCenter)
            self.notes_layout.insertWidget(0, empty)

        if focus_widget:
            focus_widget.focus_edit()

    def _save_notes_now(self) -> None:
        self.notes.save()
        self.notes_status.setText(tr("notes.saved"))

    # =============================================================== 番茄钟页
    def _build_timer_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(12)

        self.status_label = QLabel(tr("timer.idle"))
        sf = QFont("Microsoft YaHei UI", 15)
        sf.setBold(True)
        self.status_label.setFont(sf)
        self.status_label.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.status_label)

        self.countdown_label = QLabel("--:--")
        cf = QFont("Consolas", 42)
        cf.setBold(True)
        self.countdown_label.setFont(cf)
        self.countdown_label.setAlignment(Qt.AlignCenter)
        self.countdown_label.setStyleSheet("color:#c88a3a; letter-spacing:2px;")
        lay.addWidget(self.countdown_label)

        line = QFrame()
        line.setObjectName("divider")
        line.setFrameShape(QFrame.HLine)
        lay.addWidget(line)

        self.timer_section = QLabel(tr("timer.settings"))
        self.timer_section.setObjectName("section")
        lay.addWidget(self.timer_section)

        def add_spin(label_text, key, lo, hi):
            r = QHBoxLayout()
            r.setSpacing(12)
            lbl = QLabel(label_text)
            lbl.setMinimumWidth(130)
            sp = QSpinBox()
            sp.setRange(lo, hi)
            sp.setValue(int(self.config.get(key)))
            sp.setMinimumWidth(80)
            sp.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            sp.setKeyboardTracking(False)
            r.addWidget(lbl)
            r.addStretch(1)
            r.addWidget(sp)
            lay.addLayout(r)
            return sp, lbl

        self.spin_work, self.lbl_work = add_spin(tr("timer.work_min"), "work_minutes", 1, 180)
        self.spin_rest, self.lbl_rest = add_spin(tr("timer.rest_min"), "rest_minutes", 1, 120)
        self.spin_cycles, self.lbl_cycles = add_spin(tr("timer.cycles"), "cycles", 1, 12)

        self.chk_sound = QCheckBox(tr("timer.sound"))
        self.chk_sound.setChecked(bool(self.config.get("rest_sound")))
        self.chk_sound.stateChanged.connect(self._apply_settings)
        lay.addWidget(self.chk_sound)

        for sp in (self.spin_work, self.spin_rest, self.spin_cycles):
            sp.valueChanged.connect(self._apply_settings)

        line2 = QFrame()
        line2.setObjectName("divider")
        line2.setFrameShape(QFrame.HLine)
        lay.addWidget(line2)

        self.lang_section = QLabel(tr("settings.language"))
        self.lang_section.setObjectName("section")
        lay.addWidget(self.lang_section)

        lang_row = QHBoxLayout()
        lang_row.setSpacing(10)
        self.lang_combo = QComboBox()
        self.lang_combo.addItem(tr("lang.zh"), "zh")
        self.lang_combo.addItem(tr("lang.en"), "en")
        lang = self.config.get("language", "zh")
        self.lang_combo.setCurrentIndex(0 if lang != "en" else 1)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_row.addWidget(self.lang_combo, 1)
        lay.addLayout(lang_row)

        self.pet_section = QLabel(tr("timer.pet_size"))
        self.pet_section.setObjectName("section")
        lay.addWidget(self.pet_section)

        self.pet_hint = QLabel(tr("timer.pet_hint"))
        self.pet_hint.setObjectName("hint")
        lay.addWidget(self.pet_hint)

        pet_row = QHBoxLayout()
        pet_row.setSpacing(10)
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(MIN_PET_SIZE, MAX_PET_SIZE)
        self.size_slider.setValue(int(self.config.get("pet_size", 160)))
        self.size_slider.setTickPosition(QSlider.TicksBelow)
        self.size_slider.setTickInterval(40)
        self.size_label = QLabel(f"{self.size_slider.value()} px")
        self.size_label.setMinimumWidth(56)
        self.size_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.size_slider.valueChanged.connect(self._on_size_slider)
        pet_row.addWidget(self.size_slider, 1)
        pet_row.addWidget(self.size_label)
        lay.addLayout(pet_row)

        lay.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_start = QPushButton(tr("timer.start"))
        self.btn_start.clicked.connect(self.start_timer_requested.emit)
        self.btn_rest = QPushButton(tr("timer.rest"))
        self.btn_rest.setObjectName("ghost")
        self.btn_rest.clicked.connect(self.start_rest_requested.emit)
        self.btn_stop = QPushButton(tr("timer.stop"))
        self.btn_stop.setObjectName("ghost")
        self.btn_stop.clicked.connect(self.timer.stop)
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_rest)
        btn_row.addWidget(self.btn_stop)
        lay.addLayout(btn_row)
        return w

    # =============================================================== 账号页
    def _build_account_tab(self) -> QWidget:
        outer = QWidget()
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(8)
        lay.setContentsMargins(0, 0, 0, 0)

        self.sync_title = QLabel(tr("sync.title"))
        self.sync_title.setObjectName("section")
        lay.addWidget(self.sync_title)

        self.sync_env_label = _account_section(tr("sync.env_id"))
        lay.addWidget(self.sync_env_label)
        self.sync_env_input = _account_field(QLineEdit(), "auth")
        self.sync_env_input.setPlaceholderText(tr("sync.env.placeholder"))
        if self.sync:
            self.sync_env_input.setText(self.sync.user_cloudbase_env_id)
        self.sync_env_save_btn = QPushButton(tr("sync.env.save"))
        self.sync_env_save_btn.clicked.connect(self._on_save_env)
        _account_row_widget(self.sync_env_save_btn)
        lay.addLayout(_field_row(self.sync_env_input, self.sync_env_save_btn))

        self.sync_setup_hint = QLabel(tr("sync.setup_hint"))
        self.sync_setup_hint.setObjectName("hint")
        lay.addWidget(self.sync_setup_hint)

        self.sync_status_label = QLabel("")
        self.sync_status_label.setObjectName("hint")
        self.sync_status_label.setWordWrap(True)
        lay.addWidget(self.sync_status_label)

        self.sync_login_divider = _account_divider()
        lay.addWidget(self.sync_login_divider)

        self.sync_login_block = QWidget()
        login_lay = QVBoxLayout(self.sync_login_block)
        login_lay.setSpacing(6)
        login_lay.setContentsMargins(0, 0, 0, 0)

        self.sync_login_section = _account_section(tr("sync.section.login"))
        login_lay.addWidget(self.sync_login_section)

        self.sync_login_mode_label = QLabel(tr("sync.login.mode"))
        login_lay.addWidget(self.sync_login_mode_label)
        self.sync_login_mode_combo = QComboBox()
        self.sync_login_mode_combo.addItem(tr("sync.login.password"), "password")
        self.sync_login_mode_combo.addItem(tr("sync.login.sms"), "sms")
        self.sync_login_mode_combo.addItem(tr("sync.login.register"), "register")
        self.sync_login_mode_combo.setMaximumWidth(200)
        self.sync_login_mode_combo.setObjectName("accountField")
        _account_row_widget(self.sync_login_mode_combo)
        self.sync_login_mode_combo.currentIndexChanged.connect(self._on_login_mode_changed)
        login_lay.addLayout(_field_row(self.sync_login_mode_combo))

        self.sync_register_hint = QLabel(tr("sync.register.hint"))
        self.sync_register_hint.setObjectName("hint")
        self.sync_register_hint.setWordWrap(True)
        login_lay.addWidget(self.sync_register_hint)

        self.sync_phone_label = QLabel(tr("sync.phone"))
        login_lay.addWidget(self.sync_phone_label)
        self.sync_phone_input = _account_field(QLineEdit(), "phone")
        self.sync_phone_input.setPlaceholderText("13800138000")
        login_lay.addLayout(_field_row(self.sync_phone_input))

        self.sync_password_label = QLabel(tr("sync.password"))
        login_lay.addWidget(self.sync_password_label)
        self.sync_password_input = _account_field(QLineEdit(), "password")
        self.sync_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        login_lay.addLayout(_field_row(self.sync_password_input))

        self.sync_sms_code_label = QLabel(tr("sync.sms.code"))
        login_lay.addWidget(self.sync_sms_code_label)
        self.sync_sms_code_input = _account_field(QLineEdit(), "code")
        self.sync_sms_code_input.setPlaceholderText("123456")
        self.sync_sms_send_btn = QPushButton(tr("sync.sms.send"))
        self.sync_sms_send_btn.setObjectName("ghost")
        self.sync_sms_send_btn.clicked.connect(self._on_send_sms)
        _account_row_widget(self.sync_sms_send_btn)
        login_lay.addLayout(_field_row(self.sync_sms_code_input, self.sync_sms_send_btn))

        self.sync_login_btn = QPushButton(tr("sync.login"))
        self.sync_login_btn.clicked.connect(self._on_sync_login)
        login_lay.addLayout(_field_row(self.sync_login_btn))

        lay.addWidget(self.sync_login_block)

        self.sync_pause_chk = QCheckBox(tr("sync.pause"))
        self.sync_pause_chk.toggled.connect(self._on_sync_pause_toggled)
        if self.sync:
            self.sync_pause_chk.setChecked(self.sync.sync_paused)
        lay.addWidget(self.sync_pause_chk)

        self.sync_session_row = QWidget()
        session_lay = QHBoxLayout(self.sync_session_row)
        session_lay.setSpacing(8)
        session_lay.setContentsMargins(0, 0, 0, 0)
        self.sync_logout_btn = QPushButton(tr("sync.logout"))
        self.sync_logout_btn.setObjectName("ghost")
        self.sync_logout_btn.clicked.connect(self._on_sync_logout)
        self.sync_now_btn = QPushButton(tr("sync.now"))
        self.sync_now_btn.setObjectName("ghost")
        self.sync_now_btn.clicked.connect(self._on_sync_now)
        session_lay.addWidget(self.sync_logout_btn)
        session_lay.addWidget(self.sync_now_btn)
        session_lay.addStretch(1)
        lay.addWidget(self.sync_session_row)

        self.sync_contacts_divider = _account_divider()
        lay.addWidget(self.sync_contacts_divider)

        self.contacts_title = _account_section(tr("contacts.title"))
        lay.addWidget(self.contacts_title)
        self.contacts_hint = QLabel(tr("contacts.hint"))
        self.contacts_hint.setObjectName("hint")
        lay.addWidget(self.contacts_hint)
        self.contacts_phone_label = QLabel(tr("contacts.phone"))
        lay.addWidget(self.contacts_phone_label)
        self.contacts_phone_input = _account_field(QLineEdit(), "phone")
        self.contacts_phone_input.setPlaceholderText("13800138000")
        lay.addLayout(_field_row(self.contacts_phone_input))
        self.contacts_nickname_label = QLabel(tr("contacts.nickname"))
        lay.addWidget(self.contacts_nickname_label)
        self.contacts_nickname_input = _account_field(QLineEdit(), "nickname")
        lay.addLayout(_field_row(self.contacts_nickname_input))
        contact_btn_row = QHBoxLayout()
        contact_btn_row.setSpacing(8)
        self.contacts_save_btn = QPushButton(tr("contacts.save"))
        self.contacts_save_btn.clicked.connect(self._on_save_contact)
        self.contacts_remove_btn = QPushButton(tr("contacts.remove"))
        self.contacts_remove_btn.setObjectName("ghost")
        self.contacts_remove_btn.clicked.connect(self._on_remove_contact)
        contact_btn_row.addWidget(self.contacts_save_btn)
        contact_btn_row.addWidget(self.contacts_remove_btn)
        contact_btn_row.addStretch(1)
        lay.addLayout(contact_btn_row)
        self.contacts_list = QListWidget()
        self.contacts_list.setMaximumHeight(120)
        self.contacts_list.setMaximumWidth(360)
        lay.addWidget(self.contacts_list)

        self.sync_user_label = QLabel("")
        self.sync_user_label.hide()

        self._on_login_mode_changed()
        self._refresh_contacts_list()
        lay.addStretch(1)
        scroll.setWidget(w)
        outer_lay.addWidget(scroll, 1)
        return outer

    def _login_mode(self) -> str:
        if not hasattr(self, "sync_login_mode_combo"):
            return "password"
        mode = self.sync_login_mode_combo.currentData()
        return mode if mode else "password"

    def _login_mode_is_sms(self) -> bool:
        return self._login_mode() == "sms"

    def _login_mode_is_register(self) -> bool:
        return self._login_mode() == "register"

    def _on_login_mode_changed(self, _index: int = 0) -> None:
        if not hasattr(self, "sync_password_label"):
            return
        mode = self._login_mode()
        sms = mode == "sms"
        reg = mode == "register"
        self.sync_password_label.setVisible(not sms)
        self.sync_password_input.setVisible(not sms)
        self.sync_sms_code_label.setVisible(sms or reg)
        self.sync_sms_code_input.setVisible(sms or reg)
        self.sync_sms_send_btn.setVisible(sms or reg)
        if hasattr(self, "sync_register_hint"):
            self.sync_register_hint.setVisible(reg)
        if hasattr(self, "sync_login_btn"):
            self.sync_login_btn.setText(tr("sync.register") if reg else tr("sync.login"))

    def _on_sync_login(self) -> None:
        if not self.sync:
            return
        if hasattr(self, "sync_status_label"):
            self.sync_status_label.setText(tr("sync.status.logging_in"))
        self.sync_login_btn.setEnabled(False)
        if self._login_mode_is_register():
            self.sync.register(
                self.sync_phone_input.text(),
                self.sync_password_input.text(),
                self.sync_sms_code_input.text(),
            )
        elif self._login_mode_is_sms():
            self.sync.login_with_sms_code(
                self.sync_phone_input.text(),
                self.sync_sms_code_input.text(),
            )
        else:
            self.sync.login(self.sync_phone_input.text(), self.sync_password_input.text())

    def _on_send_sms(self) -> None:
        if not self.sync:
            return
        self.sync_sms_send_btn.setEnabled(False)
        if self._login_mode_is_register():
            self.sync.send_register_sms(self.sync_phone_input.text())
        else:
            self.sync.send_sms_code(self.sync_phone_input.text())

    def _on_sms_sent(self, ok: bool, message: str) -> None:
        if hasattr(self, "sync_sms_send_btn"):
            self.sync_sms_send_btn.setEnabled(True)
        if hasattr(self, "sync_status_label"):
            self.sync_status_label.setText(message)

    def _refresh_contacts_list(self) -> None:
        if not hasattr(self, "contacts_list") or not self.sync:
            return
        self.contacts_list.clear()
        rows = self.sync.contacts.list_contacts()
        if not rows:
            empty = QListWidgetItem(tr("contacts.empty"))
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.contacts_list.addItem(empty)
            return
        for phone, nickname in rows:
            item = QListWidgetItem(f"{nickname} · {phone}")
            item.setData(Qt.UserRole, phone)
            self.contacts_list.addItem(item)

    def _on_save_contact(self) -> None:
        if not self.sync:
            return
        try:
            self.sync.set_contact_nickname(
                self.contacts_phone_input.text(),
                self.contacts_nickname_input.text(),
            )
            self.contacts_phone_input.clear()
            self.contacts_nickname_input.clear()
            self._refresh_contacts_list()
            if hasattr(self, "sync_status_label"):
                self.sync_status_label.setText(tr("contacts.saved"))
        except SyncBackendError as exc:
            if hasattr(self, "sync_status_label"):
                self.sync_status_label.setText(self.sync.friendly_error(str(exc)))

    def _on_remove_contact(self) -> None:
        if not self.sync or not hasattr(self, "contacts_list"):
            return
        item = self.contacts_list.currentItem()
        if item is None:
            return
        phone = item.data(Qt.UserRole)
        if not phone:
            return
        self.sync.remove_contact(str(phone))
        self._refresh_contacts_list()
        if hasattr(self, "sync_status_label"):
            self.sync_status_label.setText(tr("contacts.removed"))

    def _set_env_save_button_style(self, *, locked: bool) -> None:
        if not hasattr(self, "sync_env_save_btn"):
            return
        self.sync_env_save_btn.setText(tr("sync.env.modify") if locked else tr("sync.env.save"))
        name = "ghost" if locked else ""
        if self.sync_env_save_btn.objectName() != name:
            self.sync_env_save_btn.setObjectName(name)
            self.sync_env_save_btn.style().unpolish(self.sync_env_save_btn)
            self.sync_env_save_btn.style().polish(self.sync_env_save_btn)
            self.sync_env_save_btn.update()

    def _update_env_save_ui(self) -> None:
        if not self.sync or not hasattr(self, "sync_env_save_btn"):
            return
        env_saved = self.sync.user_env_saved
        locked = env_saved and not self._env_editing
        self.sync_env_input.setEnabled(not locked)
        self.sync_env_save_btn.setEnabled(True)
        self._set_env_save_button_style(locked=locked)

    def _on_save_env(self) -> None:
        if not self.sync:
            return
        if self.sync.user_env_saved and not self._env_editing:
            self._env_editing = True
            self._update_env_save_ui()
            self.sync_env_input.setFocus()
            self.sync_env_input.selectAll()
            return
        self.sync_env_save_btn.setEnabled(False)
        self.sync.save_cloudbase_env_id(self.sync_env_input.text().strip())

    def _on_env_saved(self, ok: bool, message: str) -> None:
        if hasattr(self, "sync_status_label"):
            self.sync_status_label.setText(message)
        if ok:
            self._env_editing = False
        self._refresh_account_ui()
        if hasattr(self, "assign_inbox_scroll"):
            self.refresh_assignments()

    def _on_sync_logout(self) -> None:
        if not self.sync or not self.sync.is_logged_in:
            return
        answer = QMessageBox.question(
            self,
            tr("sync.logout.confirm.title"),
            tr("sync.logout.confirm.message"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if hasattr(self, "sync_logout_btn"):
            self.sync_logout_btn.setEnabled(False)
        if hasattr(self, "sync_status_label"):
            self.sync_status_label.setText(tr("sync.status.syncing"))
        self.sync.begin_logout(on_finished=self._after_sync_logout)

    def _after_sync_logout(self) -> None:
        self._refresh_account_ui()
        if hasattr(self, "sync_login_btn"):
            self.sync_login_btn.setEnabled(
                self.sync.user_env_saved if self.sync else False
            )
        if hasattr(self, "assign_inbox_scroll"):
            self.refresh_assignments()
        self._update_workbench_title()

    def _on_sync_now(self) -> None:
        if self.sync:
            self.sync.sync_now()

    def _on_sync_status(self, text: str) -> None:
        if hasattr(self, "sync_status_label"):
            self.sync_status_label.setText(text)
        self._update_todo_sync_status(text)

    def _on_login_finished(self, ok: bool, message: str) -> None:
        if hasattr(self, "sync_login_btn"):
            self.sync_login_btn.setEnabled(True)
        if hasattr(self, "sync_status_label"):
            self.sync_status_label.setText(message)
        if ok:
            self.sync_password_input.clear()
            if hasattr(self, "sync_sms_code_input"):
                self.sync_sms_code_input.clear()
            if hasattr(self, "sync_phone_input"):
                self.sync_phone_input.clear()
        elif hasattr(self, "sync_status_label"):
            QMessageBox.warning(self, tr("sync.login"), message)
        self._refresh_account_ui()
        if ok:
            self.flush_all_lists()

    def _set_login_form_visible(self, visible: bool) -> None:
        if hasattr(self, "sync_login_block"):
            self.sync_login_block.setVisible(visible)
        if hasattr(self, "sync_login_divider"):
            self.sync_login_divider.setVisible(visible)
        if visible:
            self._on_login_mode_changed()

    def _refresh_account_ui(self) -> None:
        if not self.sync:
            return
        logged_in = self.sync.is_logged_in
        phone = self.sync.phone or ""
        env_saved = self.sync.user_env_saved
        if hasattr(self, "sync_setup_hint"):
            self.sync_setup_hint.setVisible(not logged_in)
        if not self._env_editing and self.sync_env_input.text().strip() != self.sync.user_cloudbase_env_id:
            self.sync_env_input.setText(self.sync.user_cloudbase_env_id)
        self._update_env_save_ui()
        self._set_login_form_visible(not logged_in)
        if not logged_in:
            self.sync_phone_input.setEnabled(env_saved)
            self.sync_password_input.setEnabled(env_saved)
            self.sync_login_mode_combo.setEnabled(env_saved)
            self.sync_sms_code_input.setEnabled(env_saved)
            self.sync_sms_send_btn.setEnabled(env_saved)
            self.sync_login_btn.setEnabled(env_saved)
        self.sync_logout_btn.setVisible(logged_in)
        if hasattr(self, "sync_session_row"):
            self.sync_session_row.setVisible(logged_in)
        if hasattr(self, "sync_pause_chk"):
            self.sync_pause_chk.blockSignals(True)
            self.sync_pause_chk.setChecked(self.sync.sync_paused if logged_in else False)
            self.sync_pause_chk.setEnabled(logged_in)
            self.sync_pause_chk.blockSignals(False)
        self.sync_now_btn.setEnabled(
            logged_in and self.sync.backend_configured and not self.sync.sync_busy
        )
        status = self.sync.status_text() if self.sync else ""
        if self.sync and self.sync.is_logged_in and self.sync.env_mismatch:
            status = tr("sync.status.env_mismatch") + (
                f"\n{status}" if status else ""
            )
        if logged_in and phone:
            status = tr("sync.logged_in_as", phone=phone) + (f"\n{status}" if status else "")
        if hasattr(self, "sync_status_label"):
            self.sync_status_label.setText(status)
        if hasattr(self, "sync_user_label"):
            self.sync_user_label.setText("")
        self._update_workbench_title()

    def _on_size_slider(self, value: int) -> None:
        self.size_label.setText(f"{value} px")
        self.pet_size_changed.emit(value)

    def set_pet_size_display(self, size: int) -> None:
        """宠物窗口缩放时同步滑块，避免信号回路。"""
        if not hasattr(self, "size_slider"):
            return
        self.size_slider.blockSignals(True)
        self.size_slider.setValue(size)
        self.size_label.setText(f"{size} px")
        self.size_slider.blockSignals(False)

    def _apply_settings(self) -> None:
        self.config.update({
            "work_minutes": self.spin_work.value(),
            "rest_minutes": self.spin_rest.value(),
            "cycles": self.spin_cycles.value(),
            "rest_sound": self.chk_sound.isChecked(),
        })
        self.timer.configure(
            self.spin_work.value(), self.spin_rest.value(), self.spin_cycles.value()
        )
        self.settings_applied.emit()

    def _on_tick(self, remaining, state, cycle, total) -> None:
        self.countdown_label.setText(PomodoroTimer.format_time(remaining))

    def _on_language_changed(self, _index: int = 0) -> None:
        lang = self.lang_combo.currentData()
        if lang and lang != current():
            self.config.set("language", lang)
            set_language(lang)

    def retranslate_ui(self) -> None:
        self._update_workbench_title()
        self.tabs.setTabText(0, tr("tab.todo"))
        self.tabs.setTabText(1, tr("tab.notes"))
        self.tabs.setTabText(2, tr("tab.reminders"))
        self.tabs.setTabText(3, tr("tab.timer"))
        if self._account_tab_index >= 0:
            self.tabs.setTabText(self._account_tab_index, tr("tab.account"))

        self.todo_input.setPlaceholderText(tr("todo.placeholder"))
        self.todo_add_btn.setText(tr("todo.add"))
        self.todo_hint.setText(tr("todo.hint"))
        if hasattr(self, "todo_sync_retry_btn"):
            self.todo_sync_retry_btn.setText(tr("sync.retry"))
            if self.sync:
                self._update_todo_sync_status(self.sync.status_text())
        self.todo_subtabs.setTabText(0, tr("todo.subtab.active"))
        sub_idx = 1
        if hasattr(self, "assign_inbox_scroll"):
            self.todo_subtabs.setTabText(sub_idx, tr("todo.subtab.inbox"))
            sub_idx += 1
            self.todo_subtabs.setTabText(sub_idx, tr("todo.subtab.outbox"))
            sub_idx += 1
            self.assign_inbox_hint.setText(tr("assign.hint.inbox"))
            self.assign_outbox_hint.setText(tr("assign.hint.outbox"))
            self.assign_phone_input.setPlaceholderText(tr("assign.phone"))
            self.assign_title_input.setPlaceholderText(tr("assign.title"))
            if hasattr(self, "assign_description_input"):
                self.assign_description_input.setPlaceholderText(tr("assign.description.placeholder"))
            self.assign_dispatch_btn.setText(tr("assign.dispatch"))
            if hasattr(self, "assign_inbox_pending_label"):
                self.assign_inbox_pending_label.setText(tr("assign.section.inbox_pending"))
            if hasattr(self, "assign_inbox_accepted_label"):
                self.assign_inbox_accepted_label.setText(tr("assign.section.inbox_accepted"))
            if hasattr(self, "assign_inbox_rejected_label"):
                self.assign_inbox_rejected_label.setText(tr("assign.section.inbox_rejected"))
            if hasattr(self, "assign_inbox_cancelled_label"):
                self.assign_inbox_cancelled_label.setText(tr("assign.section.inbox_cancelled"))
            if hasattr(self, "assign_inbox_empty"):
                self.assign_inbox_empty.setText(tr("assign.empty.inbox"))
            if hasattr(self, "assign_outbox_pending_label"):
                self.assign_outbox_pending_label.setText(tr("assign.section.outbox_pending"))
            if hasattr(self, "assign_outbox_accepted_label"):
                self.assign_outbox_accepted_label.setText(tr("assign.section.outbox_accepted"))
            if hasattr(self, "assign_outbox_rejected_label"):
                self.assign_outbox_rejected_label.setText(tr("assign.section.outbox_rejected"))
            if hasattr(self, "assign_outbox_cancelled_label"):
                self.assign_outbox_cancelled_label.setText(tr("assign.section.outbox_cancelled"))
            if hasattr(self, "assign_outbox_empty"):
                self.assign_outbox_empty.setText(tr("assign.empty.outbox"))
            pri_idx = self.assign_priority_combo.currentIndex()
            self.assign_priority_combo.clear()
            self.assign_priority_combo.addItems(priority_labels())
            self.assign_priority_combo.setCurrentIndex(pri_idx)
        self.todo_subtabs.setTabText(sub_idx, tr("todo.subtab.archive"))
        self.todo_archive_hint.setText(tr("todo.archive.hint"))
        if hasattr(self, "todo_archive_clear_btn"):
            self.todo_archive_clear_btn.setText(tr("todo.archive.clear"))
        pri_idx = self.priority_combo.currentIndex()
        self.priority_combo.clear()
        self.priority_combo.addItems(priority_labels())
        self.priority_combo.setCurrentIndex(pri_idx)

        self.notes_hint.setText(tr("notes.hint"))
        self.note_input.setPlaceholderText(tr("notes.placeholder"))
        self.notes_add_btn.setText(tr("notes.add"))
        self.notes_save_btn.setText(tr("notes.save_all"))

        self.remind_hint.setText(tr("remind.hint"))
        self.remind_text.setPlaceholderText(tr("remind.placeholder"))
        self.remind_time_lbl.setText(tr("remind.time"))
        self.remind_repeat_lbl.setText(tr("remind.repeat"))
        repeat_idx = self.remind_repeat.currentIndex()
        self.remind_repeat.clear()
        self.remind_repeat.addItems(remind_repeat_options())
        self.remind_repeat.setCurrentIndex(repeat_idx)
        self.remind_add_btn.setText(tr("remind.add"))
        self.remind_list_hint.setText(tr("remind.list_hint"))
        self.remind_del_btn.setText(tr("remind.delete_sel"))

        self.timer_section.setText(tr("timer.settings"))
        self.lbl_work.setText(tr("timer.work_min"))
        self.lbl_rest.setText(tr("timer.rest_min"))
        self.lbl_cycles.setText(tr("timer.cycles"))
        self.chk_sound.setText(tr("timer.sound"))
        self.lang_section.setText(tr("settings.language"))
        self.lang_combo.blockSignals(True)
        self.lang_combo.setItemText(0, tr("lang.zh"))
        self.lang_combo.setItemText(1, tr("lang.en"))
        self.lang_combo.blockSignals(False)
        self.pet_section.setText(tr("timer.pet_size"))
        self.pet_hint.setText(tr("timer.pet_hint"))
        self.btn_start.setText(tr("timer.start"))
        self.btn_rest.setText(tr("timer.rest"))
        self.btn_stop.setText(tr("timer.stop"))

        if self.sync and self._account_tab_index >= 0:
            self.sync_title.setText(tr("sync.title"))
            self.sync_env_label.setText(tr("sync.env_id"))
            self.sync_env_input.setPlaceholderText(tr("sync.env.placeholder"))
            self._update_env_save_ui()
            self.sync_setup_hint.setText(tr("sync.setup_hint"))
            if hasattr(self, "sync_login_section"):
                self.sync_login_section.setText(tr("sync.section.login"))
            self.sync_login_mode_label.setText(tr("sync.login.mode"))
            mode_idx = self.sync_login_mode_combo.currentIndex()
            self.sync_login_mode_combo.blockSignals(True)
            self.sync_login_mode_combo.clear()
            self.sync_login_mode_combo.addItem(tr("sync.login.password"), "password")
            self.sync_login_mode_combo.addItem(tr("sync.login.sms"), "sms")
            self.sync_login_mode_combo.addItem(tr("sync.login.register"), "register")
            self.sync_login_mode_combo.setCurrentIndex(mode_idx)
            self.sync_login_mode_combo.blockSignals(False)
            if hasattr(self, "sync_register_hint"):
                self.sync_register_hint.setText(tr("sync.register.hint"))
            self.sync_phone_label.setText(tr("sync.phone"))
            self.sync_password_label.setText(tr("sync.password"))
            self.sync_sms_code_label.setText(tr("sync.sms.code"))
            self.sync_sms_send_btn.setText(tr("sync.sms.send"))
            self.sync_login_btn.setText(tr("sync.login"))
            self.sync_logout_btn.setText(tr("sync.logout"))
            self.sync_now_btn.setText(tr("sync.now"))
            if hasattr(self, "sync_pause_chk"):
                self.sync_pause_chk.setText(tr("sync.pause"))
            if hasattr(self, "contacts_title"):
                self.contacts_title.setText(tr("contacts.title"))
                self.contacts_hint.setText(tr("contacts.hint"))
                self.contacts_phone_label.setText(tr("contacts.phone"))
                self.contacts_nickname_label.setText(tr("contacts.nickname"))
                self.contacts_save_btn.setText(tr("contacts.save"))
                self.contacts_remove_btn.setText(tr("contacts.remove"))
                self._refresh_contacts_list()
        if hasattr(self, "assign_inbox_scroll"):
            self.refresh_assignments()
            self._refresh_account_ui()

        self.refresh_todo()
        self.refresh_notes()
        self.refresh_reminders()
        self._on_state(self.timer.state)

    def _on_state(self, state: PomodoroState) -> None:
        mapping = {
            PomodoroState.IDLE: (tr("timer.idle"), "#a89a82"),
            PomodoroState.WORKING: (
                tr("timer.working", cycle=self.timer.current_cycle, total=self.timer.total_cycles),
                "#c88a3a",
            ),
            PomodoroState.RESTING: (tr("timer.resting"), "#4fc06a"),
            PomodoroState.FINISHED: (tr("timer.finished"), "#dd9c46"),
        }
        text, color = mapping.get(state, ("", "#f3ebe0"))
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color:{color};")
        if state == PomodoroState.IDLE:
            self.countdown_label.setText("--:--")
