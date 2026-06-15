"""待办事项（To-Do List）数据管理。

提供增删改查与持久化，状态变化时通过 Qt 信号通知界面刷新。
支持三级优先级：高(2/红)、中(1/蓝)、低(0/绿)。
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, List

from PySide6.QtCore import QObject, Signal

from .config import TODO_PATH
from .i18n import tr
from .sync.ids import migrate_id, new_id

PRIORITY_LOW = 0
PRIORITY_MED = 1
PRIORITY_HIGH = 2


@dataclass
class Task:
    """单条待办任务。"""

    id: str
    text: str
    done: bool = False
    priority: int = PRIORITY_MED
    created: float = field(default_factory=time.time)
    completed_at: float | None = None
    updated_at: float = field(default_factory=time.time)
    deleted: bool = False


class TodoManager(QObject):
    """管理任务列表，自动保存到磁盘。"""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._tasks: List[Task] = []
        self._loading = False
        self.load()

    @property
    def tasks(self) -> List[Task]:
        return [t for t in self._tasks if not t.deleted]

    def pending(self) -> List[Task]:
        pending = [t for t in self.tasks if not t.done]
        pending.sort(key=lambda t: (-t.priority, t.created))
        return pending

    def completed(self) -> List[Task]:
        return [t for t in self.tasks if t.done]

    def completed_groups(self) -> list[tuple[str, list[Task]]]:
        """按完成日期（本地 YYYY-MM-DD）归档，日期从新到旧，同日内按完成时间倒序。"""
        buckets: dict[str, list[Task]] = {}
        for task in self.completed():
            ts = task.completed_at or task.updated_at or task.created
            day = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            buckets.setdefault(day, []).append(task)
        groups: list[tuple[str, list[Task]]] = []
        for day in sorted(buckets.keys(), reverse=True):
            tasks = sorted(buckets[day], key=lambda t: -(t.completed_at or t.updated_at or t.created))
            groups.append((day, tasks))
        return groups

    def find(self, task_id: str) -> Task | None:
        for t in self._tasks:
            if t.id == task_id and not t.deleted:
                return t
        return None

    def _touch(self, task: Task) -> None:
        task.updated_at = time.time()

    def add(self, text: str, priority: int = PRIORITY_MED) -> Task:
        text = text.strip()
        priority = max(PRIORITY_LOW, min(PRIORITY_HIGH, int(priority)))
        now = time.time()
        task = Task(id=new_id(), text=text, priority=priority, created=now, updated_at=now)
        self._tasks.append(task)
        self._after_change()
        return task

    def set_priority(self, task_id: str, priority: int) -> bool:
        task = self.find(task_id)
        if task is None:
            return False
        task.priority = max(PRIORITY_LOW, min(PRIORITY_HIGH, int(priority)))
        self._touch(task)
        self._after_change()
        return True

    def toggle(self, task_id: str) -> None:
        task = self.find(task_id)
        if task is None:
            return
        task.done = not task.done
        task.completed_at = time.time() if task.done else None
        self._touch(task)
        self._after_change()

    def set_done(self, task_id: str, done: bool = True) -> bool:
        task = self.find(task_id)
        if task is None:
            return False
        task.done = done
        task.completed_at = time.time() if done else None
        self._touch(task)
        self._after_change()
        return True

    def remove(self, task_id: str) -> bool:
        task = self.find(task_id)
        if task is None:
            return False
        task.deleted = True
        self._touch(task)
        self._after_change()
        return True

    def clear_completed(self) -> int:
        removed = 0
        now = time.time()
        for task in self._tasks:
            if task.done and not task.deleted:
                task.deleted = True
                task.updated_at = now
                removed += 1
        if removed:
            self._after_change()
        return removed

    def clear_all(self) -> None:
        now = time.time()
        changed = False
        for task in self._tasks:
            if not task.deleted:
                task.deleted = True
                task.updated_at = now
                changed = True
        if changed:
            self._after_change()

    def complete_by_text(self, keyword: str) -> Task | None:
        keyword = keyword.strip().lower()
        for t in self.tasks:
            if not t.done and keyword and keyword in t.text.lower():
                self.set_done(t.id, True)
                return t
        return None

    def export_sync_records(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for task in self._tasks:
            payload = asdict(task)
            rows.append(
                {
                    "record_id": task.id,
                    "collection": "todo",
                    "payload": payload,
                    "updated_at": task.updated_at,
                    "deleted": task.deleted,
                }
            )
        return rows

    def import_sync_records(self, rows: list[dict[str, Any]]) -> None:
        by_id: dict[str, Task] = {}
        for row in rows:
            payload = row.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            task_id = migrate_id(payload.get("id", row.get("record_id")), namespace="todo")
            payload["id"] = task_id
            payload.setdefault("priority", PRIORITY_MED)
            payload.setdefault("updated_at", float(row.get("updated_at", time.time())))
            payload["deleted"] = bool(row.get("deleted", payload.get("deleted", False)))
            try:
                by_id[task_id] = Task(**{k: v for k, v in payload.items() if k in Task.__dataclass_fields__})
            except TypeError:
                continue
        self._loading = True
        try:
            self._tasks = list(by_id.values())
            self.save()
            self.changed.emit()
        finally:
            self._loading = False

    def _after_change(self) -> None:
        if self._loading:
            return
        self.save()
        self.changed.emit()

    def save(self) -> None:
        try:
            payload = {"tasks": [asdict(t) for t in self._tasks]}
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

    def _normalize_task(self, raw: dict[str, Any]) -> Task | None:
        task_id = migrate_id(raw.get("id"), namespace="todo")
        raw = dict(raw)
        raw["id"] = task_id
        if "priority" not in raw:
            raw["priority"] = PRIORITY_MED
        raw.setdefault("updated_at", raw.get("created", time.time()))
        raw.setdefault("deleted", False)
        try:
            return Task(**{k: v for k, v in raw.items() if k in Task.__dataclass_fields__})
        except TypeError:
            return None

    def load(self) -> None:
        if not TODO_PATH.exists():
            self._seed_samples()
            return
        try:
            with open(TODO_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._tasks = []
            for raw in data.get("tasks", []):
                task = self._normalize_task(raw)
                if task:
                    self._tasks.append(task)
            if not self._tasks and "next_id" in data:
                self._seed_samples()
        except (json.JSONDecodeError, OSError, TypeError):
            self._tasks = []
