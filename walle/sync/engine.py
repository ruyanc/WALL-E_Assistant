"""同步引擎：导出本地、拉取/推送、合并写回。"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, TYPE_CHECKING

from .backend import SyncBackendError
from .merge import merge_records, row_key

if TYPE_CHECKING:
    pass

SYNC_SETTINGS_KEYS = (
    "work_minutes",
    "rest_minutes",
    "cycles",
    "rest_sound",
    "language",
)
SETTINGS_RECORD_ID = "global"


class SyncEngine:
    def __init__(
        self,
        client,
        config,
        todo,
        notes,
        reminders,
        contacts,
        *,
        sync_meta_path: Path,
    ) -> None:
        self.client = client
        self.config = config
        self.todo = todo
        self.notes = notes
        self.reminders = reminders
        self.contacts = contacts
        self._sync_meta_path = sync_meta_path
        meta = self._load_sync_meta()
        self._last_sync_at = float(meta.get("last_sync_at", 0))
        self._sync_user_id = str(meta.get("user_id", "") or "")

    def _read_sync_meta_file(self) -> dict[str, Any]:
        if not self._sync_meta_path.exists():
            return {}
        try:
            raw = json.loads(self._sync_meta_path.read_text(encoding="utf-8-sig"))
            return raw if isinstance(raw, dict) else {}
        except (json.JSONDecodeError, OSError, TypeError):
            return {}

    def _load_sync_meta(self) -> dict[str, Any]:
        raw = self._read_sync_meta_file()
        try:
            raw["last_sync_at"] = float(raw.get("last_sync_at", 0))
        except (TypeError, ValueError):
            raw["last_sync_at"] = 0.0
        raw["user_id"] = str(raw.get("user_id", "") or "")
        return raw

    @property
    def sync_user_id(self) -> str:
        return self._sync_user_id

    def _write_sync_meta(self, *, last_sync_at: float | None = None, user_id: str | None = None) -> None:
        payload = self._read_sync_meta_file()
        if last_sync_at is not None:
            payload["last_sync_at"] = last_sync_at
            self._last_sync_at = last_sync_at
        if user_id is not None:
            payload["user_id"] = user_id
            self._sync_user_id = user_id
        try:
            self._sync_meta_path.parent.mkdir(parents=True, exist_ok=True)
            self._sync_meta_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def bind_sync_user(self, user_id: str) -> None:
        user_id = str(user_id or "").strip()
        if not user_id:
            return
        if user_id != self._sync_user_id:
            self._write_sync_meta(user_id=user_id)

    def export_local(self) -> dict[str, dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        for record in self.todo.export_sync_records():
            rows[row_key("todo", record["record_id"])] = record
        for record in self.notes.export_sync_records():
            rows[row_key("note", record["record_id"])] = record
        for record in self.reminders.export_sync_records():
            rows[row_key("reminder", record["record_id"])] = record
        for record in self.contacts.export_sync_records():
            rows[row_key("contact", record["record_id"])] = record
        settings = self._export_settings()
        rows[row_key("settings", SETTINGS_RECORD_ID)] = settings
        return rows

    def _export_settings(self) -> dict[str, Any]:
        payload = {k: self.config.get(k) for k in SYNC_SETTINGS_KEYS}
        updated_at = float(self.config.get("settings_updated_at") or 0)
        return {
            "record_id": SETTINGS_RECORD_ID,
            "collection": "settings",
            "payload": payload,
            "updated_at": updated_at,
            "deleted": False,
        }

    def apply_rows(self, rows: dict[str, dict[str, Any]]) -> None:
        todos = [r for r in rows.values() if r["collection"] == "todo"]
        notes = [r for r in rows.values() if r["collection"] == "note"]
        reminders = [r for r in rows.values() if r["collection"] == "reminder"]
        contact_rows = [r for r in rows.values() if r["collection"] == "contact"]
        settings_rows = [r for r in rows.values() if r["collection"] == "settings"]

        self.todo.import_sync_records(todos)
        self.notes.import_sync_records(notes)
        self.reminders.import_sync_records(reminders)
        self.contacts.import_sync_records(contact_rows)

        if settings_rows:
            best = max(settings_rows, key=lambda r: float(r["updated_at"]))
            if not best.get("deleted"):
                payload = best.get("payload") or {}
                if isinstance(payload, dict):
                    self.config.update({k: payload[k] for k in SYNC_SETTINGS_KEYS if k in payload})
                    self.config.set("settings_updated_at", float(best["updated_at"]))

    def prepare_local_for_sync(self) -> None:
        """同步前落盘，避免导出/合并时丢失未保存的编辑。"""
        self.notes.save()
        self.todo.save()
        self.reminders.save()
        self.contacts.save()
        self.config.save()

    def reset_sync_state(self) -> None:
        """切换账号或退出登录时重置增量同步游标与所属用户。"""
        self._write_sync_meta(last_sync_at=0.0, user_id="")

    @staticmethod
    def _has_local_sync_data(rows: dict[str, dict[str, Any]]) -> bool:
        return any(not row.get("deleted") for row in rows.values())

    def _collect_to_push(
        self,
        rows: dict[str, dict[str, Any]],
        since: float,
        *,
        remote_keys: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        to_push: list[dict[str, Any]] = []
        to_push_keys: set[str] = set()
        for row in rows.values():
            key = row_key(str(row["collection"]), str(row["record_id"]))
            if float(row["updated_at"]) > since and key not in to_push_keys:
                to_push_keys.add(key)
                to_push.append(row)
        if since <= 0:
            for key, row in rows.items():
                if key in to_push_keys or row.get("deleted"):
                    continue
                if remote_keys is not None and key in remote_keys:
                    continue
                to_push_keys.add(key)
                to_push.append(row)
        return to_push

    def network_sync(
        self,
        local: dict[str, dict[str, Any]],
        since: float,
    ) -> tuple[dict[str, dict[str, Any]], float, int]:
        """拉取、合并、推送云端；返回 (merged, max_updated, pushed_count)。"""
        if self.client is None or not self.client.auth.is_logged_in:
            raise SyncBackendError("not_logged_in")
        remote_rows = self.client.fetch_changes(since)
        remote: dict[str, dict[str, Any]] = {}
        for row in remote_rows:
            record_id = str(row["record_id"])
            collection = str(row["collection"])
            remote[row_key(collection, record_id)] = {
                "record_id": record_id,
                "collection": collection,
                "payload": row.get("payload") or {},
                "updated_at": float(row["updated_at"]),
                "deleted": bool(row.get("deleted", False)),
            }
        merged = merge_records(local, remote)
        to_push = self._collect_to_push(merged, since, remote_keys=set(remote))
        if (
            not to_push
            and since > 0
            and self._has_local_sync_data(merged)
            and not remote
        ):
            to_push = self._collect_to_push(merged, 0.0, remote_keys=set(remote))
        self.client.upsert_records(to_push)
        max_updated = since
        for row in merged.values():
            max_updated = max(max_updated, float(row["updated_at"]))
        return merged, max_updated, len(to_push)

    def network_push_only(
        self,
        local: dict[str, dict[str, Any]],
        since: float,
    ) -> tuple[int, bool, float]:
        """仅推送本地变更；返回 (上传条数, 是否需要完整同步, 推送后游标)。"""
        if self.client is None or not self.client.auth.is_logged_in:
            raise SyncBackendError("not_logged_in")
        to_push = self._collect_to_push(local, since)
        if to_push:
            self.client.upsert_records(to_push)
            max_pushed = since
            for row in to_push:
                max_pushed = max(max_pushed, float(row["updated_at"]))
            return len(to_push), False, max_pushed
        if since > 0 and self._has_local_sync_data(local):
            remote_rows = self.client.fetch_changes(0)
            if not remote_rows:
                return 0, True, since
        return 0, False, since

    def commit_sync(
        self,
        merged: dict[str, dict[str, Any]],
        max_updated: float,
        since: float,
    ) -> None:
        """将合并结果写回本地并推进同步游标（须在主线程调用）。"""
        self.apply_rows(merged)
        if max_updated > since:
            self._write_sync_meta(last_sync_at=max_updated)

    def sync(self) -> None:
        if self.client is None or not self.client.auth.is_logged_in:
            raise SyncBackendError("not_logged_in")
        session = self.client.auth.session
        if session:
            self.bind_sync_user(session.user_id)
        self.prepare_local_for_sync()
        local = self.export_local()
        since = self._last_sync_at
        merged, max_updated, _pushed = self.network_sync(local, since)
        self.commit_sync(merged, max_updated, since)
