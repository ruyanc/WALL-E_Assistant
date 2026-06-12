"""控制面板窗口：聊天、待办列表、番茄钟设置三合一。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .chatbot import ChatBot
from .config import Config
from .pomodoro import PomodoroState, PomodoroTimer
from .todo_manager import TodoManager

STYLE = """
QWidget { background:#2b2622; color:#f1e9dc; font-size:13px; }
QTabWidget::pane { border:1px solid #4a4138; border-radius:6px; }
QTabBar::tab { background:#3a332c; padding:8px 16px; border-top-left-radius:6px;
               border-top-right-radius:6px; margin-right:2px; color:#d8cbb6; }
QTabBar::tab:selected { background:#c88a3a; color:#2b2622; font-weight:bold; }
QLineEdit, QSpinBox { background:#1f1b18; border:1px solid #4a4138; border-radius:6px;
                       padding:6px; color:#f1e9dc; }
QPushButton { background:#c88a3a; color:#2b2622; border:none; border-radius:6px;
              padding:7px 14px; font-weight:bold; }
QPushButton:hover { background:#dd9c46; }
QPushButton#ghost { background:#3a332c; color:#e7dcc8; }
QPushButton#ghost:hover { background:#4a4138; }
QListWidget { background:#1f1b18; border:1px solid #4a4138; border-radius:6px; padding:4px; }
QListWidget::item { padding:6px; border-radius:4px; }
QListWidget::item:hover { background:#3a332c; }
QTextBrowser { background:#1f1b18; border:1px solid #4a4138; border-radius:6px; padding:8px; }
QLabel#hint { color:#a89a82; font-size:12px; }
"""


class ControlPanel(QWidget):
    """主控制面板。"""

    start_timer_requested = Signal()
    start_rest_requested = Signal()
    end_rest_requested = Signal()
    settings_applied = Signal()
    emote_requested = Signal(str)   # 聊天时驱动宠物做表情

    def __init__(self, config: Config, todo: TodoManager, timer: PomodoroTimer) -> None:
        super().__init__()
        self.config = config
        self.todo = todo
        self.timer = timer
        self.bot = ChatBot(todo)

        self.setWindowTitle("WALL-E 桌面宠物 · 控制台")
        self.resize(420, 560)
        self.setStyleSheet(STYLE)

        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        self.tabs.addTab(self._build_chat_tab(), "💬 对话")
        self.tabs.addTab(self._build_todo_tab(), "📋 待办")
        self.tabs.addTab(self._build_timer_tab(), "⏱️ 番茄钟")

        self.todo.changed.connect(self.refresh_todo)
        self.timer.tick.connect(self._on_tick)
        self.timer.state_changed.connect(self._on_state)
        self.refresh_todo()
        self._append_bot("哇—力！我是你的桌面伙伴 WALL-E。平时可以随便和我聊聊、放松心情～需要做事时对我说「记一下 …」就行；输入「帮助」查看全部功能。")

    # =============================================================== 对话页
    def _build_chat_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.chat_view = QTextBrowser()
        self.chat_view.setOpenExternalLinks(False)
        lay.addWidget(self.chat_view, 1)

        row = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("和瓦力聊聊天…累了、烦了都可以告诉我")
        self.chat_input.returnPressed.connect(self._send_chat)
        send = QPushButton("发送")
        send.clicked.connect(self._send_chat)
        row.addWidget(self.chat_input, 1)
        row.addWidget(send)
        lay.addLayout(row)
        return w

    def _send_chat(self) -> None:
        text = self.chat_input.text().strip()
        if not text:
            return
        self._append_user(text)
        self.chat_input.clear()
        reply, action = self.bot.respond(text)
        self._append_bot(reply)
        self._dispatch(action)

    def _dispatch(self, action: dict) -> None:
        emote = action.get("emote")
        if emote:
            self.emote_requested.emit(emote)
        act = action.get("action")
        if act == "start_timer":
            self.start_timer_requested.emit()
        elif act == "start_rest":
            self.start_rest_requested.emit()
        elif act == "end_rest":
            self.end_rest_requested.emit()
        elif act == "refresh":
            self.refresh_todo()

    def _append_user(self, text: str) -> None:
        self.chat_view.append(
            f'<div style="margin:6px 0;text-align:right;">'
            f'<span style="background:#c88a3a;color:#2b2622;padding:6px 10px;'
            f'border-radius:10px;display:inline-block;">{self._esc(text)}</span></div>'
        )

    def _append_bot(self, text: str) -> None:
        html = self._esc(text).replace("\n", "<br>")
        self.chat_view.append(
            f'<div style="margin:6px 0;text-align:left;">'
            f'<span style="background:#3a332c;color:#f1e9dc;padding:6px 10px;'
            f'border-radius:10px;display:inline-block;">🤖 {html}</span></div>'
        )

    @staticmethod
    def _esc(text: str) -> str:
        return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    # =============================================================== 待办页
    def _build_todo_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        row = QHBoxLayout()
        self.todo_input = QLineEdit()
        self.todo_input.setPlaceholderText("输入新任务，回车添加")
        self.todo_input.returnPressed.connect(self._add_todo)
        add = QPushButton("添加")
        add.clicked.connect(self._add_todo)
        row.addWidget(self.todo_input, 1)
        row.addWidget(add)
        lay.addLayout(row)

        hint = QLabel("☑ 勾选即可划掉任务，双击可删除")
        hint.setObjectName("hint")
        lay.addWidget(hint)

        self.todo_list = QListWidget()
        self.todo_list.itemChanged.connect(self._on_item_changed)
        self.todo_list.itemDoubleClicked.connect(self._on_item_double)
        lay.addWidget(self.todo_list, 1)

        btn_row = QHBoxLayout()
        clear_done = QPushButton("清除已完成")
        clear_done.setObjectName("ghost")
        clear_done.clicked.connect(self._clear_done)
        clear_all = QPushButton("清空全部")
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
            self.todo.add(text)
            self.todo_input.clear()

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        task_id = item.data(Qt.UserRole)
        if task_id is None:
            return
        done = item.checkState() == Qt.Checked
        task = self.todo.find(task_id)
        if task and task.done != done:
            self.todo.set_done(task_id, done)

    def _on_item_double(self, item: QListWidgetItem) -> None:
        task_id = item.data(Qt.UserRole)
        if task_id is not None:
            self.todo.remove(task_id)

    def _clear_done(self) -> None:
        self.todo.clear_completed()

    def refresh_todo(self) -> None:
        if not hasattr(self, "todo_list"):
            return
        self.todo_list.blockSignals(True)
        self.todo_list.clear()
        for t in self.todo.tasks:
            item = QListWidgetItem(t.text)
            item.setData(Qt.UserRole, t.id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if t.done else Qt.Unchecked)
            if t.done:
                f = item.font()
                f.setStrikeOut(True)
                item.setFont(f)
                item.setForeground(Qt.gray)
            self.todo_list.addItem(item)
        self.todo_list.blockSignals(False)

    # =============================================================== 番茄钟页
    def _build_timer_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        self.status_label = QLabel("空闲中")
        f = QFont()
        f.setPointSize(15)
        f.setBold(True)
        self.status_label.setFont(f)
        self.status_label.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.status_label)

        self.countdown_label = QLabel("--:--")
        cf = QFont("Consolas")
        cf.setPointSize(40)
        cf.setBold(True)
        self.countdown_label.setFont(cf)
        self.countdown_label.setAlignment(Qt.AlignCenter)
        self.countdown_label.setStyleSheet("color:#c88a3a;")
        lay.addWidget(self.countdown_label)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#4a4138;")
        lay.addWidget(line)

        def add_spin(label_text, key, lo, hi):
            r = QHBoxLayout()
            lbl = QLabel(label_text)
            sp = QSpinBox()
            sp.setRange(lo, hi)
            sp.setValue(int(self.config.get(key)))
            r.addWidget(lbl, 1)
            r.addWidget(sp)
            lay.addLayout(r)
            return sp

        self.spin_work = add_spin("工作时长（分钟）", "work_minutes", 1, 180)
        self.spin_rest = add_spin("休息时长（分钟）", "rest_minutes", 1, 120)
        self.spin_cycles = add_spin("循环次数", "cycles", 1, 12)

        self.chk_sound = QCheckBox("休息提醒播放提示音")
        self.chk_sound.setChecked(bool(self.config.get("rest_sound")))
        self.chk_sound.stateChanged.connect(self._apply_settings)
        lay.addWidget(self.chk_sound)

        for sp in (self.spin_work, self.spin_rest, self.spin_cycles):
            sp.valueChanged.connect(self._apply_settings)

        lay.addStretch(1)

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("▶ 开始")
        self.btn_start.clicked.connect(self.start_timer_requested.emit)
        self.btn_rest = QPushButton("☕ 立即休息")
        self.btn_rest.setObjectName("ghost")
        self.btn_rest.clicked.connect(self.start_rest_requested.emit)
        self.btn_stop = QPushButton("■ 停止")
        self.btn_stop.setObjectName("ghost")
        self.btn_stop.clicked.connect(self.timer.stop)
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_rest)
        btn_row.addWidget(self.btn_stop)
        lay.addLayout(btn_row)
        return w

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

    def _on_state(self, state: PomodoroState) -> None:
        mapping = {
            PomodoroState.IDLE: ("空闲中", "#a89a82"),
            PomodoroState.WORKING: (f"专注工作 · 第 {self.timer.current_cycle}/{self.timer.total_cycles} 轮", "#c88a3a"),
            PomodoroState.RESTING: ("休息中 ☕", "#4fc06a"),
            PomodoroState.FINISHED: ("全部完成 🎉", "#dd9c46"),
        }
        text, color = mapping.get(state, ("", "#f1e9dc"))
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color:{color};")
        if state == PomodoroState.IDLE:
            self.countdown_label.setText("--:--")
