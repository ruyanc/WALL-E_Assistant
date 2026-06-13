"""待办存储（无 Qt 依赖，与桌面版 JSON 结构兼容）。"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, List

from storage import todos_path

PRIORITY_LOW = 0
PRIORITY_MED = 1
PRIORITY_HIGH = 2
PRIORITY_LABELS = {PRIORITY_HIGH: "高级", PRIORITY_MED: "中级", PRIORITY_LOW: "低级"}


@dataclass
class Task:
    id: int
    text: str
    done: bool = False
    priority: int = PRIORITY_MED
    created: float = field(default_factory=time.time)
    completed_at: float | None = None


class TodoStore:
    def __init__(self, on_change: Callable[[], None] | None = None) -> None:
        self._tasks: List[Task] = []
        self._next_id = 1
        self._on_change = on_change
        self.load()

    @property
    def tasks(self) -> List[Task]:
        return list(self._tasks)

    def pending(self) -> List[Task]:
        items = [t for t in self._tasks if not t.done]
        items.sort(key=lambda t: (-t.priority, t.created))
        return items

    def add(self, text: str, priority: int = PRIORITY_MED) -> None:
        text = text.strip()
        if not text:
            return
        priority = max(PRIORITY_LOW, min(PRIORITY_HIGH, int(priority)))
        self._tasks.append(Task(id=self._next_id, text=text, priority=priority))
        self._next_id += 1
        self._changed()

    def toggle(self, task_id: int) -> None:
        for t in self._tasks:
            if t.id == task_id:
                t.done = not t.done
                t.completed_at = time.time() if t.done else None
                self._changed()
                return

    def remove(self, task_id: int) -> None:
        before = len(self._tasks)
        self._tasks = [t for t in self._tasks if t.id != task_id]
        if len(self._tasks) != before:
            self._changed()

    def _changed(self) -> None:
        self.save()
        if self._on_change:
            self._on_change()

    def save(self) -> None:
        path = todos_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {"next_id": self._next_id, "tasks": [asdict(t) for t in self._tasks]},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except OSError:
            pass

    def load(self) -> None:
        path = todos_path()
        if not path.exists():
            self._seed()
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._next_id = int(data.get("next_id", 1))
            self._tasks = []
            for raw in data.get("tasks", []):
                if "priority" not in raw:
                    raw["priority"] = PRIORITY_MED
                self._tasks.append(Task(**raw))
        except (json.JSONDecodeError, OSError, TypeError):
            self._tasks = []
            self._next_id = 1

    def _seed(self) -> None:
        for text, pri in (("开会", PRIORITY_HIGH), ("交周报", PRIORITY_MED), ("取快递", PRIORITY_LOW)):
            self.add(text, pri)
