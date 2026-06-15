"""本地联系人昵称：手机号 ↔ 昵称，用于任务派发与展示。"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .backend import SyncBackendError
from .phone import normalize_phone


@dataclass
class ContactEntry:
    phone: str
    nickname: str
    updated_at: float = field(default_factory=time.time)
    deleted: bool = False


class ContactBook:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._entries: dict[str, ContactEntry] = {}
        self._loading = False
        self.load()

    def load(self) -> None:
        self._entries = {}
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8-sig"))
            now = time.time()
            for item in raw.get("contacts", []):
                if not isinstance(item, dict):
                    continue
                phone = normalize_phone(str(item.get("phone", "")))
                nickname = str(item.get("nickname", "")).strip()
                if not phone:
                    continue
                updated_at = float(item.get("updated_at", now))
                deleted = bool(item.get("deleted", False))
                if deleted or nickname:
                    self._entries[phone] = ContactEntry(
                        phone=phone,
                        nickname=nickname,
                        updated_at=updated_at,
                        deleted=deleted,
                    )
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            self._entries = {}

    def save(self) -> None:
        payload = {
            "contacts": [
                asdict(entry)
                for entry in sorted(
                    self._entries.values(),
                    key=lambda e: (e.nickname.lower() if not e.deleted else "", e.phone),
                )
            ]
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass

    def list_contacts(self) -> list[tuple[str, str]]:
        rows = [
            (entry.phone, entry.nickname)
            for entry in self._entries.values()
            if not entry.deleted and entry.nickname
        ]
        return sorted(rows, key=lambda x: x[1].lower())

    def get_nickname(self, phone: str) -> str | None:
        key = normalize_phone(phone) or phone.strip()
        entry = self._entries.get(key)
        if entry is None or entry.deleted:
            return None
        return entry.nickname

    def display_name(self, phone: str) -> str:
        phone = normalize_phone(phone) or phone.strip()
        if not phone:
            return ""
        nickname = self.get_nickname(phone)
        return nickname or phone

    def set_contact(self, phone: str, nickname: str) -> None:
        phone = normalize_phone(phone)
        nickname = nickname.strip()
        if not phone:
            raise SyncBackendError("invalid_phone")
        if not nickname:
            raise SyncBackendError("empty_nickname")
        for existing_phone, existing in self._entries.items():
            if (
                existing_phone != phone
                and not existing.deleted
                and existing.nickname.lower() == nickname.lower()
            ):
                raise SyncBackendError("duplicate_nickname")
        self._entries[phone] = ContactEntry(
            phone=phone,
            nickname=nickname,
            updated_at=time.time(),
            deleted=False,
        )
        self._after_change()

    def remove_contact(self, phone: str) -> None:
        key = normalize_phone(phone) or phone.strip()
        entry = self._entries.get(key)
        if entry is None or entry.deleted:
            return
        entry.deleted = True
        entry.updated_at = time.time()
        self._after_change()

    def clear_all(self) -> None:
        if not self._entries:
            return
        self.import_sync_records([])

    def export_sync_records(self) -> list[dict[str, Any]]:
        return [
            {
                "record_id": entry.phone,
                "collection": "contact",
                "payload": asdict(entry),
                "updated_at": entry.updated_at,
                "deleted": entry.deleted,
            }
            for entry in self._entries.values()
        ]

    def import_sync_records(self, rows: list[dict[str, Any]]) -> None:
        by_phone: dict[str, ContactEntry] = {}
        for row in rows:
            payload = row.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            phone = normalize_phone(str(payload.get("phone", row.get("record_id", ""))))
            if not phone:
                continue
            nickname = str(payload.get("nickname", "")).strip()
            updated_at = float(row.get("updated_at", payload.get("updated_at", time.time())))
            deleted = bool(row.get("deleted", payload.get("deleted", False)))
            by_phone[phone] = ContactEntry(
                phone=phone,
                nickname=nickname,
                updated_at=updated_at,
                deleted=deleted,
            )
        self._loading = True
        try:
            self._entries = by_phone
            self.save()
        finally:
            self._loading = False

    def resolve_recipient(self, text: str) -> str:
        raw = text.strip()
        if not raw:
            raise SyncBackendError("empty_recipient")
        digits = re.sub(r"\D", "", raw)
        if len(digits) >= 7:
            phone = normalize_phone(raw)
            if not phone:
                raise SyncBackendError("invalid_phone")
            return phone
        matches = [
            entry.phone
            for entry in self._entries.values()
            if not entry.deleted and entry.nickname.lower() == raw.lower()
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise SyncBackendError("duplicate_nickname")
        raise SyncBackendError("contact_not_found")

    def _after_change(self) -> None:
        if self._loading:
            return
        self.save()
