"""派发任务状态变更 → 气泡文案（按当前用户角色）。"""

from __future__ import annotations

from typing import Callable

from .assignment_events import (
    EVENT_ACCEPTED,
    EVENT_COMPLETED,
    EVENT_DISPATCHED,
    EVENT_REJECTED,
    EVENT_WITHDRAWN,
)


def assignment_notify_messages(
    kind: str,
    assignment,
    *,
    user_id: str,
    display_name: Callable[[str], str],
    tr: Callable[..., str],
) -> list[str]:
    """返回当前登录用户应看到的通知文案（0～1 条）。"""
    if not user_id:
        return []
    is_assigner = assignment.assigner_id == user_id
    is_assignee = assignment.assignee_id == user_id
    title = assignment.title
    messages: list[str] = []

    if kind == EVENT_DISPATCHED:
        if is_assignee:
            name = display_name(assignment.assigner_phone)
            messages.append(tr("assign.notify.dispatched.inbox", title=title, name=name))
        if is_assigner:
            name = display_name(assignment.assignee_phone)
            messages.append(tr("assign.notify.dispatched.outbox", title=title, name=name))
    elif kind == EVENT_ACCEPTED:
        if is_assigner:
            name = display_name(assignment.assignee_phone)
            messages.append(tr("assign.notify.accepted.assigner", title=title, name=name))
        if is_assignee:
            messages.append(tr("assign.notify.accepted.assignee", title=title))
    elif kind == EVENT_REJECTED:
        note = assignment.assignee_note or ""
        if is_assigner:
            name = display_name(assignment.assignee_phone)
            messages.append(tr("assign.notify.rejected.assigner", title=title, name=name, note=note))
        if is_assignee:
            messages.append(tr("assign.notify.rejected.assignee", title=title, note=note))
    elif kind == EVENT_COMPLETED:
        if is_assigner:
            name = display_name(assignment.assignee_phone)
            messages.append(tr("assign.notify.completed.assigner", title=title, name=name))
        if is_assignee:
            messages.append(tr("assign.notify.completed.assignee", title=title))
    elif kind == EVENT_WITHDRAWN:
        note = assignment.assigner_note or ""
        if is_assignee:
            name = display_name(assignment.assigner_phone)
            messages.append(tr("assign.notify.withdrawn.assignee", title=title, name=name, note=note))
        if is_assigner:
            messages.append(tr("assign.notify.withdrawn.assigner", title=title, note=note))

    return messages
