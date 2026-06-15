"""提醒存储与到期检测（支持 CloudBase 同步）。"""



from __future__ import annotations



import json

import sys

import time

import uuid

from dataclasses import asdict, dataclass, field

from datetime import datetime

from pathlib import Path

from typing import Any, Callable, List



from storage import reminders_path



REPEAT_ONCE = "once"

REPEAT_DAILY = "daily"

REPEAT_WEEKDAYS = "weekdays"

REPEAT_WEEKLY = "weekly"



REPEAT_LABELS = {

    REPEAT_DAILY: "每天",

    REPEAT_WEEKDAYS: "工作日",

    REPEAT_WEEKLY: "每周",

    REPEAT_ONCE: "单次",

}





def _migrate_id(raw_id: object) -> str:

    root = Path(__file__).resolve().parents[1]

    if str(root) not in sys.path:

        sys.path.insert(0, str(root))

    from walle.sync.ids import migrate_id



    return migrate_id(raw_id, namespace="reminder")





@dataclass

class Reminder:

    id: str

    text: str

    hour: int

    minute: int

    repeat: str = REPEAT_DAILY

    target_date: str | None = None

    weekday: int | None = None

    enabled: bool = True

    created: float = field(default_factory=time.time)

    updated_at: float = field(default_factory=time.time)

    deleted: bool = False

    last_fired_key: str | None = None





class ReminderStore:

    def __init__(self, on_change: Callable[[], None] | None = None, on_due: Callable[[str], None] | None = None) -> None:

        self._items: List[Reminder] = []

        self._on_change = on_change

        self._on_due = on_due

        self._loading = False

        self.load()



    @property

    def items(self) -> List[Reminder]:

        return [r for r in self._items if r.enabled and not r.deleted]



    def format_item(self, r: Reminder) -> str:

        t = f"{r.hour:02d}:{r.minute:02d}"

        tag = REPEAT_LABELS.get(r.repeat, r.repeat)

        if r.repeat == REPEAT_ONCE and r.target_date:

            tag = f"单次 {r.target_date}"

        return f"{t} · {tag} · {r.text}"



    def add(self, text: str, hour: int, minute: int, repeat: str = REPEAT_DAILY) -> None:

        text = text.strip()

        if not text:

            return

        now = time.time()

        self._items.append(

            Reminder(

                id=str(uuid.uuid4()),

                text=text,

                hour=max(0, min(23, int(hour))),

                minute=max(0, min(59, int(minute))),

                repeat=repeat,

                target_date=datetime.now().strftime("%Y-%m-%d") if repeat == REPEAT_ONCE else None,

                created=now,

                updated_at=now,

            )

        )

        self._changed()



    def remove(self, reminder_id: str) -> None:

        for r in self._items:

            if r.id == reminder_id and not r.deleted:

                r.deleted = True

                r.updated_at = time.time()

                self._changed()

                return



    def export_sync_records(self) -> list[dict[str, Any]]:

        return [

            {

                "record_id": item.id,

                "collection": "reminder",

                "payload": asdict(item),

                "updated_at": item.updated_at,

                "deleted": item.deleted,

            }

            for item in self._items

        ]



    def import_sync_records(self, rows: list[dict[str, Any]]) -> None:

        by_id: dict[str, Reminder] = {}

        for row in rows:

            payload = row.get("payload") or {}

            if not isinstance(payload, dict):

                continue

            rid = _migrate_id(payload.get("id", row.get("record_id")))

            payload = dict(payload)

            payload["id"] = rid

            payload.setdefault("updated_at", float(row.get("updated_at", time.time())))

            payload["deleted"] = bool(row.get("deleted", payload.get("deleted", False)))

            try:

                by_id[rid] = Reminder(**{k: v for k, v in payload.items() if k in Reminder.__dataclass_fields__})

            except TypeError:

                continue

        if not by_id:

            return

        self._loading = True

        try:

            self._items = list(by_id.values())

            self.save()

            if self._on_change:

                self._on_change()

        finally:

            self._loading = False



    def check_due(self) -> None:

        now = datetime.now()

        for r in self._items:

            if not r.enabled or r.deleted:

                continue

            if now.hour != r.hour or now.minute != r.minute:

                continue

            key = now.strftime("%Y-%m-%d %H:%M")

            if r.last_fired_key == key:

                continue

            if r.repeat == REPEAT_ONCE and r.target_date != now.strftime("%Y-%m-%d"):

                continue

            if r.repeat == REPEAT_WEEKDAYS and now.weekday() >= 5:

                continue

            if r.repeat == REPEAT_WEEKLY and r.weekday is not None and now.weekday() != r.weekday:

                continue

            r.last_fired_key = key

            r.updated_at = time.time()

            if r.repeat == REPEAT_ONCE:

                r.enabled = False

            self.save()

            if self._on_due:

                self._on_due(r.text)



    def _changed(self) -> None:

        if self._loading:

            return

        self.save()

        if self._on_change:

            self._on_change()



    def save(self) -> None:

        try:

            with open(reminders_path(), "w", encoding="utf-8") as f:

                json.dump({"reminders": [asdict(r) for r in self._items]}, f, ensure_ascii=False, indent=2)

        except OSError:

            pass



    def load(self) -> None:

        path = reminders_path()

        if not path.exists():

            self.add("喝水", 10, 0, REPEAT_DAILY)

            return

        try:

            with open(path, "r", encoding="utf-8-sig") as f:

                data = json.load(f)

            self._items = []

            for raw in data.get("reminders", []):

                raw = dict(raw)

                raw["id"] = str(raw.get("id", uuid.uuid4()))

                raw.setdefault("updated_at", raw.get("created", time.time()))

                raw.setdefault("deleted", False)

                self._items.append(

                    Reminder(**{k: v for k, v in raw.items() if k in Reminder.__dataclass_fields__})

                )

        except (json.JSONDecodeError, OSError, TypeError):

            self._items = []


