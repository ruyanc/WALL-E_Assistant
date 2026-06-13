"""定时提醒管理：支持单次与周期性提醒。"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Optional

from PySide6.QtCore import QObject, QTimer, Signal

from .config import REMINDERS_PATH
from .i18n import tr, weekday_name

REPEAT_ONCE = "once"
REPEAT_DAILY = "daily"
REPEAT_WEEKDAYS = "weekdays"
REPEAT_WEEKLY = "weekly"


@dataclass
class Reminder:
    id: int
    text: str
    hour: int
    minute: int
    repeat: str = REPEAT_DAILY
    target_date: Optional[str] = None  # YYYY-MM-DD，仅 repeat=once 时有效
    weekday: Optional[int] = None      # 0=周一 … 6=周日，仅 weekly
    enabled: bool = True
    created: float = field(default_factory=time.time)
    last_fired_key: Optional[str] = None  # 防重复触发 "YYYY-MM-DD HH:MM"


class ReminderManager(QObject):
    due = Signal(str, int)  # 提醒文案, reminder_id
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._items: List[Reminder] = []
        self._next_id = 1
        self.load()
        self._timer = QTimer(self)
        self._timer.setInterval(15_000)
        self._timer.timeout.connect(self._check_due)
        self._timer.start()

    @property
    def items(self) -> List[Reminder]:
        return list(self._items)

    def active(self) -> List[Reminder]:
        return [r for r in self._items if r.enabled]

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
        item = Reminder(
            id=self._next_id,
            text=text.strip(),
            hour=int(hour),
            minute=int(minute),
            repeat=repeat,
            target_date=target_date,
            weekday=weekday,
        )
        self._next_id += 1
        self._items.append(item)
        self._after_change()
        return item

    def remove(self, reminder_id: int) -> bool:
        before = len(self._items)
        self._items = [r for r in self._items if r.id != reminder_id]
        if len(self._items) != before:
            self._after_change()
            return True
        return False

    def remove_by_text(self, keyword: str) -> Reminder | None:
        keyword = keyword.strip().lower()
        for r in self._items:
            if keyword in r.text.lower():
                self.remove(r.id)
                return r
        return None

    def find(self, reminder_id: int) -> Reminder | None:
        for r in self._items:
            if r.id == reminder_id:
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

    def _is_due(self, r: Reminder, now: datetime) -> bool:
        if not r.enabled:
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
        self.save()

    def _after_change(self) -> None:
        self.save()
        self.changed.emit()

    def save(self) -> None:
        try:
            payload = {
                "next_id": self._next_id,
                "reminders": [asdict(r) for r in self._items],
            }
            with open(REMINDERS_PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _seed_samples(self) -> None:
        self.add(tr("seed.remind.water"), 10, 0, repeat=REPEAT_DAILY)
        self.add(tr("seed.remind.rest"), 22, 0, repeat=REPEAT_DAILY)

    def load(self) -> None:
        if not REMINDERS_PATH.exists():
            self._seed_samples()
            return
        try:
            with open(REMINDERS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._next_id = data.get("next_id", 1)
            self._items = [Reminder(**r) for r in data.get("reminders", [])]
        except (json.JSONDecodeError, OSError, TypeError):
            self._items = []
            self._next_id = 1
