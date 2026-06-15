"""定时提醒管理：支持单次与周期性提醒。"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal

from .config import REMINDERS_PATH
from .i18n import tr, weekday_name
from .sync.ids import migrate_id, new_id

REPEAT_ONCE = "once"
REPEAT_DAILY = "daily"
REPEAT_WEEKDAYS = "weekdays"
REPEAT_WEEKLY = "weekly"


@dataclass
class Reminder:
    id: str
    text: str
    hour: int
    minute: int
    repeat: str = REPEAT_DAILY
    target_date: Optional[str] = None
    weekday: Optional[int] = None
    enabled: bool = True
    created: float = field(default_factory=time.time)
    last_fired_key: Optional[str] = None
    updated_at: float = field(default_factory=time.time)
    deleted: bool = False


class ReminderManager(QObject):
    due = Signal(str, str)
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._items: List[Reminder] = []
        self._loading = False
        self.load()
        self._timer = QTimer(self)
        self._timer.setInterval(15_000)
        self._timer.timeout.connect(self._check_due)
        self._timer.start()

    @property
    def items(self) -> List[Reminder]:
        return [r for r in self._items if not r.deleted]

    def active(self) -> List[Reminder]:
        return [r for r in self.items if r.enabled]

    def add(
        self,
        text: str,
        hour: int,
        minute: int,
        *,
        repeat: str = REPEAT_DAILY,
        target_date: Optional[str] = None,
        weekday: Optional[int] = None,
    ) -> Reminder:
        now = time.time()
        item = Reminder(
            id=new_id(),
            text=text.strip(),
            hour=int(hour),
            minute=int(minute),
            repeat=repeat,
            target_date=target_date,
            weekday=weekday,
            updated_at=now,
        )
        self._items.append(item)
        self._after_change()
        return item

    def remove(self, reminder_id: str) -> bool:
        item = self.find(reminder_id)
        if item is None:
            return False
        item.deleted = True
        item.updated_at = time.time()
        self._after_change()
        return True

    def remove_by_text(self, keyword: str) -> Reminder | None:
        keyword = keyword.strip().lower()
        for r in self.items:
            if keyword in r.text.lower():
                self.remove(r.id)
                return r
        return None

    def find(self, reminder_id: str) -> Reminder | None:
        for r in self._items:
            if r.id == reminder_id and not r.deleted:
                return r
        return None

    def format_item(self, r: Reminder) -> str:
        t = f"{r.hour:02d}:{r.minute:02d}"
        repeat_map = {
            REPEAT_ONCE: tr("remind.fmt.once", date=r.target_date or "?"),
            REPEAT_DAILY: tr("remind.fmt.daily"),
            REPEAT_WEEKDAYS: tr("remind.fmt.weekdays"),
            REPEAT_WEEKLY: tr("remind.fmt.weekly", day=weekday_name(r.weekday or 0)),
        }
        tag = repeat_map.get(r.repeat, r.repeat)
        return f"{t} · {tag} · {r.text}"

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
            reminder_id = migrate_id(payload.get("id", row.get("record_id")), namespace="reminder")
            payload["id"] = reminder_id
            payload.setdefault("updated_at", float(row.get("updated_at", time.time())))
            payload["deleted"] = bool(row.get("deleted", payload.get("deleted", False)))
            try:
                by_id[reminder_id] = Reminder(
                    **{k: v for k, v in payload.items() if k in Reminder.__dataclass_fields__}
                )
            except TypeError:
                continue
        self._loading = True
        try:
            self._items = list(by_id.values())
            self.save()
            self.changed.emit()
        finally:
            self._loading = False

    def _is_due(self, r: Reminder, now: datetime) -> bool:
        if not r.enabled or r.deleted:
            return False
        if now.hour != r.hour or now.minute != r.minute:
            return False
        key = now.strftime("%Y-%m-%d %H:%M")
        if r.last_fired_key == key:
            return False
        if r.repeat == REPEAT_ONCE:
            return r.target_date == now.strftime("%Y-%m-%d")
        if r.repeat == REPEAT_DAILY:
            return True
        if r.repeat == REPEAT_WEEKDAYS:
            return now.weekday() < 5
        if r.repeat == REPEAT_WEEKLY:
            return r.weekday is not None and now.weekday() == r.weekday
        return False

    def _check_due(self) -> None:
        now = datetime.now()
        for r in self._items:
            if self._is_due(r, now):
                key = now.strftime("%Y-%m-%d %H:%M")
                r.last_fired_key = key
                self.due.emit(r.text, r.id)
                if r.repeat == REPEAT_ONCE:
                    r.enabled = False
                r.updated_at = time.time()
        self.save()

    def _after_change(self) -> None:
        if self._loading:
            return
        self.save()
        self.changed.emit()

    def save(self) -> None:
        try:
            payload = {"reminders": [asdict(r) for r in self._items]}
            with open(REMINDERS_PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _seed_samples(self) -> None:
        self.add(tr("seed.remind.water"), 10, 0, repeat=REPEAT_DAILY)
        self.add(tr("seed.remind.rest"), 22, 0, repeat=REPEAT_DAILY)

    def _normalize_reminder(self, raw: dict[str, Any]) -> Reminder | None:
        reminder_id = migrate_id(raw.get("id"), namespace="reminder")
        raw = dict(raw)
        raw["id"] = reminder_id
        raw.setdefault("updated_at", raw.get("created", time.time()))
        raw.setdefault("deleted", False)
        try:
            return Reminder(**{k: v for k, v in raw.items() if k in Reminder.__dataclass_fields__})
        except TypeError:
            return None

    def load(self) -> None:
        if not REMINDERS_PATH.exists():
            self._seed_samples()
            return
        try:
            with open(REMINDERS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._items = []
            for raw in data.get("reminders", []):
                item = self._normalize_reminder(raw)
                if item:
                    self._items.append(item)
            if not self._items and "next_id" in data:
                self._seed_samples()
        except (json.JSONDecodeError, OSError, TypeError):
            self._items = []
