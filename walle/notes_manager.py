"""记事本数据管理：多条目小文本，保存到 %APPDATA%\\WALL-E\\notes.json。"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, List

from PySide6.QtCore import QObject, QTimer, Signal

from .config import NOTES_LEGACY_PATH, NOTES_PATH
from .sync.ids import migrate_id, new_id


@dataclass
class NoteEntry:
    id: str
    text: str
    title: str = ""
    body_height: int = 0
    created: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    deleted: bool = False


def format_note_timestamp(ts: float) -> str:
    """本地时间，用于记事条目日期展示。"""
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return ""


class NotesManager(QObject):
    """管理多条记事本条目，延迟自动落盘。"""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._entries: List[NoteEntry] = []
        self._loading = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._flush)
        self.load()

    @property
    def entries(self) -> List[NoteEntry]:
        return [e for e in self._entries if not e.deleted]

    def find(self, note_id: str) -> NoteEntry | None:
        for e in self._entries:
            if e.id == note_id and not e.deleted:
                return e
        return None

    def add(self, text: str = "", *, title: str = "") -> NoteEntry:
        now = time.time()
        body = text.strip()
        if not body and title.strip():
            body = title.strip()
        entry = NoteEntry(id=new_id(), text=body, created=now, updated_at=now)
        self._entries.insert(0, entry)
        self._after_structure_change()
        return entry

    def update_title(self, note_id: str, title: str, *, save_now: bool = False) -> None:
        entry = self.find(note_id)
        if entry is None or entry.title == title:
            return
        entry.title = title
        entry.updated_at = time.time()
        if save_now:
            self._flush()
        else:
            self._save_timer.start(500)

    def update_body_height(self, note_id: str, height: int, *, save_now: bool = False) -> None:
        entry = self.find(note_id)
        if entry is None:
            return
        height = max(36, int(height))
        if entry.body_height == height:
            return
        entry.body_height = height
        entry.updated_at = time.time()
        if save_now:
            self._flush()
        else:
            self._save_timer.start(500)

    def update_text(self, note_id: str, text: str, *, save_now: bool = False) -> None:
        entry = self.find(note_id)
        if entry is None or entry.text == text:
            return
        entry.text = text
        entry.updated_at = time.time()
        if save_now:
            self._flush()
        else:
            self._save_timer.start(500)

    def remove(self, note_id: str) -> bool:
        entry = self.find(note_id)
        if entry is None:
            return False
        entry.deleted = True
        entry.updated_at = time.time()
        self._after_structure_change()
        return True

    def export_sync_records(self) -> list[dict[str, Any]]:
        return [
            {
                "record_id": entry.id,
                "collection": "note",
                "payload": asdict(entry),
                "updated_at": entry.updated_at,
                "deleted": entry.deleted,
            }
            for entry in self._entries
        ]

    def import_sync_records(self, rows: list[dict[str, Any]]) -> None:
        by_id: dict[str, NoteEntry] = {}
        for row in rows:
            payload = row.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            note_id = migrate_id(payload.get("id", row.get("record_id")), namespace="note")
            payload["id"] = note_id
            payload.setdefault("updated_at", float(row.get("updated_at", time.time())))
            payload["deleted"] = bool(row.get("deleted", payload.get("deleted", False)))
            try:
                by_id[note_id] = NoteEntry(**{k: v for k, v in payload.items() if k in NoteEntry.__dataclass_fields__})
            except TypeError:
                continue
        self._loading = True
        try:
            self._entries = list(by_id.values())
            self._flush()
            self.changed.emit()
        finally:
            self._loading = False

    def _after_structure_change(self) -> None:
        if self._loading:
            return
        self._flush()
        self.changed.emit()

    def _flush(self) -> None:
        if self._loading:
            return
        try:
            payload = {"entries": [asdict(e) for e in self._entries]}
            with open(NOTES_PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def save(self) -> None:
        self._save_timer.stop()
        self._flush()

    def _normalize_entry(self, raw: dict[str, Any]) -> NoteEntry | None:
        note_id = migrate_id(raw.get("id"), namespace="note")
        raw = dict(raw)
        raw["id"] = note_id
        raw.setdefault("title", "")
        raw.setdefault("body_height", 0)
        if not raw.get("text") and raw.get("title"):
            raw["text"] = str(raw["title"])
        raw.setdefault("updated_at", raw.get("created", time.time()))
        raw.setdefault("deleted", False)
        try:
            return NoteEntry(**{k: v for k, v in raw.items() if k in NoteEntry.__dataclass_fields__})
        except TypeError:
            return None

    def load(self) -> None:
        if NOTES_PATH.exists():
            try:
                with open(NOTES_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._entries = []
                for raw in data.get("entries", []):
                    entry = self._normalize_entry(raw)
                    if entry:
                        self._entries.append(entry)
                return
            except (json.JSONDecodeError, OSError, TypeError):
                pass

        if NOTES_LEGACY_PATH.exists():
            try:
                legacy = NOTES_LEGACY_PATH.read_text(encoding="utf-8").strip()
                if legacy:
                    now = time.time()
                    self._entries = [NoteEntry(id=new_id(), text=legacy, created=now, updated_at=now)]
                    self._flush()
                    return
            except OSError:
                pass

        self._entries = []
