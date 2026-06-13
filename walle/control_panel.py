"""控制面板窗口：待办、记事本、提醒、番茄钟。"""

from __future__ import annotations

from PySide6.QtCore import QDate, QSize, Qt, QTime, Signal
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
from .i18n import current, priority_labels, remind_repeat_options, set_language, tr
from .notes_manager import NoteEntry, NotesManager
from .pet_window import MAX_PET_SIZE, MIN_PET_SIZE
from .pomodoro import PomodoroState, PomodoroTimer
from .reminder_manager import (
    REPEAT_DAILY,
    REPEAT_ONCE,
    REPEAT_WEEKDAYS,
    REPEAT_WEEKLY,
    ReminderManager,
)
from .todo_bulbs import PRIORITY_COLORS
from .todo_manager import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_MED, TodoManager

FONT_FAMILY = '"Microsoft YaHei UI", "PingFang SC", "Segoe UI", sans-serif'

PRIORITY_VALUES = (PRIORITY_HIGH, PRIORITY_MED, PRIORITY_LOW)
PRIORITY_INDEX = {PRIORITY_HIGH: 0, PRIORITY_MED: 1, PRIORITY_LOW: 2}


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
    """单条记事：小文本框 + 删除。"""

    text_changed = Signal(int, str)
    delete_requested = Signal(int)

    def __init__(self, entry: NoteEntry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._note_id = entry.id
        self._loading = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.edit = QPlainTextEdit(entry.text)
        self.edit.setPlaceholderText(tr("notes.entry_placeholder"))
        self.edit.setMaximumHeight(80)
        self.edit.setMinimumHeight(52)
        nf = QFont("Microsoft YaHei UI", 13)
        self.edit.setFont(nf)
        self.edit.textChanged.connect(self._on_text)

        del_btn = QPushButton("×")
        del_btn.setObjectName("ghost")
        del_btn.setFixedSize(32, 32)
        del_btn.setToolTip(tr("notes.delete_tip"))
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self._note_id))

        lay.addWidget(self.edit, 1)
        lay.addWidget(del_btn, 0, Qt.AlignTop)

    def _on_text(self) -> None:
        if self._loading:
            return
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

    done_changed = Signal(int, bool)
    priority_changed = Signal(int, int)

    _SIDE = 22 + 4 + 10 + 84 + 28  # 勾选、色条、间距、下拉、边距

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

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addStretch(1)
        self.prio_combo = _make_priority_combo(task.priority, compact=True)
        self.prio_combo.currentIndexChanged.connect(self._on_priority_index)
        footer.addWidget(self.prio_combo, 0, Qt.AlignRight)

        body.addWidget(self.label)
        body.addLayout(footer)

        outer.addWidget(self.check, 0, Qt.AlignTop | Qt.AlignHCenter)
        outer.addWidget(self.stripe, 0, Qt.AlignTop)
        outer.addLayout(body, 1)

        self._loading = False
        self._sync_label_width()

    def _apply_card_style(self, done: bool) -> None:
        self.setObjectName("todoCardDone" if done else "todoCard")

    def _text_width(self) -> int:
        return max(120, self._list_width - self._SIDE)

    def _sync_label_width(self) -> None:
        self.label.setFixedWidth(self._text_width())

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
        self.adjustSize()
        return max(56, self.sizeHint().height())


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
    ) -> None:
        super().__init__()
        self.config = config
        self.todo = todo
        self.notes = notes
        self.reminders = reminders
        self.timer = timer

        self.setWindowTitle(tr("panel.title"))
        self.resize(560, 660)
        self.setMinimumSize(540, 520)
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

        self.todo.changed.connect(self.refresh_todo)
        self.notes.changed.connect(self.refresh_notes)
        self.reminders.changed.connect(self.refresh_reminders)
        self.timer.tick.connect(self._on_tick)
        self.timer.state_changed.connect(self._on_state)
        self.refresh_todo()
        self.refresh_notes()
        self.refresh_reminders()

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

        self.todo_hint = QLabel(tr("todo.hint"))
        self.todo_hint.setObjectName("hint")
        lay.addWidget(self.todo_hint)

        self.todo_list = QListWidget()
        self.todo_list.setUniformItemSizes(False)
        self.todo_list.setSpacing(6)
        self.todo_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.todo_list.itemDoubleClicked.connect(self._on_item_double)
        lay.addWidget(self.todo_list, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        clear_done = QPushButton(tr("todo.clear_done"))
        self.todo_clear_done_btn = clear_done
        clear_done.setObjectName("ghost")
        clear_done.clicked.connect(self._clear_done)
        clear_all = QPushButton(tr("todo.clear_all"))
        self.todo_clear_all_btn = clear_all
        clear_all.setObjectName("ghost")
        clear_all.clicked.connect(self.todo.clear_all)
        btn_row.addWidget(clear_done)
        btn_row.addWidget(clear_all)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)
        return w

    def _add_todo(self) -> None:
        text = self.todo_input.text().strip()
        if text:
            idx = self.priority_combo.currentIndex()
            pri = PRIORITY_VALUES[idx] if 0 <= idx < len(PRIORITY_VALUES) else PRIORITY_MED
            self.todo.add(text, priority=pri)
            self.todo_input.clear()

    def _on_todo_done(self, task_id: int, done: bool) -> None:
        task = self.todo.find(task_id)
        if task and task.done != done:
            self.todo.set_done(task_id, done)

    def _on_todo_priority(self, task_id: int, priority: int) -> None:
        self.todo.set_priority(task_id, priority)

    def _on_item_double(self, item: QListWidgetItem) -> None:
        task_id = item.data(Qt.UserRole)
        if task_id is not None:
            self.todo.remove(task_id)

    def _clear_done(self) -> None:
        self.todo.clear_completed()

    def refresh_todo(self) -> None:
        if not hasattr(self, "todo_list"):
            return
        self.todo_list.clear()
        list_w = max(300, self.todo_list.viewport().width())
        display_tasks = self.todo.pending() + self.todo.completed()
        for t in display_tasks:
            row = TodoItemWidget(t, list_width=list_w)
            row.done_changed.connect(self._on_todo_done)
            row.priority_changed.connect(self._on_todo_priority)

            item = QListWidgetItem()
            item.setData(Qt.UserRole, t.id)
            item.setSizeHint(QSize(list_w, row.height_hint()))
            self.todo_list.addItem(item)
            self.todo_list.setItemWidget(item, row)

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

    def _on_note_text(self, note_id: int, text: str) -> None:
        self.notes.update_text(note_id, text)
        self.notes_status.setText(tr("notes.auto_saved"))

    def _on_note_delete(self, note_id: int) -> None:
        self.notes.remove(note_id)

    def refresh_notes(self, focus_id: int | None = None) -> None:
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
        self.setWindowTitle(tr("panel.title"))
        self.header.setText(tr("panel.header"))
        self.tabs.setTabText(0, tr("tab.todo"))
        self.tabs.setTabText(1, tr("tab.notes"))
        self.tabs.setTabText(2, tr("tab.reminders"))
        self.tabs.setTabText(3, tr("tab.timer"))

        self.todo_input.setPlaceholderText(tr("todo.placeholder"))
        self.todo_add_btn.setText(tr("todo.add"))
        self.todo_hint.setText(tr("todo.hint"))
        self.todo_clear_done_btn.setText(tr("todo.clear_done"))
        self.todo_clear_all_btn.setText(tr("todo.clear_all"))
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
