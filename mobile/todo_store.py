"""待办存储（无 Qt 依赖，支持 CloudBase 同步）。"""



from __future__ import annotations



import json

import sys

import time

import uuid

from dataclasses import asdict, dataclass, field

from datetime import datetime

from pathlib import Path

from typing import Any, Callable, List



from storage import todos_path



PRIORITY_LOW = 0

PRIORITY_MED = 1

PRIORITY_HIGH = 2

PRIORITY_LABELS = {PRIORITY_HIGH: "高级", PRIORITY_MED: "中级", PRIORITY_LOW: "低级"}





def _migrate_id(raw_id: object) -> str:

    root = Path(__file__).resolve().parents[1]

    if str(root) not in sys.path:

        sys.path.insert(0, str(root))

    from walle.sync.ids import migrate_id



    return migrate_id(raw_id, namespace="todo")





@dataclass

class Task:

    id: str

    text: str

    done: bool = False

    priority: int = PRIORITY_MED

    created: float = field(default_factory=time.time)

    completed_at: float | None = None

    updated_at: float = field(default_factory=time.time)

    deleted: bool = False





class TodoStore:

    def __init__(self, on_change: Callable[[], None] | None = None) -> None:

        self._tasks: List[Task] = []

        self._on_change = on_change

        self._loading = False

        self.load()



    @property

    def tasks(self) -> List[Task]:

        return [t for t in self._tasks if not t.deleted]



    def pending(self) -> List[Task]:

        items = [t for t in self._tasks if not t.done and not t.deleted]

        items.sort(key=lambda t: (-t.priority, t.created))

        return items



    def completed(self) -> List[Task]:

        return [t for t in self._tasks if t.done and not t.deleted]



    def completed_groups(self) -> list[tuple[str, list[Task]]]:

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



    def add(self, text: str, priority: int = PRIORITY_MED) -> None:

        text = text.strip()

        if not text:

            return

        priority = max(PRIORITY_LOW, min(PRIORITY_HIGH, int(priority)))

        now = time.time()

        self._tasks.append(

            Task(id=str(uuid.uuid4()), text=text, priority=priority, created=now, updated_at=now)

        )

        self._changed()



    def toggle(self, task_id: str) -> None:

        for t in self._tasks:

            if t.id == task_id and not t.deleted:

                t.done = not t.done

                t.completed_at = time.time() if t.done else None

                t.updated_at = time.time()

                self._changed()

                return



    def set_priority(self, task_id: str, priority: int) -> None:

        priority = max(PRIORITY_LOW, min(PRIORITY_HIGH, int(priority)))

        for t in self._tasks:

            if t.id == task_id and not t.deleted:

                t.priority = priority

                t.updated_at = time.time()

                self._changed()

                return



    def remove(self, task_id: str) -> None:

        for t in self._tasks:

            if t.id == task_id and not t.deleted:

                t.deleted = True

                t.updated_at = time.time()

                self._changed()

                return



    def clear_completed(self) -> int:

        now = time.time()

        changed = 0

        for task in self._tasks:

            if task.done and not task.deleted:

                task.deleted = True

                task.updated_at = now

                changed += 1

        if changed:

            self._changed()

        return changed



    def export_sync_records(self) -> list[dict[str, Any]]:

        rows: list[dict[str, Any]] = []

        for task in self._tasks:

            rows.append(

                {

                    "record_id": task.id,

                    "collection": "todo",

                    "payload": asdict(task),

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

            task_id = _migrate_id(payload.get("id", row.get("record_id")))

            payload = dict(payload)

            payload["id"] = task_id

            payload.setdefault("priority", PRIORITY_MED)

            payload.setdefault("updated_at", float(row.get("updated_at", time.time())))

            payload["deleted"] = bool(row.get("deleted", payload.get("deleted", False)))

            try:

                by_id[task_id] = Task(**{k: v for k, v in payload.items() if k in Task.__dataclass_fields__})

            except TypeError:

                continue

        if not by_id:

            return

        self._loading = True

        try:

            self._tasks = list(by_id.values())

            self.save()

            if self._on_change:

                self._on_change()

        finally:

            self._loading = False



    def _changed(self) -> None:

        if self._loading:

            return

        self.save()

        if self._on_change:

            self._on_change()



    def save(self) -> None:

        path = todos_path()

        try:

            with open(path, "w", encoding="utf-8") as f:

                json.dump({"tasks": [asdict(t) for t in self._tasks]}, f, ensure_ascii=False, indent=2)

        except OSError:

            pass



    def load(self) -> None:

        path = todos_path()

        if not path.exists():

            self._seed()

            return

        try:

            with open(path, "r", encoding="utf-8-sig") as f:

                data = json.load(f)

            self._tasks = []

            for raw in data.get("tasks", []):

                raw = dict(raw)

                raw["id"] = str(raw.get("id", uuid.uuid4()))

                if "priority" not in raw:

                    raw["priority"] = PRIORITY_MED

                raw.setdefault("updated_at", raw.get("created", time.time()))

                raw.setdefault("deleted", False)

                self._tasks.append(Task(**{k: v for k, v in raw.items() if k in Task.__dataclass_fields__}))

        except (json.JSONDecodeError, OSError, TypeError):

            self._tasks = []



    def _seed(self) -> None:

        for text, pri in (("开会", PRIORITY_HIGH), ("交周报", PRIORITY_MED), ("取快递", PRIORITY_LOW)):

            self.add(text, pri)


