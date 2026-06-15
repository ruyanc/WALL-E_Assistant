"""跨账号任务派发数据模型。"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any

STATUS_PENDING = "pending"
STATUS_ACCEPTED = "accepted"
STATUS_REJECTED = "rejected"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"

ACTIVE_STATUSES = {STATUS_PENDING, STATUS_ACCEPTED}
ACTIVE_LIST_STATUSES = {
    STATUS_PENDING,
    STATUS_ACCEPTED,
    STATUS_REJECTED,
    STATUS_CANCELLED,
}
ARCHIVE_STATUSES = {STATUS_COMPLETED}
DISMISSIBLE_STATUSES = ARCHIVE_STATUSES | {STATUS_REJECTED, STATUS_CANCELLED}
FINISHED_STATUSES = ARCHIVE_STATUSES
INBOX_PANEL_STATUSES = {STATUS_PENDING, STATUS_REJECTED, STATUS_CANCELLED}
OUTBOX_PANEL_STATUSES = {STATUS_PENDING, STATUS_REJECTED, STATUS_CANCELLED}


@dataclass
class Assignment:
    id: str
    title: str
    assigner_id: str
    assignee_id: str
    status: str = STATUS_PENDING
    priority: int = 1
    description: str = ""
    due_at: float | None = None
    assigner_phone: str = ""
    assignee_phone: str = ""
    assignee_note: str = ""
    assigner_note: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    @property
    def is_inbox(self) -> bool:
        return self.status in ACTIVE_STATUSES or self.status == STATUS_REJECTED

    def to_cloud(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_cloud(cls, raw: dict[str, Any]) -> Assignment | None:
        assignment_id = raw.get("id") or raw.get("assignment_id") or raw.get("_id")
        if not assignment_id:
            return None
        payload = dict(raw)
        payload["id"] = str(assignment_id).strip()
        payload.setdefault("title", "")
        payload.setdefault("status", STATUS_PENDING)
        payload.setdefault("priority", 1)
        try:
            return cls(**{k: v for k, v in payload.items() if k in cls.__dataclass_fields__})
        except TypeError:
            return None
