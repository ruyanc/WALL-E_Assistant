"""待办事项（To-Do List）数据管理。

提供增删改查与持久化，状态变化时通过 Qt 信号通知界面刷新。
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import List

from PySide6.QtCore import QObject, Signal

from .config import TODO_PATH


@dataclass
class Task:
    """单条待办任务。"""

    id: int
    text: str
    done: bool = False
    created: float = field(default_factory=time.time)
    completed_at: float | None = None


class TodoManager(QObject):
    """管理任务列表，自动保存到磁盘。"""

    changed = Signal()  # 任何任务变化都会发出，供界面刷新

    def __init__(self) -> None:
        super().__init__()
        self._tasks: List[Task] = []
        self._next_id = 1
        self.load()

    # ------------------------------------------------------------------ 读取
    @property
    def tasks(self) -> List[Task]:
        return list(self._tasks)

    def pending(self) -> List[Task]:
        return [t for t in self._tasks if not t.done]

    def completed(self) -> List[Task]:
        return [t for t in self._tasks if t.done]

    def find(self, task_id: int) -> Task | None:
        for t in self._tasks:
            if t.id == task_id:
                return t
        return None

    # ------------------------------------------------------------------ 修改
    def add(self, text: str) -> Task:
        text = text.strip()
        task = Task(id=self._next_id, text=text)
        self._next_id += 1
        self._tasks.append(task)
        self._after_change()
        return task

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
        """根据关键字模糊匹配并标记完成（取第一个未完成的匹配项）。"""
        keyword = keyword.strip().lower()
        for t in self._tasks:
            if not t.done and keyword and keyword in t.text.lower():
                self.set_done(t.id, True)
                return t
        return None

    # ------------------------------------------------------------------ 持久化
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

    def load(self) -> None:
        if not TODO_PATH.exists():
            return
        try:
            with open(TODO_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._next_id = data.get("next_id", 1)
            self._tasks = [Task(**t) for t in data.get("tasks", [])]
        except (json.JSONDecodeError, OSError, TypeError):
            self._tasks = []
            self._next_id = 1
