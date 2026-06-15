"""跨账号任务派发：本地缓存 + CloudBase task_assignments。"""



from __future__ import annotations



import json

import time

from datetime import datetime

from pathlib import Path

from typing import TYPE_CHECKING, Callable



from .assignment_events import (
    EVENT_ACCEPTED,
    EVENT_COMPLETED,
    EVENT_DISPATCHED,
    EVENT_REJECTED,
    EVENT_WITHDRAWN,
)
from .assignment_models import (

    ACTIVE_LIST_STATUSES,

    ARCHIVE_STATUSES,

    DISMISSIBLE_STATUSES,

    INBOX_PANEL_STATUSES,

    OUTBOX_PANEL_STATUSES,

    STATUS_ACCEPTED,

    STATUS_CANCELLED,

    STATUS_COMPLETED,

    STATUS_PENDING,

    STATUS_REJECTED,

    Assignment,

)

from .backend import SyncBackendError

from .constants import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_MED

from .ids import new_id

from .phone import normalize_phone



if TYPE_CHECKING:

    from .cloudbase_client import CloudBaseClient





class AssignmentManager:

    def __init__(

        self,

        client_getter: Callable[[], "CloudBaseClient"],

        *,

        assignments_path: Path,

        on_change: Callable[[], None] | None = None,

        on_event: Callable[[str, Assignment], None] | None = None,

    ) -> None:

        self._client_getter = client_getter

        self._assignments_path = assignments_path

        self._on_change = on_change

        self._on_event = on_event

        self._items: dict[str, Assignment] = {}

        self._dismissed_ids: set[str] = set()

        self._last_sync_at = 0.0

        self._loading = False

        self.load()



    def _notify(self) -> None:

        if not self._loading and self._on_change:

            self._on_change()



    def load(self) -> None:

        if not self._assignments_path.exists():

            self._items = {}

            self._dismissed_ids = set()

            return

        try:

            raw = json.loads(self._assignments_path.read_text(encoding="utf-8-sig"))

            self._last_sync_at = float(raw.get("last_sync_at", 0))

            dismissed = raw.get("dismissed_ids") or []

            self._dismissed_ids = {str(x).strip() for x in dismissed if str(x).strip()}

            self._items = {}

            for item in raw.get("assignments", []):

                assignment = Assignment.from_cloud(item)

                if assignment:

                    self._items[assignment.id] = assignment

        except (json.JSONDecodeError, OSError, TypeError, ValueError):

            self._items = {}

            self._dismissed_ids = set()



    def save(self) -> None:

        try:

            payload = {

                "last_sync_at": self._last_sync_at,

                "assignments": [a.to_cloud() for a in self._items.values()],

                "dismissed_ids": sorted(self._dismissed_ids),

            }

            self._assignments_path.parent.mkdir(parents=True, exist_ok=True)

            self._assignments_path.write_text(

                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",

                encoding="utf-8",

            )

        except OSError:

            pass



    def _same_user(self, left: str, right: str) -> bool:
        return str(left or "").strip() == str(right or "").strip()

    def _session_user_id(self) -> str:
        session = self._client_getter().auth.session
        return str(session.user_id).strip() if session else ""

    def _assignments_for(
        self,
        *,
        role: str | None,
        statuses: set[str],
        include_dismissed: bool = False,
    ) -> list[Assignment]:
        uid = self._session_user_id()
        if not uid:
            return []
        rows: list[Assignment] = []
        for assignment in self._items.values():
            if not include_dismissed and assignment.id in self._dismissed_ids:
                continue
            if assignment.status not in statuses:
                continue
            if role == "inbox" and self._same_user(assignment.assignee_id, uid):
                rows.append(assignment)
            elif role == "outbox" and self._same_user(assignment.assigner_id, uid):
                rows.append(assignment)
            elif role is None:
                if self._same_user(assignment.assignee_id, uid) or self._same_user(
                    assignment.assigner_id, uid
                ):
                    rows.append(assignment)
        rows.sort(key=lambda a: (-a.updated_at, a.created_at))
        return rows

    @staticmethod
    def is_dismissible(assignment: Assignment) -> bool:
        return assignment.status in DISMISSIBLE_STATUSES

    def dismiss(self, assignment_id: str, *, role: str) -> None:
        assignment = self._items.get(assignment_id)
        if assignment is None:
            raise SyncBackendError("assignment_not_found")
        uid = self._session_user_id()
        if role == "inbox" and not self._same_user(assignment.assignee_id, uid):
            raise SyncBackendError("forbidden_action")
        if role == "outbox" and not self._same_user(assignment.assigner_id, uid):
            raise SyncBackendError("forbidden_action")
        if not self.is_dismissible(assignment):
            raise SyncBackendError("assignment_not_finished")
        self._dismissed_ids.add(assignment_id)
        self.save()
        self._notify()

    def clear_archive(self) -> int:
        cleared = 0
        for assignment in self.archive:
            self._dismissed_ids.add(assignment.id)
            cleared += 1
        if cleared:
            self.save()
            self._notify()
        return cleared

    @property
    def inbox(self) -> list[Assignment]:
        return self._assignments_for(role="inbox", statuses=ACTIVE_LIST_STATUSES)

    @property
    def inbox_panel(self) -> list[Assignment]:
        return self._assignments_for(role="inbox", statuses=INBOX_PANEL_STATUSES)

    @property
    def outbox(self) -> list[Assignment]:
        return self._assignments_for(role="outbox", statuses=ACTIVE_LIST_STATUSES)

    @property
    def outbox_panel(self) -> list[Assignment]:
        return self._assignments_for(role="outbox", statuses=OUTBOX_PANEL_STATUSES)

    @property
    def archive(self) -> list[Assignment]:
        return self._assignments_for(role=None, statuses=ARCHIVE_STATUSES)

    @property
    def archive_inbox(self) -> list[Assignment]:
        return self._assignments_for(role="inbox", statuses=ARCHIVE_STATUSES)

    @property
    def archive_outbox(self) -> list[Assignment]:
        return self._assignments_for(role="outbox", statuses=ARCHIVE_STATUSES)

    @property
    def accepted_inbox(self) -> list[Assignment]:
        return self._assignments_for(role="inbox", statuses={STATUS_ACCEPTED})

    @property
    def accepted_outbox(self) -> list[Assignment]:
        return self._assignments_for(role="outbox", statuses={STATUS_ACCEPTED})

    @property
    def outbox_cancelled(self) -> list[Assignment]:
        return self._assignments_for(role="outbox", statuses={STATUS_CANCELLED})

    @property
    def outbox_pending(self) -> list[Assignment]:
        return self._assignments_for(role="outbox", statuses={STATUS_PENDING})

    @property
    def outbox_rejected(self) -> list[Assignment]:
        return self._assignments_for(role="outbox", statuses={STATUS_REJECTED})

    @property
    def inbox_cancelled(self) -> list[Assignment]:
        return self._assignments_for(role="inbox", statuses={STATUS_CANCELLED})

    @property
    def inbox_pending(self) -> list[Assignment]:
        return self._assignments_for(role="inbox", statuses={STATUS_PENDING})

    @property
    def inbox_rejected(self) -> list[Assignment]:
        return self._assignments_for(role="inbox", statuses={STATUS_REJECTED})

    def accepted_inbox_priorities(self) -> list[int]:
        items = sorted(
            self.accepted_inbox,
            key=lambda a: (-a.priority, -a.updated_at, a.created_at),
        )
        return [a.priority for a in items]

    def accepted_outbox_priorities(self) -> list[int]:
        items = sorted(
            self.accepted_outbox,
            key=lambda a: (-a.priority, -a.updated_at, a.created_at),
        )
        return [a.priority for a in items]

    def archive_groups(self, role: str) -> list[tuple[str, list[Assignment]]]:
        buckets: dict[str, list[Assignment]] = {}
        items = self.archive_inbox if role == "inbox" else self.archive_outbox
        for assignment in items:
            ts = assignment.completed_at or assignment.updated_at or assignment.created_at
            day = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            buckets.setdefault(day, []).append(assignment)
        groups: list[tuple[str, list[Assignment]]] = []
        for day in sorted(buckets.keys(), reverse=True):
            tasks = sorted(
                buckets[day],
                key=lambda a: -(a.completed_at or a.updated_at or a.created_at),
            )
            groups.append((day, tasks))
        return groups



    def _emit(self, kind: str, assignment: Assignment) -> None:

        if self._on_event:

            self._on_event(kind, assignment)



    def _events_for_transition(

        self,

        prev: str | None,

        assignment: Assignment,

        session,

        since: float,

    ) -> list[str]:

        uid = session.user_id

        if not self._same_user(assignment.assigner_id, uid) and not self._same_user(
            assignment.assignee_id, uid
        ):
            return []

        status = assignment.status

        if prev is None:

            if since > 0 and assignment.updated_at >= since and status == STATUS_PENDING:

                if self._same_user(assignment.assignee_id, uid):

                    return [EVENT_DISPATCHED]

            return []

        if prev == status:

            return []

        mapping = {

            STATUS_ACCEPTED: EVENT_ACCEPTED,

            STATUS_REJECTED: EVENT_REJECTED,

            STATUS_COMPLETED: EVENT_COMPLETED,

            STATUS_CANCELLED: EVENT_WITHDRAWN,

        }

        kind = mapping.get(status)

        return [kind] if kind else []



    def find(self, assignment_id: str) -> Assignment | None:

        return self._items.get(assignment_id)



    def network_fetch(self, user_id: str, since: float) -> tuple[list[dict], float]:
        """拉取云端派发（可在后台线程调用）。"""
        client = self._client_getter()
        user_id = str(user_id or "").strip()
        if not user_id:
            return [], since
        max_updated = since
        rows: list[dict] = []
        for raw in client.fetch_assignment_changes(user_id, since):
            rows.append(raw)
            assignment = Assignment.from_cloud(raw)
            if assignment:
                max_updated = max(max_updated, float(assignment.updated_at))
        return rows, max_updated

    def apply_fetch(
        self,
        raw_rows: list[dict],
        max_updated: float,
        since: float,
        old_status: dict[str, str],
        session,
    ) -> None:
        """将拉取结果写回本地（须在主线程调用）。"""
        for raw in raw_rows:
            assignment = Assignment.from_cloud(raw)
            if assignment:
                self._items[assignment.id] = assignment
        for aid, assignment in self._items.items():
            prev = old_status.get(aid)
            for kind in self._events_for_transition(prev, assignment, session, since):
                self._emit(kind, assignment)
        if max_updated > since:
            self._last_sync_at = max_updated
        self.save()
        self._notify()

    def sync(self) -> None:
        client = self._client_getter()
        session = client.auth.session
        if session is None:
            raise SyncBackendError("not_logged_in")

        old_status = {aid: a.status for aid, a in self._items.items()}
        since = self._last_sync_at
        rows, max_updated = self.network_fetch(session.user_id, since)
        self.apply_fetch(rows, max_updated, since, old_status, session)

    def reset_sync_cursor(self) -> None:
        """登录后强制全量拉取派发任务，避免增量游标漏掉云端记录。"""
        self._last_sync_at = 0.0
        self.save()



    def create(

        self,

        assignee_phone: str,

        title: str,

        *,

        priority: int = PRIORITY_MED,

        description: str = "",

        due_at: float | None = None,

    ) -> Assignment:

        client = self._client_getter()

        session = client.auth.session

        if session is None:

            raise SyncBackendError("not_logged_in")

        phone = normalize_phone(assignee_phone)

        if not phone:

            raise SyncBackendError("invalid_phone")

        title = title.strip()

        if not title:

            raise SyncBackendError("empty_title")

        target = client.find_user_by_phone(phone)

        if not target:

            raise SyncBackendError("assignee_not_found")

        assignee_id = str(target.get("user_id", "") or target.get("sub", "")).strip()
        if not assignee_id:
            raise SyncBackendError("assignee_not_found")
        if self._same_user(assignee_id, session.user_id):
            raise SyncBackendError("cannot_assign_self")

        assigner_id = str(session.user_id).strip()

        priority = max(PRIORITY_LOW, min(PRIORITY_HIGH, int(priority)))

        now = time.time()

        assignment = Assignment(

            id=new_id(),

            title=title,

            description=description.strip(),

            priority=priority,

            due_at=due_at,

            assigner_id=assigner_id,

            assigner_phone=session.phone,

            assignee_id=assignee_id,

            assignee_phone=phone,

            status=STATUS_PENDING,

            created_at=now,

            updated_at=now,

        )

        client.upsert_assignment(assignment.to_cloud())

        self._items[assignment.id] = assignment

        self.save()

        self._notify()

        self._emit(EVENT_DISPATCHED, assignment)

        return assignment



    def _patch(self, assignment_id: str, *, status: str, note: str = "") -> Assignment:

        client = self._client_getter()

        session = client.auth.session

        if session is None:

            raise SyncBackendError("not_logged_in")

        assignment = self._items.get(assignment_id)

        if assignment is None:

            raise SyncBackendError("assignment_not_found")

        now = time.time()

        if status == STATUS_ACCEPTED and assignment.assignee_id == session.user_id:

            if assignment.status != STATUS_PENDING:

                raise SyncBackendError("forbidden_action")

            assignment.status = STATUS_ACCEPTED

        elif status == STATUS_REJECTED and assignment.assignee_id == session.user_id:

            if assignment.status != STATUS_PENDING:

                raise SyncBackendError("forbidden_action")

            note = note.strip()

            if not note:

                raise SyncBackendError("empty_reject_reason")

            assignment.status = STATUS_REJECTED

            assignment.assignee_note = note

        elif status == STATUS_COMPLETED and assignment.assignee_id == session.user_id:

            if assignment.status != STATUS_ACCEPTED:

                raise SyncBackendError("forbidden_action")

            assignment.status = STATUS_COMPLETED

            assignment.completed_at = now

        elif status == STATUS_CANCELLED and assignment.assigner_id == session.user_id:

            if assignment.status not in (STATUS_PENDING, STATUS_ACCEPTED):

                raise SyncBackendError("forbidden_action")

            note = note.strip()

            if not note:

                raise SyncBackendError("empty_cancel_reason")

            assignment.status = STATUS_CANCELLED

            assignment.assigner_note = note

        else:

            raise SyncBackendError("forbidden_action")

        assignment.updated_at = now

        client.upsert_assignment(assignment.to_cloud())

        self.save()

        self._notify()

        event_map = {

            STATUS_ACCEPTED: EVENT_ACCEPTED,

            STATUS_REJECTED: EVENT_REJECTED,

            STATUS_COMPLETED: EVENT_COMPLETED,

            STATUS_CANCELLED: EVENT_WITHDRAWN,

        }

        kind = event_map.get(status)

        if kind:

            self._emit(kind, assignment)

        return assignment



    def accept(self, assignment_id: str) -> Assignment:

        return self._patch(assignment_id, status=STATUS_ACCEPTED)



    def reject(self, assignment_id: str, note: str = "") -> Assignment:

        return self._patch(assignment_id, status=STATUS_REJECTED, note=note)



    def complete(self, assignment_id: str) -> Assignment:

        return self._patch(assignment_id, status=STATUS_COMPLETED)



    def cancel(self, assignment_id: str, note: str = "") -> Assignment:

        return self._patch(assignment_id, status=STATUS_CANCELLED, note=note)



    def clear_local(self) -> None:

        self._items = {}

        self._dismissed_ids = set()

        self._last_sync_at = 0.0

        self.save()

        self._notify()


