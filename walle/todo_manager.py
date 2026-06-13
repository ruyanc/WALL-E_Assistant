"""待办事项（To-Do List）数据管理。

提供增删改查与持久化，状态变化时通过 Qt 信号通知界面刷新。
支持三级优先级：高(2/红)、中(1/蓝)、低(0/绿)。
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import List

from PySide6.QtCore import QObject, Signal

from .config import TODO_PATH
from .i18n import tr

PRIORITY_LOW = 0
PRIORITY_MED = 1
PRIORITY_HIGH = 2


@dataclass
class Task:
    """单条待办任务。"""

    id: int
    text: str
    done: bool = False
    priority: int = PRIORITY_MED
    created: float = field(default_factory=time.time)
    completed_at: float | None = None


class TodoManager(QObject):
    """管理任务列表，自动保存到磁盘。"""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._tasks: List[Task] = []
        self._next_id = 1
        self.load()

    @property
    def tasks(self) -> List[Task]:
        return list(self._tasks)

    def pending(self) -> List[Task]:
        pending = [t for t in self._tasks if not t.done]
        pending.sort(key=lambda t: (-t.priority, t.created))
        return pending

    def completed(self) -> List[Task]:
        return [t for t in self._tasks if t.done]

    def find(self, task_id: int) -> Task | None:
        for t in self._tasks:
            if t.id == task_id:
                return t
        return None

    def add(self, text: str, priority: int = PRIORITY_MED) -> Task:
        text = text.strip()
        priority = max(PRIORITY_LOW, min(PRIORITY_HIGH, int(priority)))
        task = Task(id=self._next_id, text=text, priority=priority)
        self._next_id += 1
        self._tasks.append(task)
        self._after_change()
        return task

    def set_priority(self, task_id: int, priority: int) -> bool:
        task = self.find(task_id)
        if task is None:
            return False
        task.priority = max(PRIORITY_LOW, min(PRIORITY_HIGH, int(priority)))
        self._after_change()
        return True

    def toggle(self, task_id: int) -> None:
        task = self.find(task_id)
        if task is None:
            return
        task.done = not task.done
        task.completed_at = time.time() if task.done else None
        self._after_change()

    def set_done(self, task_id: int, done: bool = True) -> bool:
        task = self.find(task_id)
        if task is None:
            return False
        task.done = done
        task.completed_at = time.time() if done else None
        self._after_change()
        return True

    def remove(self, task_id: int) -> bool:
        before = len(self._tasks)
        self._tasks = [t for t in self._tasks if t.id != task_id]
        if len(self._tasks) != before:
            self._after_change()
            return True
        return False

    def clear_completed(self) -> int:
        before = len(self._tasks)
        self._tasks = [t for t in self._tasks if not t.done]
        removed = before - len(self._tasks)
        if removed:
            self._after_change()
        return removed

    def clear_all(self) -> None:
        self._tasks.clear()
        self._after_change()

    def complete_by_text(self, keyword: str) -> Task | None:
        keyword = keyword.strip().lower()
        for t in self._tasks:
            if not t.done and keyword and keyword in t.text.lower():
                self.set_done(t.id, True)
                return t
        return None

    def _after_change(self) -> None:
        self.save()
        self.changed.emit()

    def save(self) -> None:
        try:
            payload = {
                "next_id": self._next_id,
                "tasks": [asdict(t) for t in self._tasks],
            }
            with open(TODO_PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _seed_samples(self) -> None:
        for text_key, priority in (
            ("seed.todo.meeting", PRIORITY_HIGH),
            ("seed.todo.report", PRIORITY_MED),
            ("seed.todo.package", PRIORITY_LOW),
        ):
            self.add(tr(text_key), priority=priority)

    def load(self) -> None:
        if not TODO_PATH.exists():
            self._seed_samples()
            return
        try:
            with open(TODO_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._next_id = data.get("next_id", 1)
            self._tasks = []
            for raw in data.get("tasks", []):
                if "priority" not in raw:
                    raw["priority"] = PRIORITY_MED
                self._tasks.append(Task(**raw))
        except (json.JSONDecodeError, OSError, TypeError):
            self._tasks = []
            self._next_id = 1
